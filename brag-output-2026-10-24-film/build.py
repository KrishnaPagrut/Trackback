"""Generate the HyperFrames composition for the demo film: silent, subtitled (the presenter reads the subtitles aloud), built from
real 1920x1080 frames of the app. Each scene blurs and dims the frame except the region the subtitle is about (the focus), and
moves that focus as the subtitle advances. Re-run after every change: it rewrites index.html and compositions/*.html."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMP = ROOT / "composition"
SCENES_DIR = COMP / "compositions"
SCENES_DIR.mkdir(exist_ok=True)
NARR = json.loads((ROOT / "narration.json").read_text())

PAPER, SURFACE, INK, MUTED, RULE, RED, GREEN, BLUE = "#F7F4EE", "#FFFFFF", "#1C1B19", "#6B675F", "#E3DED4", "#C62828", "#2E7D32", "#1F5FBF"
WPS = 3.0            # a presenter reading aloud, steady
GROUP_MIN = 1.3      # seconds a subtitle stays up at least
GROUP_PAD = 0.12     # breath after each subtitle
FULL = [0, 0, 1920, 1080]

# ---- the storyboard. frames: (file, fraction of the scene at which it cuts in). focus: (fraction, [x, y, w, h]) regions the sharp
# window moves between; the rest of the frame is blurred and dimmed. chips: one at a time in the top band. steps: scene 6 pills.
SB = [
    dict(id="s0", title=True, chapter="Trackback"),
    dict(id="s1", chapter="1 · Meet Tidewall", frames=[("d-idle.png", 0.0)], focus=[(0.0, FULL), (0.62, [360, 160, 1480, 650])],
         chips=[("6 gyms · California", 0.0), ("~$40M a year", 0.2), ("Leverage must stay under 3.00x", 0.4), ("2 AI agents · Maya, FP&A · Dana, Controller", 0.68)]),
    dict(id="s2", chapter="2 · The source", frames=[("d-source-hover.png", 0.0)], focus=[(0.0, [630, 150, 690, 300])],
         chips=[("Billing export, March · captured April 9 · version 1", 0.1)]),
    dict(id="s3", chapter="3 · Layer one", frames=[("s-reveal-1.png", 0.0)], focus=[(0.0, [0, 290, 1920, 250]), (0.72, [470, 290, 660, 250])],
         chips=[("Close Accountant closes Q1", 0.0), ("$236,000 released · Q1 revenue $10.4M · TTM EBITDA $5.6M", 0.3), ("51 pieces of work, each with a read receipt", 0.72)]),
    dict(id="s4", chapter="4 · Layers two and three", frames=[("s-reveal-2.png", 0.0), ("s-reveal-3.png", 0.42)], focus=[(0.0, [0, 540, 1920, 245]), (0.42, [0, 780, 1920, 225]), (0.8, FULL)],
         chips=[("Leverage 2.95x · certificate sent May 15 · bonuses · tax", 0.0), ("Maya's board deck: same tools, same receipts", 0.42), ("188 pieces of work · 305 receipts", 0.8)]),
    dict(id="s5", chapter="5 · July 8: Trackback is switched on", frames=[("s-notice2.png", 0.0), ("s-notice.png", 0.5)], focus=[(0.0, [790, 60, 430, 285]), (0.5, [800, 165, 800, 75])],
         chips=[("$118,000 counted twice across five gyms", 0.3), ("Leverage 2.95x → 3.03x, crosses 3.00x", 0.55)]),
    dict(id="s6", chapter="6 · The reconciliation", frames=[("d-ripple.png", 0.0), ("d-cert-path.png", 0.7)], focus=[(0.0, FULL), (0.12, [360, 380, 1480, 120]), (0.3, [0, 56, 1500, 50]), (0.7, [900, 380, 640, 340])],
         steps=[("diff", 0.0), ("reach", 0.08), ("recompute", 0.28), ("materiality", 0.4), ("prose", 0.55), ("verdicts", 0.76)]),
    dict(id="s7", chapter="7 · One message per agent", frames=[("s-ping-ca.png", 0.0), ("s-reply-cc2.png", 0.72)], focus=[(0.0, [1140, 290, 760, 470]), (0.72, [1140, 290, 760, 480])],
         chips=[("Maya gets the same message as a notice", 0.1), ("Corrected certificate drafted for the CFO", 0.72)]),
    dict(id="s8", chapter="8 · Jade, the reviewer", frames=[("s-reply-ra.png", 0.0)], focus=[(0.0, [360, 275, 1200, 525])]),
    dict(id="s9", chapter="9 · The right person says no", frames=[("d-approvals.png", 0.0), ("d-selfapprove.png", 0.72)], focus=[(0.0, [1500, 100, 420, 910]), (0.3, [1510, 200, 410, 670]), (0.72, [1510, 100, 410, 600])],
         chips=[("Certificate → CFO · bonuses → HR · entries → Controller", 0.0), ("Q1 is locked: rejected, re-drafted in June", 0.3), ("CHECK (proposer <> approver)", 0.72)]),
    dict(id="s10", chapter="10 · It learns", frames=[("s-jade.png", 0.0)], focus=[(0.0, [350, 280, 1220, 510]), (0.45, [770, 505, 400, 130]), (0.82, [350, 640, 1220, 150])],
         chips=[("Regression gate: 71 of 72 past claims pass · 0 newly failing", 0.3), ("Held-out cases: v1 80% → v2 100%", 0.78)]),
    dict(id="s11", chapter="11 · Time travel", frames=[("s-travel.png", 0.0)], focus=[(0.0, [500, 420, 940, 420]), (0.5, [540, 600, 960, 240])]),
    dict(id="s12", chapter="12 · Go look", frames=[("d-idle-tour.png", 0.0)], focus=[(0.0, FULL)], end=True),
]

FONTS = """
@font-face { font-family: "Newsreader"; font-weight: 500; src: url("assets/fonts/newsreader-latin-500-normal.woff2") format("woff2"); }
@font-face { font-family: "Newsreader"; font-weight: 600; src: url("assets/fonts/newsreader-latin-600-normal.woff2") format("woff2"); }
@font-face { font-family: "Newsreader"; font-weight: 500; font-style: italic; src: url("assets/fonts/newsreader-latin-500-italic.woff2") format("woff2"); }
@font-face { font-family: "IBM Plex Sans"; font-weight: 400; src: url("assets/fonts/ibm-plex-sans-latin-400-normal.woff2") format("woff2"); }
@font-face { font-family: "IBM Plex Sans"; font-weight: 500; src: url("assets/fonts/ibm-plex-sans-latin-500-normal.woff2") format("woff2"); }
@font-face { font-family: "IBM Plex Sans"; font-weight: 600; src: url("assets/fonts/ibm-plex-sans-latin-600-normal.woff2") format("woff2"); }
@font-face { font-family: "IBM Plex Mono"; font-weight: 400; src: url("assets/fonts/ibm-plex-mono-latin-400-normal.woff2") format("woff2"); }
@font-face { font-family: "IBM Plex Mono"; font-weight: 500; src: url("assets/fonts/ibm-plex-mono-latin-500-normal.woff2") format("woff2"); }
"""


# ---------------------------------------------------------------- subtitles: natural clauses, paced for reading aloud
def groups_for(text: str) -> list[str]:
    """Split on sentence ends and strong pauses, then cap a group at about eleven words without breaking a short tail off."""
    parts = re.split(r"(?<=[.?!”])\s+|(?<=[:;])\s+|(?<=,)\s+(?=and |so |with |because |over |under |about |which )", text.strip())
    out: list[str] = []
    for p in parts:
        w = p.split()
        while len(w) > 12:
            cut = max(6, min(11, len(w) - 5))
            out.append(" ".join(w[:cut])); w = w[cut:]
        if w:
            if out and len(w) <= 2 and not re.search(r"[.?!”]$", out[-1]):
                out[-1] += " " + " ".join(w)
            else:
                out.append(" ".join(w))
    return out


def group_dur(g: str) -> float:
    return round(max(GROUP_MIN, len(g.split()) / WPS + GROUP_PAD), 2)


def layout() -> list[dict]:
    t = 0.0
    out = []
    for sc in SB:
        k = sc["id"][1:]
        gs = groups_for(NARR[k])
        durs = [group_dur(g) for g in gs]
        lead = 0.3
        tail = 0.4 if not sc.get("end") else 1.6
        caps, c = [], lead
        for g, d in zip(gs, durs):
            caps.append({"text": g, "start": round(c, 2), "dur": d}); c += d
        D = round(lead + sum(durs) + tail, 2)
        out.append({**sc, "k": k, "start": round(t, 2), "dur": D, "caps": caps, "voice": sum(durs), "lead": lead})
        t += D
    return out


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inset(box: list[int]) -> str:
    x, y, w, h = box
    return f"inset({y}px {1920 - x - w}px {1080 - y - h}px {x}px round 10px)"


# ---------------------------------------------------------------- scenes
def title_html(sc: dict) -> str:
    sid, D = sc["id"], sc["dur"]
    style = f"""
    #root {{ position: absolute; inset: 0; background: {PAPER}; overflow: hidden; font-family: "IBM Plex Sans", sans-serif; color: {INK}; }}
    .wrap {{ position: absolute; inset: 0 0 100px 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
    .mark {{ font-family: "Newsreader", serif; font-weight: 600; font-size: 168px; line-height: 1; letter-spacing: -0.02em; }}
    .year {{ font-family: "IBM Plex Mono", monospace; font-size: 26px; letter-spacing: 0.18em; color: {MUTED}; margin-top: 26px; text-transform: uppercase; }}
    .line {{ font-family: "Newsreader", serif; font-style: italic; font-weight: 500; font-size: 42px; color: {INK}; margin-top: 30px; max-width: 1300px; line-height: 1.25; }}
    .rule {{ width: 120px; height: 3px; background: {RED}; margin-top: 34px; }}
    .band-bottom {{ position: absolute; left: 0; top: 980px; width: 1920px; height: 100px; background: {PAPER}; border-top: 1px solid {RULE}; }}
    """
    body = f'''<div id="{sid}-w" class="clip" data-start="0" data-duration="{D}" style="position:absolute; inset:0"><div class="wrap">
      <div id="{sid}-mark" class="mark">Trackback</div>
      <div id="{sid}-year" class="year">TrackBack · 2002 · the protocol, revived</div>
      <div id="{sid}-rule" class="rule"></div>
      <div id="{sid}-line" class="line">When a page built on yours, yours got pinged. Now it's the numbers inside a company.</div>
    </div></div>
    <div id="{sid}-bb" class="clip band-bottom" data-start="0" data-duration="{D}" data-layout-ignore style="z-index:15"></div>'''
    tl = [
        f'tl.fromTo("#{sid}-mark", {{ opacity: 0, y: 24, filter: "blur(10px)" }}, {{ opacity: 1, y: 0, filter: "blur(0px)", duration: 0.9, ease: "power3.out" }}, 0.2);',
        f'tl.fromTo("#{sid}-year", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, 1.0);',
        f'tl.fromTo("#{sid}-rule", {{ scaleX: 0 }}, {{ scaleX: 1, duration: 0.5, ease: "power2.out" }}, 1.3);',
        f'tl.fromTo("#{sid}-line", {{ opacity: 0, y: 12 }}, {{ opacity: 1, y: 0, duration: 0.7, ease: "power2.out" }}, {max(1.6, round(D * 0.42, 2))});',
    ]
    return wrap(sid, style, [body], tl)


def scene_html(sc: dict) -> str:
    sid, D, v, lead = sc["id"], sc["dur"], sc["voice"], sc["lead"]
    at = lambda frac: round(lead + frac * v, 2)  # noqa: E731
    parts, tl = [], []
    # frames: a blurred, dimmed copy underneath and a sharp copy clipped to the focus window on top
    focus = sc.get("focus") or [(0.0, FULL)]
    for i, (img, frac) in enumerate(sc["frames"]):
        st = 0.0 if i == 0 else at(frac)
        dur = round(D - st, 2)
        parts.append(f'''<div id="{sid}-f{i}" class="clip frame" data-start="{st}" data-duration="{dur}" style="z-index:{i + 1}">
      <img id="{sid}-f{i}-blur" class="blur" src="assets/frames/{img}" alt="">
      <div class="dim"></div>
      <img id="{sid}-f{i}-img" class="sharp" src="assets/frames/{img}" alt="">
    </div>''')
        if i > 0:
            tl.append(f'tl.fromTo("#{sid}-f{i}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.45, ease: "power2.out" }}, {st});')
        cur = focus[0][1]
        for fr, box in focus:
            if at(fr) <= st:
                cur = box
        tl.append(f'tl.set("#{sid}-f{i}-img", {{ clipPath: "{inset(cur)}" }}, 0);')
        for fr, box in focus:
            t0 = at(fr)
            if t0 > st:
                tl.append(f'tl.to("#{sid}-f{i}-img", {{ clipPath: "{inset(box)}", duration: 0.7, ease: "power2.inOut" }}, {t0});')
        tl.append(f'tl.fromTo("#{sid}-f{i}-img, #{sid}-f{i}-blur", {{ scale: 1 }}, {{ scale: 1.025, duration: {dur}, ease: "none" }}, {st});')
    parts.append(f'<div id="{sid}-bt" class="clip band-top" data-start="0" data-duration="{D}" data-layout-ignore style="z-index:15"></div>')
    parts.append(f'<div id="{sid}-bb" class="clip band-bottom" data-start="0" data-duration="{D}" data-layout-ignore style="z-index:15"></div>')
    parts.append(f'<div id="{sid}-ch" class="clip chapter" data-start="0" data-duration="{D}" style="z-index:20"><div id="{sid}-ch-in" class="chapter-in">{esc(sc["chapter"])}</div></div>')
    tl.append(f'tl.fromTo("#{sid}-ch-in", {{ opacity: 0, y: -10 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }}, 0.25);')
    chips = sc.get("chips", [])
    for j, (text, frac) in enumerate(chips):
        st = at(frac); en = at(chips[j + 1][1]) if j + 1 < len(chips) else D
        parts.append(f'<div id="{sid}-c{j}" class="clip chip" data-start="{st}" data-duration="{round(en - st, 2)}" style="z-index:21"><div id="{sid}-c{j}-in" class="chip-in">{esc(text)}</div></div>')
        tl.append(f'tl.fromTo("#{sid}-c{j}-in", {{ opacity: 0, x: 24 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }}, {st});')
    if sc.get("steps"):
        pills = "".join(f'<span id="{sid}-st{j}" class="pill">{esc(n)}</span>' for j, (n, _) in enumerate(sc["steps"]))
        parts.append(f'<div id="{sid}-steps" class="clip steps" data-start="0" data-duration="{D}" style="z-index:22"><div id="{sid}-steps-in" class="steps-in">{pills}</div></div>')
        tl.append(f'tl.fromTo("#{sid}-steps-in", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, 0.3);')
        for j, (_, frac) in enumerate(sc["steps"]):
            tl.append(f'tl.to("#{sid}-st{j}", {{ backgroundColor: "{INK}", color: "#fff", borderColor: "{INK}", duration: 0.2 }}, {at(frac)});')
    if sc.get("end"):
        st = at(0.3)
        parts.append(f'''<div id="{sid}-end" class="clip endcard" data-start="{st}" data-duration="{round(D - st, 2)}" style="z-index:30"><div id="{sid}-end-in" class="endcard-in">
          <div class="end-kicker">LIVE · OPENS IN DEEP MODE WITH A TOUR</div>
          <div class="end-url">trackback-gamma.vercel.app</div>
          <div class="end-tag">Trackback traces any correction forward.</div>
        </div></div>''')
        tl.append(f'tl.fromTo("#{sid}-end-in", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, {st});')
    style = f"""
    #root {{ position: absolute; inset: 0; background: {PAPER}; overflow: hidden; font-family: "IBM Plex Sans", sans-serif; color: {INK}; }}
    .frame {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; overflow: hidden; }}
    .frame img {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; object-fit: contain; display: block; }}
    .frame .blur {{ filter: blur(7px); }}
    .frame .dim {{ position: absolute; inset: 0; background: rgba(247, 244, 238, 0.58); }}
    .frame .sharp {{ clip-path: inset(0 0 0 0); }}
    .band-top {{ position: absolute; left: 0; top: 0; width: 1920px; height: 64px; background: {PAPER}; border-bottom: 1px solid {RULE}; }}
    .band-bottom {{ position: absolute; left: 0; top: 980px; width: 1920px; height: 100px; background: {PAPER}; border-top: 1px solid {RULE}; }}
    .chapter {{ position: absolute; left: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .chapter-in {{ display: inline-block; font-family: "IBM Plex Mono", monospace; font-size: 22px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK}; }}
    .chip {{ position: absolute; right: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .chip-in {{ display: inline-block; font-family: "IBM Plex Mono", monospace; font-size: 22px; color: {INK}; background: {SURFACE}; border: 1px solid {RULE}; border-left: 4px solid {BLUE}; border-radius: 4px; padding: 7px 14px; }}
    .steps {{ position: absolute; right: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .steps-in {{ display: flex; gap: 10px; }}
    .pill {{ font-family: "IBM Plex Mono", monospace; font-size: 21px; padding: 6px 14px; border: 1px solid {RULE}; border-radius: 999px; background: {SURFACE}; color: {MUTED}; }}
    .endcard {{ position: absolute; inset: 0 0 100px 0; display: flex; align-items: center; justify-content: center; }}
    .endcard-in {{ width: 1240px; background: rgba(255,255,255,0.97); border: 1px solid {INK}; border-radius: 10px; padding: 56px 64px; text-align: center; box-shadow: 0 24px 64px rgba(28,27,25,0.18); }}
    .end-kicker {{ font-family: "IBM Plex Mono", monospace; font-size: 22px; letter-spacing: 0.1em; color: {MUTED}; }}
    .end-url {{ font-family: "Newsreader", serif; font-weight: 600; font-size: 74px; white-space: nowrap; line-height: 1.05; margin: 14px 0 10px; color: {INK}; }}
    .end-tag {{ font-family: "Newsreader", serif; font-style: italic; font-weight: 500; font-size: 40px; color: {MUTED}; }}
    """
    return wrap(sid, style, parts, tl)


def wrap(sid: str, style: str, parts: list[str], tl: list[str]) -> str:
    return f"""<template>
  <style>{FONTS}{style}</style>
  <div id="root" data-composition-id="{sid}" data-width="1920" data-height="1080">
    {chr(10).join('    ' + p for p in parts)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + t for t in tl)}
    window.__timelines["{sid}"] = tl;
  </script>
</template>
"""


# ---------------------------------------------------------------- subtitles track
def caps_html(lay: list[dict], total: float) -> str:
    parts, tl = [], []
    i = 0
    for sc in lay:
        for c in sc["caps"]:
            st = round(sc["start"] + c["start"], 2); dur = c["dur"]
            parts.append(f'<div id="cap{i}" class="clip cap" data-start="{st}" data-duration="{dur}"><div class="cap-wrap"><div id="cap{i}-in" class="cap-in">{esc(c["text"])}</div></div></div>')
            tl.append(f'tl.fromTo("#cap{i}-in", {{ opacity: 0, y: 6 }}, {{ opacity: 1, y: 0, duration: 0.18, ease: "power2.out" }}, {st});')
            tl.append(f'tl.to("#cap{i}-in", {{ opacity: 0, duration: 0.12 }}, {round(st + dur - 0.12, 2)});')
            i += 1
    style = f"""
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cap {{ position: absolute; inset: 0; }}
    .cap-wrap {{ position: absolute; left: 0; right: 0; bottom: 22px; height: 60px; display: flex; align-items: center; justify-content: center; text-align: center; }}
    .cap-in {{ display: inline-block; max-width: 1660px; font-family: "IBM Plex Sans", sans-serif; font-weight: 600; font-size: 38px; line-height: 1.25; color: {INK}; padding: 0 12px; }}
    """
    return f"""<template>
  <style>{FONTS}{style}</style>
  <div id="root" data-composition-id="caps" data-width="1920" data-height="1080" data-layout-allow-caption-zone>
    {chr(10).join('    ' + p for p in parts)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + t for t in tl)}
    window.__timelines["caps"] = tl;
  </script>
</template>
"""


def index_html(lay: list[dict], total: float) -> str:
    hosts = "\n".join(f'      <div id="{s["id"]}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" data-start="{s["start"]}" data-duration="{s["dur"]}" data-track-index="1" data-track-kind="graphics" data-width="1920" data-height="1080"></div>' for s in lay)
    return f"""<!doctype html>
<html lang="en" data-composition-variables='[]'>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      {FONTS}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: {PAPER}; }}
      #root {{ position: relative; width: 1920px; height: 1080px; background: {PAPER}; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1920" data-height="1080">
{hosts}
      <div id="caps" data-composition-id="caps" data-composition-src="compositions/caps.html" data-start="0" data-duration="{total}" data-track-index="2" data-track-kind="captions" data-width="1920" data-height="1080" style="z-index: 50"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


def main() -> None:
    lay = layout()
    total = round(lay[-1]["start"] + lay[-1]["dur"], 2)
    for sc in lay:
        (SCENES_DIR / f"{sc['id']}.html").write_text(title_html(sc) if sc.get("title") else scene_html(sc))
    (SCENES_DIR / "caps.html").write_text(caps_html(lay, total))
    (COMP / "index.html").write_text(index_html(lay, total))
    n = sum(len(s["caps"]) for s in lay)
    (ROOT / "timing.json").write_text(json.dumps({"total": total, "scenes": [{k: s[k] for k in ("id", "start", "dur")} | {"subtitles": [c["text"] for c in s["caps"]]} for s in lay]}, indent=1, ensure_ascii=False))
    print(f"total {total:.1f}s · {n} subtitles · " + " · ".join(f"{s['id']} {s['start']:.1f}+{s['dur']:.1f}" for s in lay))


if __name__ == "__main__":
    main()
