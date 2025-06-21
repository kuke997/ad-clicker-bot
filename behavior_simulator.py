import random
import asyncio
from playwright.async_api import Page
import logging

class BehaviorSimulator:
    def __init__(self, page: Page):
        self.page = page
        self.logger = logging.getLogger("behavior_simulator")
    
    async def simulate_behavior(self):
        """模拟人类浏览行为"""
        # 随机滚动
        await self.random_scroll()
        
        # 随机移动鼠标
        await self.move_mouse()
        
        # 随机点击非广告元素
        await self.random_clicks()
        
        # 随机等待时间
        await asyncio.sleep(random.uniform(0.5, 2.5))
    
    async def random_scroll(self):
        """随机滚动页面"""
        scroll_times = random.randint(1, 3)
        self.logger.info(f"📜 随机滚动 {scroll_times} 次")
        
        for i in range(scroll_times):
            # 随机滚动方向和距离
            scroll_y = random.randint(300, 800)
            if random.random() > 0.7:
                scroll_y = -scroll_y  # 向上滚动
            
            await self.page.mouse.wheel(0, scroll_y)
            await asyncio.sleep(random.uniform(0.3, 1.5))
    
    async def move_mouse(self):
        """模拟鼠标移动轨迹"""
        viewport = self.page.viewport_size
        if not viewport:
            return
        
        width, height = viewport["width"], viewport["height"]
        self.logger.info(f"🖱️ 模拟鼠标移动 | 窗口尺寸: {width}x{height}")
        
        # 起始位置
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        await self.page.mouse.move(start_x, start_y)
        
        # 创建随机移动路径 (3-6个点)
        points = random.randint(3, 6)
        for i in range(points):
            end_x = random.randint(0, width)
            end_y = random.randint(0, height)
            
            # 使用贝塞尔曲线移动
            await self.page.mouse.move(
                end_x, 
                end_y, 
                steps=random.randint(15, 30),
            )
            await asyncio.sleep(random.uniform(0.05, 0.3))
    
    async def random_clicks(self):
        """随机点击非广告元素"""
        if random.random() > 0.6:  # 60%概率执行额外点击
            self.logger.info("🎯 随机点击非广告元素")
            
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
                        self.logger.info("🖱️ 随机点击成功")
                        await asyncio.sleep(random.uniform(0.2, 1.0))
                        break
                except Exception as e:
                    continue
