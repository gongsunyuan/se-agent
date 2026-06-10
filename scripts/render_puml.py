# scripts/render_puml.py
"""将 PlantUML .puml 文件渲染为 PNG 图片。

使用 plantuml.jar（Java）离线渲染。
输出到 output_dir/png/ 目录，与 .puml 文件一一对应。

Usage:
    python scripts/render_puml.py outputs/<session-id>
"""

import subprocess
import sys
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLANTUML_JAR = SCRIPT_DIR / "plantuml.jar"

# 不安装 Graphviz 时非序列图渲染质量下降或跳过
_HAS_GRAPHVIZ: bool | None = None


def _check_deps() -> dict[str, bool]:
    """检查渲染依赖。返回 {java: bool, graphviz: bool}。"""
    global _HAS_GRAPHVIZ

    def _has_java():
        return shutil.which("java") is not None

    if _HAS_GRAPHVIZ is None:
        _HAS_GRAPHVIZ = shutil.which("dot") is not None

    return {"java": _has_java(), "graphviz": _HAS_GRAPHVIZ}


def render_diagrams(output_dir: Path, verbose: bool = True) -> list[Path]:
    """渲染 output_dir/diagrams/ 下所有 .puml → output_dir/png/

    Args:
        output_dir: 会话输出目录（如 outputs/<session-id>）
        verbose: 是否打印进度信息

    Returns:
        生成的 PNG 文件路径列表

    Raises:
        FileNotFoundError: plantuml.jar 或 Java 不可用
        subprocess.CalledProcessError: 渲染失败
    """
    if not PLANTUML_JAR.exists():
        raise FileNotFoundError(
            f"plantuml.jar 未找到: {PLANTUML_JAR}\n"
            "请先下载: https://github.com/plantuml/plantuml/releases"
        )

    deps = _check_deps()
    if not deps["java"]:
        raise FileNotFoundError("Java 未安装，PlantUML 渲染需要 Java Runtime")

    diagrams_dir = output_dir / "diagrams"
    if not diagrams_dir.exists() or not diagrams_dir.is_dir():
        if verbose:
            print(f"[render_puml] 跳过：{diagrams_dir} 不存在或为空")
        return []

    puml_files = sorted(diagrams_dir.glob("*.puml"))
    if not puml_files:
        if verbose:
            print(f"[render_puml] 跳过：{diagrams_dir} 中没有 .puml 文件")
        return []

    # 输出到 png/ 子目录
    png_dir = output_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        graphviz_note = "" if deps["graphviz"] else "（⚠ graphviz 缺失，非序列图可能渲染不全）"
        print(f"[render_puml] 渲染 {len(puml_files)} 个 PlantUML 文件... {graphviz_note}")

    # plantuml.jar 参数：
    #  -tpng: 输出 PNG
    #  -o <dir>: 输出目录（相对于源文件目录）
    cmd = [
        "java", "-jar", str(PLANTUML_JAR),
        "-tpng",
        "-output", str(png_dir.resolve()),
    ] + [str(f.resolve()) for f in puml_files]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError("PlantUML 渲染超时（>120s），请检查 .puml 文件是否过大")

    if result.returncode != 0:
        # plantuml 返回非 0 但部分图可能已渲染，检查 png 文件
        png_files = sorted(png_dir.glob("*.png"))
        if png_files:
            if verbose:
                print(f"[render_puml] 部分渲染成功，{len(png_files)}/{len(puml_files)} 个")
        else:
            raise RuntimeError(
                f"PlantUML 渲染全部失败 (exit={result.returncode})\n"
                f"stderr: {result.stderr[:500]}"
            )

    png_files = sorted(png_dir.glob("*.png"))
    if verbose:
        print(f"[render_puml] 完成：{len(png_files)} 个 PNG → {png_dir}/")

    return png_files


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <output_dir>")
        print(f"Example: python {sys.argv[0]} outputs/6aee4ebc")
        sys.exit(1)

    try:
        files = render_diagrams(Path(sys.argv[1]))
        for f in files:
            print(f"  {f}")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}")
        sys.exit(1)
