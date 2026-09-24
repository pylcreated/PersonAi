# chat-agent/agent/negotiation_graph.py
from langgraph.graph import StateGraph, START, END
from agent.state import NegotiationState
from agent.nodes import (
    goal_node, template_node, slice_node, update_node,
    confirm_node, finalize_node,
)


def build_negotiation_graph():
    g = StateGraph(NegotiationState)
    g.add_node("goal", goal_node.run)
    g.add_node("template", template_node.run)
    g.add_node("slice", slice_node.run)
    g.add_node("update", update_node.run)
    g.add_node("confirm", confirm_node.run)
    g.add_node("finalize", finalize_node.run)

    g.add_edge(START, "goal")
    g.add_edge("goal", "template")
    g.add_edge("template", "slice")
    g.add_edge("slice", "update")
    g.add_edge("update", "confirm")
    g.add_edge("confirm", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


negotiation_graph = build_negotiation_graph()