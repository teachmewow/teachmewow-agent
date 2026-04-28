"""
Chat service — orchestrates agent execution and message persistence.

Session management: this service creates short-lived sessions internally
rather than receiving a long-lived dependency-injected session.  This
prevents DB connections from being held idle during the long SSE
streaming phase (5-30 s) and avoids leaked-connection warnings when
clients disconnect mid-stream.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.infrastructure.database.repositories import (
    MessageRepositoryImpl,
    ThreadRepositoryImpl,
)
from app.infrastructure.llm.message_adapter import to_responses_api_messages

from ..agent.orchestrator import Orchestrator
from ..agent.prompts.orchestrator_prompt import build_orchestrator_prompt
from ..agent.state_schema import BuildInfo, CharInfo
from ..agent.tools.build_lookup import _fetch_build


class ChatService:
    """
    Coordinates between the orchestrator and repositories to:
    - Process user messages
    - Execute the orchestrator loop
    - Stream responses
    - Persist messages
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self.orchestrator = orchestrator
        self._session_factory = session_factory

    async def process_message(
        self,
        thread_id: str,
        user_id: str,
        input_text: str,
        char_info: CharInfo,
        selected_build_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Process a user message and stream the response."""
        normalized = CharInfo(
            **{
                "class": char_info.wow_class,
                "spec": char_info.spec,
                "role": char_info.role,
            }
        )
        char_dict = {
            "class": normalized.wow_class,
            "spec": normalized.spec,
            "role": normalized.role,
        }

        # --- Phase 1: DB work (short-lived session) -----------------------
        # Session is opened, used, committed, and closed BEFORE streaming
        # starts.  This returns the DB connection to the pool immediately.
        async with self._session_factory() as session:
            msg_repo = MessageRepositoryImpl(session)
            thread_repo = ThreadRepositoryImpl(session)

            persisted_thread = await self._ensure_thread(
                thread_repo, thread_id, user_id, normalized,
            )
            history = await self._save_and_load_history(
                msg_repo, thread_id, input_text,
            )
            messages = to_responses_api_messages(history)
            build_info = await self._resolve_build(
                thread_repo, thread_id, selected_build_id,
                persisted_thread, char_dict,
            )
            await session.commit()
        # Connection returned to pool here — before any streaming.

        system_prompt = build_orchestrator_prompt(
            char_info=normalized,
            build_info=build_info,
            skill_contents=self.orchestrator.skill_contents,
        )
        build_dict = build_info.model_dump(mode="json") if build_info else None

        # --- Phase 2: streaming (no DB connection held) -------------------
        async for event_str in self._stream_and_persist(
            thread_id, messages, system_prompt, char_dict, build_dict,
        ):
            yield event_str

    # ------------------------------------------------------------------
    # Private steps
    # ------------------------------------------------------------------

    async def _ensure_thread(
        self,
        thread_repo: ThreadRepositoryImpl,
        thread_id: str,
        user_id: str,
        char_info: CharInfo,
    ) -> Thread:
        """Get or create a thread for the conversation."""
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            wow_class=WowClass(char_info.wow_class),
            wow_spec=WowSpec(char_info.spec),
            wow_role=char_info.role,
        )
        persisted, _ = await thread_repo.get_or_create(thread)
        return persisted

    async def _save_and_load_history(
        self,
        msg_repo: MessageRepositoryImpl,
        thread_id: str,
        input_text: str,
    ) -> list[Message]:
        """Persist the user message and return full conversation history."""
        user_timestamp = datetime.now(timezone.utc)
        user_message = Message(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role=MessageRole.HUMAN,
            content=input_text,
            timestamp=user_timestamp,
        )
        await msg_repo.save(user_message)
        return await msg_repo.get_up_to_timestamp(
            thread_id, user_timestamp,
        )

    async def _resolve_build(
        self,
        thread_repo: ThreadRepositoryImpl,
        thread_id: str,
        selected_build_id: str | None,
        persisted_thread: Thread,
        char_dict: dict,
    ) -> BuildInfo | None:
        """Resolve build context — UI selection takes priority over cached."""
        if selected_build_id and selected_build_id != persisted_thread.active_build_id:
            build_data = await _fetch_build(
                build_id=selected_build_id,
                char_info=char_dict,
            )
            if build_data:
                build_info = BuildInfo(
                    build_id=build_data["build_id"],
                    import_code=build_data.get("import_code", ""),
                    wow_class=char_dict.get("class", ""),
                    spec=char_dict.get("spec", ""),
                    hero_talent=build_data.get("hero_talent"),
                    environment=build_data.get("environment"),
                    scenario=build_data.get("scenario"),
                    source=build_data.get("source"),
                    patch=build_data.get("patch"),
                )
                await thread_repo.set_active_build_id(
                    thread_id, selected_build_id,
                )
                await thread_repo.set_active_build_info(
                    thread_id, build_info.model_dump(mode="json"),
                )
                return build_info

        if isinstance(persisted_thread.active_build_info, dict):
            try:
                return BuildInfo.model_validate(persisted_thread.active_build_info)
            except Exception:
                return None

        return None

    async def _stream_and_persist(
        self,
        thread_id: str,
        messages: list[dict],
        system_prompt: str,
        char_dict: dict,
        build_dict: dict | None,
    ) -> AsyncGenerator[str, None]:
        """Stream orchestrator events and persist the AI response."""
        done_text = ""
        annotations: list[dict] = []

        async for event_str in self.orchestrator.stream(
            messages=messages,
            system_prompt=system_prompt,
            char_info=char_dict,
            build_info=build_dict,
        ):
            yield event_str

            try:
                event_name, data = _parse_sse_frame(event_str)
                if event_name == "annotations":
                    annotations = data.get("citations", [])
                elif event_name == "done":
                    done_text = data.get("text", "")
            except (json.JSONDecodeError, AttributeError, ValueError):
                pass

        # --- Phase 3: persist AI response (short-lived session) -----------
        if done_text:
            ai_message = Message(
                id=str(uuid.uuid4()),
                thread_id=thread_id,
                role=MessageRole.AI,
                content=done_text,
                timestamp=datetime.now(timezone.utc),
                response_metadata=(
                    {"annotations": annotations} if annotations else None
                ),
            )
            async with self._session_factory() as session:
                msg_repo = MessageRepositoryImpl(session)
                await msg_repo.save(ai_message)
                await session.commit()


def create_chat_service(
    orchestrator: Orchestrator,
    session_factory: async_sessionmaker[AsyncSession],
) -> ChatService:
    return ChatService(
        orchestrator=orchestrator,
        session_factory=session_factory,
    )


def _parse_sse_frame(frame: str) -> tuple[str, dict]:
    """Parse a standard SSE frame (event: ...\\ndata: ...) into (event_name, data_dict)."""
    event_name = ""
    data_str = ""
    for line in frame.strip().splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_str = line[5:].strip()
    if not event_name or not data_str:
        raise ValueError("Incomplete SSE frame")
    return event_name, json.loads(data_str)


