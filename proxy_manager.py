import requests
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
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
        ]
        
        proxies = set()
        for url in sources:
            try:
                self.logger.info(f"获取代理源: {url}")
                response = requests.get(url, timeout=20)
                
                if "geonode" in url:
                    # 处理 GeoNode 的 JSON 格式
                    data = response.json()
                    for item in data["data"]:
                        proxy = f"{item['ip']}:{item['port']}"
                        proxies.add(proxy)
                else:
                    # 处理文本格式
                    for line in response.text.splitlines():
                        proxy = line.strip()
                        if ":" in proxy and proxy not in proxies:
                            proxies.add(proxy)
            except Exception as e:
                self.logger.error(f"代理源获取失败 {url}: {str(e)}")
        
        return list(proxies)
    
    async def validate_proxy(self, proxy):
        """使用更可靠的验证方法"""
        test_urls = [
            "http://www.example.com",  # 轻量级页面
            "http://www.google.com/gen_204",
            "http://www.cloudflare.com/cdn-cgi/trace"
        ]
        
        for url in test_urls:
            try:
                start_time = datetime.now()
                response = requests.get(
                    url,
                    proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
                )
                if response.status_code in [200, 204]:
                    speed = (datetime.now() - start_time).total_seconds()
                    self.logger.info(f"✅ 代理可用: {proxy} | 速度: {speed:.2f}s")
                    return True, speed
            except Exception as e:
                continue
        
        self.logger.warning(f"❌ 代理不可用: {proxy}")
        return False, 10.0
    
    async def update_proxy_pool(self):
        self.logger.info("🔄 更新代理池...")
        raw_proxies = await self.fetch_proxies()
        valid_proxies = []
        
        # 并行验证代理 (限制为50个)
        tasks = [self.validate_proxy(proxy) for proxy in raw_proxies[:50]]
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
    
    async def keep_proxy_pool_updated(self):
        """定期更新代理池的后台任务，避免高峰时段更新"""
        while True:
            try:
                # 每15分钟更新一次
                await asyncio.sleep(900)  # 15分钟
                
                # 获取当前时间
                current_hour = datetime.now().hour
                
                # 只在低峰时段更新代理（凌晨2-6点）
                if 2 <= current_hour <= 6:
                    self.logger.info("🌙 低峰时段更新代理池...")
                    await self.update_proxy_pool()
                else:
                    self.logger.info("⏳ 跳过高峰时段代理更新")
            except Exception as e:
                self.logger.error(f"代理池更新失败: {str(e)}")
                await asyncio.sleep(300)  # 出错后等待5分钟重试
    
    async def get_best_proxy(self):
        """获取最佳代理，自动刷新池"""
        # 如果超过15分钟没有更新或代理池为空，则更新代理池
        if (datetime.now() - self.last_refresh) > timedelta(minutes=15) or not self.proxy_pool:
            try:
                # 快速更新代理池（30秒超时）
                await asyncio.wait_for(self.update_proxy_pool(), timeout=30)
            except asyncio.TimeoutError:
                self.logger.warning("代理更新超时，使用现有代理或直连")
        
        if not self.proxy_pool:
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
