"""
Chat service — orchestrates agent execution and message persistence.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.domain.repositories import MessageRepository, ThreadRepository
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
        message_repository: MessageRepository,
        thread_repository: ThreadRepository,
    ):
        self.orchestrator = orchestrator
        self.message_repository = message_repository
        self.thread_repository = thread_repository

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

        persisted_thread = await self._ensure_thread(thread_id, user_id, normalized)
        history = await self._save_and_load_history(thread_id, input_text)
        messages = to_responses_api_messages(history)
        build_info = await self._resolve_build(
            thread_id, selected_build_id, persisted_thread, char_dict,
        )

        system_prompt = build_orchestrator_prompt(
            char_info=normalized,
            build_info=build_info,
            skill_contents=self.orchestrator.skill_contents,
        )
        build_dict = build_info.model_dump(mode="json") if build_info else None

        async for event_str in self._stream_and_persist(
            thread_id, messages, system_prompt, char_dict, build_dict,
        ):
            yield event_str

    # ------------------------------------------------------------------
    # Private steps
    # ------------------------------------------------------------------

    async def _ensure_thread(
        self,
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
        persisted, _ = await self.thread_repository.get_or_create(thread)
        return persisted

    async def _save_and_load_history(
        self,
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
        await self.message_repository.save(user_message)
        return await self.message_repository.get_up_to_timestamp(
            thread_id, user_timestamp,
        )

    async def _resolve_build(
        self,
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
                await self.thread_repository.set_active_build_id(
                    thread_id, selected_build_id,
                )
                await self.thread_repository.set_active_build_info(
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
                parsed = json.loads(event_str.removeprefix("data: ").strip())
                event_name = parsed.get("event")
                data = parsed.get("data", {})

                if event_name == "annotations":
                    annotations = data.get("citations", [])
                elif event_name == "done":
                    done_text = data.get("text", "")
            except (json.JSONDecodeError, AttributeError):
                pass

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
            await self.message_repository.save(ai_message)


def create_chat_service(
    orchestrator: Orchestrator,
    message_repository: MessageRepository,
    thread_repository: ThreadRepository,
) -> ChatService:
    return ChatService(
        orchestrator=orchestrator,
        message_repository=message_repository,
        thread_repository=thread_repository,
    )


