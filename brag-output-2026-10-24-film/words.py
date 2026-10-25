"""Word timings for the captions: transcribe each Cartesia clip with HyperFrames (whisper, local) and write words.json
keyed by scene, times relative to the clip. Run after voice.py; build.py picks words.json up automatically."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent; COMP = ROOT / "composition"
out = {}
for wav in sorted((COMP / "assets" / "audio").glob("vo-*.wav"), key=lambda p: int(p.stem.split("-")[1])):
    k = wav.stem.split("-")[1]
    r = subprocess.run(["npx", "hyperframes", "transcribe", str(wav.relative_to(COMP)), "--json", "--model", "small.en"], cwd=COMP, capture_output=True, text=True)
    raw = r.stdout
    try:
        d = json.loads(raw[raw.index("{"):])
    except Exception:
        print(f"scene {k}: transcribe failed\n{r.stdout[-600:]}\n{r.stderr[-600:]}"); sys.exit(1)
    if isinstance(d, dict) and d.get("transcriptPath"):
        d = json.loads(Path(d["transcriptPath"]).read_text())
    if isinstance(d, list):
        d = {"words": d} if d and ("start" in d[0] and ("text" in d[0] or "word" in d[0])) else {"segments": d}
    words = d.get("words")
    if words is None and d.get("segments"):
        words = [w for s in d["segments"] for w in s.get("words", [])]
    if words is None and d.get("transcript"):
        t = d["transcript"]; words = t.get("words") or [w for s in t.get("segments", []) for w in s.get("words", [])]
    words = [{"text": (w.get("text") or w.get("word") or "").strip(), "start": float(w["start"]), "end": float(w["end"])} for w in (words or []) if (w.get("text") or w.get("word") or "").strip()]
    words = [w for w in words if not set(w["text"]) <= set("♪�")]
    out[k] = words
    print(f"scene {k}: {len(words)} words, {words[0]['start']:.2f}–{words[-1]['end']:.2f}s" if words else f"scene {k}: no words")
(ROOT / "words.json").write_text(json.dumps(out))
print("wrote words.json")
