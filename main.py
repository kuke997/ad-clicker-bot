import asyncio
import time
from clicker.click_logic import run_click_once

if __name__ == "__main__":
    while True:
        asyncio.run(run_click_once())
        time.sleep(6)  # 每分钟10次，每次间隔6秒

