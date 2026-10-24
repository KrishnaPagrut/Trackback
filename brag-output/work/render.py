import asyncio, sys, pathlib
from playwright.async_api import async_playwright
here = pathlib.Path(__file__).parent
async def main(mode):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        await pg.goto((here / "comp/index.html").as_uri()); await pg.evaluate("window.ready")
        if mode == "stills":
            out = here / "stills"; out.mkdir(exist_ok=True)
            for t in [float(x) for x in sys.argv[2].split(",")]:
                await pg.evaluate(f"render({t})"); await pg.screenshot(path=str(out / f"t{t:05.2f}.png"))
        else:
            out = here / "frames"; out.mkdir(exist_ok=True)
            fps, dur = 30, 23.0
            for i in range(int(fps * dur)):
                await pg.evaluate(f"render({i / fps})")
                await pg.screenshot(path=str(out / f"f{i:04d}.jpg"), type="jpeg", quality=95)
        await b.close()
asyncio.run(main(sys.argv[1]))
