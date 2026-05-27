# src/agent/nodes/gen_req_doc.py
import json
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, REQ_DOC_PROMPT
from agent.logger import log_execution


def generate_req_doc(state: AgentState) -> dict:
    client = get_llm_client()
    context = json.dumps(state["requirements"], ensure_ascii=False)

    content = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": REQ_DOC_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=context,
        max_tokens=4096,
        node_name="gen_req_doc",
    )

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "需求说明.md"
    doc_path.write_text(content, encoding="utf-8")

    log_execution(
        "gen_req_doc",
        input_summary=f"functional_reqs={len(state['requirements'].get('functional', []))}",
        decision="generated requirements document",
        output_summary=f"doc={doc_path}",
    )

    return {"req_doc_path": str(doc_path)}
