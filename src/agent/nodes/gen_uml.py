# src/agent/nodes/gen_uml.py
import json
import re
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import UML_GEN_PROMPT
from agent.logger import log_execution


def gen_uml_diagrams(state: AgentState) -> dict:
    """读取三份设计文档，生成所有 PlantUML 图表文件。"""
    client = get_llm_client()

    # 1. 读取三份文档内容
    docs_content = []
    for key, label in [
        ("req_doc_path", "需求说明书"),
        ("high_level_doc_path", "总体设计文档"),
        ("detail_doc_path", "详细设计文档"),
    ]:
        path = state.get(key)
        if path and Path(path).exists():
            content = Path(path).read_text(encoding="utf-8")
            docs_content.append(f"# {label}\n\n{content}")
        else:
            docs_content.append(f"# {label}\n\n（文档未生成）")

    combined = "\n\n---\n\n".join(docs_content)

    # 2. 调用 LLM 生成 PlantUML
    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": UML_GEN_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=combined,
        max_tokens=8192,
        node_name="gen_uml",
    )

    # 3. 解析 JSON 输出
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        diagram_map = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: 尝试用 @startuml 分割提取
        diagram_map = _fallback_parse(raw)

    # 4. 写入 diagrams/ 目录
    output_dir: Path = state["output_dir"]
    diagrams_dir = output_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[str] = []
    for filename, content in diagram_map.items():
        filepath = diagrams_dir / filename
        filepath.write_text(content, encoding="utf-8")
        written_files.append(str(filepath))

    log_execution(
        "gen_uml",
        input_summary=f"docs_count=3, total_chars={len(combined)}",
        decision=f"generated {len(written_files)} PlantUML files",
        output_summary=f"files={[Path(f).name for f in written_files]}",
    )

    return {"uml_diagram_files": written_files}


def _fallback_parse(raw: str) -> dict[str, str]:
    """当 JSON 解析失败时，基于 @startuml 分割提取各个图。"""
    blocks = re.split(r"(?=@startuml)", raw)
    result: dict[str, str] = {}
    
    for block in blocks:
        block = block.strip()
        if not block.startswith("@startuml"):
            continue
        first_line = block.split("\n")[0]
        title_match = re.search(r"@startuml\s+(.+)", first_line)
        if title_match:
            filename = _sanitize_filename(title_match.group(1).strip())
        else:
            filename = f"diagram_{len(result) + 1}.puml"
        if not filename.endswith(".puml"):
            filename += ".puml"
        result[filename] = block
    
    return result


def _sanitize_filename(name: str) -> str:
    """将图表标题转为安全的文件名。"""
    name = re.sub(r"[^\w\u4e00-\u9fff-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "diagram"
