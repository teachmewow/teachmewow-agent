"""
Shared helpers for knowledge explorer message scoping.
"""

from langchain_core.messages import AIMessage, BaseMessage

KNOWLEDGE_EXPLORER_START = "__knowledge_explorer_start__"


def build_explorer_start_marker() -> AIMessage:
    return AIMessage(content=KNOWLEDGE_EXPLORER_START)


def has_explorer_start_marker(messages: list[BaseMessage]) -> bool:
    return any(
        isinstance(message, AIMessage) and message.content == KNOWLEDGE_EXPLORER_START
        for message in messages
    )


def get_subgraph_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    marker_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, AIMessage) and message.content == KNOWLEDGE_EXPLORER_START:
            marker_index = index
            break
    if marker_index is None:
        return []
    return messages[marker_index + 1 :]
