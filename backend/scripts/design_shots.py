"""DESIGN.md's nine states at 1280x720 and 1920x1080, saved under docs/screenshots/round-N/, plus 25%-width copies of the
Stage shots for the legibility check. Needs the server on :8000 (make demo). Usage: design_shots.py N"""
import subprocess
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROUND = sys.argv[1] if len(sys.argv) > 1 else "1"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots" / f"round-{ROUND}"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"


def reset():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/reset", method="POST")).read()
    import time; time.sleep(0.6)


def press(page, key, wait=700):
    page.keyboard.press(key); page.wait_for_timeout(wait)


def click_node(page, text):
    box = page.locator(".react-flow__node-card").filter(has=page.locator(".tt", has_text=text)).filter(has_not_text="Fix for").first.bounding_box()
    page.mouse.move(box["x"] + 12, box["y"] + 12); page.wait_for_timeout(120); page.mouse.down(); page.wait_for_timeout(60); page.mouse.up()


errors: list[str] = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((1280, 720), (1920, 1080)):
        tag = f"{w}x{h}"
        ctx = b.new_context(viewport={"width": w, "height": h}); page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"{tag} {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"{tag} {e}"))
        # ---- Stage mode
        reset(); page.goto(f"{BASE}/?kiosk=off"); page.wait_for_timeout(2500)
        page.screenshot(path=OUT / f"1-stage-title-{tag}.png")
        press(page, "Space", 3600)                        # layered reveal, about half built
        page.screenshot(path=OUT / f"2-stage-reveal-half-{tag}.png")
        press(page, "Space", 400)                         # finish the reveal
        press(page, "Space", 900)                         # the recall notice
        press(page, "Space", 2500)                        # drop it: the calc line
        press(page, "Space", 1400)                        # ping: Close Accountant
        press(page, "Space", 1400)                        # ping: Reporting Analyst
        page.screenshot(path=OUT / f"3-stage-mid-ripple-{tag}.png")
        for _ in range(8):
            if page.locator(".payoff .big").count():
                break
            press(page, "Space", 900)
        page.wait_for_timeout(600)
        page.screenshot(path=OUT / f"4-stage-payoff-{tag}.png")
        # ---- Deep mode
        reset(); page.goto(f"{BASE}/?mode=deep&kiosk=off"); page.wait_for_timeout(2500)
        page.screenshot(path=OUT / f"5-deep-idle-{tag}.png")
        press(page, "Space", 900); press(page, "Space", 7000)    # the recall notice, dropped; the ripple runs
        click_node(page, "Lender certificate, sent"); page.wait_for_timeout(2500)
        page.screenshot(path=OUT / f"6-deep-ripple-who-built-{tag}.png")
        press(page, "a", 1200)
        page.screenshot(path=OUT / f"7-deep-approvals-e22-{tag}.png")
        press(page, "Escape", 300); press(page, "t", 1500)
        page.screenshot(path=OUT / f"8-deep-memento-april-10-{tag}.png")
        press(page, "p", 1500)
        page.screenshot(path=OUT / f"9-proof-{tag}.png")
        ctx.close()
    b.close()
reset()
for f in sorted(p for p in OUT.glob("[1-4]-stage-*.png") if not p.stem.endswith("25pct")):
    small = f.with_name(f.stem + "-25pct.png")
    subprocess.run(["sips", "-Z", str(int(int(f.stem.split("-")[-1].split("x")[0]) * 0.25)), str(f), "--out", str(small)], capture_output=True)
print(f"round {ROUND}: {len(list(OUT.glob('*.png')))} files in {OUT}")
print("console errors:", len(errors)); [print("  ", e[:200]) for e in errors[:10]]
