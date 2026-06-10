# scripts/render_puml.py
"""PlantUML → PNG 渲染（CLI 入口）。

核心逻辑在 src/agent/render_puml.py，本文件仅为独立命令行调用提供入口。

Usage:
    python scripts/render_puml.py outputs/<session-id>
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent.render_puml import render_diagrams

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <output_dir>")
        sys.exit(1)

    files = render_diagrams(Path(sys.argv[1]))
    for f in files:
        print(f"  {f}")
