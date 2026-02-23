"""
Mapper for converting domain Message entities to LangChain message types.
"""

import json

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.domain import Message, MessageRole


class MessageMapper:
    """
    Mapper for converting between domain Message entities and LangChain messages.
    
    Centralizes all conversion logic to avoid duplication across services.
    """

    @staticmethod
    def to_langchain_messages(messages: list[Message]) -> list[BaseMessage]:
        """
        Convert a list of domain Message entities to LangChain messages.

        Args:
            messages: List of domain Message entities

        Returns:
            List of LangChain BaseMessage instances

        Mapping rules:
            - HUMAN → HumanMessage
            - AI → AIMessage (with tool_calls if present)
            - TOOL → ToolMessage (using tool_call_id and content)
            - SYSTEM → SystemMessage
        """
        result: list[BaseMessage] = []
        pending_tool_calls: set[str] = set()

        for msg in messages:
            langchain_msg = MessageMapper._convert_single(msg)
            if langchain_msg is None:
                continue

            if isinstance(langchain_msg, AIMessage):
                pending_tool_calls = {
                    str(tc.get("id") or "") for tc in (langchain_msg.tool_calls or [])
                }
                pending_tool_calls = {tc for tc in pending_tool_calls if tc}
                result.append(langchain_msg)
                continue

            if isinstance(langchain_msg, ToolMessage):
                tool_call_id = str(langchain_msg.tool_call_id or "")
                if not pending_tool_calls:
                    # Tool messages without an immediately preceding AI tool_calls
                    # chain are invalid for model history; skip corrupted records.
                    continue
                if tool_call_id not in pending_tool_calls:
                    # Skip corrupted legacy tool message not tied to pending calls.
                    continue
                pending_tool_calls.remove(tool_call_id)
                result.append(langchain_msg)
                continue

            if pending_tool_calls:
                # Incomplete tool response chain from legacy history, drop pending.
                pending_tool_calls = set()
            result.append(langchain_msg)

        return result

    @staticmethod
    def _convert_single(msg: Message) -> BaseMessage | None:
        """
        Convert a single domain Message to a LangChain message.

        Args:
            msg: Domain Message entity

        Returns:
            LangChain BaseMessage or None if conversion not possible
        """
        match msg.role:
            case MessageRole.HUMAN:
                return HumanMessage(content=msg.content)

            case MessageRole.AI:
                return MessageMapper._convert_ai_message(msg)

            case MessageRole.TOOL:
                return MessageMapper._convert_tool_message(msg)

            case MessageRole.SYSTEM:
                return SystemMessage(content=msg.content)

            case _:
                return None

    @staticmethod
    def _convert_ai_message(msg: Message) -> AIMessage:
        """
        Convert a domain AI message to LangChain AIMessage.

        Handles tool_calls by converting them to the format expected by LangChain.
        """
        if msg.tool_calls:
            # Convert tool calls to LangChain format
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "args": json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments,
                }
                for tc in msg.tool_calls
            ]
            kwargs = {"content": msg.content, "tool_calls": tool_calls}
            if isinstance(msg.response_metadata, dict):
                kwargs["response_metadata"] = msg.response_metadata
            return AIMessage(**kwargs)

        kwargs = {"content": msg.content}
        if isinstance(msg.response_metadata, dict):
            kwargs["response_metadata"] = msg.response_metadata
        return AIMessage(**kwargs)

    @staticmethod
    def _convert_tool_message(msg: Message) -> ToolMessage | None:
        """
        Convert a domain TOOL message to LangChain ToolMessage.

        Requires tool_call_id to be present.
        """
        if not msg.tool_call_id:
            return None

        # Use tool_result if available, otherwise use content
        raw_content = msg.tool_result if msg.tool_result else msg.content
        content = MessageMapper._compact_tool_message_content(raw_content)

        return ToolMessage(
            content=content,
            tool_call_id=msg.tool_call_id,
        )

    @staticmethod
    def _compact_tool_message_content(raw_content: str | None) -> str:
        text = str(raw_content or "")
        parsed = MessageMapper._try_parse_json(text)
        if not isinstance(parsed, dict):
            return text[:600]

        tool_name = str(parsed.get("tool") or "").strip().lower()
        if tool_name == "build_lookup":
            build_id = str(parsed.get("build_id") or "").strip()
            hero_talent = str(parsed.get("hero_talent") or "").strip()
            environment = str(parsed.get("environment") or "").strip()
            scenario = str(parsed.get("scenario") or "").strip()
            return (
                "Build returned. Look at View Talent Tree to see the complete tree. "
                f"build_id={build_id}; hero_talent={hero_talent}; "
                f"environment={environment}; scenario={scenario}."
            )

        if tool_name == "guide_context_lookup":
            result_count = parsed.get("result_count")
            if not isinstance(result_count, int):
                result_count = 0
            markers = parsed.get("markers")
            marker_list = []
            if isinstance(markers, list):
                marker_list = [str(item).strip() for item in markers if str(item).strip()]
            evidence = parsed.get("evidence")
            first_snippet = ""
            if isinstance(evidence, list) and evidence:
                first = evidence[0]
                if isinstance(first, dict):
                    first_snippet = str(first.get("text") or "").strip()
            marker_preview = ",".join(marker_list[:4])
            snippet_preview = first_snippet[:160]
            return (
                "Guide context fetched. "
                f"result_count={result_count}; markers={marker_preview}; "
                f"first_snippet={snippet_preview}"
            )

        if tool_name == "list_builds":
            count = parsed.get("count")
            return f"List builds completed. count={count}"

        return text[:600]

    @staticmethod
    def _try_parse_json(value: str) -> dict | None:
        try:
            parsed = json.loads(value)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed
