"""
Chat service — orchestrates agent execution and message persistence.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.domain.repositories import MessageRepository, ThreadRepository

from ..agent.orchestrator import Orchestrator
from ..agent.prompts.orchestrator_prompt import build_orchestrator_prompt
from ..agent.skills import SkillRegistry
from ..agent.state_schema import BuildInfo, CharInfo


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
        skill_registry: SkillRegistry,
        message_repository: MessageRepository,
        thread_repository: ThreadRepository,
    ):
        self.orchestrator = orchestrator
        self.skill_registry = skill_registry
        self.message_repository = message_repository
        self.thread_repository = thread_repository

    async def process_message(
        self,
        thread_id: str,
        user_id: str,
        input_text: str,
        char_info: CharInfo,
    ) -> AsyncGenerator[str, None]:
        """Process a user message and stream the response."""
        normalized_char_info = CharInfo(
            **{
                "class": char_info.wow_class,
                "spec": char_info.spec,
                "role": char_info.role,
            }
        )

        # Ensure thread exists
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            wow_class=WowClass(normalized_char_info.wow_class),
            wow_spec=WowSpec(normalized_char_info.spec),
            wow_role=normalized_char_info.role,
        )
        persisted_thread, _ = await self.thread_repository.get_or_create(thread)

        # Save user message
        user_timestamp = datetime.now(timezone.utc)
        user_message = Message(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role=MessageRole.HUMAN,
            content=input_text,
            timestamp=user_timestamp,
        )
        await self.message_repository.save(user_message)

        # Load conversation history
        history = await self.message_repository.get_up_to_timestamp(
            thread_id, user_timestamp,
        )

        # Convert domain messages to Responses API format
        messages = _to_responses_api_messages(history)

        # Resolve persisted build info
        persisted_build_info: BuildInfo | None = None
        if isinstance(persisted_thread.active_build_info, dict):
            try:
                persisted_build_info = BuildInfo.model_validate(
                    persisted_thread.active_build_info,
                )
            except Exception:
                persisted_build_info = None

        # Build system prompt
        system_prompt = build_orchestrator_prompt(
            skill_registry=self.skill_registry,
            char_info=normalized_char_info,
            build_info=persisted_build_info,
        )

        # Prepare char_info dict for tool executor
        char_dict = {
            "class": normalized_char_info.wow_class,
            "spec": normalized_char_info.spec,
            "role": normalized_char_info.role,
        }
        build_dict = (
            persisted_build_info.model_dump(mode="json")
            if persisted_build_info else None
        )

        # Stream via orchestrator — pass all events through to the client.
        # Only capture the `done` event for persistence (it carries the full text).
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

        # Persist AI response from the done event
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
    skill_registry: SkillRegistry,
    message_repository: MessageRepository,
    thread_repository: ThreadRepository,
) -> ChatService:
    return ChatService(
        orchestrator=orchestrator,
        skill_registry=skill_registry,
        message_repository=message_repository,
        thread_repository=thread_repository,
    )


def _to_responses_api_messages(messages: list[Message]) -> list[dict]:
    """Convert domain Message objects to Responses API input format."""
    result: list[dict] = []
    for msg in messages:
        if msg.role == MessageRole.HUMAN:
            result.append({"role": "user", "content": msg.content or ""})
        elif msg.role == MessageRole.AI:
            result.append({"role": "assistant", "content": msg.content or ""})
        elif msg.role == MessageRole.SYSTEM:
            result.append({"role": "system", "content": msg.content or ""})
        # Skip tool messages — they are part of the Responses API's
        # internal state and not replayed as conversation history.
    return result
