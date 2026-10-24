"""Screenshots of every Stage beat (both worlds) and every Deep tab, at 1280x720 and 1920x1080: python backend/scripts/shots_v3.py [round] [WxH]
The server must be running on :8000 (python tasks.py demo). Resets the world first so live beats (Dana, the General Counsel) run from the snapshot."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8000"


def main(rnd: str = "v3", sizes: list[tuple[int, int]] | None = None) -> None:
    out = ROOT / "docs" / "screenshots" / rnd
    out.mkdir(parents=True, exist_ok=True)
    sizes = sizes or [(1280, 720), (1920, 1080)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h in sizes:
            page = b.new_page(viewport={"width": w, "height": h})
            page.request.post(f"{BASE}/api/reset")
            for world, n in (("tidewall", 10), ("lyft", 7)):
                page.goto(f"{BASE}/?world={world}&kiosk=off")
                page.wait_for_timeout(1500)
                for i in range(n):
                    page.wait_for_timeout(2600 if i in (1, 3) else 1600)
                    page.screenshot(path=str(out / f"stage-{world}-{i:02d}-{w}x{h}.png"))
                    page.keyboard.press("Space")
            page.request.post(f"{BASE}/api/reset")
            for world in ("tidewall", "lyft"):
                page.goto(f"{BASE}/?world={world}&mode=deep&kiosk=off")
                page.wait_for_timeout(1200)
                for tab in ("Reconcile", "Trace", "Graph", "Evaluate", "Pings", "Approvals", "Memo", "Time travel", "Scorecard", "Lessons", "Access"):
                    page.get_by_role("button", name=tab, exact=True).first.click()
                    page.wait_for_timeout(1300)
                    page.screenshot(path=str(out / f"deep-{world}-{tab.replace(' ', '_').lower()}-{w}x{h}.png"))
            page.close()
        b.close()
    print(f"screenshots in {out}")


if __name__ == "__main__":
    rnd = sys.argv[1] if len(sys.argv) > 1 else "v3"
    sz = [tuple(int(x) for x in sys.argv[2].split("x"))] if len(sys.argv) > 2 else None
    t0 = time.time()
    main(rnd, sz)
    print(f"{time.time() - t0:.0f}s")
