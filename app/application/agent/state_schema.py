"""
LangGraph state schema for the agent.
"""

from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

ChecklistStatus = Literal["pending", "in_progress", "complete", "failed"]
SubgraphStatus = Literal["idle", "running", "complete", "failed"]
SubgraphName = Literal["knowledge_explorer", "none"]


class ChecklistItem(BaseModel):
    id: str
    title: str
    status: ChecklistStatus = "pending"
    evidence: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    subgraph: SubgraphName = "none"
    checklist: list[ChecklistItem] = Field(default_factory=list)


class AgentState(BaseModel):
    """
    State schema for the LangGraph agent.

    This state is isolated per execution - each graph.stream() call
    creates its own state instance.

    Attributes:
        messages: Conversation history (uses add_messages reducer)
        thread_id: ID of the conversation thread (format: uuid_userId)
        user_id: ID of the user
        wow_class: WoW class context (required)
        wow_spec: WoW spec context (required)
        wow_role: WoW role context (required: tank, healer, dps)
        route_decision: Decision for routing to a subgraph
        checklist_items: Structured checklist for deep exploration
        current_checklist_id: Active checklist item id for sequential execution
        subgraph_status: Status of the active subgraph, if any
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    thread_id: str
    user_id: str
    wow_class: str
    wow_spec: str
    wow_role: str
    route_decision: RoutingDecision | None = None
    checklist_items: list[ChecklistItem] = Field(default_factory=list)
    current_checklist_id: str | None = None
    subgraph_status: SubgraphStatus = "idle"

    class Config:
        arbitrary_types_allowed = True


class StreamEvent(BaseModel):
    """
    Event emitted during streaming.
    Used to communicate with the frontend via SSE.

    Mirrors LangChain astream_events v2 envelope where possible.
    """

    # SSE event name (LangChain event or custom like "done"/"error")
    event: str
    # LangChain envelope fields
    name: str | None = None
    run_id: str | None = None
    parent_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    # Event payload
    data: dict = Field(default_factory=dict)
