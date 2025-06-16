# 使用 Playwright 自动点击网页广告并记录日志
import asyncio
from playwright.async_api import async_playwright
import random
import time
import json
import requests
import os
from datetime import datetime

TARGET_URLS = [
    "https://cloakaccess.com"  # 替换为你的广告页面
]

LOG_FILE = "logs/click_logs.json"

# 示例代理 API（请替换为真实代理服务）
def get_proxy():
    try:
        # 返回格式示例：{"ip": "1.2.3.4", "port": "8080"}
        resp = requests.get("http://example.com/proxy/api")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[!] 获取代理失败: {e}")
    return None

# 记录日志
def log_click(ip, region, url, selector):
    os.makedirs("logs", exist_ok=True)
    log = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "region": region,
        "url": url,
        "selector": selector
    }
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([log], f, indent=2)
    else:
        with open(LOG_FILE, "r+") as f:
            data = json.load(f)
            data.append(log)
            f.seek(0)
            json.dump(data, f, indent=2)

async def run_clicker():
    proxy = get_proxy()
    proxy_str = None
    if proxy:
        proxy_str = f"http://{proxy['ip']}:{proxy['port']}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy={"server": proxy_str} if proxy_str else None)
        context = await browser.new_context()
        page = await context.new_page()

        url = random.choice(TARGET_URLS)
        await page.goto(url)
        await page.wait_for_timeout(random.randint(2000, 5000))

        selectors = [
            '[class*="ad"]',
            '[id*="ad"]',
            '[data-ad]',
            'iframe[src*="ad"]',
            '.adsbygoogle',
            '.sponsor'
        ]

        for sel in selectors:
            try:
                ad = await page.query_selector(sel)
                if ad:
                    await ad.click()
                    print(f"[✓] 点击广告: {sel}")
                    ip_info = requests.get("https://ipinfo.io").json()
                    log_click(ip_info.get("ip", "unknown"), ip_info.get("country", "unknown"), url, sel)
                    await page.wait_for_timeout(random.randint(2000, 4000))
                    break
            except Exception as e:
                continue

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_clicker())
