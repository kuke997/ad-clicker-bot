import random
import asyncio
from playwright.async_api import Page

class BehaviorSimulator:
    def __init__(self, page: Page):
        self.page = page
    
    async def simulate_behavior(self):
        """简化的人类行为模拟"""
        # 随机滚动
        await self.random_scroll()
        
        # 随机移动鼠标
        await self.move_mouse()
        
        # 随机等待时间
        await asyncio.sleep(random.uniform(0.5, 1.5))
    
    async def random_scroll(self):
        """轻量级滚动模拟"""
        scroll_times = random.randint(0, 1)  # 50%概率滚动
        if scroll_times:
            scroll_y = random.randint(200, 400)
            await self.page.mouse.wheel(0, scroll_y)
            await asyncio.sleep(random.uniform(0.3, 0.6))
    
    async def move_mouse(self):
        """简化鼠标移动"""
        width, height = await self.page.evaluate("""() => {
            return [window.innerWidth, window.innerHeight];
        }""")
        
        # 创建1个移动点
        if width and height:
            end_x = random.randint(0, width)
            end_y = random.randint(0, height)
            await self.page.mouse.move(end_x, end_y, steps=5)
            await asyncio.sleep(random.uniform(0.05, 0.1))
