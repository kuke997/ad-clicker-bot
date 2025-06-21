import requests
import random
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger("proxy-manager")

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.scores = {}
        self.last_update = datetime.min

    async def fetch_proxies(self):
        sources = [
            "https://proxylist.geonode.com/api/proxy-list?limit=50&protocols=http",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
        ]
        
        proxies = set()
        for url in sources:
            try:
                resp = requests.get(url, timeout=10)
                if "geonode" in url:
                    for item in resp.json().get("data", []):
                        proxies.add(f"{item['ip']}:{item['port']}")
                else:
                    proxies.update(line.strip() for line in resp.text.splitlines() if ":" in line)
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {str(e)}")
        return list(proxies)

    async def validate(self, proxy):
        try:
            start = datetime.now()
            resp = requests.get(
                "http://www.google.com",
                proxies={"http": f"http://{proxy}"},
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                return True, (datetime.now() - start).total_seconds()
        except:
            pass
        return False, 10.0

    async def update(self):
        try:
            raw = await self.fetch_proxies()
            self.proxies = []
            
            for proxy in raw[:20]:  # 限制验证数量
                valid, speed = await self.validate(proxy)
                if valid:
                    self.scores[proxy] = max(1, 10 - int(speed * 2))
                    self.proxies.append(proxy)
            
            self.last_update = datetime.now()
            logger.info(f"Updated proxy pool: {len(self.proxies)} available")
        except Exception as e:
            logger.error(f"Proxy update failed: {str(e)}")

    async def get_best(self):
        if not self.proxies or (datetime.now() - self.last_update).seconds > 1800:
            await self.update()
            
        if not self.proxies:
            return None
            
        weighted = []
        for proxy in self.proxies:
            weighted += [proxy] * self.scores.get(proxy, 1)
        return random.choice(weighted)

    def report_failure(self, proxy):
        if proxy in self.scores:
            self.scores[proxy] = max(1, self.scores[proxy] - 2)
            if self.scores[proxy] <= 1:
                self.proxies.remove(proxy)
