# src/agent/nodes/high_level.py
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, HIGH_LEVEL_PROMPT


def high_level_design(state: AgentState) -> dict:
    client = get_llm_client()

    req_content = ""
    if state.get("req_doc_path"):
        req_content = Path(state["req_doc_path"]).read_text(encoding="utf-8")

    content = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": HIGH_LEVEL_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=req_content or "根据已知需求生成总体设计",
        max_tokens=4096,
        node_name="high_level",
    )

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "总体设计.md"
    doc_path.write_text(content, encoding="utf-8")

    return {"high_level_doc_path": str(doc_path)}
