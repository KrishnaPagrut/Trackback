"""Prose provenance: Citations API primary, [claim:ID] marker fallback, scripted text in scripted mode."""
from __future__ import annotations

import re
from typing import Any

from .. import config, db
from ..llm import gateway

MARKER = re.compile(r"\[claim:([A-Za-z0-9_\-:.]+)\]")
SYSTEM = ("You write one sentence of finance commentary for a board deck or close memo, exactly as requested. Reply with that single sentence and "
          "nothing else: no preamble, no notes, no alternatives, no explanation. Keep the request's wording and every figure the request states; "
          "add no figure the request does not state (a qualitative claim stays qualitative). Use only the facts in the claim blocks and cite the "
          "blocks the sentence rests on. If part of the request is not supported by the blocks, drop that part silently. Under 40 words.")


def strip_markers(text: str) -> str:
    return re.sub(r"\s*\[claim:[A-Za-z0-9_\-:.]+\]", "", text).strip()


META = re.compile(r"^(suggested sentence|here is the sentence|not supported|note|the claim blocks|only part|i left|i omitted|i could not|citations?:)", re.I)


def clean_sentence(text: str) -> str:
    """Keep the sentence, drop any wrapper the model added (preamble, 'Suggested sentence:', notes, bullet lists)."""
    lines = [l.strip().strip('"\u201c\u201d') for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return text.strip()
    for i, l in enumerate(lines):
        if re.match(r"^(suggested sentence|here is the sentence[^:]*|sentence)\s*:\s*$", l, re.I) and i + 1 < len(lines):
            return lines[i + 1]
        m = re.match(r"^(suggested sentence|here is the sentence[^:]*|sentence)\s*:\s*(.+)$", l, re.I)
        if m:
            return m.group(2).strip()
    good = [l for l in lines if not META.match(l) and not l.startswith(("-", "*", "\u2022"))]
    return (good[0] if good else lines[0]).strip()


def write_sentence(text_request: str, blocks: list[dict], conclusions: dict | None, ctx) -> tuple[str, list[str]]:
    """Returns (text, cited_ids). Every cited id is validated against the blocks (which were validated against the run's reads)."""
    ids = [b["id"] for b in blocks]
    m = gateway.mode()
    # scripted and replay both prefer a recorded response for this exact request (so a build and its replay agree);
    # scripted falls back to the deterministic sentence, replay to the marker path's offline fallback
    if m in ("scripted", "replay") and not _cached_prose_exists(text_request, blocks, ctx):
        # Scripted provider: the work order carries the sentence; markers (if any) select the cited claims, else all blocks are cited.
        cited = [c for c in MARKER.findall(text_request) if c in ids] or ids
        return strip_markers(text_request), cited
    path = _citations_path()
    if path == "citations":
        try:
            return _via_citations(text_request, blocks, ctx)
        except Exception as e:  # noqa: BLE001
            db.log_event("citations_fallback", f"citations path failed, using markers: {e}", ts=ctx.pinned_at, run_id=ctx.run_id)
    return _via_markers(text_request, blocks, ctx)


def _cached_prose_exists(text_request: str, blocks: list[dict], ctx) -> bool:
    for purpose in ("prose_citations", "prose_markers"):
        req = _request(purpose, text_request, blocks)
        key = gateway.cache_key(config.AGENT_MODEL, SYSTEM, req["messages"], None, req["params"], ctx.pinned_at)
        if db.q1("SELECT 1 FROM llm_cache WHERE cache_key=?", (key,)):
            return True
    return False


def _citations_path() -> str:
    import os
    return os.environ.get("TRACKBACK_PROSE_PATH", "citations")


def _request(purpose: str, text_request: str, blocks: list[dict]) -> dict:
    if purpose == "prose_citations":
        document = {"type": "document", "source": {"type": "content", "content": [{"type": "text", "text": b["text"]} for b in blocks]},
                    "title": "claims", "citations": {"enabled": True}}
        msgs = [{"role": "user", "content": [document, {"type": "text", "text": f"Write the sentence: {text_request}. Cite the claim blocks you rely on."}]}]
        return {"messages": msgs, "params": {"max_tokens": 600, "effort": "low", "citations": True}}
    listing = "\n".join(f"[{i}] id={b['id']}: {b['text']}" for i, b in enumerate(blocks))
    msgs = [{"role": "user", "content": f"Claims:\n{listing}\n\nWrite the sentence: {text_request}. After every fact, append a marker [claim:ID] with the id of the claim it rests on."}]
    return {"messages": msgs, "params": {"max_tokens": 600, "effort": "low"}}


def _via_citations(text_request: str, blocks: list[dict], ctx) -> tuple[str, list[str]]:
    req = _request("prose_citations", text_request, blocks)

    def live(_):
        from ..llm import anthropic_provider
        return anthropic_provider.call_citations(model=config.AGENT_MODEL, system=SYSTEM, blocks=blocks, instruction=req["messages"][0]["content"][1]["text"], params=req["params"])

    key = gateway.cache_key(config.AGENT_MODEL, SYSTEM, req["messages"], None, req["params"], ctx.pinned_at)
    cached = db.q1("SELECT response_json FROM llm_cache WHERE cache_key=?", (key,))
    if cached:
        import json
        resp = json.loads(cached["response_json"])
    else:
        if gateway.mode() != "record":
            raise gateway.CacheMiss("no cached citations response")
        resp = live(None)
        gateway._store(key, {"purpose": "prose_citations", **req, "pinned_at": ctx.pinned_at}, resp, config.AGENT_MODEL)
    text, cited = "", []
    for b in resp.get("content", []):
        if b.get("type") != "text":
            continue
        text += b.get("text", "")
        for c in b.get("citations") or []:
            if c.get("type") == "content_block_location":
                for i in range(int(c["start_block_index"]), int(c["end_block_index"])):
                    if 0 <= i < len(blocks) and blocks[i]["id"] not in cited:
                        cited.append(blocks[i]["id"])
    if not text.strip():
        raise RuntimeError("empty citations response")
    return clean_sentence(text), cited


def _via_markers(text_request: str, blocks: list[dict], ctx) -> tuple[str, list[str]]:
    req = _request("prose_markers", text_request, blocks)
    resp, key, hit = gateway.complete(model=config.AGENT_MODEL, system=SYSTEM, messages=req["messages"], tools=None, params=req["params"],
                                      pinned_at=ctx.pinned_at, purpose="prose_markers")
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    ids = [b["id"] for b in blocks]
    cited = []
    for c in MARKER.findall(text):
        if c in ids and c not in cited:
            cited.append(c)
    return strip_markers(text), cited


# ---- numeric slots ----------------------------------------------------------------------------------------------
SLOT = re.compile(r"\{slot:([A-Za-z0-9_]+)\}")


def _display_forms(v: float) -> list[str]:
    from ..core.judge import _displays
    return _displays(v)


def templatize(text: str, values: dict[str, float | None]) -> str | None:
    """Replace the first occurrence of each cited artifact's displayed value with a {slot:id}; None if no figure matched."""
    t = text
    hit = False
    for aid, v in values.items():
        if v is None:
            continue
        for d in sorted(_display_forms(v), key=len, reverse=True):   # most precise form first; never match a prefix of a longer number ("3" in "3.00x")
            m = re.search(r"(?<![\d.])" + re.escape(d) + r"(?!\.?\d)", t)
            if m:
                t = t[:m.start()] + "{slot:" + aid + "|" + d + "}" + t[m.end():]
                hit = True
                break
    return t if hit else None


def render_template(template: str, values: dict[str, float | None], fallback: str) -> str:
    from ..core.judge import _fmt_like

    def sub(m):
        aid, sample = m.group(1), m.group(2)
        v = values.get(aid)
        if v is None:
            return sample
        return _fmt_like(sample, 0.0, v)
    try:
        return re.sub(r"\{slot:([A-Za-z0-9_]+)\|([^}]*)\}", sub, template)
    except Exception:  # noqa: BLE001
        return fallback
