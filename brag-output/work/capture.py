import asyncio, sys
from playwright.async_api import async_playwright
URL = "http://127.0.0.1:8000/?kiosk=off"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        await pg.goto(URL); await pg.wait_for_timeout(2500)
        await pg.keyboard.press("r"); await pg.wait_for_timeout(2500)
        await pg.screenshot(path="hd/00_title.png")
        await pg.keyboard.press("Space")
        for i, ms in enumerate([700, 2300, 4700, 7300]):
            await pg.wait_for_timeout(ms - (0 if i == 0 else [700, 2300, 4700, 7300][i-1]))
            await pg.screenshot(path=f"hd/01_reveal_{i}.png")
        await pg.wait_for_timeout(1500); await pg.screenshot(path="hd/01_reveal_full.png")
        n = 2
        for k in range(12):
            await pg.keyboard.press("Space"); await pg.wait_for_timeout(2600)
            await pg.screenshot(path=f"hd/{n:02d}_step.png"); n += 1
        await pg.keyboard.press("t"); await pg.wait_for_timeout(2500); await pg.screenshot(path=f"hd/{n:02d}_memento.png"); n += 1
        await pg.keyboard.press("t"); await pg.wait_for_timeout(800)
        await pg.keyboard.press("d"); await pg.wait_for_timeout(3000); await pg.screenshot(path=f"hd/{n:02d}_deep.png"); n += 1
        await pg.keyboard.press("d"); await pg.wait_for_timeout(800)
        await pg.keyboard.press("r"); await pg.wait_for_timeout(2500)
        await b.close()
asyncio.run(main())
