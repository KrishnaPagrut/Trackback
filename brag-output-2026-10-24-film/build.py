"""Generate the HyperFrames composition for the demo film from narration.json, the frames, and (when present) the Cartesia
voice clips (durations.json) and word timings (words.json from `hyperframes transcribe`). Without them it uses estimates so the
visuals can be checked before the voice exists. Re-run after every change: it rewrites index.html and compositions/*.html."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMP = ROOT / "composition"
SCENES_DIR = COMP / "compositions"
SCENES_DIR.mkdir(exist_ok=True)
NARR = json.loads((ROOT / "narration.json").read_text())
DURS = json.loads((ROOT / "durations.json").read_text()) if (ROOT / "durations.json").exists() else {}
WORDS = json.loads((ROOT / "words.json").read_text()) if (ROOT / "words.json").exists() else {}
WPS = 2.75  # Cartesia Sonic pace, used only until durations.json exists

PAPER, SURFACE, INK, MUTED, RULE, RED, GREEN, BLUE = "#F7F4EE", "#FFFFFF", "#1C1B19", "#6B675F", "#E3DED4", "#C62828", "#2E7D32", "#1F5FBF"

# ---- the storyboard: frames (with the narration fraction at which a cut lands), chapter label, overlays
# spot = [x, y, w, h] in 1920x1080 frame pixels, drawn at narration fraction `at`
SB = [
    dict(id="s1", chapter="1 · Meet Tidewall", frames=[("d-idle.png", 0.0)],
         chips=[("6 gyms · California", 0.05), ("~$40M a year", 0.22), ("Net leverage must stay under 3.00x", 0.42), ("2 AI agents · Maya (FP&A) · Dana (Controller)", 0.72)]),
    dict(id="s2", chapter="2 · The source", frames=[("d-source-hover.png", 0.0)], zoom=dict(x=560, y=150, s=1.6, at=0.1),
         chips=[("Billing export, March · captured April 9 · version 1", 0.35)]),
    dict(id="s3", chapter="3 · Layer one", frames=[("s-reveal-1.png", 0.0)],
         chips=[("Close Accountant closes Q1", 0.05), ("$236,000 released · Q1 revenue $10.4M · TTM EBITDA $5.6M", 0.3), ("51 pieces of work, each with a read receipt", 0.7)]),
    dict(id="s4", chapter="4 · Layers two and three", frames=[("s-reveal-2.png", 0.0), ("s-reveal-3.png", 0.5)],
         chips=[("Leverage 2.95x · certificate sent May 15 · bonuses · tax", 0.08), ("Maya's board deck, same tools, same receipts", 0.55), ("188 pieces of work · 305 receipts", 0.85)]),
    dict(id="s5", chapter="5 · July 8: Trackback is switched on", frames=[("s-notice2.png", 0.0), ("s-notice.png", 0.55)],
         spots=[([815, 176, 768, 54], 0.62)], chips=[("$118,000 counted twice across five gyms", 0.45), ("Leverage 2.95x → 3.03x, crosses 3.00x", 0.68)]),
    dict(id="s6", chapter="6 · The reconciliation", frames=[("d-ripple.png", 0.0), ("d-cert-path.png", 0.62)],
         spots=[([520, 66, 300, 36], 0.74)],
         steps=[("diff", 0.0), ("reach", 0.1), ("recompute", 0.25), ("materiality", 0.36), ("prose", 0.56), ("verdicts", 0.74)]),
    dict(id="s7", chapter="7 · One message per agent", frames=[("s-ping-ca.png", 0.0), ("s-reply-cc2.png", 0.5), ("s-reply-cc.png", 0.8)],
         chips=[("Maya gets the same message as a notice", 0.12), ("Corrected certificate drafted for the CFO", 0.6), ("Cash forecast: skipped", 0.9)]),
    dict(id="s8", chapter="8 · Jade, the reviewer", frames=[("s-reply-ra.png", 0.0)]),
    dict(id="s9", chapter="9 · The right person says no", frames=[("d-approvals.png", 0.0), ("d-selfapprove.png", 0.72)],
         chips=[("Certificate → CFO · bonuses → HR · entries → Controller", 0.05), ("Q1 is locked: rejected, re-drafted in June", 0.4), ("CHECK (proposer <> approver)", 0.8)]),
    dict(id="s10", chapter="10 · It learns", frames=[("s-jade.png", 0.0)],
         chips=[("Regression gate: 71 of 72 past claims pass · 0 newly failing", 0.3), ("Held-out cases: v1 80% → v2 100%", 0.78)]),
    dict(id="s11", chapter="11 · Time travel", frames=[("s-travel.png", 0.0)]),
    dict(id="s12", chapter="12 · Go look", frames=[("d-idle-tour.png", 0.0)], end=True),
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


def voice_len(k: str) -> float:
    return float(DURS.get(k) or len(NARR[k].split()) / WPS)


def layout() -> list[dict]:
    t = 0.0
    out = []
    for sc in SB:
        k = sc["id"][1:]
        v = voice_len(k)
        lead = 0.3                       # the picture lands a beat before the voice
        tail = 0.5 if not sc.get("end") else 1.5
        d = round(lead + v + tail, 2)
        out.append({**sc, "k": k, "start": round(t, 2), "dur": d, "voice": v, "lead": lead})
        t += d
    return out


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def scene_html(sc: dict) -> str:
    sid, D, v, lead = sc["id"], sc["dur"], sc["voice"], sc["lead"]
    at = lambda frac: round(lead + frac * v, 2)  # noqa: E731
    parts, tl = [], []
    # frames
    for i, (img, frac) in enumerate(sc["frames"]):
        st = 0.0 if i == 0 else at(frac)
        dur = round(D - st, 2)
        parts.append(f'<div id="{sid}-f{i}" class="clip frame" data-start="{st}" data-duration="{dur}" style="z-index:{i + 1}"><img id="{sid}-f{i}-img" src="assets/frames/{img}" alt=""></div>')
        if i == 0:
            z = sc.get("zoom")
            if z:
                ox, oy = z["x"] / 1920 * 100, z["y"] / 1080 * 100
                tl.append(f'tl.set("#{sid}-f0-img", {{ transformOrigin: "{ox:.1f}% {oy:.1f}%" }}, 0);')
                tl.append(f'tl.fromTo("#{sid}-f0-img", {{ scale: 1 }}, {{ scale: {z["s"]}, duration: 1.4, ease: "power2.inOut" }}, {at(z["at"])});')
            else:
                tl.append(f'tl.fromTo("#{sid}-f0-img", {{ scale: 1 }}, {{ scale: 1.035, duration: {D}, ease: "none" }}, 0);')
        else:
            tl.append(f'tl.fromTo("#{sid}-f{i}-img", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, {st});')
            tl.append(f'tl.fromTo("#{sid}-f{i}-img", {{ scale: 1 }}, {{ scale: 1.03, duration: {dur}, ease: "none" }}, {st});')
    # paper bands over the app's own header and footer: the film's chrome lives there, never over the UI
    parts.append(f'<div id="{sid}-bt" class="clip band-top" data-start="0" data-duration="{D}" data-layout-ignore style="z-index:15"></div>')
    parts.append(f'<div id="{sid}-bb" class="clip band-bottom" data-start="0" data-duration="{D}" data-layout-ignore style="z-index:15"></div>')
    # chapter label, left of the top band
    parts.append(f'<div id="{sid}-ch" class="clip chapter" data-start="0" data-duration="{D}" style="z-index:20"><div id="{sid}-ch-in" class="chapter-in">{esc(sc["chapter"])}</div></div>')
    tl.append(f'tl.fromTo("#{sid}-ch-in", {{ opacity: 0, y: -10 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power2.out" }}, 0.25);')
    # chips: one slot at the right of the top band; each replaces the one before
    chips = sc.get("chips", [])
    for j, (text, frac) in enumerate(chips):
        st = at(frac); en = at(chips[j + 1][1]) if j + 1 < len(chips) else D
        parts.append(f'<div id="{sid}-c{j}" class="clip chip" data-start="{st}" data-duration="{round(en - st, 2)}" style="z-index:21"><div id="{sid}-c{j}-in" class="chip-in">{esc(text)}</div></div>')
        tl.append(f'tl.fromTo("#{sid}-c{j}-in", {{ opacity: 0, x: 24 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }}, {st});')
    # reconciliation steps (scene 6): a row of pills in the band, each lighting when named
    if sc.get("steps"):
        pills = "".join(f'<span id="{sid}-st{j}" class="pill">{esc(n)}</span>' for j, (n, _) in enumerate(sc["steps"]))
        parts.append(f'<div id="{sid}-steps" class="clip steps" data-start="0" data-duration="{D}" style="z-index:22"><div id="{sid}-steps-in" class="steps-in">{pills}</div></div>')
        tl.append(f'tl.fromTo("#{sid}-steps-in", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3 }}, 0.3);')
        for j, (_, frac) in enumerate(sc["steps"]):
            tl.append(f'tl.to("#{sid}-st{j}", {{ backgroundColor: "{INK}", color: "#fff", borderColor: "{INK}", duration: 0.2 }}, {at(frac)});')
    # spots: an outline that draws attention to a region
    for j, (box, frac) in enumerate(sc.get("spots", [])):
        x, y, w, h = box
        st = at(frac)
        parts.append(f'<div id="{sid}-sp{j}" class="clip spot" data-start="{st}" data-duration="{round(D - st, 2)}" data-layout-ignore style="z-index:19; left:{x - 10}px; top:{y - 10}px; width:{w + 20}px; height:{h + 20}px"><div id="{sid}-sp{j}-in" class="spot-in"></div></div>')
        tl.append(f'tl.fromTo("#{sid}-sp{j}-in", {{ opacity: 0, scale: 1.06 }}, {{ opacity: 1, scale: 1, duration: 0.35, ease: "power2.out" }}, {st});')
    # end card (scene 12)
    if sc.get("end"):
        st = at(0.08)
        parts.append(f'''<div id="{sid}-end" class="clip endcard" data-start="{st}" data-duration="{round(D - st, 2)}" style="z-index:30"><div id="{sid}-end-in" class="endcard-in">
          <div class="end-kicker">LIVE · OPENS IN DEEP MODE WITH A TOUR</div>
          <div class="end-url">trackback-gamma.vercel.app</div>
          <div class="end-tag">Trackback traces any correction forward.</div>
          <div class="end-seat">Trackback does the senior close accountant's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign.</div>
        </div></div>''')
        tl.append(f'tl.fromTo("#{sid}-end-in", {{ opacity: 0, y: 16 }}, {{ opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }}, {st});')
    style = f"""
    #root {{ position: absolute; inset: 0; background: {PAPER}; overflow: hidden; font-family: "IBM Plex Sans", sans-serif; color: {INK}; }}
    .frame {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; overflow: hidden; }}
    .frame img {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; object-fit: contain; display: block; }}
    .band-top {{ position: absolute; left: 0; top: 0; width: 1920px; height: 64px; background: {PAPER}; border-bottom: 1px solid {RULE}; }}
    .band-bottom {{ position: absolute; left: 0; top: 1004px; width: 1920px; height: 76px; background: {PAPER}; border-top: 1px solid {RULE}; }}
    .chapter {{ position: absolute; left: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .chapter-in {{ display: inline-block; font-family: "IBM Plex Mono", monospace; font-size: 22px; letter-spacing: 0.08em; text-transform: uppercase; color: {INK}; }}
    .chip {{ position: absolute; right: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .chip-in {{ display: inline-block; font-family: "IBM Plex Mono", monospace; font-size: 22px; color: {INK}; background: {SURFACE}; border: 1px solid {RULE}; border-left: 4px solid {BLUE}; border-radius: 4px; padding: 7px 14px; }}
    .steps {{ position: absolute; right: 48px; top: 0; height: 64px; display: flex; align-items: center; }}
    .steps-in {{ display: flex; gap: 10px; }}
    .pill {{ font-family: "IBM Plex Mono", monospace; font-size: 21px; padding: 6px 14px; border: 1px solid {RULE}; border-radius: 999px; background: {SURFACE}; color: {MUTED}; }}
    .spot {{ position: absolute; }}
    .spot-in {{ position: absolute; inset: 0; border: 3px solid {BLUE}; border-radius: 8px; box-shadow: 0 0 0 6px rgba(31,95,191,0.14); }}
    .endcard {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }}
    .endcard-in {{ width: 1240px; background: rgba(255,255,255,0.97); border: 1px solid {INK}; border-radius: 10px; padding: 56px 64px; text-align: center; box-shadow: 0 24px 64px rgba(28,27,25,0.18); }}
    .end-kicker {{ font-family: "IBM Plex Mono", monospace; font-size: 22px; letter-spacing: 0.1em; color: {MUTED}; }}
    .end-url {{ font-family: "Newsreader", serif; font-weight: 600; font-size: 74px; white-space: nowrap; line-height: 1.05; margin: 14px 0 10px; color: {INK}; }}
    .end-tag {{ font-family: "Newsreader", serif; font-style: italic; font-weight: 500; font-size: 40px; color: {MUTED}; }}
    .end-seat {{ font-size: 24px; line-height: 1.4; margin-top: 26px; color: {INK}; }}
    """
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


def caption_groups(lay: list[dict]) -> list[dict]:
    """Groups of 4-6 words with absolute times: from words.json when the voice has been transcribed, else spread over the clip."""
    groups = []
    for sc in lay:
        k = sc["k"]; base = sc["start"] + sc["lead"]
        words = WORDS.get(k)
        toks = NARR[k].split()
        if words and len(words) == len(toks):           # script text, transcript timing, matched by position
            seq = [(t, base + w["start"], base + w["end"]) for t, w in zip(toks, words)]
        elif words:                                       # counts differ: spread the script over the spoken span
            s0, e0 = base + words[0]["start"], base + words[-1]["end"]; n = len(toks)
            seq = [(t, s0 + (e0 - s0) * i / n, s0 + (e0 - s0) * (i + 1) / n) for i, t in enumerate(toks)]
        else:
            toks = NARR[k].split(); n = len(toks); v = sc["voice"]
            seq = [(t, base + v * i / n, base + v * (i + 1) / n) for i, t in enumerate(toks)]
        cur: list = []
        for i, (text, s, e) in enumerate(seq):
            cur.append((text, s, e))
            end_sentence = bool(re.search(r"[.?!:;]$", text))
            if len(cur) >= 6 or (len(cur) >= 3 and end_sentence) or i == len(seq) - 1:
                groups.append({"text": " ".join(c[0] for c in cur), "start": round(cur[0][1], 2), "end": round(cur[-1][2] + 0.15, 2)})
                cur = []
    # no overlaps
    for a, b in zip(groups, groups[1:]):
        if a["end"] > b["start"]:
            a["end"] = round(b["start"] - 0.02, 2)
    return groups


def caps_html(groups: list[dict], total: float) -> str:
    parts, tl = [], []
    for i, g in enumerate(groups):
        st = max(0.15, g["start"]); dur = round(max(0.4, g["end"] - st), 2)
        parts.append(f'<div id="cap{i}" class="clip cap" data-start="{st}" data-duration="{dur}"><div class="cap-wrap"><div id="cap{i}-in" class="cap-in"><span class="cap-text">{esc(g["text"])}</span></div></div></div>')
        tl.append(f'tl.fromTo("#cap{i}-in", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12 }}, {st});')
        tl.append(f'tl.to("#cap{i}-in", {{ opacity: 0, duration: 0.1 }}, {round(st + dur - 0.1, 2)});')
    style = f"""
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cap {{ position: absolute; inset: 0; }}
    .cap-wrap {{ position: absolute; left: 0; right: 0; bottom: 14px; text-align: center; }}
    .cap-in {{ display: inline-block; max-width: 1600px; font-family: "IBM Plex Sans", sans-serif; font-weight: 600; font-size: 34px; line-height: 1.3; color: {INK}; padding: 4px 12px; }}
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
    audio = [f'      <audio id="bed" class="clip" src="assets/audio/bed.mp3" data-start="0" data-duration="{total}" data-volume="0.14" data-fade-in="0.4" data-fade-out="1.5" data-track-index="3"></audio>']
    for s in lay:
        f = COMP / "assets" / "audio" / f"vo-{s['k']}.wav"
        if f.exists():
            audio.append(f'      <audio id="vo{s["k"]}" class="clip" src="assets/audio/vo-{s["k"]}.wav" data-start="{round(s["start"] + s["lead"], 2)}" data-volume="1" data-track-index="4"></audio>')
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
{chr(10).join(audio)}
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
        (SCENES_DIR / f"{sc['id']}.html").write_text(scene_html(sc))
    groups = caption_groups(lay)
    (SCENES_DIR / "caps.html").write_text(caps_html(groups, total))
    (COMP / "index.html").write_text(index_html(lay, total))
    (ROOT / "timing.json").write_text(json.dumps({"total": total, "scenes": [{k: s[k] for k in ("id", "start", "dur", "voice")} for s in lay], "captions": len(groups)}, indent=1))
    print(f"total {total:.1f}s · " + " · ".join(f"{s['id']} {s['start']:.1f}+{s['dur']:.1f}" for s in lay) + f" · {len(groups)} caption groups · voice {'measured' if DURS else 'estimated'}")


if __name__ == "__main__":
    main()
