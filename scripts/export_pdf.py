#!/usr/bin/env python
"""PDF 导出工具 — 使用 pandoc + mermaid-filter + xelatex"""
import subprocess
import sys
import os
import shutil
from pathlib import Path


def _find_pandoc() -> str | None:
    """查找 pandoc 可执行文件，包括 winget 安装路径"""
    path = shutil.which("pandoc")
    if path:
        return path
    candidates = [
        Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe",
        Path("C:/Program Files/Pandoc/pandoc.exe"),
        Path.home() / "scoop" / "apps" / "pandoc" / "current" / "pandoc.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


_PANDOC = _find_pandoc()

# 中文字体优先级列表（xelatex 用系统字体名）
_CJK_FONT_CANDIDATES = [
    "SimSun",           # 宋体 (Windows 默认)
    "Songti SC",        # 宋体 (macOS)
    "Noto Serif CJK SC",
    "WenQuanYi Micro Hei",
    "FandolSong",
]


def _detect_cjk_font() -> str:
    """检测可用中文字体，返回第一个可用的"""
    try:
        result = subprocess.run(
            [_PANDOC or "pandoc", "--version"],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass
    # 简单回退：xelatex 找不到字体会报错，用户可手动指定
    for font in _CJK_FONT_CANDIDATES:
        try:
            test = subprocess.run(
                ["xelatex", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if test.returncode == 0:
                # xelatex 可用，尝试最安全的字体
                return font
        except FileNotFoundError:
            break
    return _CJK_FONT_CANDIDATES[0]


def check_pandoc() -> bool:
    return _PANDOC is not None


def _build_env() -> dict:
    """构建包含 pandoc 和 mermaid-filter 的子进程环境"""
    env = dict(os.environ)
    paths = list(env.get("PATH", "").split(";"))

    # pandoc 所在目录加入 PATH
    if _PANDOC:
        pandoc_dir = str(Path(_PANDOC).parent)
        if pandoc_dir not in paths:
            paths.insert(0, pandoc_dir)

    # npm 全局 bin 加入 PATH（mermaid-filter.cmd 所在）
    npm_bin = str(Path.home() / "AppData" / "Roaming" / "npm")
    if npm_bin not in paths:
        paths.insert(0, npm_bin)

    env["PATH"] = ";".join(paths)

    # puppeteer 使用系统 Chrome
    chrome_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    for cp in chrome_paths:
        if Path(cp).exists():
            env["PUPPETEER_EXECUTABLE_PATH"] = cp
            break

    return env


def export_docs(output_dir: Path) -> list[Path]:
    """将 output_dir 中的所有 .md 文件转换为 .pdf"""
    if not check_pandoc():
        print("错误: 未安装 pandoc。")
        print("  winget install JohnMacFarlane.Pandoc")
        print("  或从 https://pandoc.org/installing.html 下载安装")
        sys.exit(1)

    if not output_dir.exists():
        print(f"错误: 目录不存在: {output_dir}")
        sys.exit(1)

    docs = ["澄清记录", "需求说明", "总体设计", "详细设计"]
    cjk_font = _detect_cjk_font()
    env = _build_env()
    generated = []

    for doc_name in docs:
        md_path = output_dir / f"{doc_name}.md"
        pdf_path = output_dir / f"{doc_name}.pdf"

        if not md_path.exists():
            print(f"  跳过 (文件不存在): {md_path.name}")
            continue

        print(f"  正在转换: {md_path.name} -> {pdf_path.name} ...")
        result = subprocess.run([
            _PANDOC,
            str(md_path),
            "-o", str(pdf_path),
            "--filter", str(Path.home() / "AppData" / "Roaming" / "npm" / "mermaid-filter.cmd"),
            "--pdf-engine=xelatex",
            "-V", f"CJKmainfont={cjk_font}",
            "-V", "geometry:margin=2.5cm",
            "-V", "fontsize=12pt",
            "--from", "markdown+smart",
            "--standalone",
        ], capture_output=True, text=True, env=env)

        if result.returncode != 0:
            print(f"    错误: {result.stderr[:200]}")
        else:
            print(f"    完成: {pdf_path}")
            generated.append(pdf_path)

    return generated


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/export_pdf.py <outputs/<session-id>>")
        print("示例: python scripts/export_pdf.py outputs/abc12345")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    print(f"输出目录: {out_dir}\n")
    files = export_docs(out_dir)
    print(f"\n全部完成！共生成 {len(files)} 个 PDF 文件。")
