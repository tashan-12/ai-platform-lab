"""LangGraph 图组装：analyze -> verify -> report，两条条件边。"""

from __future__ import annotations

from ai_lab_mcp.config import Settings
from ai_lab_mcp.registry import ToolRegistry, build_registry
from langgraph.graph import END, START, StateGraph

from .nodes import build_nodes, route_after_analyze, route_after_verify
from .state import AgentState


def build_graph(settings: Settings, registry: ToolRegistry | None = None):
    """编译好的图。传入 registry 可复用已有工具实例（测试时常这么用）。"""

    registry = registry or build_registry(settings)
    nodes = build_nodes(settings, registry)

    graph = StateGraph(AgentState)
    graph.add_node("analyze", nodes["analyze"])
    graph.add_node("verify", nodes["verify"])
    graph.add_node("retrieve", nodes["retrieve"])
    graph.add_node("report", nodes["report"])

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {"verify": "verify", "report": "report"},
    )
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"verify": "verify", "retrieve": "retrieve"},
    )
    graph.add_edge("retrieve", "report")
    graph.add_edge("report", END)

    return graph.compile()
