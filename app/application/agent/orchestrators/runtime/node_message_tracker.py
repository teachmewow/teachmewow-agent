"""
Track and deduplicate messages emitted on node completion events.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage


class NodeMessageTracker:
    def __init__(self, initial_messages: list[BaseMessage]):
        self._total_message_count = len(initial_messages)
        self._seen_message_keys = self._build_seen_message_keys(initial_messages)

    def extract_new_messages(self, event_data: dict) -> list[BaseMessage]:
        messages = self._get_messages_from_event_data(event_data)
        if not messages:
            return []

        candidate_messages: list[BaseMessage]
        if len(messages) > self._total_message_count:
            candidate_messages = messages[self._total_message_count :]
            self._total_message_count = len(messages)
        else:
            candidate_messages = messages
            self._total_message_count = max(self._total_message_count, len(messages))

        new_messages: list[BaseMessage] = []
        for message in candidate_messages:
            key = self._message_key(message)
            if not key:
                continue
            if key in self._seen_message_keys:
                continue
            self._seen_message_keys.add(key)
            new_messages.append(message)

        return new_messages

    def _build_seen_message_keys(self, messages: list[BaseMessage]) -> set[str]:
        keys: set[str] = set()
        for message in messages:
            key = self._message_key(message)
            if key:
                keys.add(key)
        return keys

    def _message_key(self, message: BaseMessage) -> str | None:
        message_type = getattr(message, "type", None) or message.__class__.__name__
        message_id = getattr(message, "id", None)
        if isinstance(message_id, str) and message_id:
            return f"{message_type}:{message_id}"

        if message_type == "tool":
            tool_call_id = getattr(message, "tool_call_id", None)
            if isinstance(tool_call_id, str) and tool_call_id:
                return f"tool_call:{tool_call_id}"

        content = getattr(message, "content", "")
        tool_calls = getattr(message, "tool_calls", None)
        return f"{message_type}:{content}:{tool_calls}"

    def _get_messages_from_event_data(self, event_data: dict) -> list[BaseMessage]:
        for key in ("output", "state", "result"):
            container = event_data.get(key)
            if isinstance(container, dict) and "messages" in container:
                messages = container.get("messages", [])
                if isinstance(messages, list):
                    return messages

        if "messages" in event_data and isinstance(event_data["messages"], list):
            return event_data["messages"]

        return []
