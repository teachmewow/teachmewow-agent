import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from langchain_core.messages import AIMessage, ToolMessage

from app.application.agent.nodes.llm_node import LLMNode


class _DummyModel:
    async def astream(self, messages, config):
        yield AIMessage(content="ok")


def test_llm_node_collects_and_attaches_citations() -> None:
    node = LLMNode(_DummyModel())  # type: ignore[arg-type]
    messages = [
        ToolMessage(
            content=(
                '{"tool":"guide_context_lookup","citations":['
                '{"citation_id":"source_icy_arms_rotation_0004","source_doc_id":"icy_arms_rotation_cooldowns"}'
                "]} "
            ),
            tool_call_id="call_1",
        )
    ]

    citations = node._collect_citations(messages)  # noqa: SLF001
    response = AIMessage(content="Use Execute here [[source_icy_arms_rotation_0004]]")
    enriched = node._attach_citations(response, citations)  # noqa: SLF001

    assert enriched.response_metadata is not None
    assert enriched.response_metadata.get("citations")
    assert enriched.response_metadata["citations"][0]["citation_id"] == "source_icy_arms_rotation_0004"
