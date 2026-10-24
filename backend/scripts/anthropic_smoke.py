"""M0: one plain call + one Citations API call (custom-content document). Logs the outcome.
Run: backend/.venv/bin/python backend/scripts/anthropic_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import config  # noqa: E402

try:
    import anthropic
except ImportError:
    print("anthropic SDK missing"); sys.exit(2)

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("NO_KEY: ANTHROPIC_API_KEY is not set (put it in .env). Skipping live test.")
    sys.exit(3)

client = anthropic.Anthropic()

r = client.messages.create(model=config.AGENT_MODEL, max_tokens=200,
                           messages=[{"role": "user", "content": "Reply with the single word: ok"}])
print("plain:", [b.text for b in r.content if b.type == "text"], r.stop_reason)

claims = [
    {"id": "c_rev_q1", "text": "Q1 2026 membership revenue was $7,420,000."},
    {"id": "c_route_q1", "text": "Q1 2026 route-setting contract labor was $142,000."},
    {"id": "c_route_q4", "text": "Q4 2025 route-setting contract labor was $173,000."},
]
doc = {
    "type": "document",
    "source": {"type": "content", "content": [{"type": "text", "text": c["text"]} for c in claims]},
    "title": "claims",
    "citations": {"enabled": True},
}
r2 = client.messages.create(
    model=config.AGENT_MODEL, max_tokens=400,
    messages=[{"role": "user", "content": [doc, {"type": "text", "text": "Write one sentence comparing route-setting cost quarter over quarter. Cite the claims you use."}]}],
)
out = []
for b in r2.content:
    if b.type == "text":
        cites = [(c.type, getattr(c, "start_block_index", None), getattr(c, "end_block_index", None)) for c in (b.citations or [])]
        out.append({"text": b.text, "citations": cites})
print("citations:", json.dumps(out, indent=1))
ok = any(o["citations"] for o in out)
print("CITATIONS_OK" if ok else "CITATIONS_EMPTY")
