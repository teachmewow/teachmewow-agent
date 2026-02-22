from __future__ import annotations

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

        fallback_route = "coach" if _looks_like_coaching_request(user_text) else "default"
        try:
            structured = self.classifier_model.with_structured_output(RouteDecision)
            decision = await structured.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Route user intent to one of two options:\n"
                            "- coach: user asks how to play/rotate/execute/tips for selected build.\n"
                            "- default: discovery, selection, generic or unrelated request.\n"
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
            route = str(getattr(decision, "route", fallback_route) or fallback_route)
            if route not in {"default", "coach"}:
                route = fallback_route
            return {"route": route}
        except Exception:
            return {"route": fallback_route}


def _last_human_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "").strip()
    return ""


def _looks_like_coaching_request(text: str) -> bool:
    lowered = text.lower()
    coaching_tokens = (
        "rotation",
        "rotação",
        "execute",
        "opener",
        "cooldown",
        "priority",
        "prioridade",
        "tips",
        "dicas",
        "como jogar",
        "how to play",
        "gameplay",
        "mythic+",
        "mythic plus",
        "raid",
        "m+",
    )
    return any(token in lowered for token in coaching_tokens)
