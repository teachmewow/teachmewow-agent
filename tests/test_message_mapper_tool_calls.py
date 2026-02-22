import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from langchain_core.messages import AIMessage, ToolMessage

from app.application.agent.mappers.message_mapper import MessageMapper
from app.domain import Message, MessageRole, ToolCall


def test_message_mapper_reconstructs_ai_and_tool_chain() -> None:
    messages = [
        Message(
            id="ai-1",
            thread_id="t1",
            role=MessageRole.AI,
            content="",
            tool_calls=[ToolCall(id="call_1", name="list_builds", arguments="{}")],
            response_metadata={"citations": [{"citation_id": "source_1"}]},
        ),
        Message(
            id="tool-1",
            thread_id="t1",
            role=MessageRole.TOOL,
            content='{"ok": true}',
            tool_call_id="call_1",
            tool_result='{"ok": true}',
        ),
    ]

    mapped = MessageMapper.to_langchain_messages(messages)
    assert len(mapped) == 2
    assert isinstance(mapped[0], AIMessage)
    assert mapped[0].tool_calls[0]["id"] == "call_1"
    assert mapped[0].response_metadata == {"citations": [{"citation_id": "source_1"}]}
    assert isinstance(mapped[1], ToolMessage)
    assert mapped[1].tool_call_id == "call_1"


def test_message_mapper_skips_orphan_tool_message() -> None:
    messages = [
        Message(
            id="tool-1",
            thread_id="t1",
            role=MessageRole.TOOL,
            content='{"ok": true}',
            tool_call_id="orphan_call",
            tool_result='{"ok": true}',
        )
    ]

    mapped = MessageMapper.to_langchain_messages(messages)
    assert mapped == []
