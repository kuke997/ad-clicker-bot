import random
import asyncio
import logging

logger = logging.getLogger("behavior-simulator")

class BehaviorSimulator:
    def __init__(self, page):
        self.page = page
        self.viewport = {"width": 1280, "height": 720}

    async def execute(self):
        try:
            await self.get_viewport()
            await self.random_scroll()
            await self.mouse_movement()
            await self.random_delay()
        except Exception as e:
            logger.warning(f"Behavior simulation failed: {str(e)}")

    async def get_viewport(self):
        try:
            self.viewport = await self.page.evaluate("""() => ({
                width: Math.max(window.innerWidth, 1280),
                height: Math.max(window.innerHeight, 720)
            })""")
        except:
            pass

    async def random_scroll(self):
        scrolls = random.randint(1, 3)
        for _ in range(scrolls):
            try:
                distance = random.randint(100, min(500, self.viewport["height"]))
                await self.page.mouse.wheel(0, distance)
                await asyncio.sleep(random.uniform(0.5, 1.5))
            except:
                break

    async def mouse_movement(self):
        try:
            x = random.randint(0, self.viewport["width"])
            y = random.randint(0, self.viewport["height"])
            steps = random.randint(5, 15)
            await self.page.mouse.move(x, y, steps=steps)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        except:
            pass

    async def random_delay(self):
        await asyncio.sleep(random.uniform(0.5, 2.0))
