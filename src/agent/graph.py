# src/agent/graph.py
import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.state import AgentState
from agent.nodes.process import process_requirement
from agent.nodes.judge import judge
from agent.nodes.clarify import clarify
from agent.nodes.gen_req_doc import generate_req_doc
from agent.nodes.checkpoints import checkpoint_req_doc, checkpoint_high_level
from agent.nodes.high_level import high_level_design
from agent.nodes.detailed import detailed_design


def _route_judge(state: AgentState) -> str:
    if state["is_clear"]:
        return "ok"
    if state["clarification_round"] >= state["max_clarification_rounds"]:
        return "ok"
    return "clarify"


def _route_checkpoint_a(state: AgentState) -> str:
    return "ok" if state["req_doc_confirmed"] else "revise"


def _route_checkpoint_b(state: AgentState) -> str:
    return "ok" if state["high_level_confirmed"] else "revise"


def _route_after_gen_req(state: AgentState) -> str:
    """auto 模式跳过 checkpoint_a 直通 high_level。"""
    return "skip_checkpoint" if state.get("auto_mode", False) else "to_checkpoint"


def _route_after_high_level(state: AgentState) -> str:
    """auto 模式跳过 checkpoint_b 直通 detail。"""
    return "skip_checkpoint" if state.get("auto_mode", False) else "to_checkpoint"


def build_graph(use_memory: bool = True, auto_mode: bool = False):
    g = StateGraph(AgentState)

    g.add_node("process",      process_requirement)
    g.add_node("judge",        judge)
    g.add_node("clarify",      clarify)
    g.add_node("gen_req_doc",  generate_req_doc)
    g.add_node("checkpoint_a", checkpoint_req_doc)
    g.add_node("high_level",   high_level_design)
    g.add_node("checkpoint_b", checkpoint_high_level)
    g.add_node("detail",       detailed_design)

    g.set_entry_point("process")
    g.add_edge("process", "judge")
    g.add_conditional_edges(
        "judge",
        _route_judge,
        {"ok": "gen_req_doc", "clarify": "clarify"},
    )
    g.add_edge("clarify", "process")
    g.add_conditional_edges(
        "gen_req_doc",
        _route_after_gen_req,
        {"skip_checkpoint": "high_level", "to_checkpoint": "checkpoint_a"},
    )
    g.add_conditional_edges(
        "checkpoint_a",
        _route_checkpoint_a,
        {"ok": "high_level", "revise": "process"},
    )
    g.add_conditional_edges(
        "high_level",
        _route_after_high_level,
        {"skip_checkpoint": "detail", "to_checkpoint": "checkpoint_b"},
    )
    g.add_conditional_edges(
        "checkpoint_b",
        _route_checkpoint_b,
        {"ok": "detail", "revise": "high_level"},
    )
    g.add_edge("detail", END)

    if use_memory:
        from pathlib import Path
        Path("outputs").mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect("outputs/checkpoints.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        return g.compile(checkpointer=checkpointer)
    return g.compile()
