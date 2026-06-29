#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "首次运行请先初始化: bash start.sh"
    exit 1
fi
if [ ! -f .env ]; then
    echo "缺少 .env，请先初始化: bash start.sh --init"
    exit 1
fi
exec .venv/bin/python register_gitlab.py "$@"
