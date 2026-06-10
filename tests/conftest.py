# tests/conftest.py
import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def setup_env():
    """确保测试环境中始终有假的 ANTHROPIC_API_KEY"""
    old = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-mock-key"
    yield
    if old is not None:
        os.environ["ANTHROPIC_API_KEY"] = old


@pytest.fixture
def tmp_output(tmp_path) -> Path:
    d = tmp_path / "outputs"
    d.mkdir()
    return d


@pytest.fixture
def base_state(tmp_output):
    from agent.state import AgentState
    return AgentState(
        raw_input="构建一个任务管理系统",
        auto_mode=False,
        requirements={},
        clarification_round=0,
        max_clarification_rounds=5,
        is_clear=False,
        clarify_questions=[],
        user_answers=[],
        req_doc_confirmed=False,
        high_level_confirmed=False,
        revision_comment=None,
        output_dir=tmp_output,
        req_doc_path=None,
        high_level_doc_path=None,
        detail_doc_path=None,
        messages=[],
        errors=[],
        uml_diagram_files=[],
    )
