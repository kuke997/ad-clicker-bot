import asyncio
import json
import random
import logging
from datetime import datetime
from proxy_manager import ProxyManager
from behavior_simulator import BehaviorSimulator
from playwright.async_api import async_playwright

# 配置参数
CLICKS_PER_MINUTE = 10
MIN_INTERVAL = 3  # 秒
MAX_INTERVAL = 12  # 秒
MAX_RETRIES = 3

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ad_clicker.log')
    ]
)

async def click_ads(playwright, url, selector, proxy=None):
    browser = None
    try:
        proxy_str = f"http://{proxy}" if proxy else None
        browser = await playwright.chromium.launch(
            proxy={"server": proxy_str} if proxy_str else None,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                f"--user-agent={get_random_user_agent()}"
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            locale='en-US',
            timezone_id='America/New_York'
        )
        page = await context.new_page()
        
        # 屏蔽常见检测点
        await page.add_init_script("""
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        # 访问目标页面
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        logging.info(f"访问成功: {url} | 代理: {proxy}")
        
        # 等待页面加载
        await asyncio.sleep(random.uniform(1, 3))
        
        # 模拟人类行为
        simulator = BehaviorSimulator(page)
        await simulator.simulate_behavior()
        
        # 定位并点击广告
        await page.wait_for_selector(selector, state="visible", timeout=15000)
        await page.click(selector, delay=random.randint(50, 250))
        logging.info(f"✅ 广告点击成功: {selector}")
        
        # 点击后停留随机时间
        await asyncio.sleep(random.uniform(2, 5))
        
        return True
    except Exception as e:
        logging.error(f"点击失败: {str(e)}")
        return False
    finally:
        if browser:
            await browser.close()

def get_random_user_agent():
    user_agents = [
        # Chrome
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        # Firefox
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.4; rv:109.0) Gecko/20100101 Firefox/114.0",
        # Safari
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15"
    ]
    return random.choice(user_agents)

async def main():
    # 加载广告目标
    with open("ad_targets.json", "r") as f:
        targets = json.load(f)
    
    # 初始化代理管理器
    proxy_manager = ProxyManager()
    
    async with async_playwright() as playwright:
        logging.info("广告点击机器人启动")
        
        while True:
            clicks_this_minute = 0
            start_time = datetime.now()
            
            while clicks_this_minute < CLICKS_PER_MINUTE:
                target = random.choice(targets)
                proxy = await proxy_manager.get_best_proxy()
                
                if not proxy:
                    logging.warning("没有可用代理，等待更新...")
                    await asyncio.sleep(30)
                    continue
                
                success = False
                for attempt in range(MAX_RETRIES):
                    logging.info(f"尝试 #{attempt+1} | 目标: {target['url']} | 代理: {proxy}")
                    success = await click_ads(playwright, target["url"], target["selector"], proxy)
                    if success:
                        clicks_this_minute += 1
                        break
                    else:
                        # 报告代理失败并获取新代理
                        proxy_manager.report_proxy_failure(proxy)
                        proxy = await proxy_manager.get_best_proxy()
                
                # 随机间隔避免检测
                interval = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
                await asyncio.sleep(interval)
            
            # 每分钟精确控制
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed < 60:
                await asyncio.sleep(60 - elapsed)

if __name__ == "__main__":
    asyncio.run(main())
