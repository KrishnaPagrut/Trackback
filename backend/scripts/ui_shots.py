"""Headless walkthrough of the UI at 1280x720 along the story bar (screenshots to data/eval/screens, console errors reported). Needs the server on :8000."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "data" / "eval" / "screens"
OUT.mkdir(parents=True, exist_ok=True)
errors: list[str] = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 720})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8000/"); page.wait_for_timeout(2500); page.screenshot(path=OUT / "01_before.png")
    page.keyboard.press("r"); page.wait_for_timeout(2000)
    page.keyboard.press("ArrowLeft"); page.wait_for_timeout(1500); page.screenshot(path=OUT / "00_lyft.png")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(1500)
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(800); page.screenshot(path=OUT / "02_notice.png")
    page.get_by_role("button", name="Drop on the source").click(); page.wait_for_timeout(6000); page.screenshot(path=OUT / "03_ripple.png")
    box = page.locator(".react-flow__node").filter(has_text="Lender certificate, sent").first.bounding_box()
    page.mouse.move(box["x"] + 6, box["y"] + 6); page.wait_for_timeout(150); page.mouse.down(); page.wait_for_timeout(60); page.mouse.up(); page.wait_for_timeout(1400)
    page.screenshot(path=OUT / "04_detail.png")
    page.keyboard.press("Escape"); page.wait_for_timeout(300)
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(1200); page.screenshot(path=OUT / "05_pings.png")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(1200); page.screenshot(path=OUT / "06_inbox.png")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(1800)
    try:
        page.locator("button", has_text="Try to read").first.click(); page.wait_for_timeout(800)
    except Exception as e:  # noqa: BLE001
        errors.append(f"try-future button: {e}")
    page.screenshot(path=OUT / "07_replay.png")
    page.keyboard.press("ArrowRight"); page.wait_for_timeout(1500); page.screenshot(path=OUT / "08_proof.png")
    page.keyboard.press("?"); page.wait_for_timeout(500); page.screenshot(path=OUT / "09_help.png")
    page.keyboard.press("Escape"); page.keyboard.press("w"); page.wait_for_timeout(1500)
    page.get_by_role("button", name="Show the ripple").click(); page.wait_for_timeout(2500); page.screenshot(path=OUT / "10_lyft_board.png")
    b.close()
print("console errors:", len(errors)); [print("  ", e[:200]) for e in errors[:10]]
