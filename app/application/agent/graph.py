"""
LangGraph agent definition.
Defines the graph structure with nodes and edges.
"""

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.infrastructure.llm import LLMClient

from .state_schema import AgentState


def create_system_prompt(state: AgentState) -> str:
    """
    Create a system prompt based on the conversation context.

    Args:
        state: Current agent state

    Returns:
        System prompt string
    """
    base_prompt = """You are an expert World of Warcraft coach. You help players improve their gameplay by providing advice on:
- Class and specialization mechanics
- Optimal rotations and ability usage
- Gear choices and stat priorities
- Raid and dungeon strategies
- PvP tactics and arena compositions

Be friendly, encouraging, and provide specific, actionable advice. When discussing rotations or abilities, be precise about timing and priorities.
"""

    context_parts = []
    if state.wow_spec:
        context_parts.append(f"The player is asking about the {state.wow_spec} specialization.")
    if state.wow_class:
        context_parts.append(f"They play a {state.wow_class}.")
    if state.wow_role:
        context_parts.append(f"Their role is {state.wow_role}.")

    if context_parts:
        base_prompt += "\n\nContext:\n" + "\n".join(context_parts)

    return base_prompt


def should_continue(state: AgentState) -> str:
    """
    Determine if the agent should continue to tools or end.

    Args:
        state: Current agent state

    Returns:
        Next node name ("tools" or "end")
    """
    messages = state.messages
    if not messages:
        return END

    last_message = messages[-1]

    # Check if there are tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


def create_agent_graph(llm_client: LLMClient, tools: list[BaseTool]) -> StateGraph:
    """
    Create the LangGraph agent graph.

    Args:
        llm_client: The LLM client to use
        tools: List of tools available to the agent

    Returns:
        Configured StateGraph (not compiled)
    """
    # Bind tools to the model
    model = llm_client.model
    if tools:
        model = model.bind_tools(tools)

    # Define the agent node
    async def agent_node(state: AgentState) -> dict:
        """Call the LLM with the current state."""
        # Add system message if not present
        messages = list(state.messages)
        if not messages or not isinstance(messages[0], SystemMessage):
            system_prompt = create_system_prompt(state)
            messages = [SystemMessage(content=system_prompt)] + messages

        # Call the model
        response = await model.ainvoke(messages)

        return {"messages": [response]}

    # Create the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)

    if tools:
        tool_node = ToolNode(tools)
        graph.add_node("tools", tool_node)

        # Add edges
        graph.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                END: END,
            },
        )
        graph.add_edge("tools", "agent")
    else:
        graph.add_edge("agent", END)

    # Set entry point
    graph.set_entry_point("agent")

    return graph
