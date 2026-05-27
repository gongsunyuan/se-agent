# src/agent/nodes/judge.py
import json
import re
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, JUDGE_PROMPT


def judge(state: AgentState) -> dict:
    reqs = state["requirements"]
    # Rule-based fast path: 有 functioal 且无 open_questions 直接放行
    if reqs.get("functional") and not reqs.get("open_questions"):
        return {"is_clear": True}

    client = get_llm_client()
    reqs_text = json.dumps(state["requirements"], ensure_ascii=False)

    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": JUDGE_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=reqs_text,
        max_tokens=256,
        node_name="judge",
    )
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        try:
            result = json.loads(match.group()) if match else {"is_clear": False}
        except json.JSONDecodeError:
            result = {"is_clear": False}

    return {"is_clear": result.get("is_clear", False)}
