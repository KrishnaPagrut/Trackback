"""Narration with Cartesia (Sonic): one WAV per scene into composition/assets/audio/vo-N.wav, plus durations.json.
Key from .env (CARTESIA_API_KEY). Voice id from argv[1] or CARTESIA_VOICE in .env; `list` prints voices."""
import json, os, ssl, sys, wave, urllib.request
import certifi
CTX = ssl.create_default_context(cafile=certifi.where())
from pathlib import Path
ROOT = Path(__file__).resolve().parent
for line in (ROOT.parent / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
KEY = os.environ.get("CARTESIA_API_KEY")
if not KEY:
    sys.exit("CARTESIA_API_KEY missing from .env")
H = {"X-API-Key": KEY, "Cartesia-Version": "2025-04-16", "Content-Type": "application/json"}

def req(path, body=None):
    r = urllib.request.Request("https://api.cartesia.ai" + path, data=json.dumps(body).encode() if body else None, headers=H, method="POST" if body else "GET")
    with urllib.request.urlopen(r, timeout=120, context=CTX) as resp:
        return resp.read()

if len(sys.argv) > 1 and sys.argv[1] == "list":
    data = json.loads(req("/voices/?limit=100"))
    items = data.get("data", data) if isinstance(data, dict) else data
    for v in items:
        print(v.get("id"), "|", v.get("name"), "|", v.get("language"), "|", (v.get("description") or "")[:90])
    sys.exit()

VOICE = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("CARTESIA_VOICE")
if not VOICE:
    sys.exit("voice id needed: voice.py <voice_id>  (voice.py list to see them)")
MODEL = os.environ.get("CARTESIA_MODEL", "sonic-2")
scenes = json.loads((ROOT / "narration.json").read_text())
out = ROOT / "composition" / "assets" / "audio"; out.mkdir(parents=True, exist_ok=True)
durs = {}
for k, text in scenes.items():
    body = {"model_id": MODEL, "transcript": text, "voice": {"mode": "id", "id": VOICE}, "language": "en",
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}}
    wav = req("/tts/bytes", body)
    p = out / f"vo-{k}.wav"; p.write_bytes(wav)
    import subprocess
    durs[k] = round(float(subprocess.run(["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()), 2)
    print(f"scene {k}: {durs[k]:.2f}s  ({len(text.split())} words)")
(ROOT / "durations.json").write_text(json.dumps(durs, indent=1))
print("total voice:", round(sum(durs.values()), 1), "s")
