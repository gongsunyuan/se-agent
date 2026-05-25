#!/bin/bash
# PDF 导出脚本 — 使用 pandoc + mermaid-filter + xelatex
# 用法: bash scripts/export_pdf.sh [outputs/<session-id>]
set -euo pipefail

OUTPUT_DIR="${1:-outputs/latest}"

if ! command -v pandoc &>/dev/null; then
    echo "错误: 未安装 pandoc。请运行: conda install -n xchi-agent -c conda-forge pandoc"
    echo "或从 https://pandoc.org/installing.html 下载安装"
    exit 1
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "错误: 目录不存在: $OUTPUT_DIR"
    exit 1
fi

echo "输出目录: $OUTPUT_DIR"
echo ""

for doc in "澄清记录" "需求说明" "总体设计" "详细设计"; do
    input="$OUTPUT_DIR/${doc}.md"
    output="$OUTPUT_DIR/${doc}.pdf"

    if [ -f "$input" ]; then
        echo "正在转换: ${doc}.md -> ${doc}.pdf ..."
        pandoc "$input" \
            -o "$output" \
            --filter mermaid-filter \
            --pdf-engine=xelatex \
            -V CJKmainfont="SimSun" \
            -V geometry:margin=2.5cm \
            -V fontsize=12pt \
            --from markdown+smart \
            --standalone
        echo "  完成: $output"
    else
        echo "  跳过 (文件不存在): $input"
    fi
done

echo ""
echo "全部完成！PDF 文件位于: $OUTPUT_DIR"
