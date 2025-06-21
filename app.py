import os
import asyncio
import json
import random
import logging
from datetime import datetime
from fastapi import FastAPI
from proxy_manager import ProxyManager
from behavior_simulator import BehaviorSimulator
from playwright.async_api import async_playwright

# 配置参数
CLICKS_PER_MINUTE = 8
MIN_INTERVAL = 5
MAX_INTERVAL = 15
MAX_RETRIES = 3

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ad-clicker")

class AdClickerBot:
    def __init__(self):
        self.is_running = False
        self.proxy_manager = ProxyManager()
        self.last_success = datetime.now()

    def get_random_user_agent(self):
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        return random.choice(agents)

    async def init_browser(self, playwright, proxy=None):
        chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            f"--user-agent={self.get_random_user_agent()}"
        ]
        
        browser = await playwright.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=chrome_args,
            timeout=120000,
            proxy={"server": f"http://{proxy}"} if proxy else None
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
            java_script_enabled=True
        )
        
        return browser, context

    async def click_ads(self, playwright, target):
        browser = None
        try:
            proxy = await self.proxy_manager.get_best_proxy()
            browser, context = await self.init_browser(playwright, proxy)
            page = await context.new_page()
            
            # 导航到目标页面
            await page.goto(
                target["url"],
                timeout=60000,
                wait_until="domcontentloaded"
            )
            
            # 模拟人类行为
            simulator = BehaviorSimulator(page)
            await simulator.execute()
            
            # 执行广告点击
            elements = await page.query_selector_all(target["selector"])
            if not elements:
                raise Exception("No elements found")
                
            element = random.choice(elements)
            await element.click(delay=random.randint(50, 250))
            
            # 记录成功
            self.last_success = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"点击失败: {str(e)}")
            if proxy:
                self.proxy_manager.report_failure(proxy)
            return False
        finally:
            if browser:
                await browser.close()

    async def run(self):
        self.is_running = True
        logger.info("Starting ad clicker bot")
        
        # 加载广告目标
        with open("ad_targets.json") as f:
            targets = json.load(f)
        
        async with async_playwright() as playwright:
            while self.is_running:
                target = random.choice(targets)
                logger.info(f"Processing target: {target['name']}")
                
                for attempt in range(MAX_RETRIES):
                    if await self.click_ads(playwright, target):
                        break
                    await asyncio.sleep(2)
                
                await asyncio.sleep(random.uniform(MIN_INTERVAL, MAX_INTERVAL))

bot = AdClickerBot()
app = FastAPI()

@app.on_event("startup")
async def startup():
    asyncio.create_task(bot.run())

@app.get("/health")
async def health():
    return {
        "status": "running",
        "last_success": bot.last_success.isoformat()
    }

if __name__ == "__main__":
    asyncio.run(bot.run())
