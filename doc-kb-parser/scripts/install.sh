#!/bin/bash
# doc-kb-parser 一键安装脚本
# 在本地终端（非 WorkBuddy sandbox）运行此脚本安装所有依赖
# 要求 Python >= 3.10

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SKILL_DIR/.venv"

echo "=========================================="
echo " doc-kb-parser 依赖安装"
echo "=========================================="

# 0. 查找可用的 Python >= 3.10
echo "[0/5] 检测 Python 环境..."
PYTHON_CMD=""

# 优先级: WorkBuddy managed > Homebrew > pyenv > 系统
for candidate in \
    "$HOME/.workbuddy/binaries/python/versions/3.13.12/bin/python3" \
    "$HOME/.workbuddy/binaries/python/versions/3.13/bin/python3" \
    "$HOME/.workbuddy/binaries/python/versions/3.12/bin/python3" \
    "$HOME/.workbuddy/binaries/python/versions/3.11/bin/python3" \
    "$HOME/.workbuddy/binaries/python/versions/3.10/bin/python3" \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    "$HOME/.pyenv/shims/python3" \
    python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD="$candidate"
            echo "  找到 Python $ver: $PYTHON_CMD"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "  错误: 未找到 Python >= 3.10"
    echo ""
    echo "  请先安装 Python 3.13（推荐）:"
    echo "    brew install python@3.13"
    echo ""
    echo "  或通过官网下载: https://www.python.org/downloads/"
    echo "  安装后重新运行此脚本"
    exit 1
fi

# 1. 创建专用 venv
if [ -d "$VENV_DIR" ]; then
    echo "[1/5] 删除旧的虚拟环境..."
    rm -rf "$VENV_DIR"
fi
echo "[1/5] 创建 Python 虚拟环境 ($PYTHON_CMD)..."
"$PYTHON_CMD" -m venv "$VENV_DIR"

# 2. 安装 Python 依赖
echo "[2/5] 安装 Python 依赖（markitdown, python-pptx 等）..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

# 3. 检查系统工具
echo "[3/5] 检查系统工具..."
missing=()
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg (brew install ffmpeg)")
command -v tesseract >/dev/null 2>&1 || missing+=("tesseract (brew install tesseract)")
# LibreOffice (可选)
if ! command -v soffice >/dev/null 2>&1 && [ ! -f "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    echo "  (可选) LibreOffice 未安装 — PPT 截图兜底功能需要: brew install --cask libreoffice"
fi

if [ ${#missing[@]} -gt 0 ]; then
    echo "  以下工具未安装（部分功能受限）:"
    for m in "${missing[@]}"; do
        echo "    - $m"
    done
fi

# 4. 验证 Python 依赖
echo "[4/5] 验证 Python 依赖..."
"$VENV_DIR/bin/python3" -c "
from markitdown import MarkItDown
import pptx
print('  markitdown: OK')
print('  python-pptx:', pptx.__version__)
try:
    from markitdown.converters import PptxConverter, DocxConverter, PdfConverter
    print('  converters: OK')
except Exception as e:
    print('  converters warning:', e)
" || { echo "  Python 依赖验证失败，请检查上方错误信息"; exit 1; }

# 5. 完成
echo "[5/5] 安装完成！"
echo ""
echo "=========================================="
echo " 使用方式"
echo "=========================================="
echo ""
echo "单文件解析:"
echo "  $SKILL_DIR/.venv/bin/python3 $SCRIPT_DIR/parse_document.py input.pptx -o output.md"
echo ""
echo "批量解析:"
echo "  $SKILL_DIR/.venv/bin/python3 $SCRIPT_DIR/parse_document.py ./docs/ -o ./output/ --batch"
echo ""
echo "生成总索引:"
echo "  $SKILL_DIR/.venv/bin/python3 $SCRIPT_DIR/build_index.py ./output/"
echo ""
echo "或激活虚拟环境后使用:"
echo "  source $SKILL_DIR/.venv/bin/activate"
echo "  python3 scripts/parse_document.py input.pptx -o output.md"
