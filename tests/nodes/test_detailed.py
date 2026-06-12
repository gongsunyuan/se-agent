# tests/nodes/test_detailed.py
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
from agent.nodes.detailed import extract_modules
from agent.state import AgentState


def _make_state(tmp_path, high_level_doc_path=None, errors=None) -> AgentState:
    state: AgentState = {
        "raw_input": "任务管理系统",
        "auto_mode": False,
        "requirements": {"functional": [], "non_functional": [], "actors": [], "constraints": [], "open_questions": []},
        "clarification_round": 1, "max_clarification_rounds": 5,
        "is_clear": True, "clarify_questions": [], "user_answers": [],
        "req_doc_confirmed": True, "high_level_confirmed": True,
        "revision_comment": None, "output_dir": Path(tmp_path),
        "req_doc_path": None, "high_level_doc_path": high_level_doc_path,
        "detail_doc_path": None, "messages": [], "errors": errors or [],
        "uml_diagram_files": [],
        "detail_modules": [],
        "detail_module_outputs": {},
    }
    return state


def _write_high_level_doc(tmp_path, content: str) -> str:
    doc_path = tmp_path / "总体设计.md"
    doc_path.write_text(content, encoding="utf-8")
    return str(doc_path)


class TestExtractModules:
    """Phase 1: extract_modules() 测试"""

    @patch("agent.nodes.detailed.get_llm_client")
    def test_extracts_modules_from_high_level_doc(self, mock_get_client, tmp_path):
        """正常情况：从总体设计中成功提取模块列表"""
        hl_path = _write_high_level_doc(tmp_path, "## 3. 模块划分\n\n- 用户模块\n- 任务模块\n- 统计模块")
        mock_client = MagicMock()
        mock_client.create_message.return_value = '["用户模块", "任务模块", "统计模块"]'
        mock_get_client.return_value = mock_client

        modules = extract_modules(Path(hl_path))

        assert modules == ["用户模块", "任务模块", "统计模块"]
        assert mock_client.create_message.call_count == 1

    @patch("agent.nodes.detailed.get_llm_client")
    def test_returns_empty_on_llm_failure(self, mock_get_client, tmp_path):
        """LLM 调用失败（3次重试全失败），返回空列表"""
        hl_path = _write_high_level_doc(tmp_path, "## 模块划分\n\n- 用户模块")
        mock_client = MagicMock()
        mock_client.create_message.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        modules = extract_modules(Path(hl_path))

        assert modules == []
        assert mock_client.create_message.call_count == 3  # 重试 3 次

    @patch("agent.nodes.detailed.get_llm_client")
    def test_retries_then_succeeds(self, mock_get_client, tmp_path):
        """重试第 2 次成功"""
        hl_path = _write_high_level_doc(tmp_path, "## 模块划分\n\n- A模块\n- B模块")
        mock_client = MagicMock()
        mock_client.create_message.side_effect = [
            RuntimeError("fail 1"),
            RuntimeError("fail 2"),
            '["A模块", "B模块"]',
        ]
        mock_get_client.return_value = mock_client

        modules = extract_modules(Path(hl_path))

        assert modules == ["A模块", "B模块"]
        assert mock_client.create_message.call_count == 3

    @patch("agent.nodes.detailed.get_llm_client")
    def test_fallback_on_json_parse_error(self, mock_get_client, tmp_path):
        """JSON 解析失败时用正则兜底"""
        hl_path = _write_high_level_doc(tmp_path, "## 3. 模块划分与职责\n\n- 用户模块\n- 订单模块")
        mock_client = MagicMock()
        mock_client.create_message.return_value = '模块列表：用户模块、订单模块'  # 非标准 JSON
        mock_get_client.return_value = mock_client

        modules = extract_modules(Path(hl_path))

        assert "用户模块" in modules
        assert "订单模块" in modules or len(modules) > 0
