import random
import asyncio
from playwright.async_api import Page

class BehaviorSimulator:
    def __init__(self, page: Page):
        self.page = page
        self.viewport_width = 1200
        self.viewport_height = 800
    
    async def simulate_behavior(self):
        # 随机滚动行为
        await self.random_scroll()
        
        # 鼠标移动轨迹
        await self.move_mouse()
        
        # 随机点击页面元素
        await self.random_clicks()
        
        # 随机等待时间
        await asyncio.sleep(random.uniform(0.5, 2.5))
    
    async def random_scroll(self):
        scroll_times = random.randint(1, 4)
        for _ in range(scroll_times):
            # 随机滚动方向和距离
            scroll_y = random.randint(200, 800)
            if random.random() > 0.7:
                scroll_y = -scroll_y  # 向上滚动
            
            await self.page.mouse.wheel(0, scroll_y)
            await asyncio.sleep(random.uniform(0.3, 1.2))
    
    async def move_mouse(self):
        start_x = random.randint(0, self.viewport_width)
        start_y = random.randint(0, self.viewport_height)
        
        await self.page.mouse.move(start_x, start_y)
        
        # 创建随机移动路径
        for _ in range(random.randint(3, 8)):
            end_x = random.randint(0, self.viewport_width)
            end_y = random.randint(0, self.viewport_height)
            
            # 使用贝塞尔曲线移动
            await self.page.mouse.move(
                end_x, 
                end_y, 
                steps=random.randint(20, 50),
                **{"behavior": "smooth"}
            )
            
            await asyncio.sleep(random.uniform(0.05, 0.3))
    
    async def random_clicks(self):
        if random.random() > 0.7:  # 70%概率执行额外点击
            # 尝试点击非广告元素
            non_ad_selectors = [
                "a", "button", "div", "img",
                "input", "label", "span"
            ]
            
            for _ in range(3):
                try:
                    elements = await self.page.query_selector_all(
                        random.choice(non_ad_selectors)
                    )
                    if elements:
                        element = random.choice(elements)
                        await element.click(timeout=2000)
                        print("🖱️ 随机点击非广告元素")
                        await asyncio.sleep(random.uniform(0.2, 1.0))
                        break
                except:
                    continue
