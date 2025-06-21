#!/bin/bash

# 启动虚拟显示
Xvfb :99 -screen 0 1280x720x16 -ac &
export DISPLAY=:99

# 启动应用
uvicorn app:app --host 0.0.0.0 --port 10000
