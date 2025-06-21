import aiohttp
import random
import asyncio
from datetime import datetime, timedelta
import logging
import re

class ProxyManager:
    def __init__(self):
        self.proxy_pool = []
        self.last_refresh = datetime.min
        self.logger = logging.getLogger("proxy_manager")
        self.proxy_score = {}
        self.failed_proxies = set()
    
    async def fetch_proxies(self):
        """使用更可靠的代理源，包括HTTPS代理"""
        sources = [
            "https://proxylist.geonode.com/api/proxy-list?protocols=http,https&limit=300&country=US,GB,CA,DE,FR",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=yes",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
            "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"
        ]
        
        proxies = set()
        async with aiohttp.ClientSession() as session:
            for url in sources:
                try:
                    self.logger.info(f"获取代理源: {url}")
                    async with session.get(url, timeout=25) as response:
                        content_type = response.headers.get('Content-Type', '')
                        
                        if "application/json" in content_type:
                            data = await response.json()
                            if "geonode" in url:
                                for item in data["data"]:
                                    proxy = f"{item['ip']}:{item['port']}"
                                    proxies.add(proxy)
                            else:
                                # 处理其他JSON格式的代理源
                                for item in data:
                                    if 'ip' in item and 'port' in item:
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
        return list(proxies)
    
    async def validate_proxy(self, proxy):
        """使用异步验证代理，测试HTTP和HTTPS连接"""
        test_urls = [
            "http://www.example.com",
            "https://www.example.com",
            "http://www.google.com/gen_204",
            "https://www.wikipedia.org"
        ]
        
        async with aiohttp.ClientSession() as session:
            for url in test_urls:
                try:
                    start_time = datetime.now()
                    # 增加超时时间到20秒
                    timeout = aiohttp.ClientTimeout(total=20)
                    
                    # 根据URL协议确定代理协议
                    proxy_type = "https" if url.startswith("https") else "http"
                    
                    async with session.get(
                        url,
                        proxy=f"{proxy_type}://{proxy}",
                        timeout=timeout,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"},
                        ssl=False  # 禁用SSL验证以加快速度
                    ) as response:
                        if response.status in [200, 204]:
                            speed = (datetime.now() - start_time).total_seconds()
                            return True, speed
                except asyncio.TimeoutError:
                    self.logger.warning(f"⌛ 代理验证超时: {proxy} | URL: {url}")
                except Exception as e:
                    continue
        
        self.logger.warning(f"❌ 代理不可用: {proxy}")
        return False, 15.0
    
    async def update_proxy_pool(self):
        self.logger.info("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 并行验证代理 (限制为150个)
        tasks = [self.validate_proxy(proxy) for proxy in raw_proxies[:150]]
        results = await asyncio.gather(*tasks)
        
        for i, (is_valid, speed) in enumerate(results):
            proxy = raw_proxies[i]
            if is_valid:
                # 跳过最近失败的代理
                if proxy in self.failed_proxies:
                    self.failed_proxies.discard(proxy)
                    
                valid_proxies.append(proxy)
                # 根据速度评分 (1-10)
                self.proxy_score[proxy] = max(1, min(10, int(10 - speed * 2)))
                self.logger.info(f"✅ 代理可用: {proxy} | 速度: {speed:.2f}s | 评分: {self.proxy_score[proxy]}")
            else:
                # 标记失败代理
                self.failed_proxies.add(proxy)
        
        self.proxy_pool = valid_proxies
        self.last_refresh = datetime.now()
        self.logger.info(f"代理池更新完成. 可用代理: {len(self.proxy_pool)}")
    
    async def get_best_proxy(self):
        """获取最佳代理，自动刷新池，跳过失败代理"""
        # 每10分钟刷新一次代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=10) or not self.proxy_pool:
            await self.update_proxy_pool()
        
        if not self.proxy_pool:
            # 添加回退机制：当没有代理时尝试直接连接
            self.logger.warning("⚠️ 没有可用代理，尝试直接连接...")
            return None
        
        # 根据评分加权随机选择，跳过最近失败的代理
        weighted_pool = []
        for proxy in self.proxy_pool:
            if proxy in self.failed_proxies:
                continue
                
            weight = self.proxy_score.get(proxy, 5)
            weighted_pool.extend([proxy] * weight)
        
        if not weighted_pool:
            self.logger.warning("⚠️ 没有高质量代理，使用低质量代理...")
            # 如果没有高质量代理，尝试使用任何可用代理
            for proxy in self.proxy_pool:
                weight = max(1, self.proxy_score.get(proxy, 1))
                weighted_pool.extend([proxy] * weight)
        
        return random.choice(weighted_pool) if weighted_pool else None
    
    def report_proxy_failure(self, proxy):
        """代理失败处理"""
        # 添加到失败代理列表
        self.failed_proxies.add(proxy)
        
        if proxy in self.proxy_score:
            self.proxy_score[proxy] = max(1, self.proxy_score[proxy] - 3)
            self.logger.warning(f"⚠️ 代理降级: {proxy} | 新评分: {self.proxy_score[proxy]}")
