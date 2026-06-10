# src/agent/render_puml.py
"""将 PlantUML .puml 文件渲染为 PNG 图片。

使用 plantuml.jar（Java）离线渲染，输出到 output_dir/png/ 目录。
"""

import subprocess
import shutil
from pathlib import Path

# plantuml.jar 相对于项目根目录的位置
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PLANTUML_JAR = _PROJECT_ROOT / "scripts" / "plantuml.jar"

# 不安装 Graphviz 时非序列图渲染质量下降
_HAS_GRAPHVIZ: bool | None = None


def _check_deps() -> dict[str, bool]:
    global _HAS_GRAPHVIZ
    if _HAS_GRAPHVIZ is None:
        _HAS_GRAPHVIZ = shutil.which("dot") is not None
    return {"java": shutil.which("java") is not None, "graphviz": _HAS_GRAPHVIZ}


def render_diagrams(output_dir: Path, verbose: bool = True) -> list[Path]:
    """渲染 output_dir/diagrams/ 下所有 .puml → output_dir/png/

    Returns:
        生成的 PNG 文件路径列表
    """
    if not _PLANTUML_JAR.exists():
        if verbose:
            print(f"[render_puml] plantuml.jar 未找到: {_PLANTUML_JAR}，跳过渲染")
        return []

    deps = _check_deps()
    if not deps["java"]:
        if verbose:
            print("[render_puml] Java 未安装，跳过渲染")
        return []

    diagrams_dir = output_dir / "diagrams"
    if not diagrams_dir.exists():
        if verbose:
            print(f"[render_puml] 跳过：{diagrams_dir} 不存在")
        return []

    puml_files = sorted(diagrams_dir.glob("*.puml"))
    if not puml_files:
        if verbose:
            print(f"[render_puml] 跳过：没有 .puml 文件")
        return []

    png_dir = output_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)

    graphviz_note = "" if deps["graphviz"] else " (graphviz 缺失，非序列图可能不全)"
    print(f"[render_puml] 渲染 {len(puml_files)} 个 PlantUML 文件...{graphviz_note}")

    cmd = [
        "java", "-jar", str(_PLANTUML_JAR),
        "-tpng",
        "-output", str(png_dir.resolve()),
    ] + [str(f.resolve()) for f in puml_files]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print("[render_puml] 渲染超时（>120s），跳过")
        return []

    png_files = sorted(png_dir.glob("*.png"))
    if result.returncode != 0 and not png_files:
        print(f"[render_puml] 渲染失败 (exit={result.returncode}): {result.stderr[:200]}")
        return []

    print(f"[render_puml] 完成：{len(png_files)} 个 PNG → {png_dir}/")
    return png_files
