import requests
import time
import os

# Render健康检查URL（部署后设置）
RENDER_HEALTH_CHECK_URL = os.getenv("RENDER_HEALTH_CHECK_URL", "")

def keep_alive():
    while True:
        try:
            if RENDER_HEALTH_CHECK_URL:
                response = requests.get(RENDER_HEALTH_CHECK_URL)
                print(f"健康检查: {response.status_code}")
            
            # 每分钟触发一次
            time.sleep(60)
        except Exception as e:
            print(f"保活错误: {str(e)}")
            time.sleep(300)

if __name__ == "__main__":
    print("保活脚本启动...")
    keep_alive()
