"""直接运行 Agent，绕过 typer CLI 的 shell 编码问题"""
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from agent.graph import build_graph
from agent.state import AgentState
from langgraph.types import Command


def run_agent(input_text: str, output_dir: str, max_rounds: int = 3):
    thread_id = str(uuid.uuid4())
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"SE Agent 启动")
    print(f"输入: {input_text}")
    print(f"输出目录: {output_path}")
    print(f"会话 ID: {thread_id}")
    print("=" * 60)

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
        "output_dir": output_path,
        "req_doc_path": None,
        "high_level_doc_path": None,
        "detail_doc_path": None,
        "messages": [],
        "errors": [],
    }

    # 第一阶段：stream 直到遇到 interrupt
    print("\n[Phase 1] 处理需求 -> 判断 -> ...")
    for event in graph.stream(initial_state, config=config, stream_mode="values"):
        node_name = event.get("current_node", "")
        print(f"  -> {node_name}")

    # 处理 interrupt resume
    while True:
        state = graph.get_state(config)
        if not state.next:
            break

        tasks = state.tasks if hasattr(state, 'tasks') else []
        if not tasks:
            break

        interrupts = tasks[0].interrupts if hasattr(tasks[0], 'interrupts') else []
        if not interrupts:
            break

        interrupt_data = interrupts[0].value
        interrupt_type = interrupt_data.get("type")

        if interrupt_type == "confirm_req_doc":
            doc_path = interrupt_data.get("path")
            print(f"\n[Checkpoint A] 需求文档: {doc_path}")
            if doc_path and Path(doc_path).exists():
                content = Path(doc_path).read_text(encoding="utf-8")
                print(content[:800])
                print("...(省略)...")
            # 自动确认（测试模式）
            print("\n>>> 自动确认需求文档（测试模式）")
            for _ in graph.stream(
                Command(resume={"confirmed": True, "comment": None}),
                config=config, stream_mode="values",
            ):
                pass

        elif interrupt_type == "confirm_high_level":
            doc_path = interrupt_data.get("path")
            print(f"\n[Checkpoint B] 总体设计: {doc_path}")
            if doc_path and Path(doc_path).exists():
                content = Path(doc_path).read_text(encoding="utf-8")
                print(content[:800])
                print("...(省略)...")
            print("\n>>> 自动确认总体设计（测试模式）")
            for _ in graph.stream(
                Command(resume={"confirmed": True, "comment": None}),
                config=config, stream_mode="values",
            ):
                pass
        else:
            break

    print("\n" + "=" * 60)
    print("Agent 执行完成！")
    print(f"输出文件位于: {output_path}")

    # 列出生成的文件
    for f in sorted(output_path.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name} ({size} bytes)")


if __name__ == "__main__":
    run_agent(
        input_text="构建一个在线图书馆系统，支持借阅、归还、搜索功能",
        output_dir="outputs/test-run",
        max_rounds=0,  # 测试模式：跳过澄清，直接生成文档
    )
