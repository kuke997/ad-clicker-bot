import time
import json
import random
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

TARGET_URLS = ["https://example.com"]

def get_proxy():
    try:
        res = requests.get("https://proxylist.geonode.com/api/proxy-list?limit=1&page=1&sort_by=lastChecked&sort_type=desc")
        result = res.json()['data'][0]
        return f"{result['ip']}:{result['port']}", result['ip']
    except:
        return None, None

def get_ip_location(ip):
    try:
        res = requests.get(f"https://ipapi.co/{ip}/json/").json()
        return res.get("country_name"), res.get("region"), res.get("city")
    except:
        return "Unknown", "Unknown", "Unknown"

def setup_driver(proxy):
    options = webdriver.ChromeOptions()
    options.add_argument(f'--proxy-server=http://{proxy}')
    options.add_argument('--headless')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(f'--window-size={random.randint(800, 1200)},{random.randint(600, 900)}')
    return webdriver.Chrome(options=options)

def log_click(data):
    log_path = "logs/click_logs.json"
    try:
        with open(log_path, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    logs.append(data)
    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)

def main():
    proxy, ip = get_proxy()
    if not proxy:
        print("No proxy found.")
        return
    country, region, city = get_ip_location(ip)
    driver = setup_driver(proxy)
    url = random.choice(TARGET_URLS)
    ad_selectors = ['[class*="ad"]', '[id*="ad"]', '[data-ad]', 'iframe[src*="ad"]']
    status = "failed"
    used_selector = ""
    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        for selector in ad_selectors:
            try:
                ad = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                time.sleep(random.uniform(1, 2))
                ad.click()
                used_selector = selector
                status = "success"
                break
            except:
                continue
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()
    log_click({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ip": ip,
        "country": country,
        "region": region,
        "city": city,
        "click_url": url,
        "ad_selector": used_selector,
        "status": status
    })

if __name__ == "__main__":
    main()
