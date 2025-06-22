import aiohttp
import random
import asyncio
from datetime import datetime, timedelta
import logging
import re
import time

class ProxyManager:
    def __init__(self):
        self.proxy_pool = []
        self.last_refresh = datetime.min
        self.logger = logging.getLogger("proxy_manager")
        self.proxy_score = {}
        self.failed_proxies = set()
        self.lock = asyncio.Lock()
        # 添加可信代理源
        self.reliable_sources = [
            "https://proxylist.geonode.com/api/proxy-list?protocols=http,https&limit=50&country=US,GB,CA,DE,FR",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=US,GB&ssl=yes",
        ]
    
    async def fetch_proxies(self):
        """使用更可靠的代理源，限制数量"""
        proxies = set()
        async with aiohttp.ClientSession() as session:
            for url in self.reliable_sources:
                try:
                    self.logger.info(f"获取代理源: {url}")
                    async with session.get(url, timeout=15) as response:
                        content_type = response.headers.get('Content-Type', '')
                        
                        if "application/json" in content_type:
                            data = await response.json()
                            if "geonode" in url:
                                for item in data["data"]:
                                    proxy = f"{item['ip']}:{item['port']}"
                                    proxies.add(proxy)
                            else:
                                # 处理其他JSON格式的代理源
                                if isinstance(data, list):
                                    for item in data:
                                        if 'ip' in item and 'port' in item:
                                            proxy = f"{item['ip']}:{item['port']}"
                                            proxies.add(proxy)
                                elif 'proxies' in data:  # 处理proxyscrape的格式
                                    for item in data['proxies']:
                                        proxy = f"{item['ip']}:{item['port']}"
                                        proxies.add(proxy)
                        else:
                            text = await response.text()
                            for line in text.splitlines():
                                proxy = line.strip()
                                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$', proxy):
                                    proxies.add(proxy)
                except Exception as e:
                    self.logger.error(f"代理源获取失败 {url}: {str(e)}")
        
        self.logger.info(f"从源获取到 {len(proxies)} 个候选代理")
        return list(proxies)[:50]  # 限制为50个
    
    async def validate_proxy(self, proxy):
        """优化代理验证，减少测试URL"""
        # 使用单个可靠的测试URL
        test_url = "http://www.google.com/gen_204"
        
        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                # 减少超时时间到8秒
                timeout = aiohttp.ClientTimeout(total=8)
                
                async with session.get(
                    test_url,
                    proxy=f"http://{proxy}",
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"},
                    ssl=False
                ) as response:
                    if response.status == 204:
                        speed = time.time() - start_time
                        return True, speed
            except asyncio.TimeoutError:
                self.logger.debug(f"⌛ 代理验证超时: {proxy}")
            except Exception as e:
                self.logger.debug(f"代理验证失败: {proxy} - {str(e)}")
        
        return False, 10.0
    
    async def update_proxy_pool(self):
        self.logger.info("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 限制验证数量为20个代理
        tasks = [self.validate_proxy(proxy) for proxy in raw_proxies[:20]]
        results = await asyncio.gather(*tasks)
        
        for i, (is_valid, speed) in enumerate(results):
            proxy = raw_proxies[i]
            if is_valid:
                if proxy in self.failed_proxies:
                    self.failed_proxies.discard(proxy)
                valid_proxies.append(proxy)
                self.proxy_score[proxy] = max(1, min(10, int(10 - speed * 2)))
                self.logger.info(f"✅ 代理可用: {proxy} | 速度: {speed:.2f}s | 评分: {self.proxy_score[proxy]}")
            else:
                self.failed_proxies.add(proxy)
        
        self.proxy_pool = valid_proxies
        self.last_refresh = datetime.now()
        self.logger.info(f"代理池更新完成. 可用代理: {len(self.proxy_pool)}")
    
    async def get_best_proxy(self):
        """获取最佳代理，自动刷新池，跳过失败代理"""
        # 每15分钟刷新一次代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=15) or not self.proxy_pool:
            await self.update_proxy_pool()
        
        if not self.proxy_pool:
            self.logger.warning("⚠️ 没有可用代理，尝试直接连接...")
            return None
        
        # 根据评分选择前5个最佳代理
        sorted_proxies = sorted(
            [p for p in self.proxy_pool if p not in self.failed_proxies],
            key=lambda p: self.proxy_score.get(p, 0),
            reverse=True
        )[:5]
        
        if sorted_proxies:
            return random.choice(sorted_proxies)
        
        self.logger.warning("⚠️ 没有高质量代理，尝试使用任何可用代理...")
        return random.choice(self.proxy_pool) if self.proxy_pool else None
    
    def report_proxy_failure(self, proxy):
        """代理失败处理"""
        self.failed_proxies.add(proxy)
        if proxy in self.proxy_score:
            self.proxy_score[proxy] = max(1, self.proxy_score[proxy] - 2)
            self.logger.warning(f"⚠️ 代理降级: {proxy} | 新评分: {self.proxy_score[proxy]}")
