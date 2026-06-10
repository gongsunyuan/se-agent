# src/agent/cli.py
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
import typer
from rich.console import Console
from rich.panel import Panel
from langgraph.types import Command

from agent.graph import build_graph
from agent.state import AgentState

load_dotenv()
app = typer.Typer(help="SE Agent — 需求分析 + 软件设计")
console = Console()


@app.command()
def run(
    input_text: str = typer.Argument(..., help="需求描述文字"),
    output_dir: Path = typer.Option(Path("outputs") / str(uuid.uuid4())[:8], help="输出目录"),
    max_rounds: int = typer.Option(5, help="最大澄清轮次"),
    thread_id: str = typer.Option(str(uuid.uuid4()), help="会话 ID（用于断点续跑）"),
    auto_mode: bool = typer.Option(False, "--auto", "--auto-mode", help="全自动模式，无需用户交互"),
):
    """运行需求分析 + 软件设计 Agent"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]错误: 请设置 ANTHROPIC_API_KEY 环境变量[/red]")
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    from agent.logger import init_logs
    init_logs(output_dir)
    console.print(Panel(f"[bold green]SE Agent 启动[/bold green]\n输出目录: {output_dir}\n会话 ID: {thread_id}"))

    if auto_mode:
        console.print("[dim]全自动模式：无需用户交互，所有决策由 LLM 自动完成[/dim]")

    graph = build_graph(use_memory=True)
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "raw_input": input_text,
        "auto_mode": auto_mode,
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
        "uml_diagram_files": [],
    }

    for _ in graph.stream(initial_state, config=config, stream_mode="values"):
        pass

    # 处理 interrupt 的 resume 逻辑
    while not auto_mode:
        state = graph.get_state(config)
        if not state.next:
            break

        interrupt_data = state.tasks[0].interrupts[0].value if state.tasks else None
        if not interrupt_data:
            break

        interrupt_type = interrupt_data.get("type")
        if interrupt_type == "confirm_req_doc":
            doc_path = interrupt_data.get("path")
            if doc_path:
                console.print(f"\n[bold]需求文档已生成：[/bold] {doc_path}")
                console.print(Path(doc_path).read_text(encoding="utf-8")[:500] + "...")
            confirm = typer.confirm("\n确认需求文档并继续？")
            comment = None if confirm else typer.prompt("请输入修改意见")
            for _ in graph.stream(
                Command(resume={"confirmed": confirm, "comment": comment}),
                config=config, stream_mode="values",
            ):
                pass

        elif interrupt_type == "confirm_high_level":
            doc_path = interrupt_data.get("path")
            if doc_path:
                console.print(f"\n[bold]总体设计已生成：[/bold] {doc_path}")
                console.print(Path(doc_path).read_text(encoding="utf-8")[:500] + "...")
            confirm = typer.confirm("\n确认总体设计并继续？")
            comment = None if confirm else typer.prompt("请输入修改意见")
            for _ in graph.stream(
                Command(resume={"confirmed": confirm, "comment": comment}),
                config=config, stream_mode="values",
            ):
                pass
        else:
            break

    # 渲染 PlantUML 图表为 PNG
    try:
        from scripts.render_puml import render_diagrams
        render_diagrams(output_dir)
    except Exception as e:
        console.print(f"[yellow]图表渲染跳过: {e}[/yellow]")

    console.print(Panel("[bold green]Agent 执行完成！[/bold green]"))
    console.print(f"输出文件位于: {output_dir}")


if __name__ == "__main__":
    app()
