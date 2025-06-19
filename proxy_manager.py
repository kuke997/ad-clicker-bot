import requests
import random
import time
import asyncio
from datetime import datetime, timedelta

class ProxyManager:
    def __init__(self):
        self.proxy_pool = []
        self.last_refresh = datetime.min
        self.proxy_score = {}
    
    async def fetch_proxies(self):
        sources = [
            "https://www.proxy-list.download/api/v1/get?type=https&country=US",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=US",
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
            "https://raw.githubusercontent.com/roosterkid/openproxylist/main/https_RAW.txt"
        ]
        
        proxies = set()
        for url in sources:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    for line in response.text.splitlines():
                        proxy = line.strip()
                        if ":" in proxy and proxy not in proxies:
                            proxies.add(proxy)
            except Exception as e:
                print(f"代理源获取失败 {url}: {str(e)}")
        
        return list(proxies)
    
    async def validate_proxy(self, proxy):
        test_urls = [
            "https://www.google.com",
            "https://www.amazon.com",
            "https://www.microsoft.com"
        ]
        
        for url in random.sample(test_urls, 2):
            try:
                start_time = time.time()
                response = requests.get(
                    url,
                    proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                    timeout=10
                )
                if response.status_code == 200:
                    speed = time.time() - start_time
                    return True, speed
            except:
                continue
        
        return False, 10.0
    
    async def update_proxy_pool(self):
        print("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 并行验证代理
        tasks = [self.validate_proxy(proxy) for proxy in raw_proxies[:50]]  # 限制验证数量
        results = await asyncio.gather(*tasks)
        
        for i, (is_valid, speed) in enumerate(results):
            if is_valid:
                proxy = raw_proxies[i]
                valid_proxies.append(proxy)
                # 根据速度评分 (1-10)
                self.proxy_score[proxy] = max(1, min(10, int(10 - speed)))
                print(f"✅ 代理可用: {proxy} | 速度: {speed:.2f}s | 评分: {self.proxy_score[proxy]}")
        
        self.proxy_pool = valid_proxies
        self.last_refresh = datetime.now()
        print(f"代理池更新完成. 可用代理: {len(self.proxy_pool)}")
    
    async def get_best_proxy(self):
        # 每30分钟刷新一次代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=30) or not self.proxy_pool:
            await self.update_proxy_pool()
        
        if not self.proxy_pool:
            return None
        
        # 根据评分加权随机选择
        weighted_pool = []
        for proxy in self.proxy_pool:
            weight = self.proxy_score.get(proxy, 5)
            weighted_pool.extend([proxy] * weight)
        
        return random.choice(weighted_pool)
    
    def report_proxy_failure(self, proxy):
        if proxy in self.proxy_score:
            self.proxy_score[proxy] = max(1, self.proxy_score[proxy] - 2)
            print(f"⚠️ 代理降级: {proxy} | 新评分: {self.proxy_score[proxy]}")
