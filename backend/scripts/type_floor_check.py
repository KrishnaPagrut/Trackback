"""Smallest rendered text size (CSS px after the canvas zoom) in each main state, at 1280x720 and 1920x1080. DESIGN.md: nothing under 13 px."""
import urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
JS = """() => {
  const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  while (w.nextNode()) {
    const t = w.currentNode; if (!t.textContent.trim()) continue
    const el = t.parentElement; const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue
    let scale = 1; const vp = el.closest('.react-flow__viewport'); if (vp) { const m = getComputedStyle(vp).transform.match(/matrix\\(([^,]+)/); if (m) scale = parseFloat(m[1]) }
    if (el.closest('.react-flow__minimap, .react-flow__controls, .payoff')) continue
    out.push([parseFloat(cs.fontSize) * scale, t.textContent.trim().slice(0, 40)])
  }
  out.sort((a, b) => a[0] - b[0]); return out.slice(0, 3)
}"""


def reset():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/reset", method="POST")).read()


worst = 99.0
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((1280, 720), (1920, 1080)):
        pg = b.new_page(viewport={"width": w, "height": h})
        states = []
        reset(); pg.goto(f"{BASE}/?kiosk=off"); pg.wait_for_timeout(2000); states.append(("stage title", pg.evaluate(JS)))
        for _ in range(5): pg.keyboard.press("Space"); pg.wait_for_timeout(1200)
        states.append(("stage ripple", pg.evaluate(JS)))
        reset(); pg.goto(f"{BASE}/?mode=deep&kiosk=off"); pg.wait_for_timeout(2500); states.append(("deep idle", pg.evaluate(JS)))
        pg.keyboard.press("Space"); pg.wait_for_timeout(600); pg.keyboard.press("Space"); pg.wait_for_timeout(7000); states.append(("deep ripple", pg.evaluate(JS)))
        pg.keyboard.press("a"); pg.wait_for_timeout(1000); states.append(("approvals", pg.evaluate(JS)))
        pg.keyboard.press("p"); pg.wait_for_timeout(1200); states.append(("proof", pg.evaluate(JS)))
        pg.goto(f"{BASE}/styleguide"); pg.wait_for_timeout(1200); states.append(("styleguide", pg.evaluate(JS)))
        for name, rows in states:
            m = rows[0][0] if rows else 99
            worst = min(worst, m)
            print(f"{w}x{h} {name:<14} smallest {m:5.1f}px  ({rows[0][1] if rows else ''})")
        pg.close()
    b.close()
reset()
print(f"== smallest rendered text anywhere: {worst:.1f}px ({'PASS' if worst >= 13 else 'FAIL'}: floor 13px)")
