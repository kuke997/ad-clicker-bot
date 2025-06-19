#!/bin/bash

# 确保脚本在任何错误时停止执行
set -e

echo "===== 开始构建 ====="

# 1. 安装 Python 依赖
echo "安装 Python 依赖..."
pip install -r requirements.txt

# 2. 安装 Playwright 和 Chromium（绕过 root 要求）
echo "安装 Playwright 和 Chromium（绕过 root 要求）..."

# 设置环境变量绕过 root 检查
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
pip install playwright

# 手动安装 Chromium（不要求 root）
PLAYWRIGHT_BROWSERS_PATH=./ms-playwright npx playwright install chromium --with-deps

echo "===== 构建完成 ====="
