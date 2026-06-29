#!/bin/bash
set -e
cd "$(dirname "$0")"

force_init=0
if [ "${1:-}" = "--init" ] || [ "${1:-}" = "--reconfig" ]; then
    force_init=1
    shift
fi

if [ $# -gt 0 ]; then
    echo "start.sh 只负责初始化。运行注册服务请使用: bash run.sh $*"
    exit 2
fi

echo "=== gitlab-register 初始化 ==="

echo "[1/4] 检查 Python 环境..."
if [ ! -d .venv ]; then
    echo "[*] 首次运行，开始安装依赖和浏览器。"
    bash setup.sh
else
    echo "[*] Python 环境已存在。"
fi

echo "[2/4] 检查浏览器..."
if ! .venv/bin/python -m cloakbrowser info >/dev/null 2>&1; then
    install_log="${TMPDIR:-/tmp}/gitlab-register-browser.log"
    echo "[*] 开始下载 CloakBrowser Chromium，可能需要几分钟。"
    if ! .venv/bin/python -m cloakbrowser install >"$install_log" 2>&1; then
        echo "[!] CloakBrowser Chromium 安装失败，详细日志: $install_log"
        exit 1
    fi
else
    echo "[*] CloakBrowser Chromium 已就绪。"
fi

echo "[3/4] 初始化配置..."
if [ ! -f .env ] || [ "$force_init" = "1" ]; then
    if [ "$force_init" = "1" ]; then
        .venv/bin/python init_env.py --force
    else
        .venv/bin/python init_env.py
    fi
else
    echo "[*] 已存在 .env，保留当前配置。需要重置请执行: bash start.sh --init"
fi

echo ""
echo "[4/4] 初始化完成。"
echo "下一步运行: bash run.sh"
