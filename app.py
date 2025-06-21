import os
import asyncio
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from proxy_manager import ProxyManager
from behavior_simulator import BehaviorSimulator
from playwright.async_api import async_playwright
from fastapi import FastAPI

# 配置参数
CLICKS_PER_MINUTE = 8
MIN_INTERVAL = 5  # 秒
MAX_INTERVAL = 15  # 秒
MAX_RETRIES = 3
NETWORK_ERROR_RETRY_DELAY = 10  # 网络错误重试延迟（秒）

# 日志配置
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别获取更多信息
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
            # 通过取消任务并重新创建来重启
            global task, is_running
            is_running = False
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            is_running = True
            task = asyncio.create_task(clicker_task())
            last_successful_click = datetime.now()
            return True
        return False

async def click_ads(playwright, url, selector, target, proxy=None):
    """执行广告点击操作，支持时间敏感和点击深度功能"""
    global last_successful_click
    
    browser = None
    try:
        # 检查Chromium是否存在
        chromium_path = Path("/ms-playwright/chromium/chrome-linux/chrome")
        if not chromium_path.exists():
            logger.error(f"❌ Chromium not found at {chromium_path}")
            # 尝试重新安装
            logger.warning("⚠️ Attempting to reinstall Chromium...")
            os.system("PLAYWRIGHT_BROWSERS_PATH=/ms-playwright npx playwright install chromium --with-deps")
            if not chromium_path.exists():
                logger.error("❌ Failed to reinstall Chromium")
                return False
        
        logger.info(f"🌐 访问目标: {url} | 选择器: {selector} | 广告位: {target.get('name', '未知')}")
        
        # 配置浏览器选项
        launch_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",  # 解决Docker内存问题
                "--single-process",         # 减少资源占用
                f"--user-agent={get_random_user_agent()}",
                # 添加GPU禁用参数
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-gl-drawing-for-tests",
                "--disable-breakpad",
                "--disable-setuid-sandbox",
                "--no-zygote",
                "--ignore-gpu-blocklist",
                "--disable-gpu-early-init",
                "--disable-gpu-sandbox",
                "--enable-webgl",
                "--use-gl=swiftshader",
                "--use-angle=swiftshader"
            ],
            # 指定Chromium可执行路径
            "executable_path": "/ms-playwright/chromium/chrome-linux/chrome"
        }
        
        # 如果提供了代理，添加到启动选项
        if proxy:
            launch_options["proxy"] = {"server": f"http://{proxy}"}
        
        # 启动浏览器
        logger.info("🚀 启动Chromium浏览器...")
        browser = await playwright.chromium.launch(**launch_options)
        
        # 创建浏览器上下文
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            locale='en-US',
            # 禁用WebDriver检测
            bypass_csp=True
        )
        
        # 反检测措施
        await context.add_init_script("""
            delete navigator.__proto__.webdriver;
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        page = await context.new_page()
        
        # 访问目标页面 - 增加错误处理和重试机制
        use_direct_connection = False
        navigation_attempts = 0
        max_navigation_attempts = 3
        navigation_success = False
        
        while not navigation_success and navigation_attempts < max_navigation_attempts:
            try:
                logger.info(f"🧭 导航到: {url} (尝试 {navigation_attempts+1}/{max_navigation_attempts})")
                await page.goto(url, timeout=60000, wait_until="networkidle")
                logger.info(f"✅ 页面加载成功")
                navigation_success = True
            except Exception as e:
                navigation_attempts += 1
                error_str = str(e)
                
                # 如果是代理问题，尝试不使用代理
                if "ERR_TUNNEL_CONNECTION_FAILED" in error_str or "ERR_PROXY_CONNECTION_FAILED" in error_str:
                    logger.warning(f"⚠️ 代理连接失败，尝试直接连接...")
                    await browser.close()
                    
                    # 重新启动浏览器不使用代理
                    if "proxy" in launch_options:
                        del launch_options["proxy"]
                    
                    browser = await playwright.chromium.launch(**launch_options)
                    context = await browser.new_context(
                        viewport={'width': 1280, 'height': 720},
                        locale='en-US',
                        bypass_csp=True
                    )
                    await context.add_init_script("""
                        delete navigator.__proto__.webdriver;
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.chrome = { runtime: {} };
                    """)
                    page = await context.new_page()
                    
                    logger.info(f"🧭 直接导航到: {url}")
                    await page.goto(url, timeout=60000, wait_until="networkidle")
                    logger.info(f"✅ 页面加载成功")
                    use_direct_connection = True
                    navigation_success = True
                # 处理连接重置错误
                elif "ERR_CONNECTION_RESET" in error_str or "ERR_EMPTY_RESPONSE" in error_str:
                    logger.warning(f"⚠️ 网络错误: {error_str} (尝试 {navigation_attempts}/{max_navigation_attempts})")
                    if navigation_attempts < max_navigation_attempts:
                        wait_time = NETWORK_ERROR_RETRY_DELAY * navigation_attempts
                        logger.info(f"⏱️ 等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ 导航失败: {error_str}")
                        return False
                # 处理其他网络错误
                elif "net::" in error_str:
                    logger.warning(f"⚠️ 网络错误: {error_str} (尝试 {navigation_attempts}/{max_navigation_attempts})")
                    if navigation_attempts < max_navigation_attempts:
                        wait_time = NETWORK_ERROR_RETRY_DELAY * navigation_attempts
                        logger.info(f"⏱️ 等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ 导航失败: {error_str}")
                        return False
                else:
                    logger.error(f"❌ 导航失败: {error_str}")
                    return False
        
        if not navigation_success:
            logger.error("❌ 导航失败，放弃尝试")
            return False
        
        # 等待页面加载
        await asyncio.sleep(random.uniform(2, 4))
        
        # 模拟人类行为
        logger.info("🧠 模拟人类行为...")
        simulator = BehaviorSimulator(page)
        await simulator.simulate_behavior()
        
        # ======== 广告点击深度功能实现 ========
        click_depth_config = target.get("click_depth", {})
        
        # 确定点击次数
        if isinstance(click_depth_config, int):
            click_count = click_depth_config
        elif isinstance(click_depth_config, dict) and "min" in click_depth_config and "max" in click_depth_config:
            click_count = random.randint(click_depth_config["min"], click_depth_config["max"])
        else:
            click_count = 1
        
        # 确定可点击元素类型
        if isinstance(click_depth_config, dict):
            allowed_elements = click_depth_config.get("elements", ["a", "button", "div"])
        else:
            allowed_elements = ["a", "button", "div"]
        
        clickable_selector = f"{selector} {','.join(allowed_elements)}"
        
        logger.info(f"🎯 点击深度: {click_count}次 | 元素选择器: {clickable_selector}")
        
        # 执行多次点击
        for i in range(click_count):
            # 等待元素可能出现
            try:
                await page.wait_for_selector(clickable_selector, timeout=5000, state="attached")
            except Exception as e:
                logger.warning(f"⏳ 等待元素超时: {clickable_selector}")
            
            # 查找所有可点击元素
            elements = await page.query_selector_all(clickable_selector)
            
            if not elements:
                logger.warning(f"⚠️ 未找到可点击元素: {clickable_selector}")
                # 尝试截图用于调试
                try:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    await page.screenshot(path=f"screenshot_error_{timestamp}.png")
                    logger.info(f"📸 已保存错误截图: screenshot_error_{timestamp}.png")
                except Exception as e:
                    logger.error(f"截图失败: {str(e)}")
                break
            
            # 随机选择一个元素点击
            element = random.choice(elements)
            
            # 高亮元素用于调试
            try:
                await element.evaluate("el => el.style.border = '2px solid red'")
            except Exception as e:
                logger.warning(f"⚠️ 无法高亮元素: {str(e)}")
            
            # 点击元素
            try:
                await element.click(delay=random.randint(50, 250))
                logger.info(f"🖱️ ✅ 深度点击 {i+1}/{click_count} 成功")
            except Exception as e:
                logger.error(f"❌ 点击失败: {str(e)}")
                # 尝试使用其他方式点击
                try:
                    await element.dispatch_event("click")
                    logger.info(f"🖱️ ✅ 备选点击方式成功")
                except Exception as e2:
                    logger.error(f"❌ 备选点击方式也失败: {str(e2)}")
                    break
            
            # 点击后随机等待
            await asyncio.sleep(random.uniform(0.5, 2.5))
        
        # 更新最后成功时间
        last_successful_click = datetime.now()
        
        # 返回连接方式用于统计
        return "direct" if use_direct_connection else "proxy"
    except Exception as e:
        logger.error(f"❌ 点击失败: {str(e)}")
        # 添加详细错误日志
        import traceback
        logger.debug(f"错误详情: {traceback.format_exc()}")
        return False
    finally:
        if browser:
            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"⚠️ 关闭浏览器时出错: {str(e)}")

def should_skip_target(target):
    """检查广告目标是否应跳过（基于时间敏感配置）"""
    if "active_hours" not in target:
        return False  # 没有时间限制
    
    config = target["active_hours"]
    current_time = datetime.now()
    current_hour = current_time.hour
    current_weekday = current_time.weekday()  # 周一=0, 周日=6
    
    # "always" 表示始终激活
    if config == "always":
        return False
    
    # 时间段配置 (如 "start": 9, "end": 21)
    if isinstance(config, dict) and "start" in config and "end" in config:
        if config["start"] <= current_hour < config["end"]:
            return False  # 在活跃时段
        return True  # 在非活跃时段
    
    # 详细配置 (如 "weekdays": [1,2,3,4,5], "hours": [12,13,18,19])
    if isinstance(config, dict) and "weekdays" in config and "hours" in config:
        if current_weekday in config["weekdays"] and current_hour in config["hours"]:
            return False  # 在活跃时段
        return True  # 在非活跃时段
    
    return False  # 未知配置，默认不跳过

async def clicker_task():
    """广告点击后台任务，支持时间敏感功能"""
    global last_successful_click, is_running
    
    is_running = True
    logger.info("🚀 广告点击任务启动")
    
    # 初始化代理管理器
    proxy_manager = ProxyManager()
    
    async with async_playwright() as playwright:
        # 首次代理池更新
        await proxy_manager.update_proxy_pool()
        
        # 加载广告目标
        try:
            with open("ad_targets.json", "r") as f:
                targets = json.load(f)
            logger.info(f"✅ 成功加载 {len(targets)} 个广告目标")
        except Exception as e:
            logger.error(f"加载广告目标失败: {str(e)}")
            # 添加详细错误信息
            import traceback
            logger.error(traceback.format_exc())
            targets = [{"url": "https://www.wikipedia.org", "selector": "a", "name": "测试广告", "weight": 1, "active_hours": "always", "click_depth": 1}]
        
        # 统计变量
        direct_connections = 0
        proxy_connections = 0
        failed_attempts = 0
        
        while is_running:
            clicks_this_minute = 0
            start_time = datetime.now()
            
            while clicks_this_minute < CLICKS_PER_MINUTE and is_running:
                # 选择目标，考虑权重
                weighted_targets = []
                for target in targets:
                    if should_skip_target(target):
                        logger.info(f"⏰ 跳过非活跃时段广告: {target.get('name', '未知')}")
                        continue
                    weight = target.get("weight", 1)
                    weighted_targets.extend([target] * weight)
                
                if not weighted_targets:
                    logger.warning("⚠️ 没有可用广告目标（可能全部处于非活跃时段）")
                    await asyncio.sleep(60)
                    continue
                
                target = random.choice(weighted_targets)
                
                # 获取代理（如果可用）
                proxy = None
                try:
                    proxy = await proxy_manager.get_best_proxy()
                    if not proxy:
                        logger.warning("⚠️ 没有可用代理，尝试直接连接...")
                        # 这里不设置代理，后续会使用直接连接
                except Exception as e:
                    logger.error(f"获取代理失败: {str(e)}")
                
                success = False
                connection_type = "unknown"
                for attempt in range(MAX_RETRIES):
                    logger.info(f"🔁 尝试 #{attempt+1} | 目标: {target['url']} | 广告位: {target.get('name', '未知')} | 代理: {proxy if proxy else '无'}")
                    result = await click_ads(playwright, target["url"], target["selector"], target, proxy)
                    
                    if result:
                        success = True
                        clicks_this_minute += 1
                        connection_type = result
                        failed_attempts = 0  # 重置失败计数器
                        break
                    else:
                        # 指数退避策略
                        backoff_time = min(30, 2 ** attempt)  # 最大等待30秒
                        logger.info(f"⏱️ 等待 {backoff_time} 秒后重试...")
                        await asyncio.sleep(backoff_time)
                        
                        if proxy:
                            # 报告代理失败并获取新代理
                            proxy_manager.report_proxy_failure(proxy)
                            try:
                                proxy = await proxy_manager.get_best_proxy()
                            except Exception as e:
                                logger.error(f"获取新代理失败: {str(e)}")
                                proxy = None
                
                # 更新连接统计
                if success:
                    if connection_type == "direct":
                        direct_connections += 1
                    elif connection_type == "proxy":
                        proxy_connections += 1
                else:
                    failed_attempts += 1
                    # 连续失败多次时延长等待时间
                    if failed_attempts >= 3:
                        extended_wait = 30
                        logger.warning(f"⚠️ 连续失败 {failed_attempts} 次，等待 {extended_wait} 秒...")
                        await asyncio.sleep(extended_wait)
                
                # 每10次点击打印一次统计
                total_connections = direct_connections + proxy_connections
                if total_connections > 0 and total_connections % 10 == 0:
                    logger.info(f"📊 连接统计: 代理连接 {proxy_connections} 次, 直接连接 {direct_connections} 次")
                
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

@app.get("/report")
async def time_report():
    """广告活跃状态报告端点"""
    try:
        with open("ad_targets.json", "r") as f:
            targets = json.load(f)
    except:
        targets = []
    
    active_counts = {}
    current_time = datetime.now()
    current_hour = current_time.hour
    current_weekday = current_time.weekday()
    
    for target in targets:
        name = target.get("name", target["url"])
        active_counts[name] = {
            "status": "Active" if not should_skip_target(target) else "Inactive",
            "reason": ""
        }
        
        if "active_hours" in target:
            config = target["active_hours"]
            if config == "always":
                active_counts[name]["reason"] = "全天激活"
            elif isinstance(config, dict) and "start" in config and "end" in config:
                active_counts[name]["reason"] = f"激活时段: {config['start']}:00-{config['end']}:00"
            elif isinstance(config, dict) and "weekdays" in config and "hours" in config:
                weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                active_weekdays = [weekdays[i] for i in config["weekdays"]]
                active_counts[name]["reason"] = f"激活时间: {', '.join(active_weekdays)} {', '.join(map(str, config['hours']))}点"
    
    return active_counts

@app.get("/resources")
async def resource_monitor():
    """资源监控端点"""
    import psutil
    return {
        "memory": psutil.virtual_memory()._asdict(),
        "cpu": psutil.cpu_percent(),
        "disk": psutil.disk_usage('/')._asdict()
    }

if __name__ == "__main__":
    # 本地运行入口
    logger.info("🚀 启动广告点击机器人...")
    asyncio.run(clicker_task())
