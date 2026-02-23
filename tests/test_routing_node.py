import pytest
from langchain_core.messages import HumanMessage

from app.application.agent.nodes.routing_node import RoutingNode
from app.application.agent.state_schema import AgentState, CharInfo


class _NeverCalledClassifier:
    def with_structured_output(self, _schema):
        raise AssertionError("classifier must not run for smalltalk")


class _ClassifierReturns:
    def __init__(self, route: str) -> None:
        self.route = route

    def with_structured_output(self, schema):
        selected_route = self.route

        class _Runner:
            async def ainvoke(self, _messages):
                return schema.model_validate(
                    {"route": selected_route, "reason": "unit-test"}
                )

        return _Runner()


def _state(*, text: str, with_build: bool = True) -> AgentState:
    return AgentState(
        messages=[HumanMessage(content=text)],
        thread_id="t-route",
        user_id="u-route",
        char_info=CharInfo(**{"class": "warrior", "spec": "arms", "role": "dps"}),
        active_build_id="arms_slayer_single_raid" if with_build else None,
    )


@pytest.mark.asyncio
async def test_routing_smalltalk_with_active_build_stays_default() -> None:
    node = RoutingNode(classifier_model=_NeverCalledClassifier())
    result = await node(_state(text="oi", with_build=True))
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_routing_smalltalk_with_punctuation_stays_default() -> None:
    node = RoutingNode(classifier_model=_NeverCalledClassifier())
    result = await node(_state(text="oi!", with_build=True))
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_routing_explicit_coaching_can_go_to_coach() -> None:
    node = RoutingNode(classifier_model=_ClassifierReturns(route="coach"))
    result = await node(
        _state(text="quero opener e prioridade de gcd para essa build", with_build=True)
    )
    assert result["route"] == "coach"
