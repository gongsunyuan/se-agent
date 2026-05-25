# src/agent/nodes/detailed.py
from pathlib import Path
from agent.state import AgentState
from agent.config import get_client, MODEL_ID
from agent.prompts import SYSTEM_BASE, DETAIL_PROMPT


def detailed_design(state: AgentState) -> dict:
    client = get_client()

    hl_content = ""
    if state.get("high_level_doc_path"):
        hl_content = Path(state["high_level_doc_path"]).read_text(encoding="utf-8")

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=8192,
        system=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": DETAIL_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": hl_content or "根据总体设计生成详细设计"}],
    )
    content = response.content[0].text

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "详细设计.md"
    doc_path.write_text(content, encoding="utf-8")

    return {"detail_doc_path": str(doc_path)}
