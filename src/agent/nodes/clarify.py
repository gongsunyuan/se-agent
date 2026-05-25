# src/agent/nodes/clarify.py
import json
import re
from pathlib import Path
from agent.state import AgentState
from agent.config import get_client, MODEL_ID
from agent.prompts import SYSTEM_BASE, CLARIFY_PROMPT
from rich.console import Console
from rich.prompt import Prompt

console = Console()


def clarify(state: AgentState) -> dict:
    client = get_client()
    open_qs = state["requirements"].get("open_questions", [])
    context = json.dumps({"open_questions": open_qs, "requirements": state["requirements"]}, ensure_ascii=False)

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=512,
        system=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": CLARIFY_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        messages=[{"role": "user", "content": context}],
    )
    raw = response.content[0].text
    try:
        questions = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        questions = json.loads(match.group()) if match else [raw]

    answers = []
    console.print(f"\n[bold yellow]澄清轮次 {state['clarification_round'] + 1}[/bold yellow]")
    for q in questions:
        answer = Prompt.ask(f"  [cyan]{q}[/cyan]")
        answers.append(answer)

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    clarify_path = output_dir / "澄清记录.md"
    with open(clarify_path, "a", encoding="utf-8") as f:
        round_num = state["clarification_round"] + 1
        f.write(f"\n## 澄清轮次 {round_num}\n\n")
        for q, a in zip(questions, answers):
            f.write(f"**Q：** {q}\n\n**A：** {a}\n\n")

    return {
        "clarification_round": state["clarification_round"] + 1,
        "clarify_questions": questions,
        "user_answers": answers,
    }
