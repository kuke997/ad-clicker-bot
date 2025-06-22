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
    level=logging.INFO,  # 降低日志级别为INFO
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
proxy_manager = None  # 代理管理器全局实例

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
    """自保活机制 - 当检测到长时间无成功点击时重置状态"""
    global last_successful_click, proxy_manager
    
    time_since_last_success = (datetime.now() - last_successful_click).total_seconds()
    if time_since_last_success > 1800:  # 30分钟无成功点击
        logger.warning("⚠️ 长时间无成功点击，重置状态...")
        last_successful_click = datetime.now()
        
        # 重置代理管理器
        if proxy_manager:
            # 重新创建代理管理器并更新代理池
            proxy_manager = ProxyManager()
            try:
                await proxy_manager.update_proxy_pool()
                logger.info("🔄 代理池已重置")
            except Exception as e:
                logger.error(f"重置代理池失败: {str(e)}")
        else:
            logger.error("代理管理器未初始化，无法重置")
        
        return True
    return False

async def simulate_ad_browse(page):
    """在广告页面模拟5秒随机浏览和滑动"""
    logger.info("🔄 进入广告页面，模拟5秒随机浏览...")
    
    start_time = datetime.now()
    while (datetime.now() - start_time).total_seconds() < 5:
        # 随机滚动
        scroll_amount = random.randint(100, 500)
        scroll_direction = random.choice([-1, 1])  # 随机向上或向下滚动
        await page.evaluate(f"window.scrollBy(0, {scroll_amount * scroll_direction})")
        
        # 随机等待
        wait_time = random.uniform(0.5, 1.5)
        await asyncio.sleep(wait_time)
        
        # 随机点击页面上的元素（非广告）
        try:
            elements = await page.query_selector_all("a, button, div")
            if elements:
                element = random.choice(elements)
                await element.click(delay=random.randint(50, 250))
                logger.debug("🖱️ 随机点击页面元素")
        except Exception:
            pass  # 忽略点击错误
    
    logger.info("✅ 广告浏览完成，返回主页面")

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
            
            # 记录点击前的URL
            original_url = page.url
            logger.info(f"📌 点击前URL: {original_url}")
            
            # 点击元素
            try:
                # 使用更可靠的点击方法
                await element.scroll_into_view_if_needed()
                await element.click(delay=random.randint(100, 300))
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
            
            # === 新增功能：广告页面浏览 ===
            try:
                logger.info("🔍 开始检测广告页面...")
                ad_page = None
                ad_page_type = "unknown"
                
                # 1. 等待一段时间让页面反应
                logger.info("⏱️ 等待2秒让页面反应...")
                await asyncio.sleep(2)
                
                # 2. 检查URL是否变化
                current_url = page.url
                logger.info(f"📌 当前URL: {current_url}")
                
                if current_url != original_url:
                    logger.info(f"🔗 URL变化: {original_url} -> {current_url}")
                    ad_page = page
                    ad_page_type = "url_change"
                else:
                    logger.info("🔗 URL未变化")
                
                # 3. 检查是否有新标签页
                pages = context.pages
                if len(pages) > 1:
                    logger.info(f"🪟 检测到 {len(pages)-1} 个新标签页")
                    for p in pages:
                        if p != page:
                            logger.info(f"  - 新标签页URL: {p.url}")
                            ad_page = p
                            ad_page_type = "popup"
                            break
                
                # 4. 检查页面内容变化（DOM变化）
                if not ad_page:
                    try:
                        # 检查页面标题或主要内容区域是否变化
                        new_title = await page.title()
                        logger.info(f"📝 当前标题: {new_title}")
                        
                        # 检查是否有广告相关元素出现
                        ad_indicators = await page.query_selector_all(
                            ".ad, .advertisement, .promo, .banner, .modal, .popup"
                        )
                        if ad_indicators:
                            logger.info(f"🔍 检测到 {len(ad_indicators)} 个广告指示器元素")
                            ad_page = page
                            ad_page_type = "ad_element"
                    except Exception as e:
                        logger.warning(f"⚠️ 检查页面内容变化失败: {str(e)}")
                
                # 5. 如果检测到广告页面，进行浏览
                if ad_page:
                    logger.info(f"🎯 检测到广告页面 ({ad_page_type})")
                    
                    # 确保切换到广告页面
                    if ad_page != page:
                        await ad_page.bring_to_front()
                    
                    # 等待广告页面加载
                    try:
                        logger.info("⏱️ 等待广告页面加载...")
                        await ad_page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info("✅ 广告页面加载完成")
                    except Exception as e:
                        logger.warning(f"⚠️ 广告页面加载超时: {str(e)}")
                    
                    # 模拟浏览行为
                    await simulate_ad_browse(ad_page)
                    
                    # 关闭新标签页或返回原始页面
                    if ad_page != page:
                        logger.info("🔒 关闭广告标签页...")
                        await ad_page.close()
                        await page.bring_to_front()  # 切换回原始页面
                    else:
                        # 返回原始页面
                        logger.info("↩️ 尝试返回原始页面...")
                        try:
                            await page.go_back()
                            await page.wait_for_load_state("networkidle", timeout=60000)
                            logger.info("✅ 已返回原始页面")
                        except Exception as e:
                            logger.error(f"❌ 返回原始页面失败: {str(e)}")
                else:
                    logger.info("⏱️ 未检测到广告页面跳转")
            except Exception as e:
                logger.error(f"⚠️ 广告浏览出错: {str(e)}")
                # 尝试返回原始页面
                try:
                    if page.url != original_url:
                        await page.go_back()
                        await page.wait_for_load_state("networkidle", timeout=60000)
                except Exception:
                    pass
            
            # 点击后随机等待
            wait_time = random.uniform(0.5, 2.5)
            logger.info(f"⏱️ 等待 {wait_time:.1f}秒后进行下一次点击")
            await asyncio.sleep(wait_time)
        
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

# 其他函数保持不变（should_skip_target, clicker_task, 等）
# ... [保持不变的部分代码] ...

if __name__ == "__main__":
    # 本地运行入口
    logger.info("🚀 启动广告点击机器人...")
    asyncio.run(clicker_task())
