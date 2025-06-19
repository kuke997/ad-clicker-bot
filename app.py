import os  # 修复缺失的 os 导入
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

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

# 创建全局记录器
logger = logging.getLogger("ad-clicker-bot")

# 全局状态变量
last_successful_click = datetime.now()
is_running = False
task = None

# 创建 FastAPI 应用
from fastapi import FastAPI
app = FastAPI()

def get_random_user_agent():
    """返回随机的用户代理字符串"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"
    ]
    return random.choice(user_agents)

async def self_keep_alive():
    """自保活机制 - 当检测到长时间无成功点击时重启任务"""
    global last_successful_click
    
    while True:
        await asyncio.sleep(300)  # 每5分钟检查一次
        
        time_since_last_success = (datetime.now() - last_successful_click).total_seconds()
        if time_since_last_success > 1800:  # 30分钟无成功点击
            logger.warning("⚠️ 长时间无成功点击，重启任务...")
            # 通过抛出异常重启（Render会自动重启服务）
            raise Exception("Self-restart due to inactivity")

async def click_ads(playwright, url, selector, proxy=None):
    """执行广告点击操作"""
    global last_successful_click
    
    browser = None
    try:
        # 使用环境变量中的浏览器路径
        browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")
        chrome_path = os.path.join(browser_path, "chrome-linux", "chrome")
        
        logger.info(f"🌐 访问目标: {url} | 选择器: {selector} | 代理: {proxy if proxy else '无'}")
        logger.info(f"🔍 浏览器路径: {chrome_path}")
        
        # 验证浏览器文件是否存在
        if not os.path.exists(chrome_path):
            logger.error(f"❌ 浏览器文件不存在: {chrome_path}")
            return False
        
        # 配置浏览器选项
        launch_options = {
            "executable_path": chrome_path,
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                f"--user-agent={get_random_user_agent()}"
            ]
        }
        
        # 如果提供了代理，添加到启动选项
        if proxy:
            launch_options["proxy"] = {"server": f"http://{proxy}"}
        
        # 启动浏览器
        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            locale='en-US'
        )
        page = await context.new_page()
        
        # 基本反检测
        await page.add_init_script("""
            delete navigator.__proto__.webdriver;
        """)
        
        # 访问目标页面
        logger.info(f"🚀 导航到: {url}")
        await page.goto(url, timeout=45000, wait_until="domcontentloaded")
        logger.info(f"✅ 页面加载成功")
        
        # 等待页面加载
        await asyncio.sleep(random.uniform(1, 2))
        
        # 模拟人类行为
        logger.info("🧠 模拟人类行为...")
        simulator = BehaviorSimulator(page)
        await simulator.simulate_behavior()
        
        # 定位并点击广告
        logger.info(f"🔍 查找选择器: {selector}")
        await page.wait_for_selector(selector, state="visible", timeout=20000)
        await page.click(selector, delay=random.randint(50, 150))
        logger.info(f"🖱️ ✅ 广告点击成功: {selector}")
        
        # 更新最后成功时间
        last_successful_click = datetime.now()
        
        # 点击后停留随机时间
        await asyncio.sleep(random.uniform(2, 4))
        
        return True
    except Exception as e:
        logger.error(f"❌ 点击失败: {str(e)}")
        return False
    finally:
        if browser:
            await browser.close()

async def clicker_task():
    """广告点击后台任务"""
    global last_successful_click, is_running
    
    is_running = True
    logger.info("🚀 广告点击任务启动")
    
    # 初始化代理管理器
    proxy_manager = ProxyManager()
    
    async with async_playwright() as playwright:
        # 首次代理池更新
        await proxy_manager.update_proxy_pool()
        
        while is_running:
            clicks_this_minute = 0
            start_time = datetime.now()
            
            while clicks_this_minute < CLICKS_PER_MINUTE and is_running:
                # 加载广告目标
                try:
                    with open("ad_targets.json", "r") as f:
                        targets = json.load(f)
                except Exception as e:
                    logger.error(f"加载广告目标失败: {str(e)}")
                    targets = [{"url": "https://www.wikipedia.org", "selector": "a"}]  # 默认目标
                
                target = random.choice(targets)
                
                # 获取代理（如果可用）
                proxy = None
                try:
                    proxy = await proxy_manager.get_best_proxy()
                    if not proxy:
                        logger.warning("⚠️ 没有可用代理，等待更新...")
                        await asyncio.sleep(30)
                        continue
                except Exception as e:
                    logger.error(f"获取代理失败: {str(e)}")
                
                success = False
                for attempt in range(MAX_RETRIES):
                    logger.info(f"🔁 尝试 #{attempt+1} | 目标: {target['url']} | 代理: {proxy if proxy else '无'}")
                    success = await click_ads(playwright, target["url"], target["selector"], proxy)
                    if success:
                        clicks_this_minute += 1
                        break
                    else:
                        if proxy:
                            # 报告代理失败并获取新代理
                            proxy_manager.report_proxy_failure(proxy)
                            proxy = await proxy_manager.get_best_proxy()
                        await asyncio.sleep(2)  # 失败后短暂等待
                
                # 随机间隔避免检测
                interval = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
                logger.info(f"⏱️ 等待 {interval:.1f}秒后进行下一次点击")
                await asyncio.sleep(interval)
            
            # 每分钟精确控制
            if is_running:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed < 60:
                    sleep_time = 60 - elapsed
                    logger.info(f"⏱️ 等待 {sleep_time:.1f}秒进入下一分钟")
                    await asyncio.sleep(sleep_time)
                
                # 检查是否需要重启
                if await self_keep_alive():
                    logger.info("🔄 重新启动点击任务...")
                    return

@app.on_event("startup")
async def startup_event():
    """应用启动时开始点击任务"""
    global task
    task = asyncio.create_task(clicker_task())
    logger.info("✅ FastAPI 应用启动")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止任务"""
    global is_running, task
    is_running = False
    if task:
        await task
    logger.info("🛑 应用已停止")

@app.get("/")
async def read_root():
    """根端点，用于健康检查"""
    time_since_last_success = (datetime.now() - last_successful_click).total_seconds()
    status = "running" if time_since_last_success < 600 else "warning"
    
    return {
        "status": status,
        "last_success": last_successful_click.isoformat(),
        "clicks_per_minute": CLICKS_PER_MINUTE,
        "message": "广告点击机器人运行中"
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    time_since_last_success = (datetime.now() - last_successful_click).total_seconds()
    status = "healthy" if time_since_last_success < 600 else "unhealthy"
    
    return {
        "status": status,
        "last_success": last_successful_click.isoformat(),
        "uptime": (datetime.now() - last_successful_click).total_seconds()
    }

if __name__ == "__main__":
    # 本地运行入口
    logger.info("🚀 启动广告点击机器人...")
    asyncio.run(clicker_task())
