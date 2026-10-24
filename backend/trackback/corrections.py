"""Apply, refuse and execute: the glue between the diff, the engine, the ledger and approvals."""
from __future__ import annotations

import json

from . import approvals, config, db, graph, ledger, scenarios
from .core import diff, fence, propagate, waves


def apply_correction(correction_id: str, *, body: dict | None = None, tx_time: str | None = None, kind: str | None = None, knowable_at: str | None = None,
                     source_id: str | None = None, version_id: str | None = None, note: str | None = None, booking_period: str | None = None, dry_run: bool = False) -> dict:
    meta = scenarios.CORRECTIONS.get(correction_id, {})
    source_id = source_id or meta["source_id"]
    if body is None:
        gen = scenarios.load_body(source_id, meta["version"], correction_id)
        body = gen["body"]; version_id = version_id or gen["version_id"]; document_date = gen.get("document_date")
    else:
        document_date = body.get("document_date")
        version_id = version_id or f"{source_id}@{correction_id}"
    tx_time = tx_time or meta["tx_time"]
    kind = kind or meta["kind"]
    knowable_at = knowable_at or meta["knowable_at"]
    note = note if note is not None else meta.get("note", "")
    booking_period = booking_period or meta.get("booking_period")
    if dry_run:
        return _dry_run(correction_id, source_id, version_id, body, tx_time, kind, knowable_at, booking_period, note)
    if db.q1("SELECT 1 FROM corrections WHERE correction_id=?", (correction_id,)):
        raise ValueError(f"{correction_id} already applied")
    summary = diff.apply_version(correction_id, source_id, version_id, body, tx_time, document_date=document_date, supersedes=None, kind=kind, knowable_at=knowable_at,
                                 booking_period=booking_period, note=note)
    db.log_event("correction_received", f"RECALL NOTICE {correction_id}: {source_id} {summary['old_version']} -> {version_id}: {len(summary['changed'])} claims changed, {len(summary['unchanged'])} unchanged, {len(summary['added'])} added, {len(summary['removed'])} removed",
                 actor="source", ts=tx_time, correction_id=correction_id, detail={"kind": kind, "knowable_at": knowable_at, "note": note})
    result = waves.run_wave(correction_id, tx_time)
    result["diff"] = {k: (v if not isinstance(v, list) else len(v)) for k, v in summary.items()}
    result["evaluation"] = _review(correction_id, tx_time)
    return result


def apply_corrections(correction_ids: list[str], tx_time: str | None = None) -> dict:
    """Coalescing: corrections that arrive together (the 'Apply corrections' button or the debounce window) become one wave.
    Each gets its own corrections row and claim diff; the first id names the wave and carries the findings."""
    if not correction_ids:
        raise ValueError("no corrections")
    primary, extras = correction_ids[0], correction_ids[1:]
    tx = tx_time or scenarios.CORRECTIONS[primary]["tx_time"]
    for cid in correction_ids:
        meta = scenarios.CORRECTIONS[cid]
        gen = scenarios.load_body(meta["source_id"], meta["version"], cid)
        if db.q1("SELECT 1 FROM corrections WHERE correction_id=?", (cid,)):
            raise ValueError(f"{cid} already applied")
        summary = diff.apply_version(cid, meta["source_id"], gen["version_id"], gen["body"], tx, document_date=gen.get("document_date"), supersedes=None, kind=meta["kind"],
                                     knowable_at=meta["knowable_at"], booking_period=meta.get("booking_period"), note=meta.get("note", ""))
        db.log_event("correction_received", f"RECALL NOTICE {cid}: {meta['source_id']} {summary['old_version']} -> {gen['version_id']}: {len(summary['changed'])} claims changed (coalesced with {', '.join(x for x in correction_ids if x != cid)})",
                     actor="source", ts=tx, correction_id=cid, detail={"coalesced": correction_ids})
    result = waves.run_wave(primary, tx, extra_ids=extras)
    result["evaluations"] = {cid: _review(cid, tx) for cid in correction_ids}
    return result


def _review(correction_id: str, ts: str) -> dict | None:
    """The agent's Error Evaluation and Jade's review, after the wave. Never allowed to break the pipeline."""
    from . import review
    if correction_id.startswith(("LYFT", "REV-")):   # the real-world reconstruction and agents' own revisions carry no playbook claims
        return None
    try:
        ev = review.evaluate(correction_id, ts)
        return {"playbook_version": ev["playbook_version"], "overruled": ev["jade"]["summary"]["overruled_claims"], "headline": ev["headline"]} if ev else None
    except Exception as e:  # noqa: BLE001
        db.log_event("jade_error", f"Jade could not review {correction_id}: {e}", actor="jade", ts=ts, correction_id=correction_id)
        db.commit()
        return None


def _dry_run(correction_id, source_id, version_id, body, tx_time, kind, knowable_at, booking_period, note) -> dict:
    """Judge's red pen preview: apply inside a transaction, propagate with dry_run, roll back."""
    conn = db.get_conn()
    conn.execute("BEGIN")
    try:
        tmp_id = f"{correction_id}"
        diff.apply_version(tmp_id, source_id, version_id, body, tx_time, document_date=body.get("document_date"), supersedes=None, kind=kind, knowable_at=knowable_at, booking_period=booking_period, note=note)
        out = waves.run_wave(tmp_id, tx_time, dry_run=True)
    finally:
        conn.execute("ROLLBACK")
    return out


def refuse_correction(attempt_id: str, source_id: str, doc_id: str, reason: str, ts: str, detail: dict | None = None) -> dict:
    db.log_event("correction_refused", f"{attempt_id}: refused correction to {source_id} from {doc_id}: {reason}", actor="trackback:engine", ts=ts, correction_id=attempt_id,
                 detail={"source_id": source_id, "doc_id": doc_id, "reason": reason, **(detail or {})})
    db.commit()
    return {"attempt_id": attempt_id, "refused": True, "reason": reason}


def verify_vendor_change(doc_id: str, ts: str) -> dict:
    """E15: a bank-detail change by email is never accepted; the sender domain must match the vendor master and a callback is required."""
    v = db.source_version_as_of(doc_id, ts)
    body = json.loads(v["body"])
    sender = next((c["value_text"] for c in body["claims"] if c["line_item"] == "sender_domain"), None)
    vm = db.q1("SELECT cv.value_text FROM claims c JOIN claim_versions cv ON cv.claim_id=c.claim_id WHERE c.source_id='vendor_master' AND c.line_item='email_domain' AND c.entity='Kletterwerk GmbH' AND cv.tx_to=?", (config.TX_CURRENT,))
    ok = vm is not None and sender == vm["value_text"]
    reason = ("sender domain matches the vendor master" if ok else f"sender domain '{sender}' does not match the vendor master domain '{vm['value_text'] if vm else '?'}'; policy V-3: bank-detail changes by email are never accepted; callback to the number on file required (owner Priya Nair)")
    return {"ok": ok, "reason": reason, "sender": sender}


def execute_action(action_id: str, ts: str) -> dict:
    """Execute an approved action after the fence passes. Journal entries post to the ledger (locked periods rejected)."""
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    if a is None:
        raise KeyError(action_id)
    if a["state"] != "approved":
        raise PermissionError(f"{action_id} is {a['state']}, not approved")
    ok, stale = fence.guard_execute(action_id, ts)
    if not ok:
        return {"action_id": action_id, "executed": False, "blocked": stale}
    params = json.loads(a["params_json"])
    apr = db.q1("SELECT approval_id FROM approvals WHERE action_id=? AND decision='approved' ORDER BY ts DESC LIMIT 1", (action_id,))
    from .core.domain import get_domain
    eff = get_domain().execute_effect(dict(a), params, ts, apr["approval_id"] if apr else None)
    tx_id = eff.get("ledger_tx_id")
    matched = eff.get("effect_spec") == eff.get("observed_effect") or not isinstance(eff.get("effect_spec"), list)
    if db.q1("SELECT 1 FROM effects WHERE action_id=?", (action_id,)) is None:
        db.insert("effects", {"action_id": action_id, "effect_spec_json": db.dumps(eff.get("effect_spec")), "observed_effect_json": db.dumps(eff.get("observed_effect")), "matched": 1 if matched else 0, "checked_at": db.norm_ts(ts)})
    graph.set_action_state(action_id, "executed", ts, ledger_tx_id=tx_id, executed_at=ts)
    db.commit()
    return {"action_id": action_id, "executed": True, "ledger_tx_id": tx_id}
