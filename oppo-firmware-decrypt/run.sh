#!/bin/sh
# OPPO / Realme / OnePlus 固件解密工具 —— Linux 启动脚本
# 默认启动 GUI；无 Tk/显示环境时提示改用 CLI。
# 用法：
#   ./run.sh                 GUI
#   ./run.sh --cli decrypt --input <固件> [--outdir <目录>] [--out-type img|zip]
set -u
cd "$(dirname "$0")"

if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[错误] 未检测到 Python 3.10+，请先安装 python3。" >&2
    exit 1
fi

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    echo "[错误] 当前 Python 版本低于 3.10，本工具需要 Python 3.10+。" >&2
    "$PY" --version >&2 || true
    exit 1
fi

if [ "${1:-}" = "--cli" ]; then
    shift
    exec "$PY" decrypt_cli.py "$@"
fi

if ! "$PY" -c 'import tkinter; tkinter.Tk().destroy()' >/dev/null 2>&1; then
    echo "[错误] 当前 Python 缺少可用的 Tkinter/Tcl-Tk，或没有图形显示环境。" >&2
    echo "       可安装 python3-tk（Debian/Ubuntu：sudo apt install python3-tk），" >&2
    echo "       或改用命令行：" >&2
    echo "       ./run.sh --cli decrypt --input <固件> [--outdir <目录>] [--out-type img|zip]" >&2
    exit 1
fi

exec "$PY" main.py
