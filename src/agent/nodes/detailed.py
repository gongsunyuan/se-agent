# src/agent/nodes/detailed.py
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, DETAIL_PROMPT


def detailed_design(state: AgentState) -> dict:
    client = get_llm_client()

    hl_content = ""
    if state.get("high_level_doc_path"):
        hl_content = Path(state["high_level_doc_path"]).read_text(encoding="utf-8")

    content = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": DETAIL_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=hl_content or "根据总体设计生成详细设计",
        max_tokens=8192,
    )

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "详细设计.md"
    doc_path.write_text(content, encoding="utf-8")

    return {"detail_doc_path": str(doc_path)}
