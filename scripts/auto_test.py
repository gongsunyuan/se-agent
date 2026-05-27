#!/usr/bin/env python
"""Auto-test script for se-agent — LLM-in-the-loop instead of human-in-the-loop.

Usage:
    python scripts/auto_test.py "构建一个在线图书馆系统" --mode simple
    python scripts/auto_test.py "构建一个在线图书馆系统" --mode review
"""

import argparse
import json
import os
import re
import uuid
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on sys.path so `agent` imports work
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from langgraph.types import Command

from agent.graph import build_graph
from agent.state import AgentState
from agent.config import get_llm_client

load_dotenv()
console = Console()

# ---------------------------------------------------------------------------
# Prompts for the reviewer LLM (review mode)
# ---------------------------------------------------------------------------

REVIEWER_SYSTEM = """你是一名资深软件工程师，负责审查软件设计文档的质量。

请阅读以下文档，判断是否达到可交付标准。仅输出 JSON，不要其他内容：
{"confirmed": true/false, "comment": "审查意见"}

审查标准：
- 内容完整、结构清晰，覆盖了应有的章节
- 无明显的逻辑矛盾或遗漏
- Mermaid 图表与文字描述一致
- 技术方案合理可行

如果文档基本合格，confirmed 设为 true，comment 写简短通过评语。
如果文档有较大问题（如章节缺失、明显矛盾），confirmed 设为 false，comment 写明具体问题和修改建议。"""

CLARIFY_ANSWER_SYSTEM = """你是一名资深软件工程师，正在帮助澄清一个软件项目的需求。

你会被问到一个关于需求的问题，请根据你的专业知识给出合理、具体的回答。
仅输出回答文本，不要加引号或额外说明。"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict | list:
    """Best-effort JSON extraction from LLM output."""
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Try to find JSON object/array inside the text
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    # Last resort: wrap as single-item list
    return [stripped]


def review_document(doc_path: str) -> dict:
    """Ask the LLM to review a generated document. Returns {confirmed, comment}."""
    client = get_llm_client()
    doc_content = Path(doc_path).read_text(encoding="utf-8")

    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": REVIEWER_SYSTEM, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=f"请审查以下文档：\n\n{doc_content[:8000]}",
        max_tokens=512,
    )
    result = _extract_json(raw)
    if isinstance(result, list):
        return {"confirmed": True, "comment": str(result)}
    return {"confirmed": result.get("confirmed", True), "comment": result.get("comment")}


def answer_question(question: str) -> str:
    """Ask the LLM to answer a single clarification question."""
    client = get_llm_client()
    raw = client.create_message(
        system_prompts=[
            {"type": "text", "text": CLARIFY_ANSWER_SYSTEM, "cache_control": {"type": "ephemeral"}},
        ],
        user_content=question,
        max_tokens=256,
    )
    return raw.strip().strip('"')


def _strip_rich_markup(text: str) -> str:
    """Strip basic rich markup tags from a string."""
    return re.sub(r"\[/?\w+\]", "", text).strip()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_auto_test(
    input_text: str,
    mode: str,
    output_dir: Path,
    max_rounds: int,
    thread_id: str,
) -> None:
    """Run the se-agent graph with automated human-in-the-loop."""

    output_dir.mkdir(parents=True, exist_ok=True)

    # -- Build graph ---------------------------------------------------------
    graph = build_graph(use_memory=True)
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "raw_input": input_text,
        "requirements": {},
        "clarification_round": 0,
        "max_clarification_rounds": max_rounds,
        "is_clear": False,
        "clarify_questions": [],
        "user_answers": [],
        "req_doc_confirmed": False,
        "high_level_confirmed": False,
        "revision_comment": None,
        "output_dir": output_dir,
        "req_doc_path": None,
        "high_level_doc_path": None,
        "detail_doc_path": None,
        "messages": [],
        "errors": [],
    }

    console.print(
        Panel(
            f"[bold green]Auto-Test 启动[/bold green]\n"
            f"模式: [bold]{mode}[/bold]\n"
            f"输入: {input_text}\n"
            f"输出: {output_dir}\n"
            f"会话: {thread_id}"
        )
    )

    # -- Monkey-patch clarify node's Prompt.ask ------------------------------
    from agent.nodes import clarify as clarify_module

    if mode == "simple":
        def _simple_ask(prompt: str = "", **kwargs) -> str:
            clean = _strip_rich_markup(prompt)
            console.print(f"  [dim]Auto-answer (simple): {clean[:80]}...[/dim]")
            return "暂不清楚，请按常规做法处理"

        patcher = patch.object(clarify_module.Prompt, "ask", side_effect=_simple_ask)
    else:
        def _review_ask(prompt: str = "", **kwargs) -> str:
            clean = _strip_rich_markup(prompt)
            console.print(f"  [dim]LLM answering: {clean[:80]}...[/dim]")
            return answer_question(clean)

        patcher = patch.object(clarify_module.Prompt, "ask", side_effect=_review_ask)

    patcher.start()

    try:
        # -- First stream pass through the graph -----------------------------
        for _ in graph.stream(initial_state, config=config, stream_mode="values"):
            pass

        # -- Interrupt handling loop ----------------------------------------
        while True:
            state = graph.get_state(config)
            if not state.next:
                break

            interrupt_data = state.tasks[0].interrupts[0].value if state.tasks else None
            if not interrupt_data:
                break

            interrupt_type = interrupt_data.get("type")

            if interrupt_type == "confirm_req_doc":
                doc_path = interrupt_data.get("path")
                console.print(f"\n[bold yellow]━ Checkpoint A: 需求文档审查 ━[/bold yellow]")
                console.print(f"  文档: {doc_path}")

                if mode == "simple":
                    confirmed, comment = True, None
                    console.print("  [dim]Simple 模式 → 自动确认[/dim]")
                else:
                    console.print("  [dim]正在用 LLM 审查文档...[/dim]")
                    result = review_document(doc_path)
                    confirmed = result["confirmed"]
                    comment = result["comment"]
                    status = "[green]通过[/green]" if confirmed else "[red]需修改[/red]"
                    console.print(f"  审查结果: {status}")
                    console.print(f"  意见: {comment}")

                for _ in graph.stream(
                    Command(resume={"confirmed": confirmed, "comment": comment}),
                    config=config,
                    stream_mode="values",
                ):
                    pass

            elif interrupt_type == "confirm_high_level":
                doc_path = interrupt_data.get("path")
                console.print(f"\n[bold yellow]━ Checkpoint B: 总体设计审查 ━[/bold yellow]")
                console.print(f"  文档: {doc_path}")

                if mode == "simple":
                    confirmed, comment = True, None
                    console.print("  [dim]Simple 模式 → 自动确认[/dim]")
                else:
                    console.print("  [dim]正在用 LLM 审查文档...[/dim]")
                    result = review_document(doc_path)
                    confirmed = result["confirmed"]
                    comment = result["comment"]
                    status = "[green]通过[/green]" if confirmed else "[red]需修改[/red]"
                    console.print(f"  审查结果: {status}")
                    console.print(f"  意见: {comment}")

                for _ in graph.stream(
                    Command(resume={"confirmed": confirmed, "comment": comment}),
                    config=config,
                    stream_mode="values",
                ):
                    pass
            else:
                console.print(f"[dim]未知 interrupt 类型: {interrupt_type}，退出循环[/dim]")
                break

        # -- Done ------------------------------------------------------------
        console.print(Panel("[bold green]Auto-Test 完成！[/bold green]"))
        console.print(f"输出目录: {output_dir}")
        for f in sorted(output_dir.glob("*.md")):
            console.print(f"  - {f.name}")

    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="se-agent 自动测试 — 用 LLM 替代人工交互",
    )
    parser.add_argument(
        "input",
        help="需求描述文字",
    )
    parser.add_argument(
        "--mode", choices=["simple", "review"], default="simple",
        help="simple=所有交互自动确认, review=LLM 审查文档并决策 (default: simple)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="输出目录 (default: outputs/<uuid8>)",
    )
    parser.add_argument(
        "--max-rounds", type=int, default=5,
        help="最大澄清轮次 (default: 5)",
    )
    parser.add_argument(
        "--thread-id", type=str, default=None,
        help="会话 ID，用于断点续跑 (default: 自动生成)",
    )
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]错误: 请设置 ANTHROPIC_API_KEY 环境变量[/red]")
        sys.exit(1)

    output_dir = args.output_dir or Path(__file__).resolve().parent.parent / "outputs" / str(uuid.uuid4())[:8]
    thread_id = args.thread_id or str(uuid.uuid4())

    run_auto_test(
        input_text=args.input,
        mode=args.mode,
        output_dir=output_dir,
        max_rounds=args.max_rounds,
        thread_id=thread_id,
    )


if __name__ == "__main__":
    main()
