# tests/nodes/test_judge.py
from unittest.mock import MagicMock, patch
from pathlib import Path
from agent.nodes.judge import judge
from agent.state import AgentState

def _make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "raw_input": "test",
        "requirements": {"functional": ["登录"], "non_functional": [], "actors": ["用户"], "constraints": [], "open_questions": []},
        "clarification_round": 0, "max_clarification_rounds": 5,
        "is_clear": False, "clarify_questions": [], "user_answers": [],
        "req_doc_confirmed": False, "high_level_confirmed": False,
        "revision_comment": None, "output_dir": Path("outputs/test"),
        "req_doc_path": None, "high_level_doc_path": None, "detail_doc_path": None,
        "messages": [], "errors": [],
    }
    base.update(kwargs)
    return base

def test_judge_clear_fastpath():
    """有 functional 且无 open_questions 时，规则路径直接返回 is_clear=True"""
    result = judge(_make_state())
    assert result["is_clear"] is True

@patch("agent.nodes.judge.get_llm_client")
def test_judge_llm_path_when_open_questions(mock_get_client):
    """有 open_questions 时走 LLM 路径"""
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"is_clear": true, "reason": "需求完整"}'
    mock_get_client.return_value = mock_client

    state = _make_state()
    state["requirements"]["open_questions"] = ["需要明确用户角色"]
    result = judge(state)
    assert result["is_clear"] is True
