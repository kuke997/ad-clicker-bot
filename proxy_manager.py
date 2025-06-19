import requests
import random
import asyncio
from datetime import datetime, timedelta

class ProxyManager:
    def __init__(self):
        self.proxy_pool = []
        self.last_refresh = datetime.min
    
    async def fetch_proxies(self):
        """只使用最可靠的免费代理源"""
        sources = [
            "https://www.proxy-list.download/api/v1/get?type=https&country=US",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=US"
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
        """使用轻量级验证方法"""
        test_url = "https://www.google.com/gen_204"  # Google空响应页面
        
        try:
            response = requests.get(
                test_url,
                proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                timeout=8
            )
            if response.status_code == 204:  # Google空响应状态码
                return True
        except:
            pass
        
        return False
    
    async def update_proxy_pool(self):
        print("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 只验证前10个代理以节省资源
        for proxy in raw_proxies[:10]:
            if await self.validate_proxy(proxy):
                valid_proxies.append(proxy)
                print(f"✅ 代理可用: {proxy}")
        
        self.proxy_pool = valid_proxies
        self.last_refresh = datetime.now()
        print(f"代理池更新完成. 可用代理: {len(self.proxy_pool)}")
    
    async def get_best_proxy(self):
        """获取最佳代理，自动刷新池"""
        # 每60分钟刷新一次代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=60) or not self.proxy_pool:
            await self.update_proxy_pool()
        
        if not self.proxy_pool:
            return None
        
        # 简单随机选择
        return random.choice(self.proxy_pool)
    
    def report_proxy_failure(self, proxy):
        """简单移除失败代理"""
        if proxy in self.proxy_pool:
            self.proxy_pool.remove(proxy)
            print(f"⚠️ 移除失败代理: {proxy}")
