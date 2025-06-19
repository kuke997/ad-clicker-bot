#!/bin/bash

# 设置 Python 版本
pyenv install 3.10.13
pyenv global 3.10.13

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 和 Chromium
playwright install --with-deps chromium
