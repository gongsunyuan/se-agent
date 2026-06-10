# tests/nodes/test_gen_uml.py
import sys
from unittest.mock import MagicMock

# Workaround: openai not installed + anthropic hangs on import in WSL.
# Mock both before gen_uml (and thus config.py) is imported.
sys.modules.setdefault("openai", MagicMock())
sys.modules.setdefault("openai.types", MagicMock())
sys.modules.setdefault("openai.types.chat", MagicMock())
sys.modules.setdefault("anthropic", MagicMock())

import json
from unittest.mock import patch
from pathlib import Path
from agent.nodes.gen_uml import gen_uml_diagrams, _sanitize_filename, _fallback_parse


def _make_state(tmp_path: Path) -> dict:
    """创建包含三份文档路径的基础状态。"""
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True)

    req_path = output_dir / "需求说明.md"
    hl_path = output_dir / "总体设计.md"
    detail_path = output_dir / "详细设计.md"

    req_path.write_text("# 需求说明书\n\n## 5. 参与者\n- 读者\n- 管理员\n\n## 6. 用例\n读者→借阅", encoding="utf-8")
    hl_path.write_text("# 总体设计\n\n## 2. 架构\n客户端层 → 服务层", encoding="utf-8")
    detail_path.write_text("# 详细设计\n\n## 2. 类\nUser, Reader, Book\n\n## 4. 数据库\nusers 表", encoding="utf-8")

    return {
        "raw_input": "test",
        "auto_mode": False,
        "requirements": {},
        "clarification_round": 0,
        "max_clarification_rounds": 5,
        "is_clear": True,
        "clarify_questions": [],
        "user_answers": [],
        "req_doc_confirmed": True,
        "high_level_confirmed": True,
        "revision_comment": None,
        "output_dir": output_dir,
        "req_doc_path": str(req_path),
        "high_level_doc_path": str(hl_path),
        "detail_doc_path": str(detail_path),
        "messages": [],
        "errors": [],
        "uml_diagram_files": [],
    }


@patch("agent.nodes.gen_uml.get_llm_client")
def test_gen_uml_creates_diagram_files(mock_get_client, tmp_path):
    """gen_uml 节点应生成 .puml 文件到 diagrams/ 目录。"""
    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps({
        "use-case.puml": "@startuml\nactor 读者\n@enduml",
        "class-diagram.puml": "@startuml\nclass User\n@enduml",
    }, ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(tmp_path)
    result = gen_uml_diagrams(state)

    assert len(result["uml_diagram_files"]) == 2
    diagrams_dir = state["output_dir"] / "diagrams"
    assert diagrams_dir.exists()
    assert (diagrams_dir / "use-case.puml").exists()
    assert (diagrams_dir / "class-diagram.puml").exists()

    content = (diagrams_dir / "use-case.puml").read_text(encoding="utf-8")
    assert "@startuml" in content
    assert "读者" in content


@patch("agent.nodes.gen_uml.get_llm_client")
def test_gen_uml_handles_missing_docs(mock_get_client, tmp_path):
    """当某些文档路径为 None 时，节点应不崩溃。"""
    mock_client = MagicMock()
    mock_client.create_message.return_value = json.dumps({
        "use-case.puml": "@startuml\n@enduml",
    }, ensure_ascii=False)
    mock_get_client.return_value = mock_client

    state = _make_state(tmp_path)
    state["req_doc_path"] = None
    state["high_level_doc_path"] = None

    result = gen_uml_diagrams(state)
    assert len(result["uml_diagram_files"]) == 1


@patch("agent.nodes.gen_uml.get_llm_client")
def test_gen_uml_fallback_parse(mock_get_client, tmp_path):
    """当 LLM 不返回合法 JSON 时，回退到 @startuml 分割。"""
    mock_client = MagicMock()
    mock_client.create_message.return_value = """@startuml use-case
actor 读者
@enduml

@startuml class-diagram
class User
@enduml"""
    mock_get_client.return_value = mock_client

    state = _make_state(tmp_path)
    result = gen_uml_diagrams(state)

    assert len(result["uml_diagram_files"]) == 2


def test_sanitize_filename():
    assert _sanitize_filename("use-case") == "use-case"
    assert _sanitize_filename("用例图") == "用例图"
    assert _sanitize_filename("use case diagram!") == "use-case-diagram"


def test_fallback_parse_extracts_blocks():
    raw = "@startuml\na -> b\n@enduml\n\n@startuml my-title\nx -> y\n@enduml"
    result = _fallback_parse(raw)
    assert len(result) == 2
    # Either diagram_1.puml or my-title.puml should exist
    assert any("puml" in k for k in result)
