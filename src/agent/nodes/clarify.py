# src/agent/nodes/clarify.py
import json
import re
from pathlib import Path
from agent.state import AgentState
from agent.config import get_llm_client
from agent.prompts import SYSTEM_BASE, CLARIFY_PROMPT
from agent.logger import log_execution
from rich.console import Console
from rich.prompt import Prompt

console = Console()


def render_choices(question: str, options: list[str]) -> str:
    """将问题和选项渲染为终端显示字符串。不带选项时返回空字符串。"""
    if not options or len(options) == 0:
        return ""
    letters = []
    for i in range(len(options)):
        letters.append(chr(65 + i))  # 65 = 'A'
    lines = [f"  {question}"]
    for letter, opt in zip(letters, options):
        lines.append(f"    {letter}. {opt}")
    lines.append("    T. Type something（自己输入）")
    return "\n".join(lines)


def clarify(state: AgentState) -> dict:
    client = get_llm_client()
    open_qs = state["requirements"].get("open_questions", [])
    context = json.dumps({"open_questions": open_qs, "requirements": state["requirements"]}, ensure_ascii=False)

    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": CLARIFY_PROMPT, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=context,
        max_tokens=512,
        node_name="clarify",
    )
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())
    try:
        questions = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", stripped, re.DOTALL)
        try:
            questions = json.loads(match.group()) if match else [raw]
        except json.JSONDecodeError:
            questions = [raw]

    # 规范化为统一格式：[(question_text, options_list_or_none), ...]
    parsed_questions: list[tuple[str, list[str] | None]] = []
    for item in questions:
        if isinstance(item, dict):
            q = item.get("question", "")
            opts = item.get("options", [])
            if not isinstance(opts, list):
                opts = []
            parsed_questions.append((q, opts))
        elif isinstance(item, str):
            parsed_questions.append((item, None))

    auto_mode = state.get("auto_mode", False)
    answers: list[str] = []

    if auto_mode:
        from agent.prompts import AUTO_ANSWER_PROMPT

        answer_context = json.dumps({
            "requirements": state["requirements"],
            "questions": questions,
        }, ensure_ascii=False)

        raw_answer = client.create_message(
            system_prompts=[
                {"type": "text", "text": SYSTEM_BASE, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": AUTO_ANSWER_PROMPT, "cache_control": {"type": "ephemeral"}},
            ],
            user_content=answer_context,
            max_tokens=512,
            node_name="clarify_auto_answer",
        )
        answer_stripped = re.sub(r"^```(?:json)?\s*", "", raw_answer.strip(), flags=re.IGNORECASE)
        answer_stripped = re.sub(r"\s*```$", "", answer_stripped.strip())
        try:
            answers = json.loads(answer_stripped)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", answer_stripped, re.DOTALL)
            try:
                answers = json.loads(match.group()) if match else [raw_answer]
            except json.JSONDecodeError:
                answers = [raw_answer]
    else:
        console.print(f"\n[bold yellow]澄清轮次 {state['clarification_round'] + 1}[/bold yellow]")
        for q_text, opts in parsed_questions:
            if opts and len(opts) > 0:
                # 有选项 → 选择题
                rendered = render_choices(q_text, opts)
                console.print(rendered)
                letters = [chr(65 + i) for i in range(len(opts))] + ["T"]
                answer_letter = Prompt.ask(
                    "  请选择",
                    choices=letters,
                    default="A",
                    case_sensitive=False,
                )
                if answer_letter.upper() == "T":
                    answer = Prompt.ask("  请输入你的答案")
                else:
                    idx = ord(answer_letter.upper()) - 65  # 'A'=0, 'B'=1, ...
                    answer = opts[idx]
            else:
                # 无选项 → 自由输入（老行为）
                answer = Prompt.ask(f"  [cyan]{q_text}[/cyan]")
            answers.append(answer)

    output_dir: Path = state["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    clarify_path = output_dir / "澄清记录.md"
    with open(clarify_path, "a", encoding="utf-8") as f:
        round_num = state["clarification_round"] + 1
        mode_tag = " (auto)" if auto_mode else ""
        f.write(f"\n## 澄清轮次 {round_num}{mode_tag}\n\n")
        q_texts = [q_text for q_text, _ in parsed_questions] if parsed_questions else questions
        for q, a in zip(q_texts, answers):
            f.write(f"**Q：** {q}\n\n**A：** {a}\n\n")

    log_execution(
        "clarify",
        input_summary=f"round={state['clarification_round'] + 1}, open_qs={len(open_qs)}",
        decision=f"generated {len(questions)} questions{' (auto-answered)' if auto_mode else ''}",
        output_summary=f"answers={len(answers)}, next_round={state['clarification_round'] + 2}",
    )

    clarify_questions_out = [q_text for q_text, _ in parsed_questions] if parsed_questions else questions
    return {
        "clarification_round": state["clarification_round"] + 1,
        "clarify_questions": clarify_questions_out,
        "user_answers": answers,
    }
