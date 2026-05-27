"""Tests for logger module."""
import json
import threading
from pathlib import Path
from agent.logger import init_logs, log_trace, log_execution


def test_init_logs_creates_files(tmp_path):
    d = tmp_path / "outputs"
    init_logs(d)
    assert (d / "trace.log").exists()
    assert (d / "execution.log").exists()
    assert (d / "trace.log").read_text() == ""


def test_log_trace_writes_json_line(tmp_path):
    d = tmp_path / "outputs"
    init_logs(d)
    log_trace({"node": "test", "response": "hello"})
    lines = (d / "trace.log").read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["node"] == "test"
    assert entry["response"] == "hello"
    assert "timestamp" in entry


def test_log_execution_writes_markdown(tmp_path):
    d = tmp_path / "outputs"
    init_logs(d)
    log_execution("clarify", "q=3", "生成 3 个问题", "answers=3")
    content = (d / "execution.log").read_text(encoding="utf-8")
    assert "## [" in content
    assert "clarify" in content
    assert "q=3" in content


def test_logs_thread_safe(tmp_path):
    d = tmp_path / "outputs"
    init_logs(d)

    def write_logs(n):
        for i in range(10):
            log_trace({"node": f"node-{n}", "seq": i})

    threads = [threading.Thread(target=write_logs, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = (d / "trace.log").read_text().strip().split("\n")
    assert len(lines) == 40
