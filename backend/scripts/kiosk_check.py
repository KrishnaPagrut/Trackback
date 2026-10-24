"""Kiosk and mode checks for Stage mode, against the running server (make demo). Waits out the real 60-second idle timer.

1. After 60 s with no input Stage mode resets and plays the attract loop with captions.
2. Any key stops it and offers the visitor card with three presets and "Paste your own".
3. Each preset runs: the trivial 40-cent bank fee ends with 0 agents pinged; the utilities invoice and the billing duplicate ping agents.
4. D switches to Deep mode and back without losing the Stage step or the correction.
5. The full presenter sequence runs from keypresses alone, title card to payoff, with the payoff numbers from the run."""
import re
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = "docs/screenshots/kiosk"
fails: list[str] = []


def ok(cond: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
    if not cond:
        fails.append(label)


def reset():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/reset", method="POST")).read()


def caption(page) -> str:
    return page.locator(".stage .caption").inner_text()


def run_to_payoff(page, max_steps=20) -> str:
    for _ in range(max_steps):
        if page.locator(".stage .payoff .big").count():
            break
        page.keyboard.press("Space"); page.wait_for_timeout(900)
    page.wait_for_timeout(500)
    return page.locator(".stage .payoff").inner_text() if page.locator(".stage .payoff .big").count() else ""


import os  # noqa: E402
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 1280, "height": 720})
    errors: list[str] = []; page.on("pageerror", lambda e: errors.append(str(e)))
    # ---------------- presenter sequence, keys only
    reset(); page.goto(f"{BASE}/?kiosk=off"); page.wait_for_timeout(2000)
    ok("told its lender leverage was" in page.locator(".stage .title-card").inner_text(), "Stage mode opens on the title card")
    payoff = run_to_payoff(page, 20)
    m = re.search(r"(\d+) of (\d+)\s+pieces of work.*?(\d) of 3 agents needed to act · (\d+) actions? waiting for a human · (\d+) things left stale", payoff, re.S)
    ok(bool(m), "Space alone runs title → layered reveal → recall → ripple → replies → payoff", payoff.replace("\n", " | ")[:160])
    import json
    pl = json.loads(urllib.request.urlopen(f"{BASE}/pings?correction=E11").read())["pings"]
    agents_api = len({x["target_agent_id"] for x in pl}); items_api = sum(x["n_items"] for x in pl)
    ok(bool(m) and int(m.group(3)) == agents_api and int(m.group(1)) == items_api, "payoff numbers come from the run",
       f"page: {m.group(1) if m else '?'} items, {m.group(3) if m else '?'} of 3 agents; /pings: {items_api} items to {agents_api} agents")
    page.screenshot(path=f"{OUT}/presenter-payoff.png")
    # ---------------- D keeps state
    page.keyboard.press("d"); page.wait_for_timeout(2500)
    strip = page.locator("text=agents pinged").first.inner_text() if page.locator("text=agents pinged").count() else ""
    ok("3 of 3" in page.content() and page.locator(".react-flow").count() > 0, "D opens Deep mode on the same correction", strip)
    page.keyboard.press("d"); page.wait_for_timeout(1500)
    ok(page.locator(".stage .payoff .big").count() == 1, "D again returns to Stage mode at the same step (the payoff)")
    page.close()

    # ---------------- kiosk: attract after 60 s idle
    reset(); page = b.new_page(viewport={"width": 1280, "height": 720}); page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/"); page.wait_for_timeout(2000)
    t0 = time.time(); page.wait_for_timeout(58_000)
    ok("Three AI agents built on one number" not in caption(page), "no attract loop before 60 s idle", f"{time.time() - t0:.0f} s")
    page.wait_for_timeout(5_000)
    cap = caption(page)
    ok("Three AI agents built on one number" in cap, "attract loop starts after 60 s idle, with a caption", f"{time.time() - t0:.0f} s: {cap[:70]}")
    page.wait_for_timeout(9_000)
    page.screenshot(path=f"{OUT}/attract-loop.png")
    advancing = page.locator(".stage .layer-label").count() > 0 or page.locator(".stage .snode").count() > 0
    ok(advancing, "the attract loop plays the sequence by itself")
    page.keyboard.press("x"); page.wait_for_timeout(1500)
    card = page.locator("text=Try it: drop a recall notice").count() > 0
    btns = [page.get_by_role("button", name=n).count() for n in ("The billing duplicate", "A 40-cent bank fee", "A utilities invoice", "Paste your own")]
    ok(card and all(btns), "any key stops the loop and offers three presets plus Paste your own")
    page.screenshot(path=f"{OUT}/visitor-card.png")
    # ---------------- presets
    for name, expect in (("A 40-cent bank fee", 0), ("A utilities invoice", None), ("The billing duplicate", 3)):
        if not page.get_by_role("button", name=name).count():
            page.keyboard.press("Escape"); reset(); page.goto(f"{BASE}/"); page.wait_for_timeout(1500)
            page.evaluate("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'x'}))")
        page.get_by_role("button", name=name).click(); page.wait_for_timeout(1500)
        ok(page.locator(".recall-notice").count() == 1, f"preset '{name}': its recall notice appears")
        out = run_to_payoff(page, 20)
        mm = re.search(r"(\d) of 3 agents needed to act", out)
        n = int(mm.group(1)) if mm else -1
        good = (n == expect) if expect is not None else (n >= 1)
        ok(good, f"preset '{name}': payoff shows {n} of 3 agents needed to act", "zero pings, everything cleared" if expect == 0 and n == 0 else out.replace('\n', ' | ')[:120])
        page.screenshot(path=f"{OUT}/preset-{name.split()[-1]}.png")
        # back to the card for the next preset
        reset()
        if name == "A 40-cent bank fee":
            page.goto(f"{BASE}/"); page.wait_for_timeout(64_000)
            ok("Three AI agents built on one number" in caption(page), "after idling, the kiosk returns to the attract loop")
            page.keyboard.press("x"); page.wait_for_timeout(1200)
        else:
            page.goto(f"{BASE}/?visitor=1"); page.wait_for_timeout(1500)
    ok(not errors, "no page errors", "; ".join(errors[:2]))
    b.close()
reset()
print(f"== {'PASS' if not fails else 'FAIL'} ({len(fails)} failed)")
