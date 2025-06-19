import random
from datetime import datetime
from clicker.proxy import get_us_proxy
import os, json
from playwright.async_api import async_playwright
import requests

TARGET_URLS = ["https://cloakaccess.com"]
LOG_FILE = "logs/click_logs.json"

def log_click(ip, region, url, selector):
    os.makedirs("logs", exist_ok=True)
    log = {
        "timestamp": datetime.utcnow().isoformat(),
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

async def run_click_once():
    proxy = get_us_proxy()
    proxy_str = f"http://{proxy['ip']}:{proxy['port']}" if proxy else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy={"server": proxy_str} if proxy_str else None)
        context = await browser.new_context()
        page = await context.new_page()
        url = random.choice(TARGET_URLS)
        await page.goto(url)
        await page.wait_for_timeout(random.randint(1000, 3000))

        selectors = ['[class*="ad"]', '[id*="ad"]', '[data-ad]', 'iframe[src*="ad"]', '.adsbygoogle', '.sponsor']

        for sel in selectors:
            try:
                ad = await page.query_selector(sel)
                if ad:
                    await ad.click()
                    ip_info = requests.get("https://ipinfo.io/json").json()
                    log_click(ip_info.get("ip", "unknown"), ip_info.get("country", "unknown"), url, sel)
                    print(f"[✓] Clicked ad: {sel}")
                    await page.wait_for_timeout(random.randint(1000, 3000))
                    break
            except:
                continue

        await browser.close()

