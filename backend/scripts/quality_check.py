"""DESIGN.md checklist items that can be measured, at 1280x720 and 1920x1080, against the running server:
no horizontal scroll, no raw undefined/NaN/null on screen, at most 25 cards in the Deep hero view and about 10 in Stage mode,
equal lane heights and aligned rails, text contrast of the tokens (WCAG AA), no layout shift when the drawer opens,
and the whole Stage sequence under prefers-reduced-motion."""
import re
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
fails: list[str] = []


def ok(cond, label, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
    if not cond:
        fails.append(label)


def reset():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/reset", method="POST")).read(); time.sleep(0.5)


def lum(hexc):
    c = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---- contrast of the text tokens against the surfaces they sit on
PAIRS = [("ink", "#1C1B19", "paper", "#F7F4EE"), ("ink-muted", "#6B675F", "paper", "#F7F4EE"), ("ink-muted", "#6B675F", "surface", "#FFFFFF"),
         ("recall", "#C62828", "surface", "#FFFFFF"), ("recall", "#C62828", "recall-wash", "#FBECEA"), ("cleared", "#2E7D32", "surface", "#FFFFFF"),
         ("caution-ink", "#8A5300", "caution-wash", "#FBF1E0"), ("ping", "#1F5FBF", "ping-wash", "#EAF0FA"), ("ping", "#1F5FBF", "surface", "#FFFFFF"), ("white", "#FFFFFF", "ink", "#1C1B19")]
worst = min(ratio(f, b) for _, f, _, b in PAIRS)
for fn, f, bn, b in PAIRS:
    print(f"     contrast {fn} on {bn}: {ratio(f, b):.2f}:1")
ok(worst >= 4.5, "text tokens meet WCAG AA (4.5:1) on their surfaces", f"lowest {worst:.2f}:1")

BAD = re.compile(r"\b(undefined|NaN)\b|\bnull\b")
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((1280, 720), (1920, 1080)):
        ctx = b.new_context(viewport={"width": w, "height": h}); pg = ctx.new_page()
        states = []
        reset(); pg.goto(f"{BASE}/?kiosk=off"); pg.wait_for_timeout(2000); states.append("stage title")
        scan = []
        for i in range(12):
            if pg.locator(".stage .payoff .big").count():
                break
            pg.keyboard.press("Space"); pg.wait_for_timeout(1000)
            n = pg.evaluate("document.querySelectorAll('.stage .snode:not(.hidden)').length")
            scan.append(n)
        ok(max(scan) <= 10, f"{w}: Stage mode shows at most about 10 cards", f"max {max(scan)}")
        txt = pg.evaluate("document.body.innerText")
        ok(not BAD.search(txt), f"{w}: no undefined/NaN/null on the Stage screens")
        sw = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"); ok(sw[0] <= sw[1], f"{w}: no horizontal scroll in Stage mode", f"{sw}")
        reset(); pg.goto(f"{BASE}/?mode=deep&kiosk=off"); pg.wait_for_timeout(2500)
        cards = pg.evaluate("document.querySelectorAll('.dcard').length"); ok(cards <= 25, f"{w}: Deep hero view shows at most 25 cards at rest", str(cards))
        pg.keyboard.press("Space"); pg.wait_for_timeout(700); pg.keyboard.press("Space"); pg.wait_for_timeout(7000)
        cards = pg.evaluate("document.querySelectorAll('.dcard').length"); ok(cards <= 25, f"{w}: Deep hero view shows at most 25 cards after E11", str(cards))
        lanes = pg.evaluate("[...document.querySelectorAll('.react-flow__node-lane')].map(n => [Math.round(n.getBoundingClientRect().height), Math.round(n.querySelector('.lane-rail').getBoundingClientRect().left)])")
        ok(len({x[0] for x in lanes}) == 1 and len({x[1] for x in lanes}) == 1, f"{w}: lane heights equal and rails aligned", f"{lanes}")
        before = pg.evaluate("(() => { const r=document.querySelector('.deep-canvas').getBoundingClientRect(); return [r.left, r.top, r.width, r.height, document.querySelector('.react-flow__viewport').style.transform] })()")
        pg.locator("button.row").first.click(); pg.wait_for_timeout(900)
        after = pg.evaluate("(() => { const r=document.querySelector('.deep-canvas').getBoundingClientRect(); return [r.left, r.top, r.width, r.height, document.querySelector('.react-flow__viewport').style.transform] })()")
        ok(pg.locator(".drawer").count() == 1 and before == after, f"{w}: the drawer opens without shifting the canvas", "")
        txt = pg.evaluate("document.body.innerText"); ok(not BAD.search(txt), f"{w}: no undefined/NaN/null in Deep mode")
        sw = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"); ok(sw[0] <= sw[1], f"{w}: no horizontal scroll in Deep mode", f"{sw}")
        for path in ("/?mode=deep&view=proof&kiosk=off", "/?mode=deep&world=lyft&kiosk=off", "/styleguide"):
            pg.goto(f"{BASE}{path}"); pg.wait_for_timeout(1500)
            txt = pg.evaluate("document.body.innerText"); sw = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            ok(not BAD.search(txt) and sw[0] <= sw[1], f"{w}: {path} has no raw values and no horizontal scroll")
        ctx.close()
    # ---- reduced motion: the full Stage sequence still runs, with no animation
    ctx = b.new_context(viewport={"width": 1280, "height": 720}, reduced_motion="reduce"); pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    reset(); pg.goto(f"{BASE}/?kiosk=off"); pg.wait_for_timeout(1500)
    anim = pg.evaluate("getComputedStyle(document.body).animationName")
    for i in range(14):
        if pg.locator(".stage .payoff .big").count():
            break
        pg.keyboard.press("Space"); pg.wait_for_timeout(600)
    dur = pg.evaluate("(() => { const e=document.querySelector('.stage .payoff'); return e ? getComputedStyle(e).animationName : 'none' })()")
    ok(pg.locator(".stage .payoff .big").count() == 1 and dur == "none" and not errs, "reduced motion: the Stage sequence runs to the payoff with animations off", f"payoff animation {dur}")
    ctx.close(); b.close()
reset()
print(f"== {'PASS' if not fails else 'FAIL'} ({len(fails)} failed)")
