"""The review run (SPEC.md Section 3): detect, trust, trace, evaluate, review, ask, report, learn, pinned to the demo clock.

This module wires the engines together and stores what each step found, so the API, the Stage beats and the scorecard read the same
rows. Steps 4 to 8 (agent, Jade, workflow, memo, lessons) and the iteration-2 hub (pings to owners) hang off `run_all`.
"""
from __future__ import annotations

import json
import time
import uuid
from functools import lru_cache

from . import config as C
from .core import db
from .engine import graph as GR, lineage as L, recon as RC, replay as R
from .engine.books import MetricLibrary, tidewall_library

SNAP_ORDER = ["draft", "close", "now"]
SNAP_LABEL = {"draft": "Apr 9 draft trial balance", "close": "Apr 10 close", "now": "Jul 8 books"}
TRACED = [("covenant_workbook", "xlsx", "WB"), ("board_deck", "pptx", "DECK"), ("compliance_certificate", "pdf", "CERT")]


def owner_of(file: str, locator: str) -> str:
    """Who made each line: people's files belong to people; the agents' lines carry receipts as well."""
    if file.startswith("Covenant_"):
        return "priya"
    if file.startswith("Board_Deck"):
        return "sam" if locator.startswith("slide 2") else "reporting_analyst"
    if file.startswith("Compliance_Certificate"):
        return "covenant_comp"
    return "unknown"


# ------------------------------------------------------------------------------------------------------------------ context
class Ctx:
    """Everything an engine needs for one world at one pin. Cached by ledger size so a new correcting entry refreshes it."""

    def __init__(self, pin: str):
        from .world.build import load_entries, targets
        self.pin = db.norm_ts(pin)
        self.entries = [e for e in load_entries() if db.norm_ts(e["posted_at"]) <= self.pin]
        self.targets = targets()
        self.lib: MetricLibrary = tidewall_library(self.targets)
        self.snapshots = {k: v for k, v in C.SNAPSHOTS.items() if db.norm_ts(v) <= self.pin}
        self._vals: dict | None = None

    @property
    def values(self) -> dict:
        if self._vals is None:
            self._vals = L.snapshot_values(self.lib, self.entries, self.snapshots)
        return self._vals

    def account_metrics_by_q(self) -> dict:
        return {q: [m for m in self.lib.metrics if m.startswith("acct.") and m.endswith("@" + q)] for q in C.QUARTERS}


@lru_cache(maxsize=4)
def _ctx(pin: str, n_entries: int) -> Ctx:
    return Ctx(pin)


def ctx(pin: str | None = None) -> Ctx:
    pin = db.norm_ts(pin or C.KEY_DATES["now"])
    n = db.q1("SELECT COUNT(*) n FROM gl_entries WHERE world='tidewall'")["n"]
    return _ctx(pin, n)


# ------------------------------------------------------------------------------------------------------------------ steps
def detect(pin: str, run_id: str | None = None, store: bool = True) -> list[dict]:
    res = RC.run_all(RC.load_inputs(pin, run_id))
    n = 0
    for r in res:
        for e in r["exceptions"]:
            n += 1
            e["exception_id"] = f"EX-{n:02d}"
    if store and run_id:
        conn = db.get_conn()
        conn.execute("BEGIN")
        for r in res:
            for o, rows in (("matched", r["matched"]), ("cleared", r["cleared"])):
                conn.executemany("INSERT INTO recon_items(run_id, world, recon, outcome, reason, amount, detail_json, exception_id) VALUES(?,?,?,?,?,?,?,?)",
                                 [(run_id, "tidewall", r["recon"], o, x.get("reason") if o == "cleared" else "matched", x.get("amount"), json.dumps(x.get("detail", x), default=str), None) for x in rows])
            for e in r["exceptions"]:
                db.insert("recon_items", {"run_id": run_id, "world": "tidewall", "recon": r["recon"], "outcome": "exception", "reason": e["kind"], "amount": e["amount"],
                                          "detail_json": json.dumps({k: v for k, v in e.items() if k not in ("correction",)}, default=str), "exception_id": e["exception_id"]})
                db.insert("exceptions", {"exception_id": e["exception_id"], "run_id": run_id, "world": "tidewall", "recon": r["recon"], "kind": e["kind"], "title": e["title"], "amount": e["amount"],
                                         "system_of_record": e.get("system_of_record"), "trust_why": json.dumps(e.get("trust")), "knowable_at": (e.get("knowable") or {}).get("at"),
                                         "evidence_json": json.dumps(e.get("evidence"), default=str), "correction_json": json.dumps(e.get("correction")), "detail_json": json.dumps(e, default=str)})
        db.insert("kv", {"key": f"recon.{run_id}", "value": json.dumps([{k: r[k] for k in ("recon", "title", "counts", "cleared_by_reason")} | {"handoff": r.get("handoff"), "learned_lags": r.get("learned_lags"),
                                                                        "learned_habits": r.get("learned_habits")} for r in res], default=str)})
        conn.execute("COMMIT")
    return res


def trace(pin: str, run_id: str | None = None, store: bool = True) -> list[dict]:
    cx = ctx(pin)
    items, fsnap, fq = [], {}, {}
    for src, kind, prefix in TRACED:
        v = R.timegate(src, pin, run_id)
        p = R.file_path(v)
        its = {"xlsx": L.extract_xlsx, "pptx": L.extract_pptx, "pdf": L.extract_pdf}[kind](p, prefix)
        items += its
        made = db.norm_ts(v["captured_at"])
        fsnap[p.name] = max((n for n, t in cx.snapshots.items() if db.norm_ts(t) <= made), key=lambda n: db.norm_ts(cx.snapshots[n]))
        fq[p.name] = max(q for q, ms in C.QUARTERS.items() if f"{ms[-1]}-28" <= made[:10])
    links = L.match(items, cx.lib, cx.values, fsnap, [s for s in SNAP_ORDER if s in cx.snapshots], fq, cx.account_metrics_by_q(), SNAP_LABEL)
    for l in links:
        l["owner"] = owner_of(l["file"], l["locator"])
        l["method"] = l.get("method") or "matched"
    if store and run_id:
        conn = db.get_conn()
        conn.execute("BEGIN")
        for it, l in zip(items, links):
            db.insert("trace_items", {"item_id": it.item_id, "run_id": run_id, "world": "tidewall", "file": it.file, "locator": it.locator, "label": it.label, "kind": it.kind,
                                      "value_num": it.value if isinstance(it.value, (int, float)) else None, "value_text": it.value if isinstance(it.value, str) else None,
                                      "unit": it.unit, "tolerance": it.tolerance, "display": it.display, "owner": l["owner"], "refs_json": json.dumps(it.refs)})
            db.insert("trace_links", {"item_id": l["item_id"], "run_id": run_id, "status": l["status"], "metric_id": l.get("metric_id"), "snapshot": l.get("snapshot"), "method": l.get("method"),
                                      "confidence": l.get("confidence"), "explanation": l.get("explanation"), "candidates_json": json.dumps(l.get("candidates", []) + ([{"near_misses": l["near_misses"]}] if l.get("near_misses") else [])),
                                      "confirmed_by": None, "confirmed_at": None})
        conn.execute("COMMIT")
    return links


def actions() -> list[dict]:
    from .world.human_files import ACTIONS
    return ACTIONS


def ripple_for(exc: dict, links: list[dict], pin: str, run_id: str | None = None, agent_nodes: list[dict] | None = None, store: bool = True) -> dict:
    cx = ctx(pin)
    lines = (exc.get("correction") or {}).get("lines") or []
    res = GR.ripple(correction={"id": exc["exception_id"], "title": exc["title"], "lines": lines}, lib=cx.lib, entries=cx.entries, snapshots=cx.snapshots,
                    links=links, actions=actions(), agent_nodes=agent_nodes)
    if store and run_id:
        db.insert("ripples", {"ripple_id": f"RP-{run_id}-{exc['exception_id']}", "run_id": run_id, "world": "tidewall", "exception_id": exc["exception_id"], "created_at": pin,
                              "counts_json": json.dumps(res["counts"]), "result_json": json.dumps(res, default=str)})
    return res


def judge(excs: list[dict], ripples: dict, pin: str, run_id: str | None, pb: dict | None = None, store: bool = True) -> dict:
    """Steps 4 and 5: the agent's Error Evaluations under its playbook, then Jade's review of every claim."""
    from . import jade
    from .agent import agent as AG, playbook as PB
    from .engine import materiality as MAT
    pb = pb or PB.current()
    classified = [{**e, "classification": AG.classify(e, PB.apply(PB.V1, ["classify_by_knowable_at"]), AG.knowable(e))["value"]} for e in excs]
    mlog = R.rows("misstatement_log", pin, run_id)
    mat = MAT.evaluate(classified, mlog, ripples)
    out = {"materiality": mat, "evaluations": {}, "jade": {}, "final": {}, "playbook": pb}
    for e in excs:
        ev = AG.evaluate(e, ripples.get(e["exception_id"]), mat, pb, pin)
        jf = jade.review(ev, e, mat, pin)
        fin = jade.apply(ev, jf)
        out["evaluations"][e["exception_id"]] = ev
        out["jade"][e["exception_id"]] = jf
        out["final"][e["exception_id"]] = fin
        if store and run_id:
            eid = f"EV-{run_id}-{e['exception_id']}"
            db.insert("evaluations", {"eval_id": eid, "run_id": run_id, "world": "tidewall", "exception_id": e["exception_id"], "playbook_version": pb["version"],
                                      "claims_json": json.dumps(ev, default=str), "created_at": db.norm_ts(pin), "superseded_by": None})
            db.insert("evaluations", {"eval_id": eid + "-J", "run_id": run_id, "world": "tidewall", "exception_id": e["exception_id"], "playbook_version": pb["version"] + "+jade",
                                      "claims_json": json.dumps(fin, default=str), "created_at": db.norm_ts(pin), "superseded_by": None})
            jade.store(eid, jf, pin)
    if store and run_id:
        db.insert("kv", {"key": f"materiality.{run_id}", "value": json.dumps(mat, default=str)})
    return out


def send_waves(excs: list[dict], ripples: dict, links: list[dict], agent_nodes: list[dict], pin: str, run_id: str) -> dict:
    """Iteration 2: tell every owner. One wave per error with invalidations (X1 first); bank fact updates found together are coalesced into
    one wave (S2), each keeping its own reach; the Reporting Analyst then challenges the Close Accountant's allocation (S3)."""
    from . import hub
    out = {}
    ts = db.norm_ts(pin)
    order = sorted(excs, key=lambda e: (e["kind"] != "duplicate_import", e["exception_id"]))
    for e in order:
        rp = ripples.get(e["exception_id"])
        if not rp or e["recon"] == "bank_to_book":
            continue
        if rp["counts"]["invalidated"] or rp["counts"]["agent_suspect"]:
            out[e["exception_id"]] = hub.dispatch(rp, ts)
    bank = [e for e in excs if e["recon"] == "bank_to_book" and (e.get("correction") or {}).get("lines")]
    if bank:
        cid = "+".join(e["exception_id"] for e in bank)
        lines = [l for e in bank for l in e["correction"]["lines"]]
        rp = ripple_for({"exception_id": cid, "title": "Bank fact updates found together (coalesced): " + "; ".join(e["title"] for e in bank), "correction": {"lines": lines}},
                        links, pin, run_id, agent_nodes)
        solo = {e["exception_id"]: ripples[e["exception_id"]]["counts"]["agent_suspect"] for e in bank}
        w = hub.dispatch(rp, ts)
        w["coalesced"] = [e["exception_id"] for e in bank]
        w["solo_pings"] = solo
        out[cid] = w
    x1 = next((e for e in excs if e["kind"] == "duplicate_import"), None)
    if x1:
        out["S3"] = {"challenge": hub.challenge("reporting_analyst", "CA.q1_close_memo", "Is the duplicate allocated to the right gyms? Slide 4 moves by region; please confirm the B07 cohort's gym mapping before I reissue.", ts)}
    db.insert("kv", {"key": f"waves.{run_id}", "value": json.dumps(out, default=str)})
    return out


def new_run(pin: str, playbook: str = "v1") -> str:
    rid = f"RV-{uuid.uuid4().hex[:8]}"
    db.insert("review_runs", {"run_id": rid, "world": "tidewall", "pinned_at": db.norm_ts(pin), "playbook_version": playbook, "status": "running", "started_at": db.norm_ts(pin), "finished_at": None, "summary_json": None})
    db.insert("runs", {"run_id": rid, "agent": "close_accountant", "task": "Error review: reconcile, trace, evaluate, route", "pinned_at": db.norm_ts(pin), "mode": "review", "status": "running",
                       "started_at": db.norm_ts(pin), "finished_at": None, "turns": 0, "note": None})
    return rid


def run_all(pin: str | None = None, playbook: str = "v1") -> dict:
    """The canonical review run that ships in the snapshot."""
    t0 = time.time()
    pin = pin or C.KEY_DATES["now"]
    rid = new_run(pin, playbook)
    res = detect(pin, rid)
    links = trace(pin, rid)
    excs = [e for r in res for e in r["exceptions"]]
    import importlib.util
    agent_nodes = []
    if importlib.util.find_spec("trackback.world.history"):
        from .world import history
        agent_nodes = history.agent_nodes()
    ripples = {e["exception_id"]: ripple_for(e, links, pin, rid, agent_nodes) for e in excs if (e.get("correction") or {}).get("lines")}
    j = judge(excs, ripples, pin, rid)
    waves = send_waves(excs, ripples, links, agent_nodes, pin, rid)
    from . import memo, workflow
    by_id = {e["exception_id"]: e for e in excs}
    proposals = workflow.propose(j["final"], by_id, pin)
    memos = [eid for eid, fin in j["final"].items() if fin["q5_matters"].get("material")]
    for eid in memos:
        memo.build(rid, eid, pin)
    overrules = {eid: [f["claim_key"] for f in fs if f["verdict"] in ("overrule", "flag")] for eid, fs in j["jade"].items()}
    summary = {"exceptions": len(excs), "links": len(links), "ripples": {k: v["counts"] for k, v in ripples.items()}, "jade": overrules,
               "aggregate": j["materiality"]["aggregate"], "waves": {k: v.get("stats") for k, v in waves.items()}, "proposals": proposals, "memos": memos, "seconds": round(time.time() - t0, 2)}
    db.get_conn().execute("UPDATE review_runs SET status='done', finished_at=?, summary_json=? WHERE run_id=?", (db.norm_ts(pin), json.dumps(summary), rid))
    db.insert("kv", {"key": "review.latest.tidewall", "value": rid}) if db.q1("SELECT 1 FROM kv WHERE key='review.latest.tidewall'") is None else \
        db.get_conn().execute("UPDATE kv SET value=? WHERE key='review.latest.tidewall'", (rid,))
    print(f"review {rid}: {len(excs)} exceptions, {len(links)} traced items, ripples {summary['ripples']} ({summary['seconds']}s)")
    return {"run_id": rid, "detect": res, "links": links, "ripples": ripples, "judge": j, "summary": summary}


def latest_run() -> str | None:
    r = db.q1("SELECT value FROM kv WHERE key='review.latest.tidewall'")
    return r["value"] if r else None
