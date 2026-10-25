"""Extra 1920x1080 frames for the film, beyond design_shots: the full reveal, the notice, the calc line, the Covenant ping and
reply, the self-approve refusal, the payoff and the live tour screen. Needs the local server (make demo)."""
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
B = "http://127.0.0.1:8000"; OUT = Path(__file__).resolve().parent / "frames"; OUT.mkdir(exist_ok=True)
def reset(): urllib.request.urlopen(urllib.request.Request(f"{B}/api/reset", method="POST")).read()
def press(pg, k, w=800): pg.keyboard.press(k); pg.wait_for_timeout(w)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    reset(); pg.goto(f"{B}/?kiosk=off"); pg.wait_for_timeout(2500); pg.screenshot(path=OUT / "s-title.png")
    press(pg, "Space", 2200); pg.screenshot(path=OUT / "s-reveal-1.png")          # layer 1 only
    pg.wait_for_timeout(2400); pg.screenshot(path=OUT / "s-reveal-2.png")          # layer 2
    pg.wait_for_timeout(2600); pg.screenshot(path=OUT / "s-reveal-3.png")          # all layers
    press(pg, "Space", 500); press(pg, "Space", 1000); pg.screenshot(path=OUT / "s-notice.png")
    press(pg, "Space", 3000); pg.screenshot(path=OUT / "s-calc.png")
    press(pg, "Space", 1500); pg.screenshot(path=OUT / "s-ping-ca.png")
    press(pg, "Space", 1500); pg.screenshot(path=OUT / "s-ping-cc.png")
    press(pg, "Space", 1500); pg.screenshot(path=OUT / "s-ping-ra.png")
    press(pg, "Space", 1200); press(pg, "Space", 1200); pg.screenshot(path=OUT / "s-reply-cc.png")
    press(pg, "Space", 1200); pg.screenshot(path=OUT / "s-reply-ra.png")
    press(pg, "Space", 1200); pg.screenshot(path=OUT / "s-jade.png")
    press(pg, "Space", 3500); pg.screenshot(path=OUT / "s-lesson.png")
    press(pg, "Space", 1200); pg.screenshot(path=OUT / "s-payoff.png")
    press(pg, "t", 1800); pg.screenshot(path=OUT / "s-travel.png"); press(pg, "t", 300)
    # deep
    press(pg, "d", 2500); pg.mouse.move(5, 5); pg.wait_for_timeout(800); pg.screenshot(path=OUT / "d-ripple.png")
    box = pg.locator(".react-flow__node-card").filter(has=pg.locator(".tt", has_text="Lender certificate, sent")).first.bounding_box()
    pg.mouse.move(box["x"] + 12, box["y"] + 12); pg.mouse.down(); pg.wait_for_timeout(60); pg.mouse.up(); pg.mouse.move(5, 5); pg.wait_for_timeout(1500)
    pg.locator("button[aria-label='Close drawer']").click(); pg.wait_for_timeout(600); pg.screenshot(path=OUT / "d-cert-path.png")
    press(pg, "a", 1500); pg.screenshot(path=OUT / "d-approvals.png")
    btn = pg.get_by_role("button", name="Try self-approve").first
    if btn.count(): btn.click(); pg.wait_for_timeout(1200); pg.screenshot(path=OUT / "d-selfapprove.png")
    press(pg, "j", 1500); pg.screenshot(path=OUT / "d-jade.png")
    press(pg, "e", 1500); pg.screenshot(path=OUT / "d-lessons.png")
    press(pg, "Escape", 400); press(pg, "p", 1500); pg.screenshot(path=OUT / "d-scorecard.png")
    pg.close()
    reset(); pg = b.new_page(viewport={"width": 1920, "height": 1080}); pg.goto(f"{B}/?mode=deep&tour=1"); pg.wait_for_timeout(2500); pg.screenshot(path=OUT / "d-idle-tour.png")
    pg.get_by_role("button", name="Next").click(); pg.wait_for_timeout(300)
    box = pg.locator(".react-flow__node-card").filter(has=pg.locator(".tt", has_text="Billing export")).first.bounding_box()
    pg.mouse.move(box["x"] + 40, box["y"] + 20); pg.wait_for_timeout(700); pg.screenshot(path=OUT / "d-source-hover.png")
    b.close()
reset(); print("frames:", len(list(OUT.glob("*.png"))))
