import asyncio
import json
import random
import logging
from datetime import datetime
from proxy_manager import ProxyManager
from behavior_simulator import BehaviorSimulator
from playwright.async_api import async_playwright

# 配置参数
CLICKS_PER_MINUTE = 8  # 降低频率以适应免费资源
MIN_INTERVAL = 5  # 秒
MAX_INTERVAL = 15  # 秒
MAX_RETRIES = 2

# 日志配置 - 简化版
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# 全局状态变量
last_successful_click = datetime.now()

def get_random_user_agent():
    """简化的User-Agent列表"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0"
    ]
    return random.choice(user_agents)

async def self_keep_alive():
    """自保活机制 - 当检测到长时间无成功点击时重启任务"""
    global last_successful_click
    
    while True:
        await asyncio.sleep(300)  # 每5分钟检查一次
        
        time_since_last_success = (datetime.now() - last_successful_click).total_seconds()
        if time_since_last_success > 1800:  # 30分钟无成功点击
            logging.warning("⚠️ 长时间无成功点击，重启任务...")
            # 通过抛出异常重启（Render会自动重启服务）
            raise Exception("Self-restart due to inactivity")

async def click_ads(playwright, url, selector, proxy=None):
    global last_successful_click
    
    browser = None
    try:
        # 简化浏览器启动配置
        browser = await playwright.chromium.launch(
            proxy={"server": f"http://{proxy}"} if proxy else None,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--user-agent={get_random_user_agent()}"
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()
        
        # 轻量级反检测
        await page.add_init_script("""
            delete navigator.__proto__.webdriver;
        """)
        
        # 访问目标页面（增加超时时间）
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        logging.info(f"访问成功: {url} | 代理: {proxy}")
        
        # 等待页面加载
        await asyncio.sleep(random.uniform(1, 2))
        
        # 模拟人类行为
        simulator = BehaviorSimulator(page)
        await simulator.simulate_behavior()
        
        # 定位并点击广告
        await page.wait_for_selector(selector, state="visible", timeout=20000)
        await page.click(selector, delay=random.randint(50, 150))
        logging.info(f"✅ 广告点击成功: {selector}")
        
        # 更新最后成功时间
        last_successful_click = datetime.now()
        
        # 点击后停留随机时间
        await asyncio.sleep(random.uniform(2, 4))
        
        return True
    except Exception as e:
        logging.error(f"点击失败: {str(e)}")
        return False
    finally:
        if browser:
            await browser.close()

async def main():
    # 启动自保活任务
    asyncio.create_task(self_keep_alive())
    
    # 加载广告目标
    try:
        with open("ad_targets.json", "r") as f:
            targets = json.load(f)
    except:
        logging.error("无法加载广告目标，使用默认配置")
        targets = [{"url": "https://example.com", "selector": ".ad"}]
    
    # 初始化代理管理器
    proxy_manager = ProxyManager()
    
    async with async_playwright() as playwright:
        # 首次代理池更新
        await proxy_manager.update_proxy_pool()
        
        logging.info("🚀 广告点击机器人启动")
        
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
                sleep_time = 60 - elapsed
                logging.info(f"⏱️ 等待 {sleep_time:.1f}秒进入下一分钟")
                await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main())
