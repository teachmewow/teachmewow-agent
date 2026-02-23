from __future__ import annotations

import re
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.application.agent.state_schema import AgentState


class RouteDecision(BaseModel):
    route: Literal["default", "coach"]
    reason: str


class RoutingNode:
    """
    Chooses the main execution route: default graph flow or coaching subgraph.
    """

    def __init__(self, classifier_model: BaseChatModel) -> None:
        self.classifier_model = classifier_model

    async def __call__(self, state: AgentState, config=None) -> AgentState:
        user_text = _last_human_message_text(state.messages)
        has_build = state.build_info is not None or bool(state.active_build_id)
        if not has_build:
            return {"route": "default"}
        if not user_text:
            return {"route": "default"}
        if _is_smalltalk_or_ack(user_text):
            return {"route": "default"}

        try:
            structured = self.classifier_model.with_structured_output(RouteDecision)
            decision = await structured.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Classify the LAST user message intent into one route:\n"
                            "- coach: explicit coaching request about gameplay execution for the active build\n"
                            "  (examples: rotation, opener, priority, cooldown usage, mistake fixing, raid/m+ optimization).\n"
                            "- default: any other intent (greetings, acknowledgements, small talk, generic chat,\n"
                            "  build discovery/listing/selection, or vague messages without actionable coaching request).\n"
                            "Important:\n"
                            "- has_active_build=true is only an eligibility signal, not intent.\n"
                            "- If the user did not explicitly ask for coaching guidance in this last message, choose default.\n"
                            "Return strict JSON following schema."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"user_text={user_text}\n"
                            f"has_active_build={has_build}\n"
                            f"char_class={state.char_info.wow_class}\n"
                            f"char_spec={state.char_info.spec}"
                        )
                    ),
                ]
            )
            route = str(getattr(decision, "route", "default") or "default")
            if route not in {"default", "coach"}:
                route = "default"
            return {"route": route}
        except Exception:
            return {"route": "default"}


def _last_human_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "").strip()
    return ""


_SMALLTALK_PATTERN = re.compile(
    r"^(oi+|ol[aá]|hello|hi+|hey+|yo+|e ai|e aí|blz|beleza|ok+|valeu|thanks?)$",
    re.IGNORECASE,
)


def _is_smalltalk_or_ack(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    return _SMALLTALK_PATTERN.fullmatch(normalized) is not None
