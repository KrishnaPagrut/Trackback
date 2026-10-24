"""The scorecard (SPEC.md Section 12): every metric computed from runs against the key, never typed.

Steps scored per case: detect (exceptions found vs expected, false alarms on noise), classify, size (rollover and iron curtain exact),
materiality (reported separately for small-but-covenant-breaking cases), trace (lineage links and stale detection), impact (invalidated vs
still valid against Appendix A; over-flagging vs the naive count), fix (treatment, balanced entries, right approver), Jade (catch rate on
planted agent mistakes, false overrule rate on correct claims), learning (v1 vs v2 on held-out cases), Replay (future reads leaked).

Baselines: a naive "under 5% of annual pretax is immaterial" rule; the agent without Jade (v1); the agent with Jade (v1); the agent with
Jade after approved lessons (v2). The proof page reads only data/eval/latest.json. Runs on a scratch copy of the canonical snapshot.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

from .. import config as C
from ..core import db

SCRATCH = C.DATA_DIR / "build" / "eval.sqlite"


def _scratch() -> None:
    SCRATCH.parent.mkdir(parents=True, exist_ok=True)
    for p in (SCRATCH, Path(str(SCRATCH) + "-wal"), Path(str(SCRATCH) + "-shm")):
        if p.exists():
            p.unlink()
    shutil.copy(C.SNAPSHOT_PATH, SCRATCH)
    C.DB_PATH = SCRATCH
    db.reset_connection()


def prepare() -> dict:
    from .. import review as RV
    from ..engine import recon as RC
    from ..world import generator as G
    from ..world.build import load_entries, targets
    from . import cases as CS
    pin = C.KEY_DATES["now"]
    key = json.loads(C.ANSWER_KEY_V3.read_text(encoding="utf-8"))
    inp = RC.load_inputs(pin)
    base_exc = [e for r in RC.run_all(inp) for e in r["exceptions"]]
    links = RV.trace(pin, store=False)
    w = G.build()
    entries = load_entries()
    tg = {r: v * 100 for r, v in targets().items()}
    cases = CS.build([e for e in entries if not e.get("correction_id")], w.members, tg)
    return {"pin": pin, "key": key, "inp": inp, "base_exc": base_exc, "links": links, "cases": cases, "entries": entries, "targets": tg}


def _sig(e: dict) -> tuple:
    return (e["recon"], e["kind"], round(e["amount"], 2), e["title"])


def precompute(base: dict) -> dict:
    """Per case: detection, the exception, its ripple and the full materiality framework (all independent of the playbook)."""
    from .. import review as RV
    from ..engine import materiality as MAT, recon as RC, replay as R
    from ..agent import agent as AG, playbook as PB
    from . import cases as CS
    pin = base["pin"]
    base_sigs = {_sig(e) for e in base["base_exc"]}
    mlog = R.rows("misstatement_log", pin)
    known = PB.apply(PB.V1, ["classify_by_knowable_at"])
    out = {}
    for case in base["cases"]:
        rec = {"case": case, "detect": None}
        if case.stage == "real":
            exc = next(e for e in base["base_exc"] if e["kind"] == case.expected_kind)
            rec["detect"] = {"expected": [case.expected_kind], "found": [case.expected_kind], "new": 1, "false_alarms": 0}
        elif case.stage == "detect":
            res = RC.run_all(CS.apply(base["inp"], case))
            new = [e for r in res for e in r["exceptions"] if _sig(e) not in base_sigs]
            exp = [case.expected_kind] if case.expected_kind else []
            hit = [e for e in new if e["kind"] == case.expected_kind]
            rec["detect"] = {"expected": exp, "found": [e["kind"] for e in new], "new": len(new), "false_alarms": len(new) - len(hit[:1]),
                             "tp": 1 if (hit and exp) else 0, "fn": 1 if (exp and not hit) else 0}
            exc = hit[0] if hit else None
        else:
            exc = dict(case.exception)
        if exc is None:
            out[case.id] = rec
            continue
        exc = {**exc, "exception_id": case.id}
        rp = RV.ripple_for(exc, base["links"], pin, store=False) if (exc.get("correction") or {}).get("lines") else None
        cls = AG.classify(exc, known, AG.knowable(exc))["value"]
        mat = MAT.evaluate([{**exc, "classification": cls}], mlog, {case.id: rp} if rp else {})
        rec.update(exc=exc, ripple=rp, mat=mat)
        out[case.id] = rec
    return out


def expected_for(case, key: dict) -> dict:
    if case.stage != "real":
        return case.expected
    k = next(x for x in key["exceptions"] if x["id"] == case.id.split("-")[1])
    exp = {"classification": k["classification"], "material": k["material"], "covenant_flip": "covenant_flip" in (k.get("triggers") or [])}
    if k.get("rollover") is not None and k["classification"] != "estimate_change":
        exp.update(rollover=k["rollover"], iron_curtain=k["iron_curtain"])
    if k["classification"] == "estimate_change":
        exp.update(treatment="no_action_or_prospective", approvers={})
    elif k["id"] in ("X1", "X2"):
        exp.update(posting_period=k["posting_period"], approvers={"journal_entry": "dana", **({"lender_document": "sam"} if k.get("lender_documents_to") else {})})
    elif k["id"] == "X4":
        exp.update(approvers={"vendor_credit": "marco", "vendor_hold": "marco"})
    else:
        exp.update(posting_period=C.OPEN_PERIOD, approvers={"journal_entry": "dana"})
    return exp


def score(pre: dict, key: dict, lesson_keys: list[str], with_jade: bool, only: set[str] | None = None, naive: bool = False) -> dict:
    """One configuration over the case library. Returns per-case checks and aggregates."""
    from .. import jade
    from ..agent import agent as AG, playbook as PB
    from ..engine import materiality as MAT
    pb = PB.apply(PB.V1, lesson_keys) if lesson_keys else PB.V1
    rows, passed, checks = [], {}, {}
    for cid, rec in pre.items():
        case = rec["case"]
        if only is not None and cid not in only:
            continue
        exp = expected_for(case, key)
        r = {"case": cid, "family": case.family, "split": case.split, "checks": {}, "jade": [], "planted": case.planted}
        if rec["detect"] is not None:
            d = rec["detect"]
            r["checks"]["detect"] = (d["false_alarms"] == 0) and (bool(d.get("tp", 1)) if d["expected"] else d["new"] == 0)
        if "exc" not in rec:
            rows.append(r)
            passed[cid] = all(r["checks"].values())
            continue
        exc, rp, mat = rec["exc"], rec["ripple"], rec["mat"]
        if naive:
            r["checks"]["materiality"] = MAT.naive_five_percent(exc)["material"] == exp.get("material", False)
        else:
            ev = AG.evaluate(exc, rp, mat, pb, C.KEY_DATES["now"])
            if with_jade:
                jf = jade.review(ev, exc, mat, C.KEY_DATES["now"])
                fin = jade.apply(ev, jf)
                r["jade"] = jf
            else:
                fin = ev
            r["agent_claims"] = {"classification": ev["q3_classification"]["value"], "material": ev["q5_matters"]["material"], "posting": ev["q7_fix"].get("posting_period"),
                                 "approvers": ev["q7_fix"].get("approvers")}
            q3, q4, q5, q7 = fin["q3_classification"], fin["q4_size"], fin["q5_matters"], fin["q7_fix"]
            r["checks"]["classify"] = q3["value"] == exp["classification"]
            if "rollover" in exp:
                r["checks"]["size"] = abs(q4["rollover"] - exp["rollover"]) < 0.01 and abs(q4["iron_curtain"] - exp["iron_curtain"]) < 0.01
            if "material" in exp:
                r["checks"]["materiality"] = bool(q5.get("material")) == exp["material"]
            if exp["classification"] == "estimate_change":
                r["checks"]["fix"] = not q7.get("entries")
            elif exp["classification"] != "fact_update" or q7.get("entries"):
                bal = sum(l["amount_cents"] for l in q7.get("entries", [])) == 0
                post = exp.get("posting_period") is None or q7.get("posting_period") == exp["posting_period"] or (case.family == "duplicate_vendor_invoice")
                appr = all((q7.get("approvers") or {}).get(k) == v for k, v in (exp.get("approvers") or {}).items())
                r["checks"]["fix"] = bal and post and appr
            r["covenant_breaking_small"] = bool(exp.get("covenant_flip")) and max(abs(exp.get("rollover", 0)), abs(exp.get("iron_curtain", 0))) < C.MATERIALITY_V3["overall"]
        rows.append(r)
        passed[cid] = all(r["checks"].values())
        for k, v in r["checks"].items():
            checks[(cid, k)] = v
    return {"rows": rows, "passed": passed, "checks": {f"{a}:{b}": v for (a, b), v in checks.items()}}


def _rate(xs: list[bool]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def summarize(run: dict) -> dict:
    rows = run["rows"]
    out = {}
    for step in ("detect", "classify", "size", "materiality", "fix"):
        v = [r["checks"][step] for r in rows if step in r["checks"]]
        out[step] = {"n": len(v), "correct": sum(v), "accuracy": _rate(v)}
    small = [r["checks"]["materiality"] for r in rows if r.get("covenant_breaking_small") and "materiality" in r["checks"]]
    out["materiality_small_covenant_breaking"] = {"n": len(small), "correct": sum(small), "accuracy": _rate(small)}
    out["cases"] = {"n": len(rows), "passed": sum(run["passed"].values()), "pass_rate": _rate(list(run["passed"].values()))}
    return out


def jade_metrics(run: dict, pre: dict, key: dict) -> dict:
    """Catch rate on planted agent mistakes (the v1 claim was wrong and Jade overruled, flagged or escalated it) and false overrules on correct claims."""
    caught = missed = false = correct_claims = 0
    details = []
    for r in run["rows"]:
        if "agent_claims" not in r:
            continue
        exp = expected_for(pre[r["case"]]["case"], key)
        a = r["agent_claims"]
        jv = {f["claim_key"]: f["verdict"] for f in r["jade"]}
        pairs = [("q3_classification", a["classification"] == exp["classification"]),
                 ("q5_matters", ("material" not in exp) or a["material"] == exp["material"] or exp["classification"] == "estimate_change")]
        if exp.get("posting_period") and exp["classification"] != "estimate_change" and a["posting"]:
            pairs.append(("q7_fix.posting", a["posting"] == exp["posting_period"]))
        for k, v in (exp.get("approvers") or {}).items():
            pairs.append((f"q7_fix.approvers.{k}", (a["approvers"] or {}).get(k) == v))
        for claim, ok in pairs:
            verdict = jv.get(claim, "approve")
            if not ok:
                if verdict in ("overrule", "flag", "escalate"):
                    caught += 1
                else:
                    missed += 1
                details.append({"case": r["case"], "claim": claim, "jade": verdict})
            else:
                correct_claims += 1
                if verdict in ("overrule", "flag"):
                    false += 1
    return {"planted_mistakes": caught + missed, "caught": caught, "catch_rate": _rate([True] * caught + [False] * missed), "correct_claims": correct_claims,
            "false_overrules": false, "false_overrule_rate": round(false / correct_claims, 3) if correct_claims else 0.0, "misses": [d for d in details if d["jade"] == "approve"][:10]}


def lineage_metrics(base: dict) -> dict:
    truth = {t["id"]: t for t in base["key"]["lineage"]}
    tp = fp = fn = stale_ok = 0
    for l in base["links"]:
        t = truth.get(l["item_id"])
        if t is None:
            fp += 1
            continue
        if t["link"] == "derived":
            ok = l["status"] == "derived"
        elif t["metric"].startswith("sum:"):
            ok = l.get("metric_id", "") and sorted(l["metric_id"][4:].split("+")) == sorted(t["metric"][4:].split("+"))
        else:
            ok = l.get("metric_id") == t["metric"]
        tp += bool(ok)
        fn += not ok
        stale_ok += (l["status"] == "stale") == bool(t.get("stale"))
    return {"truths": len(truth), "correct": tp, "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / len(truth), 3),
            "stale_detection": f"{stale_ok}/{len(truth)}", "min_confidence": min((l["confidence"] for l in base["links"] if l["status"] in ("linked", "policy", "stale")), default=None)}


def impact_metrics(base: dict, pre: dict) -> dict:
    out = {}
    for cid, kid in (("TW-X1", "X1"), ("TW-X2", "X2"), ("TW-X4", "X4"), ("TW-X6", "X6")):
        rp = pre.get(cid, {}).get("ripple")
        if not rp:
            continue
        exp = base["key"]["impact"][kid]
        got = {**{i: v for i, v in rp["items"].items()}, **{a: v for a, v in rp["actions"].items()}}
        want = {**exp["items"], **exp["actions"]}
        inv_g = {i for i, v in got.items() if v["verdict"] == "invalidated"}
        inv_w = {i for i, v in want.items() if v["verdict"] == "invalidated"}
        tp = len(inv_g & inv_w)
        reasons = sum(1 for i in want if i in got and got[i]["reason"] == want[i]["reason"])
        out[kid] = {"invalidated": len(inv_g), "still_valid": sum(1 for v in got.values() if v["verdict"] == "still_valid"), "compensations": rp["counts"]["compensations"],
                    "precision": round(tp / len(inv_g), 3) if inv_g else 1.0, "recall": round(tp / len(inv_w), 3) if inv_w else 1.0, "reasons_correct": f"{reasons}/{len(want)}",
                    "naive_flagged": rp["counts"]["naive"], "over_flagging_naive_vs_true": round(rp["counts"]["naive"] / max(1, len(inv_w)), 2), "metrics_recomputed": rp["counts"]["metrics_recomputed"],
                    "metrics_total": rp["counts"]["metrics_total"], "seconds": rp["seconds"]}
    return out


def replay_leak_test() -> dict:
    from ..engine import replay as R
    attempts = served = refused = 0
    pins = ["2026-01-10T09:00:00-08:00", "2026-04-09T17:59:00-07:00", "2026-04-10T17:00:00-07:00", "2026-05-15T10:00:00-07:00", "2026-06-30T12:00:00-07:00", "2026-07-05T09:00:00-07:00"]
    for s in db.q("SELECT source_id FROM sources WHERE kind='file'"):
        for v in R.timemap(s["source_id"]):
            for pin in pins:
                if db.norm_ts(v["captured_at"]) > db.norm_ts(pin):
                    attempts += 1
                    try:
                        R.fetch(v["version_id"], pin)
                        served += 1
                    except R.Refusal:
                        refused += 1
    return {"adversarial_fetches": attempts, "leaked": served, "refused": refused}


def iteration2_metrics(key: dict) -> dict:
    from .. import review as RV
    rid = RV.latest_run()
    w = json.loads(db.q1("SELECT value FROM kv WHERE key=?", (f"waves.{rid}",))["value"])
    x1 = next(v for k, v in w.items() if k.startswith("EX-") and "+" not in k and v.get("pings") and len(v["pings"]) == 3) if w else {}
    exp_agents = set(key["iteration2"]["X1_pings"])
    got_agents = {p["agent"] for p in x1.get("pings", [])}
    items = [i for p in x1.get("pings", []) for i in p["items"]]
    still = [i["artifact_id"] for i in items if i["verdict"] == "still_valid"]
    rework_nochange = sum(1 for i in items if i["verdict"] == "reworked" and (i.get("new_version") or {}).get("content") == db.q1(
        "SELECT content FROM artifacts WHERE artifact_id=? AND version=1", (i["artifact_id"],))["content"])
    total_nodes = db.q1("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts WHERE world='tidewall' AND agent_id<>'trackback'")["n"]
    calls = db.q1("SELECT COUNT(*) n FROM llm_calls")["n"]
    runs = db.q1("SELECT COUNT(*) n FROM runs WHERE mode='history'")["n"]
    return {"x1": {"agents_expected": sorted(exp_agents), "agents_pinged": sorted(got_agents), "ping_precision": round(len(exp_agents & got_agents) / max(1, len(got_agents)), 3),
                   "ping_recall": round(len(exp_agents & got_agents) / max(1, len(exp_agents)), 3), "nodes_in_pings": len(items),
                   "still_valid_with_reason": still, "false_still_valid": sum(1 for s in still if s not in key["iteration2"]["X1_still_valid_agent_answers"]),
                   "unnecessary_rework": rework_nochange, "skipped": [s["node_id"] for s in x1.get("skipped", [])],
                   "inspection_fraction": round(len(items) / max(1, total_nodes), 3), "notices": [{"owner": n["owner"], "to": n["to"]} for n in x1.get("notices", [])]},
            "s2": next(({"coalesced": v["coalesced"], "pings": [p["agent"] for p in v["pings"]], "solo_pings": v["solo_pings"]} for v in w.values() if v.get("coalesced")), None),
            "s3": w.get("S3"), "llm_calls_in_waves": calls, "rerun_all_agent_runs": runs}


def main() -> dict:
    old = C.DB_PATH
    try:
        return _main()
    finally:
        C.DB_PATH = old
        db.reset_connection()


def _main() -> dict:
    t0 = time.time()
    from .. import lessons as LS
    from ..agent import playbook as PB
    _scratch()
    base = prepare()
    pre = precompute(base)
    key = base["key"]
    good = ["materiality_framework", "classify_by_knowable_at", "post_in_open_period", "lender_documents_to_cfo"]
    configs = {
        "naive_5pct_rule": score(pre, key, [], False, naive=True),
        "agent_v1_no_jade": score(pre, key, [], False),
        "agent_v1_with_jade": score(pre, key, [], True),
    }
    # learning: training half under v1 with Jade -> mistakes -> lessons -> gate -> Dana approves -> v2; then held-out v1 vs v2
    train = {cid for cid, r in pre.items() if r["case"].split == "train"}
    held = {cid for cid, r in pre.items() if r["case"].split == "heldout"}
    train_run = score(pre, key, [], True, only=train)
    mistakes = LS.mistakes_from(train_run["rows"])
    ids = LS.propose(mistakes, C.KEY_DATES["now"], extra=["closed_period_invoices_are_estimates"])

    def run_checks(keys):
        r = score(pre, key, keys, False)
        return {"passed": r["checks"]}

    active: list[str] = []
    gates = []
    for lid in sorted(ids, key=lambda x: (x.endswith("estimates"), x)):
        g = LS.gate(lid, run_checks, active)
        gates.append(g)
        if g["result"] == "pass":
            LS.approve(lid, "dana", C.KEY_DATES["now"])
            active.append(g["lesson"])
    configs["agent_v2_with_jade"] = score(pre, key, active, True)
    v1_held = summarize(score(pre, key, [], False, only=held))
    v2_held = summarize(score(pre, key, active, False, only=held))
    v1j_held = summarize(score(pre, key, [], True, only=held))
    v2j_held = summarize(score(pre, key, active, True, only=held))
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "world": "tidewall", "llm_mode": __import__("os").environ.get("TRACKBACK_LLM_MODE", C.LLM_MODE),
        "answer_key": {"sha256": hashlib.sha256(C.ANSWER_KEY_V3.read_bytes()).hexdigest(), "path": "data/world/answer_key.json"},
        "cases": {"n": len(pre), "by_family": _count([r["case"].family for r in pre.values()]), "train": len(train), "heldout": len(held),
                  "list": [{"id": cid, "family": r["case"].family, "split": r["case"].split, "title": r["case"].title} for cid, r in pre.items()]},
        "configs": {k: summarize(v) for k, v in configs.items()},
        "jade": jade_metrics(configs["agent_v1_with_jade"], pre, key),
        "lineage": lineage_metrics(base),
        "impact": impact_metrics(base, pre),
        "learning": {"mistakes": len(mistakes), "lessons": [{"lesson": g["lesson"], "gate": g["result"], "broke": g["broke"][:6], "fixed": len(g["fixed"])} for g in gates], "active": active,
                     "playbook": PB.apply(PB.V1, active)["version"], "heldout": {"v1": v1_held, "v2": v2_held, "v1_with_jade": v1j_held, "v2_with_jade": v2j_held}},
        "replay": replay_leak_test(),
        "iteration2": iteration2_metrics(key),
        "seconds": round(time.time() - t0, 1),
        "real_vs_simulated": {"real": ["the reconciliation, lineage, ripple and materiality engines", "Jade's code checks", "the scoring", "file parsing (xlsx formulas, pptx, pdf)", "the ping protocol and the approvals schema",
                                       "Lyft's Feb 13, 2024 release as filed, the CFO's correction and the tape"],
                              "simulated": ["Tidewall Climbing Co., its books, people and files", "the planted cases and variants", "the agents' history (scripted unless recorded)"]},
    }
    x1 = out["impact"].get("X1", {})
    out["headline"] = {"exceptions_found": f"{sum(1 for r in pre.values() if r['case'].stage == 'real' and r['detect'])}/6",
                       "noise_false_alarms": sum(r["detect"]["false_alarms"] for r in pre.values() if r["detect"] and r["case"].family == "noise"),
                       "lineage": f"{out['lineage']['correct']}/{out['lineage']['truths']}", "x1_invalidated": x1.get("invalidated"), "x1_still_valid": x1.get("still_valid"),
                       "x1_compensations": x1.get("compensations"), "x1_naive_flagged": x1.get("naive_flagged"),
                       "materiality_naive": out["configs"]["naive_5pct_rule"]["materiality"]["accuracy"], "materiality_v1": out["configs"]["agent_v1_no_jade"]["materiality"]["accuracy"],
                       "materiality_v1_jade": out["configs"]["agent_v1_with_jade"]["materiality"]["accuracy"], "materiality_v2_jade": out["configs"]["agent_v2_with_jade"]["materiality"]["accuracy"],
                       "jade_catch_rate": out["jade"]["catch_rate"], "jade_false_overrule_rate": out["jade"]["false_overrule_rate"],
                       "heldout_pass_v1": v1_held["cases"]["pass_rate"], "heldout_pass_v2": v2_held["cases"]["pass_rate"], "replay_leaks": out["replay"]["leaked"]}
    C.EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    (C.DATA_DIR / "eval").mkdir(parents=True, exist_ok=True)
    path = C.DATA_DIR / "eval" / "latest.json"
    path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8", newline="\n")
    print(json.dumps(out["headline"], indent=1))
    print(f"wrote {path} ({out['seconds']}s)")
    return out


def _count(xs: list[str]) -> dict:
    d: dict[str, int] = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return d
