# tests/nodes/test_detailed.py
from unittest.mock import MagicMock, patch
from pathlib import Path
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
        """前两次失败，第三次成功"""
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


class TestGenModule:
    """Phase 2: gen_module() 测试"""

    @patch("agent.nodes.detailed.get_llm_client")
    def test_generates_module_detail(self, mock_get_client, tmp_path):
        """正常生成模块详细设计"""
        hl_path = _write_high_level_doc(tmp_path, "## 总体设计\n\n### 模块划分\n- 用户模块")
        mock_client = MagicMock()
        mock_client.create_message.return_value = "### 用户模块详细设计\n\n内容..."
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import gen_module
        result = gen_module(Path(hl_path), "用户模块")

        assert "用户模块" in result
        assert mock_client.create_message.call_count == 1

    @patch("agent.nodes.detailed.get_llm_client")
    def test_retries_on_failure(self, mock_get_client, tmp_path):
        """失败后重试成功"""
        hl_path = _write_high_level_doc(tmp_path, "## 总体设计\n\n- 支付模块")
        mock_client = MagicMock()
        mock_client.create_message.side_effect = [
            RuntimeError("fail"),
            "### 支付模块\n\n支付接口设计..."
        ]
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import gen_module
        result = gen_module(Path(hl_path), "支付模块")

        assert "支付模块" in result
        assert mock_client.create_message.call_count == 2

    @patch("agent.nodes.detailed.get_llm_client")
    def test_returns_none_on_all_failures(self, mock_get_client, tmp_path):
        """3 次全失败返回 None"""
        hl_path = _write_high_level_doc(tmp_path, "## 总体设计\n\n- 失败模块")
        mock_client = MagicMock()
        mock_client.create_message.side_effect = RuntimeError("fail")
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import gen_module
        result = gen_module(Path(hl_path), "失败模块", max_retries=3)

        assert result is None
        assert mock_client.create_message.call_count == 3


class TestDetailedConcurrency:
    """Phase 2: 并发流程测试"""

    @patch("agent.nodes.detailed.get_llm_client")
    def test_concurrent_module_generation(self, mock_get_client, tmp_path):
        """测试线程池并发生成多个模块"""
        hl_path = _write_high_level_doc(tmp_path, "## 模块划分\n\n- A模块\n- B模块\n- C模块")

        call_count = [0]

        def create_message(*args, **kwargs):
            node_name = kwargs.get("node_name", "")
            if node_name == "extract_modules":
                return '["A模块", "B模块", "C模块"]'

            call_count[0] += 1
            user_content = kwargs.get("user_content", "")
            for mod in ["A模块", "B模块", "C模块"]:
                if mod in user_content:
                    return f"### {mod}详细设计\n\n内容..."

            if node_name == "merge_detail":
                return "# 详细设计\n\n汇总内容..."

            return "default"

        mock_client = MagicMock()
        mock_client.create_message.side_effect = create_message
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import detailed_design
        state = _make_state(tmp_path, high_level_doc_path=hl_path)
        result = detailed_design(state)

        assert call_count[0] == 3
        assert result.get("detail_doc_path") is not None
        assert Path(result["detail_doc_path"]).exists()

    @patch("agent.nodes.detailed.get_llm_client")
    def test_fallback_to_single_llm_on_few_modules(self, mock_get_client, tmp_path):
        """模块数不足 2 个时回退到原单次 LLM 模式"""
        hl_path = _write_high_level_doc(tmp_path, "## 模块划分\n\n- 唯一模块")
        mock_client = MagicMock()

        def create_message(*args, **kwargs):
            node_name = kwargs.get("node_name", "")
            if node_name == "extract_modules":
                return '["唯一模块"]'
            if node_name == "detail_fallback":
                return "# 详细设计\n\n回退模式生成的完整文档"
            return ""

        mock_client.create_message.side_effect = create_message
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import detailed_design
        state = _make_state(tmp_path, high_level_doc_path=hl_path)
        result = detailed_design(state)

        assert result.get("detail_doc_path") is not None
        assert Path(result["detail_doc_path"]).exists()

    @patch("agent.nodes.detailed.get_llm_client")
    def test_skip_failed_modules(self, mock_get_client, tmp_path):
        """部分模块失败不阻塞其他模块"""
        hl_path = _write_high_level_doc(tmp_path, "## 模块划分\n\n- 好模块\n- 坏模块\n- 好模块2")

        def create_message(*args, **kwargs):
            node_name = kwargs.get("node_name", "")
            if node_name == "extract_modules":
                return '["好模块", "坏模块", "好模块2"]'

            user_content = kwargs.get("user_content", "")
            if "坏模块" in user_content and node_name.startswith("gen_module_"):
                raise RuntimeError("坏模块生成失败")
            if node_name.startswith("gen_module_"):
                return "### 模块内容\n\n成功生成"
            if node_name == "merge_detail":
                return "# 详细设计\n\n汇总（跳过坏模块）"

            return "ok"

        mock_client = MagicMock()
        mock_client.create_message.side_effect = create_message
        mock_get_client.return_value = mock_client

        from agent.nodes.detailed import detailed_design
        state = _make_state(tmp_path, high_level_doc_path=hl_path)
        result = detailed_design(state)

        assert result.get("detail_doc_path") is not None
        assert Path(result["detail_doc_path"]).exists()
