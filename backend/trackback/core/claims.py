"""Turn a source-version body into claims. Stable claim key: (source, entity, line_item, period, unit)."""
from __future__ import annotations

import json
from typing import Any

from . import db


def claim_id_for(source_id: str, entity: str, line_item: str, period_start: str, period_end: str, unit: str) -> str:
    return "c_" + db.hid("claim", source_id, entity, line_item, period_start, period_end, unit)


def render_text(body: dict) -> str:
    """Human-readable rendering of a body; claims list their value lines so spans can be recorded."""
    if "text" in body and body.get("text"):
        return body["text"]
    lines = [body.get("title", "")]
    if body.get("rows"):
        cols = list(body["rows"][0].keys())
        lines.append(",".join(cols))
        for r in body["rows"]:
            lines.append(",".join(str(r[c]) for c in cols))
    for c in body.get("claims", []):
        ent = f" [{c['entity']}]" if c.get("entity") else ""
        per = c.get("period_start") or ""
        v = c.get("value_text") if c.get("value_num") is None else c["value_num"]
        lines.append(f"{c['line_item']}{ent} {per}: {v}")
    return "\n".join(lines)


def extract(source_id: str, kind: str, body: dict) -> list[dict[str, Any]]:
    """Return claim dicts with keys entity, account, line_item, unit, period_start, period_end, value_num, value_text, span."""
    text = render_text(body)
    out: list[dict[str, Any]] = []
    if kind == "billing_export":
        agg: dict[tuple, float] = {}
        for r in body["rows"]:
            key = (r["gym"], r["line"], r["period"])
            agg[key] = agg.get(key, 0.0) + float(r["amount"])
        for (gym, line, period), amt in sorted(agg.items()):
            out.append({"entity": gym, "account": "4000", "line_item": line, "unit": "USD",
                        "period_start": period + "-01", "period_end": _month_end(period), "value_num": round(amt, 2), "value_text": None})
    else:
        for c in body.get("claims", []):
            out.append({"entity": c.get("entity") or "", "account": c.get("account"), "line_item": c["line_item"],
                        "unit": c.get("unit", "USD"), "period_start": c.get("period_start") or "", "period_end": c.get("period_end") or "",
                        "value_num": c.get("value_num"), "value_text": c.get("value_text")})
    for c in out:
        c["claim_id"] = claim_id_for(source_id, c["entity"], c["line_item"], c["period_start"], c["period_end"], c["unit"])
        needle = None
        if c["value_num"] is not None:
            v = c["value_num"]
            needle = str(int(v)) if float(v).is_integer() else str(v)
        elif c["value_text"]:
            needle = str(c["value_text"])[:40]
        idx = text.find(needle) if needle else -1
        c["span_start"], c["span_end"] = (idx, idx + len(needle)) if idx >= 0 else (None, None)
    return out


def period_bounds(period: str | None) -> tuple[str, str]:
    """'YYYY-MM' -> month; 'YYYY-Qn' -> quarter; 'YYYY' -> year; 'YYYY-Hn' -> half; a full date -> that day."""
    if not period:
        return "", ""
    if len(period) == 7 and period[5] == "Q":
        y, qn = int(period[:4]), int(period[-1])
        return f"{y}-{(qn-1)*3+1:02d}-01", _month_end(f"{y}-{qn*3:02d}")
    if len(period) == 7 and period[5] == "H":
        y, h = int(period[:4]), int(period[-1])
        return (f"{y}-01-01", f"{y}-06-30") if h == 1 else (f"{y}-07-01", f"{y}-12-31")
    if len(period) == 7:
        return period + "-01", _month_end(period)
    if len(period) == 4:
        return f"{period}-01-01", f"{period}-12-31"
    return period, period


def _month_end(period: str) -> str:
    import calendar
    y, m = int(period[:4]), int(period[5:7])
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def load_version(source_id: str, version_id: str, kind: str, body: dict, tx_from: str, *,
                 document_date: str | None, supersedes: str | None, correction_id: str | None) -> list[dict]:
    """Insert a source version plus its claim versions; close the superseded claim versions."""
    import hashlib
    raw = json.dumps(body, sort_keys=True)
    tx = db.norm_ts(tx_from)
    db.insert("source_versions", {"version_id": version_id, "source_id": source_id, "body": raw,
                                  "content_hash": hashlib.sha256(raw.encode()).hexdigest()[:16], "document_date": document_date,
                                  "tx_from": tx, "tx_to": "9999-12-31T00:00:00+00:00",
                                  "supersedes": supersedes, "correction_id": correction_id})
    if supersedes:
        db.close_tx("source_versions", "version_id", supersedes, tx)
    claims = extract(source_id, kind, body)
    for c in claims:
        if db.q1("SELECT 1 FROM claims WHERE claim_id=?", (c["claim_id"],)) is None:
            db.insert("claims", {"claim_id": c["claim_id"], "source_id": source_id, "entity": c["entity"], "account": c["account"],
                                 "line_item": c["line_item"], "unit": c["unit"], "period_start": c["period_start"], "period_end": c["period_end"]})
        prev = db.claim_version_current(c["claim_id"])
        cv_id = "cv_" + db.hid("cv", c["claim_id"], version_id)
        if prev is not None:
            db.close_tx("claim_versions", "claim_id", c["claim_id"], tx)
        db.insert("claim_versions", {"claim_version_id": cv_id, "claim_id": c["claim_id"], "source_version_id": version_id,
                                     "value_num": c["value_num"], "value_text": c["value_text"], "span_start": c["span_start"],
                                     "span_end": c["span_end"], "valid_from": c["period_start"] or None, "valid_to": c["period_end"] or None,
                                     "tx_from": tx, "tx_to": "9999-12-31T00:00:00+00:00"})
        c["claim_version_id"] = cv_id
        c["prev_claim_version_id"] = prev["claim_version_id"] if prev is not None else None
    return claims
