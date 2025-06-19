import threading
import time
import asyncio
from clicker.click_logic import run_click_once
import server

# 启动 HTTP Server 保活
threading.Thread(target=server.run_server, daemon=True).start()

async def loop_click():
    while True:
        await run_click_once()
        time.sleep(6)

if __name__ == "__main__":
    asyncio.run(loop_click())
