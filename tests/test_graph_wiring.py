# tests/test_graph_wiring.py
from pathlib import Path
from agent.graph import build_graph

def test_graph_compiles():
    graph = build_graph(use_memory=False)
    assert graph is not None

def test_graph_has_expected_nodes():
    graph = build_graph(use_memory=False)
    nodes = set(graph.get_graph().nodes.keys())
    expected = {
        "process", "judge", "clarify",
        "gen_req_doc", "checkpoint_a",
        "high_level", "checkpoint_b", "detail",
        "__start__",
    }
    assert expected.issubset(nodes)


def test_graph_auto_mode_skips_checkpoints():
    """Auto mode graph: gen_req_doc routes to high_level, high_level routes to detail."""
    graph = build_graph(use_memory=False)
    nodes = set(graph.get_graph().nodes.keys())
    # Checkpoints are still in the graph (they exist as nodes)
    assert "checkpoint_a" in nodes
    assert "checkpoint_b" in nodes


def test_graph_routing_functions():
    """Route functions return correct values based on auto_mode."""
    from agent.graph import _route_after_gen_req, _route_after_high_level
    from agent.state import AgentState

    auto_state: AgentState = {
        "raw_input": "test",
        "auto_mode": True,
        "requirements": {},
        "clarification_round": 0, "max_clarification_rounds": 5,
        "is_clear": False, "clarify_questions": [], "user_answers": [],
        "req_doc_confirmed": False, "high_level_confirmed": False,
        "revision_comment": None, "output_dir": Path("outputs/test"),
        "req_doc_path": None, "high_level_doc_path": None, "detail_doc_path": None,
        "messages": [], "errors": [],
    }
    assert _route_after_gen_req(auto_state) == "skip_checkpoint"
    assert _route_after_high_level(auto_state) == "skip_checkpoint"

    auto_state["auto_mode"] = False
    assert _route_after_gen_req(auto_state) == "to_checkpoint"
    assert _route_after_high_level(auto_state) == "to_checkpoint"


def test_graph_auto_mode_missing_key():
    """When auto_mode not in state, defaults to False (to_checkpoint)."""
    from agent.graph import _route_after_gen_req
    from agent.state import AgentState

    state: AgentState = {
        "raw_input": "test",
        "requirements": {},
        "clarification_round": 0, "max_clarification_rounds": 5,
        "is_clear": False, "clarify_questions": [], "user_answers": [],
        "req_doc_confirmed": False, "high_level_confirmed": False,
        "revision_comment": None, "output_dir": Path("outputs/test"),
        "req_doc_path": None, "high_level_doc_path": None, "detail_doc_path": None,
        "messages": [], "errors": [],
    }
    # auto_mode key is absent — should default to to_checkpoint
    assert _route_after_gen_req(state) == "to_checkpoint"
