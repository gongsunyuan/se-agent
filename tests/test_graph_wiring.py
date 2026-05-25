# tests/test_graph_wiring.py
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
