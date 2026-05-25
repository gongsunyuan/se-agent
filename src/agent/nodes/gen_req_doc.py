# src/agent/nodes/gen_req_doc.py
import json
from pathlib import Path
from agent.state import AgentState
from agent.config import get_client, MODEL_ID
from agent.prompts import SYSTEM_BASE, REQ_DOC_PROMPT


def generate_req_doc(state: AgentState) -> dict:
    client = get_client()
    context = json.dumps(state["requirements"], ensure_ascii=False)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=4096,
        system=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": REQ_DOC_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": context}],
    )
    content = response.content[0].text

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "需求说明.md"
    doc_path.write_text(content, encoding="utf-8")

    return {"req_doc_path": str(doc_path)}
