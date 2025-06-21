# 使用官方 Python 基础镜像
FROM python:3.10-slim-bullseye

# 安装必要的系统依赖
RUN apt-get update && \
    apt-get install -y \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    libgtk-3-0 \
    fonts-noto-color-emoji \
    # 添加缺失的依赖
    libharfbuzz0b \
    libpango-1.0-0 \
    libcairo2 \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/*

# 安装最新版 Node.js
RUN wget -qO- https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# 设置工作目录
WORKDIR /app

# 先复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 和 Chromium - 修复路径问题
RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright npx playwright install chromium --with-deps

# 创建符号链接解决路径问题
RUN cd /ms-playwright && \
    ln -s chromium-* chromium && \
    cd chromium && \
    if [ -d "chrome-linux" ]; then ln -s chrome-linux chrome; fi

# 复制其余项目文件
COPY . .

# 设置环境变量
ENV DISPLAY=:99
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 暴露端口
EXPOSE 10000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
