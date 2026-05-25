# tests/nodes/test_gen_req_doc.py
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
from agent.nodes.gen_req_doc import generate_req_doc
from agent.state import AgentState

def _make_state(tmp_path) -> AgentState:
    return {
        "raw_input": "任务管理系统",
        "requirements": {"functional": ["增删任务"], "non_functional": [], "actors": ["用户"], "constraints": [], "open_questions": []},
        "clarification_round": 1, "max_clarification_rounds": 5,
        "is_clear": True, "clarify_questions": [], "user_answers": [],
        "req_doc_confirmed": False, "high_level_confirmed": False,
        "revision_comment": None, "output_dir": Path(tmp_path),
        "req_doc_path": None, "high_level_doc_path": None, "detail_doc_path": None,
        "messages": [], "errors": [],
    }

@patch("agent.config.anthropic.Anthropic")
def test_gen_req_doc_writes_file(mock_client_class, tmp_path):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# 需求说明书\n\n## 1. 项目概述\n测试项目")]
    mock_client.messages.create.return_value = mock_response

    result = generate_req_doc(_make_state(tmp_path))
    assert result["req_doc_path"] is not None
    assert Path(result["req_doc_path"]).exists()
    assert Path(result["req_doc_path"]).read_text(encoding="utf-8").startswith("# 需求说明书")
