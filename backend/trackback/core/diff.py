"""Claim diff: load a new source version and classify every claim as changed / unchanged / added / removed."""
from __future__ import annotations

import json

from .. import config
from . import claims as CL, db


def apply_version(correction_id: str, source_id: str, version_id: str, body: dict, tx_time: str, *, document_date: str | None,
                  supersedes: str | None, kind: str, knowable_at: str, booking_period: str | None, note: str) -> dict:
    """Insert the new version + claim versions, write the corrections row and claim_diffs. Returns the diff summary."""
    src = db.q1("SELECT kind FROM sources WHERE source_id=?", (source_id,))
    if src is None:
        raise KeyError(f"unknown source {source_id}")
    old = supersedes or (db.source_version_as_of(source_id, tx_time) or {"version_id": None})["version_id"]
    old_claims = {r["claim_id"]: dict(r) for r in db.q("SELECT * FROM claim_versions WHERE source_version_id=?", (old,))} if old else {}
    loaded = CL.load_version(source_id, version_id, src["kind"], body, tx_time, document_date=document_date, supersedes=old, correction_id=correction_id)
    tx = db.norm_ts(tx_time)
    diffs = []
    seen = set()
    for c in loaded:
        seen.add(c["claim_id"])
        prev = old_claims.get(c["claim_id"])
        if prev is None:
            change = "added"
        elif _same(prev, c):
            change = "unchanged"
        else:
            change = "changed"
        diffs.append({"correction_id": correction_id, "claim_id": c["claim_id"], "old_cv": prev["claim_version_id"] if prev else None, "new_cv": c["claim_version_id"], "change": change})
    for cid_, prev in old_claims.items():
        if cid_ not in seen:
            db.close_tx("claim_versions", "claim_id", cid_, tx)
            diffs.append({"correction_id": correction_id, "claim_id": cid_, "old_cv": prev["claim_version_id"], "new_cv": None, "change": "removed"})
    for d in diffs:
        db.insert("claim_diffs", d)
    if db.q1("SELECT 1 FROM corrections WHERE correction_id=?", (correction_id,)) is None:
        db.insert("corrections", {"correction_id": correction_id, "source_id": source_id, "old_version": old, "new_version": version_id, "kind": kind,
                                  "knowable_at": db.norm_ts(knowable_at), "materiality_verdict": None, "booking_period": booking_period, "tx_time": tx, "note": note})
    db.commit()
    summary = {"changed": [d for d in diffs if d["change"] == "changed"], "unchanged": [d for d in diffs if d["change"] == "unchanged"],
               "added": [d for d in diffs if d["change"] == "added"], "removed": [d for d in diffs if d["change"] == "removed"], "old_version": old, "new_version": version_id}
    return summary


def _same(a: dict, b: dict) -> bool:
    if a["value_num"] is None and b["value_num"] is None:
        return (a["value_text"] or "") == (b["value_text"] or "")
    if a["value_num"] is None or b["value_num"] is None:
        return False
    return abs(float(a["value_num"]) - float(b["value_num"])) < 1e-9


def diffs_for(correction_id: str) -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM claim_diffs WHERE correction_id=?", (correction_id,))]
