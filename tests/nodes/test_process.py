# tests/nodes/test_process.py
from unittest.mock import MagicMock, patch
from pathlib import Path
from agent.nodes.process import process_requirement
from agent.state import AgentState


def _make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "raw_input": "构建一个任务管理系统，支持多用户",
        "requirements": {},
        "clarification_round": 0,
        "max_clarification_rounds": 5,
        "is_clear": False,
        "clarify_questions": [],
        "user_answers": [],
        "req_doc_confirmed": False,
        "high_level_confirmed": False,
        "revision_comment": None,
        "output_dir": Path("outputs/test"),
        "req_doc_path": None,
        "high_level_doc_path": None,
        "detail_doc_path": None,
        "messages": [],
        "errors": [],
    }
    base.update(kwargs)
    return base


@patch("agent.nodes.process.get_llm_client")
def test_process_returns_requirements(mock_get_client):
    mock_client = MagicMock()
    mock_client.create_message.return_value = '{"functional": ["管理任务"], "non_functional": [], "actors": ["用户"], "constraints": [], "open_questions": []}'
    mock_get_client.return_value = mock_client

    result = process_requirement(_make_state())
    assert "requirements" in result
    assert isinstance(result["requirements"].get("functional"), list)
