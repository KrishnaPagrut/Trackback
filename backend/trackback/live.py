"""The live demo flows: drop the E11 recall notice (with E12, E22, E23), and Scenario B (E20). Shared by the API, build_history
(to prime the cache) and eval."""
from __future__ import annotations

from . import approvals, config, corrections, db
from .agents import base, workorders as wo

CONTROLLER = config.PEOPLE["controller"]
E22_REASON = "Q1 is locked; book in Q2 with an out-of-period tag; restate the lender package separately"
E20_REASON = "Prior-year error: revise the FY2025 comparatives, adjust opening retained earnings and deferred revenue, disclose. Do not run it through Q2."


def _run(order: dict) -> dict:
    order = wo.with_handoffs(order)
    return base.run_agent(run_id=order["run_id"], agent=order["agent"], task=order["task"], pinned_at=order["pinned_at"],
                          required_outputs=wo.required_outputs_text(order), script=order["steps"])


def drop_e11() -> dict:
    """E11 recall notice arrives: propagate, then the E22 recovery (first draft into locked Q1 + self-approval attempt, rejection, re-draft)."""
    if db.q1("SELECT 1 FROM corrections WHERE correction_id='E11'"):
        return {"already_applied": True, "correction": "E11"}
    result = corrections.apply_correction("E11")
    r12 = _run(wo.r12_e11_first_draft())
    draft = next((x["result"] for x in r12["results"] if x["tool"] == "propose_journal_entry"), {})
    approvals.decide("JE-je_e11_dedupe_v1", CONTROLLER, "rejected", E22_REASON, "2026-07-08T09:12:00-07:00")
    from . import lessons
    lessons.signal_rejection("E11", "JE-je_e11_dedupe_v1", CONTROLLER, E22_REASON, "2026-07-08T09:12:00-07:00")
    r13 = _run(wo.r13_e11_redraft())
    from .core import waves as WV
    challenge = WV.file_challenge("reporting_analyst", "q1_membership_revenue_G4",
                                  "X3: the deck's Fresno tile moved by $32,000; please confirm the gym allocation of the duplicate before the board sees v2 (the export groups batches by gym, but Fresno's annual plans were partly sold through Oakland).",
                                  "2026-07-08T09:16:00-07:00")
    return {"correction": result, "draft1": {"run": r12["run_id"], "result": draft}, "rejection": {"by": CONTROLLER, "reason": E22_REASON, "at": "2026-07-08T09:12:00-07:00"},
            "redraft": {"run": r13["run_id"], "produced": r13["produced"]}, "challenge": challenge}


def scenario_b() -> dict:
    """E20 (prior-year error, little r) with the Q2-OOP trap and the Controller's rejection."""
    if db.q1("SELECT 1 FROM corrections WHERE correction_id='E20'"):
        return {"already_applied": True, "correction": "E20"}
    result = corrections.apply_correction("E20")
    r1 = _run(wo.fu_e20_trap())
    approvals.decide("JE-je_e20_oop_q2", CONTROLLER, "rejected", E20_REASON, "2026-07-08T09:34:00-07:00")
    from . import lessons
    lessons.signal_rejection("E20", "JE-je_e20_oop_q2", CONTROLLER, E20_REASON, "2026-07-08T09:34:00-07:00")
    r2 = _run(wo.fu_e20_redraft())
    return {"correction": result, "draft1": {"run": r1["run_id"]}, "rejection": {"by": CONTROLLER, "reason": E20_REASON, "at": "2026-07-08T09:34:00-07:00"}, "redraft": {"run": r2["run_id"], "produced": r2["produced"]}}


def prime_cache_from_scratch() -> int:
    """Run the live flows on a scratch copy of the current DB and copy the resulting llm_cache rows back, so replay mode has
    every judge/prose/agent response the live demo needs. Returns the number of rows copied."""
    import shutil
    import sqlite3
    scratch = config.DATA_DIR / "eval" / "prime_scratch.sqlite"
    scratch.parent.mkdir(exist_ok=True, parents=True)
    db.reset_connection()
    s = sqlite3.connect(str(config.DB_PATH)); d = sqlite3.connect(str(scratch)); s.backup(d); d.close(); s.close()
    real = config.DB_PATH
    config.DB_PATH = scratch; db.reset_connection()
    try:
        before = {r["cache_key"] for r in db.q("SELECT cache_key FROM llm_cache")}
        drop_e11(); scenario_b()
        corrections.apply_correction("E26")
        rows = [dict(r) for r in db.q("SELECT * FROM llm_cache") if r["cache_key"] not in before]
    finally:
        config.DB_PATH = real; db.reset_connection()
    n = 0
    for r in rows:
        if db.q1("SELECT 1 FROM llm_cache WHERE cache_key=?", (r["cache_key"],)) is None:
            db.insert("llm_cache", r); n += 1
    db.commit()
    scratch.unlink(missing_ok=True)
    return n
