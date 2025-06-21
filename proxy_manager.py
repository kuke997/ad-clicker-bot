import aiohttp
import random
import asyncio
from datetime import datetime, timedelta
import logging

class ProxyManager:
    def __init__(self):
        self.proxy_pool = []
        self.last_refresh = datetime.min
        self.logger = logging.getLogger("proxy_manager")
        self.proxy_score = {}
    
    async def fetch_proxies(self):
        """使用更可靠的代理源"""
        sources = [
            "https://proxylist.geonode.com/api/proxy-list?protocols=http&limit=200&country=US,GB,CA,DE",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        ]
        
        proxies = set()
        async with aiohttp.ClientSession() as session:
            for url in sources:
                try:
                    self.logger.info(f"获取代理源: {url}")
                    async with session.get(url, timeout=20) as response:
                        if "geonode" in url:
                            data = await response.json()
                            for item in data["data"]:
                                proxy = f"{item['ip']}:{item['port']}"
                                proxies.add(proxy)
                        else:
                            text = await response.text()
                            for line in text.splitlines():
                                proxy = line.strip()
                                if ":" in proxy and proxy not in proxies:
                                    proxies.add(proxy)
                except Exception as e:
                    self.logger.error(f"代理源获取失败 {url}: {str(e)}")
        
        return list(proxies)
    
    async def validate_proxy(self, proxy):
        """使用异步验证代理"""
        test_urls = [
            "http://www.example.com",
            "http://www.google.com/gen_204",
        ]
        
        async with aiohttp.ClientSession() as session:
            for url in test_urls:
                try:
                    start_time = datetime.now()
                    # 增加超时时间到15秒
                    timeout = aiohttp.ClientTimeout(total=15)
                    async with session.get(
                        url,
                        proxy=f"http://{proxy}",
                        timeout=timeout,  # 使用自定义超时
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
                    ) as response:
                        if response.status in [200, 204]:
                            speed = (datetime.now() - start_time).total_seconds()
                            return True, speed
                except asyncio.TimeoutError:
                    self.logger.warning(f"⌛ 代理验证超时: {proxy}")
                    continue
                except Exception as e:
                    continue
        
        self.logger.warning(f"❌ 代理不可用: {proxy}")
        return False, 10.0
    
    async def update_proxy_pool(self):
        self.logger.info("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 并行验证代理 (限制为100个)
        tasks = [self.validate_proxy(proxy) for proxy in raw_proxies[:100]]
        results = await asyncio.gather(*tasks)
        
        for i, (is_valid, speed) in enumerate(results):
            if is_valid:
                proxy = raw_proxies[i]
                valid_proxies.append(proxy)
                # 根据速度评分 (1-10)
                self.proxy_score[proxy] = max(1, min(10, int(10 - speed * 2)))
                self.logger.info(f"✅ 代理可用: {proxy} | 速度: {speed:.2f}s | 评分: {self.proxy_score[proxy]}")
        
        self.proxy_pool = valid_proxies
        self.last_refresh = datetime.now()
        self.logger.info(f"代理池更新完成. 可用代理: {len(self.proxy_pool)}")
    
    async def get_best_proxy(self):
        """获取最佳代理，自动刷新池"""
        # 每15分钟刷新一次代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=15) or not self.proxy_pool:
            await self.update_proxy_pool()
        
        if not self.proxy_pool:
            # 添加回退机制：当没有代理时尝试直接连接
            self.logger.warning("⚠️ 没有可用代理，尝试直接连接...")
            return None
        
        # 根据评分加权随机选择
        weighted_pool = []
        for proxy in self.proxy_pool:
            weight = self.proxy_score.get(proxy, 5)
            weighted_pool.extend([proxy] * weight)
        
        return random.choice(weighted_pool)
    
    def report_proxy_failure(self, proxy):
        """代理失败处理"""
        if proxy in self.proxy_score:
            self.proxy_score[proxy] = max(1, self.proxy_score[proxy] - 3)
            self.logger.warning(f"⚠️ 代理降级: {proxy} | 新评分: {self.proxy_score[proxy]}")
