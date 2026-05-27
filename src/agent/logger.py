"""统一日志模块：trace.log（LLM 调用全记录）+ execution.log（节点执行摘要）。"""
import json
import threading
from datetime import datetime
from pathlib import Path

_log_dir: Path | None = None
_lock = threading.Lock()


def init_logs(output_dir: Path) -> None:
    """初始化日志文件。CLI 在创建 output_dir 后调用一次。"""
    global _log_dir
    _log_dir = output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "trace.log").write_text("", encoding="utf-8")
    (output_dir / "execution.log").write_text("", encoding="utf-8")


def log_trace(entry: dict) -> None:
    """追加一条 trace 记录到 trace.log。"""
    if _log_dir is None:
        return
    entry = {**entry, "timestamp": entry.get("timestamp", datetime.now().isoformat())}
    with _lock:
        with open(_log_dir / "trace.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_execution(node: str, input_summary: str, decision: str, output_summary: str) -> None:
    """追加一条节点执行摘要到 execution.log。"""
    if _log_dir is None:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"## [{ts}] {node}\n\n"
        f"**输入**: {input_summary}\n"
        f"**决策**: {decision}\n"
        f"**输出**: {output_summary}\n\n"
    )
    with _lock:
        with open(_log_dir / "execution.log", "a", encoding="utf-8") as f:
            f.write(entry)
