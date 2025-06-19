#!/bin/bash

# 确保脚本在任何错误时停止执行
set -e

echo "===== 开始构建 ====="

# 1. 安装 Python 依赖
echo "安装 Python 依赖..."
pip install -r requirements.txt

# 2. 安装 Playwright 和 Chromium
echo "安装 Playwright 和 Chromium..."
playwright install --with-deps chromium

echo "===== 构建完成 ====="
