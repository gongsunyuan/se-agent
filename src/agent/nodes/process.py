# src/agent/nodes/process.py
import json
import re
from agent.state import AgentState
from agent.config import get_client, MODEL_ID
from agent.prompts import SYSTEM_BASE, PROCESS_PROMPT


def process_requirement(state: AgentState) -> dict:
    client = get_client()

    user_content = state["raw_input"]
    if state["user_answers"]:
        answers_text = "\n".join(
            f"Q: {q}\nA: {a}"
            for q, a in zip(state["clarify_questions"], state["user_answers"])
        )
        user_content = f"{user_content}\n\n澄清信息：\n{answers_text}"

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=2048,
        system=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": PROCESS_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text
    try:
        reqs = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        reqs = json.loads(match.group()) if match else {}

    return {"requirements": reqs, "messages": state["messages"] + [{"role": "assistant", "content": raw}]}
