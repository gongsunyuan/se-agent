"""Tests for clarify node."""
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
from agent.nodes.clarify import clarify
from agent.state import AgentState


def _make_state(**kwargs) -> AgentState:
    base: AgentState = {
        "raw_input": "构建一个在线图书馆",
        "auto_mode": False,
        "requirements": {
            "functional": ["借阅", "归还", "搜索"],
            "non_functional": [],
            "actors": ["读者", "管理员"],
            "constraints": [],
            "open_questions": ["用户认证方式未确定", "数据库选型未确定"],
        },
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


@patch("agent.nodes.clarify.get_llm_client")
def test_clarify_auto_mode_self_answers(mock_get_client, tmp_path):
    """Auto mode: LLM generates questions, then LLM answers them."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.side_effect = [
        '["认证方式应该怎么选？", "数据库用什么？"]',
        '["使用 JWT 认证", "使用 PostgreSQL"]',
    ]
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=True, output_dir=output_dir)
    result = clarify(state)

    assert mock_client.create_message.call_count == 2
    assert result["user_answers"] == ["使用 JWT 认证", "使用 PostgreSQL"]
    assert result["clarification_round"] == 1
    assert result["clarify_questions"] == ["认证方式应该怎么选？", "数据库用什么？"]


from agent.nodes.clarify import render_choices


def test_render_choices_normal():
    """render_choices 生成带 A/B/C 编号的选项字符串。"""
    result = render_choices("数据库选型？", ["PostgreSQL", "MySQL", "MongoDB"])
    assert "数据库选型？" in result
    assert "A. PostgreSQL" in result
    assert "B. MySQL" in result
    assert "C. MongoDB" in result
    assert "T. Type something" in result


def test_render_choices_two_options():
    """2 个选项时只渲染 A、B。"""
    result = render_choices("认证方式？", ["JWT", "Session"])
    assert "A. JWT" in result
    assert "B. Session" in result
    assert "C." not in result
    assert "T. Type something" in result


def test_render_choices_no_options():
    """空选项列表返回空字符串。"""
    result = render_choices("随便问个问题", [])
    assert result == ""


@patch("agent.nodes.clarify.get_llm_client")
def test_clarify_auto_mode_writes_clarify_log(mock_get_client, tmp_path):
    """Auto mode writes 澄清记录.md with Q&A pairs."""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.side_effect = [
        '["认证方式应该怎么选？"]',
        '["使用 JWT 认证"]',
    ]
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=True, output_dir=output_dir)
    clarify(state)

    clarify_path = output_dir / "澄清记录.md"
    assert clarify_path.exists()
    content = clarify_path.read_text(encoding="utf-8")
    assert "认证方式应该怎么选" in content
    assert "使用 JWT 认证" in content
    assert "澄清轮次 1" in content


@patch("agent.nodes.clarify.get_llm_client")
def test_parse_new_json_format(mock_get_client, tmp_path):
    """LLM 返回 [{question, options}] 格式 → 正确解析问题与选项。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
        {"question": "数据库？", "options": ["Pg", "MySQL"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["A", "B"]
        result = clarify(state)

    assert result["clarify_questions"] == ["认证方式？", "数据库？"]
    assert result["user_answers"] == ["JWT", "MySQL"]
    assert result["clarification_round"] == 1


@patch("agent.nodes.clarify.get_llm_client")
def test_parse_old_format_fallback(mock_get_client, tmp_path):
    """LLM 返回老格式 ["q1", "q2"] → 降级为自由输入，不崩溃。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = '["问题1", "问题2"]'
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["自由答案1", "自由答案2"]
        result = clarify(state)

    assert result["clarify_questions"] == ["问题1", "问题2"]
    assert result["user_answers"] == ["自由答案1", "自由答案2"]


@patch("agent.nodes.clarify.get_llm_client")
def test_user_selects_option(mock_get_client, tmp_path):
    """用户选 B → user_answers 含对应选项文字。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session", "OAuth"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["B"]
        result = clarify(state)

    assert result["user_answers"] == ["Session"]


@patch("agent.nodes.clarify.get_llm_client")
def test_user_types_custom(mock_get_client, tmp_path):
    """用户选 T 再输入自定义文字 → user_answers 含自定义文字。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        # 第一次 ask 选 T，第二次 ask 是自定义输入
        mock_prompt.ask.side_effect = ["T", "使用 Firebase Auth"]
        result = clarify(state)

    assert result["user_answers"] == ["使用 Firebase Auth"]


@patch("agent.nodes.clarify.get_llm_client")
def test_user_default_enter_selects_a(mock_get_client, tmp_path):
    """Prompt.ask 传入 default='A'。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        # 模拟回车（返回默认值 A）
        mock_prompt.ask.return_value = "A"
        result = clarify(state)

    # 验证 Prompt.ask 被调用时传了 default="A"
    call_kwargs = mock_prompt.ask.call_args_list[0][1]
    assert call_kwargs.get("default") == "A"
    assert result["user_answers"] == ["JWT"]


@patch("agent.nodes.clarify.get_llm_client")
def test_clarify_log_unchanged(mock_get_client, tmp_path):
    """澄清记录.md 只记问答文字，不记选项结构。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps([
        {"question": "认证方式？", "options": ["JWT", "Session"]},
    ], ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(auto_mode=False, output_dir=output_dir)
    with patch("agent.nodes.clarify.Prompt") as mock_prompt:
        mock_prompt.ask.side_effect = ["B"]
        clarify(state)

    clarify_path = output_dir / "澄清记录.md"
    assert clarify_path.exists()
    content = clarify_path.read_text(encoding="utf-8")
    assert "认证方式？" in content
    assert "Session" in content
    assert "澄清轮次 1" in content
    # 不应包含选项结构
    assert "JWT" not in content
    assert "options" not in content
