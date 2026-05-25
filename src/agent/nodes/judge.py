# src/agent/nodes/judge.py
import json
import re
from agent.state import AgentState
from agent.config import get_client, MODEL_ID
from agent.prompts import SYSTEM_BASE, JUDGE_PROMPT


def judge(state: AgentState) -> dict:
    reqs = state["requirements"]
    # Rule-based fast path: 有 functioal 且无 open_questions 直接放行
    if reqs.get("functional") and not reqs.get("open_questions"):
        return {"is_clear": True}

    client = get_client()
    reqs_text = json.dumps(state["requirements"], ensure_ascii=False)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=256,
        system=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": JUDGE_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": reqs_text}],
    )
    raw = response.content[0].text
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(match.group()) if match else {"is_clear": False}

    return {"is_clear": result.get("is_clear", False)}
