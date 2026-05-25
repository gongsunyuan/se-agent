# tests/test_state.py
from agent.state import AgentState
from pathlib import Path

def test_agent_state_has_required_fields():
    state: AgentState = {
        "raw_input": "构建一个任务管理系统",
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
    assert state["raw_input"] == "构建一个任务管理系统"
    assert state["clarification_round"] == 0
