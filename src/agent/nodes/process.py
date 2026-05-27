# src/agent/nodes/process.py
import json
import re
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, PROCESS_PROMPT
from agent.logger import log_execution


def process_requirement(state: AgentState) -> dict:
    client = get_llm_client()

    user_content = state["raw_input"]
    if state["user_answers"]:
        answers_text = "\n".join(
            f"Q: {q}\nA: {a}"
            for q, a in zip(state["clarify_questions"], state["user_answers"])
        )
        user_content = f"{user_content}\n\n澄清信息：\n{answers_text}"

    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": PROCESS_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=user_content,
        max_tokens=2048,
        node_name="process",
    )
    # 剥离 markdown 代码块包装（```json ... ``` 或 ``` ... ```）
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())
    try:
        reqs = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        try:
            reqs = json.loads(match.group()) if match else {}
        except json.JSONDecodeError:
            reqs = {}

    log_execution(
        "process",
        input_summary=f"input={state['raw_input'][:60]}, prev_answers={len(state.get('user_answers', []))}",
        decision=f"extracted {len(reqs.get('functional', []))} functional, {len(reqs.get('open_questions', []))} open_questions",
        output_summary=f"req keys={list(reqs.keys())}",
    )

    return {"requirements": reqs, "messages": state["messages"] + [{"role": "assistant", "content": raw}]}
