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

        for msg in messages:
            langchain_msg = MessageMapper._convert_single(msg)
            if langchain_msg is not None:
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
            return AIMessage(content=msg.content, tool_calls=tool_calls)

        return AIMessage(content=msg.content)

    @staticmethod
    def _convert_tool_message(msg: Message) -> ToolMessage | None:
        """
        Convert a domain TOOL message to LangChain ToolMessage.

        Requires tool_call_id to be present.
        """
        if not msg.tool_call_id:
            return None

        # Use tool_result if available, otherwise use content
        content = msg.tool_result if msg.tool_result else msg.content

        return ToolMessage(
            content=content,
            tool_call_id=msg.tool_call_id,
        )
