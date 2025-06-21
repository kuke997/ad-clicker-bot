# 使用官方Python镜像
FROM python:3.10-slim-bullseye

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y \
    wget gnupg \
    libnss3 libx11-xcb1 libxcomposite1 libxcursor1 \
    libxdamage1 libxi6 libxtst6 libxrandr2 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libpangocairo-1.0-0 \
    libxss1 libgtk-3-0 fonts-noto-color-emoji

# 安装Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 10000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
