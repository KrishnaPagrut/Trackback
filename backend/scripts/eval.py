"""Answer key vs findings, baselines B1-B3, Memento leak test, replay fidelity -> data/eval/latest.json.
Every number on the proof page comes from this file. Nothing is typed by hand."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import config, corrections, db, graph, scenarios  # noqa: E402
from trackback.llm import gateway  # noqa: E402

KEY = yaml.safe_load(config.ANSWER_KEY_PATH.read_text())
HISTORY_CORRECTIONS = [c for c in KEY["corrections"] if not scenarios.CORRECTIONS.get(c, {}).get("live") and c != "MPWR_RESTATEMENT"] + ["MPWR_RESTATEMENT"]
LIVE_ORDER = ["E11", "E20", "E26"]


def key_hash() -> dict:
    raw = config.ANSWER_KEY_PATH.read_bytes()
    try:
        commit = subprocess.run(["git", "log", "-1", "--format=%H %cI", "--", str(config.ANSWER_KEY_PATH)], capture_output=True, text=True, cwd=config.ROOT).stdout.strip()
        tag = subprocess.run(["git", "describe", "--tags", "--match", "answer-key-frozen", "--exact-match", "answer-key-frozen"], capture_output=True, text=True, cwd=config.ROOT).stdout.strip()
    except Exception:  # noqa: BLE001
        commit, tag = "", ""
    return {"sha256": hashlib.sha256(raw).hexdigest(), "frozen": KEY.get("frozen"), "git": commit, "tag": tag or None}


def findings_for(correction_id: str) -> dict[str, dict]:
    return {r["artifact_id"]: dict(r) for r in db.q("SELECT * FROM impact_findings WHERE correction_id=?", (correction_id,))}


def with_scratch_db(fn):
    """Run fn on a scratch copy of the canonical snapshot (live scenarios are applied without touching the real DB)."""
    scratch = config.DATA_DIR / "eval" / "scratch.sqlite"
    src = config.SNAPSHOT_PATH if config.SNAPSHOT_PATH.exists() else config.DB_PATH
    db.reset_connection()
    s = sqlite3.connect(str(src)); d = sqlite3.connect(str(scratch)); s.backup(d); d.close(); s.close()
    real = config.DB_PATH
    config.DB_PATH = scratch
    db.reset_connection()
    try:
        return fn()
    finally:
        config.DB_PATH = real
        db.reset_connection()
        scratch.unlink(missing_ok=True)


def score(correction_id: str, found: dict[str, dict], naive_set: set[str] | None, naive_count: int | None) -> dict:
    spec = KEY["corrections"][correction_id]
    expected = {a: v for a, v in spec["artifacts"].items()}
    universe = set(expected) | set(found)
    tp = fp = fn = tn = 0
    reason_rows = []
    per_artifact = []
    for a in sorted(universe):
        exp = expected.get(a, {"verdict": KEY["default_verdict"], "reason": None})
        got = found.get(a, {"verdict": "unaffected", "reason": "not_reached"})
        e_inv, g_inv = exp["verdict"] == "invalidated", got["verdict"] == "invalidated"
        tp += e_inv and g_inv; fp += (not e_inv) and g_inv; fn += e_inv and not g_inv; tn += (not e_inv) and not g_inv
        if a in expected:
            reason_rows.append((exp["reason"], got.get("reason")))
        per_artifact.append({"artifact": a, "expected": exp["verdict"], "expected_reason": exp.get("reason"), "got": got["verdict"], "got_reason": got.get("reason"),
                             "match": exp["verdict"] == got["verdict"], "reason_match": (exp.get("reason") == got.get("reason")) if a in expected else None})
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    decoys = [a for a, v in expected.items() if v["verdict"] != "invalidated"]
    decoy_ok = sum(1 for a in decoys if found.get(a, {"verdict": "unaffected"})["verdict"] != "invalidated")
    verdict_matches = sum(1 for r in per_artifact if r["match"] and r["artifact"] in expected)
    reason_matches = sum(1 for e, g in reason_rows if e == g)
    must = spec.get("must_stay_valid", [])
    must_ok = [a for a in must if found.get(a, {"verdict": "unaffected"})["verdict"] != "invalidated"]
    true_affected = sum(1 for v in expected.values() if v["verdict"] == "invalidated")
    flagged = tp + fp
    return {"correction": correction_id, "title": spec.get("title"), "kind": spec.get("kind"), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1,
            "n_expected": len(expected), "verdict_matches": verdict_matches, "reason_matches": reason_matches, "n_reasons": len(reason_rows),
            "decoys": len(decoys), "decoys_cleared": decoy_ok, "must_stay_valid": len(must), "must_stay_valid_ok": len(must_ok), "must_stay_valid_failed": [a for a in must if a not in must_ok],
            "true_affected": true_affected, "trackback_flagged": flagged, "naive_flagged": naive_count, "naive_set": sorted(naive_set) if naive_set else None,
            "expected_materiality": spec.get("expected_materiality"), "reason_pairs": reason_rows, "per_artifact": per_artifact}


def naive_sets(correction_id: str) -> tuple[set[str], int]:
    """B1: every artifact of a run that read any version of the corrected source before the correction."""
    corr = db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,))
    if corr is None:
        return set(), 0
    runs = {r["run_id"] for r in db.q("SELECT DISTINCT r.run_id FROM reads r JOIN source_versions sv ON sv.version_id=r.source_version_id WHERE sv.source_id=? AND r.http_status=200 AND r.pinned_at<=?", (corr["source_id"], corr["tx_time"]))}
    arts = {r["artifact_id"] for r in db.q("SELECT DISTINCT artifact_id FROM artifacts WHERE run_id IN (%s)" % ",".join("?" * len(runs)), tuple(runs))} if runs else set()
    seeds = {r["artifact_id"] for r in db.q("SELECT artifact_id FROM impact_findings WHERE correction_id=? AND hop=0 AND reason NOT IN ('different_period','different_line_item','claim_unchanged')", (correction_id,))}
    arts |= seeds
    return arts, len(arts)


def baseline_scores(correction_id: str, naive_set: set[str]) -> dict:
    spec = KEY["corrections"][correction_id]
    expected = spec["artifacts"]
    truth = {a for a, v in expected.items() if v["verdict"] == "invalidated"}
    out = {}
    # B1 source-level
    tp = len(truth & naive_set); fp = len(naive_set - truth); fn = len(truth - naive_set)
    out["B1"] = {"precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0, "flagged": len(naive_set), "true_affected": len(truth)}
    # B2 no tracking
    out["B2"] = {"precision": 1.0 if not truth else 0.0, "recall": 0.0 if truth else 1.0, "flagged": 0, "true_affected": len(truth)}
    # B3 ask-the-agent
    guess = ask_the_agent(correction_id)
    tp = len(truth & guess); fp = len(guess - truth); fn = len(truth - guess)
    out["B3"] = {"precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0, "flagged": len(guess), "true_affected": len(truth), "mode": gateway.mode()}
    return out


def ask_the_agent(correction_id: str) -> set[str]:
    """B3: give the model the correction and the artifact catalog (names, line items, periods) and ask which are now wrong.
    In scripted mode this is a keyword stand-in (line-item match on the changed claims), labeled as such."""
    corr = db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,))
    if corr is None:
        return set()
    changed = [dict(r) for r in db.q("SELECT c.line_item, c.entity, c.period_start FROM claim_diffs d JOIN claims c ON c.claim_id=d.claim_id WHERE d.correction_id=? AND d.change IN ('changed','removed')", (correction_id,))]
    catalog = [dict(r) for r in db.q("SELECT artifact_id, kind, line_item, period, content FROM artifacts WHERE tx_from<=? GROUP BY artifact_id", (corr["tx_time"],))]
    names = {c["artifact_id"] for c in catalog}
    system = "You are a finance analyst. Given a source correction and a list of artifacts (names, line items, periods), list the artifact names that are now wrong. Return JSON: {\"invalidated\": [names]}."
    user = json.dumps({"correction": {"id": correction_id, "note": corr["note"], "changed_claims": changed}, "artifacts": catalog}, default=str)

    def scripted(_):
        words = {(c["line_item"] or "").split("_")[0] for c in changed}
        guess = [a["artifact_id"] for a in catalog if any(w and w in (a["line_item"] or "") for w in words)]
        return {"content": [{"type": "text", "text": json.dumps({"invalidated": guess})}], "stop_reason": "end_turn"}

    try:
        resp, _, _ = gateway.complete(model=config.AGENT_MODEL, system=system, messages=[{"role": "user", "content": user}], tools=None,
                                      params={"max_tokens": 2000, "effort": "low", "json_schema": {"type": "object", "properties": {"invalidated": {"type": "array", "items": {"type": "string"}}}, "required": ["invalidated"], "additionalProperties": False}},
                                      pinned_at=corr["tx_time"], scripted=scripted, purpose=f"B3:{correction_id}")
        raw = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        return {a for a in json.loads(raw).get("invalidated", []) if a in names}
    except Exception:  # noqa: BLE001
        return set()


def leak_test() -> dict:
    """Adversarial agent told to use the latest information: every future-dated fetch must be refused."""
    from fastapi.testclient import TestClient
    from trackback.main import app
    client = TestClient(app)
    pins = [("R1_q1_close", "2026-04-10T17:00:00-07:00"), ("R2_q1_board_deck", "2026-04-24T15:00:00-07:00"), ("R5_cash_refresh_0602", "2026-06-02T09:00:00-07:00")]
    attempts, leaked, refused = [], 0, 0
    for run_id, pin in pins:
        pin_n = db.norm_ts(pin)
        future = db.q("SELECT source_id, version_id, tx_from FROM source_versions WHERE tx_from>? ORDER BY tx_from", (pin_n,))
        for v in future:
            from trackback.memento import ts14
            for path in (f"/m/{v['source_id']}/{ts14(v['tx_from'])}", f"/r/{v['source_id']}"):
                r = client.get(path, headers={"X-Trackback-Run": run_id})
                leak = r.status_code == 200 and r.json().get("version_id") == v["version_id"]
                leaked += leak; refused += (not leak)
                attempts.append({"run": run_id, "path": path, "status": r.status_code, "leaked": bool(leak)})
            r = client.get(f"/tg/{v['source_id']}", headers={"X-Trackback-Run": run_id, "Accept-Datetime": "Thu, 09 Jul 2026 00:00:00 GMT"}, follow_redirects=False)
            leak = r.status_code == 302 and ts14(v["tx_from"]) in r.headers.get("Location", "")
            leaked += leak; refused += (not leak)
            attempts.append({"run": run_id, "path": f"/tg/{v['source_id']} (Accept-Datetime in the future)", "status": r.status_code, "leaked": bool(leak)})
    # the canned sneaky case: a memo whose text claims March 15 but was captured July 1
    r = client.get("/r/memo_backdated_2026_03_15", headers={"X-Trackback-Run": "R1_q1_close"})
    sneaky_refused = r.status_code in (403, 404)
    return {"attempts": len(attempts), "leaked": int(leaked), "refused": int(refused), "sneaky_backdated_memo_refused": sneaky_refused, "sample": attempts[:5]}


def replay_fidelity() -> dict:
    """Re-run every historical agent run pinned, with cached LLM responses only (replay mode), on a scratch DB.
    Each artifact gets a new version; it must be byte-identical (value and text) to the recorded one. Any cache miss is a failure."""
    from trackback.agents import base, workorders as wo
    orders = [wo.with_handoffs(f()) for f in wo.HISTORY_RUNS] + [wo.with_handoffs(wo.r7_ap_run(pin="2026-06-12T09:35:00-07:00", suffix="_v2"))] + [wo.with_handoffs(f()) for f in wo.FOLLOWUPS.values()]
    results = []

    def go_one(o):
        import os
        prev = os.environ.get("TRACKBACK_LLM_MODE")
        os.environ["TRACKBACK_LLM_MODE"] = "replay"
        try:
            for o in [o]:
                orig = {r["artifact_id"]: (r["value_num"], r["content"]) for r in db.q(
                    "SELECT artifact_id, value_num, content FROM artifacts WHERE run_id=? AND version=(SELECT MIN(version) FROM artifacts a2 WHERE a2.artifact_id=artifacts.artifact_id)", (o["run_id"],))}
                try:
                    r = base.run_agent(run_id=o["run_id"], agent=o["agent"], task=o["task"], pinned_at=o["pinned_at"], required_outputs=wo.required_outputs_text(o), script=o["steps"])
                    same = 0
                    for k, v in r["produced"].items():
                        row = db.q1("SELECT value_num, content FROM artifacts WHERE artifact_id=? AND version=?", (k, v))
                        if k in orig and row is not None and _eq(orig[k], (row["value_num"], row["content"])):
                            same += 1
                    results.append({"run": o["run_id"], "artifacts": len(orig), "identical": same, "cache_misses": 0})
                except gateway.CacheMiss as e:
                    results.append({"run": o["run_id"], "artifacts": len(orig), "identical": 0, "cache_misses": 1, "error": str(e)[:120]})
        finally:
            if prev is None:
                os.environ.pop("TRACKBACK_LLM_MODE", None)
            else:
                os.environ["TRACKBACK_LLM_MODE"] = prev
        return results
    for o in orders:  # each run replays on a fresh copy of the snapshot, so replayed versions never shadow recalculated ones
        with_scratch_db(lambda o=o: go_one(o))
    total = sum(r["artifacts"] for r in results); ident = sum(r["identical"] for r in results)
    return {"runs": results, "artifacts": total, "identical": ident, "fidelity": (ident / total) if total else 0.0, "cache_misses": sum(r["cache_misses"] for r in results)}


def _eq(a, b) -> bool:
    va, ca = a; vb, cb = b
    if (va is None) != (vb is None):
        return False
    if va is not None and abs(float(va) - float(vb)) > 1e-9:
        return False
    return (ca or "").split(" [recalculated")[0] == (cb or "")


def judge_agreement(scored: list[dict]) -> dict:
    """Judge agreement on prose edges only: engine prose verdicts vs hand labels, with Cohen's kappa."""
    pairs = []
    for s in scored:
        for r in s["per_artifact"]:
            if r["expected_reason"] == "prose_judged" and r["got_reason"] == "prose_judged":
                pairs.append((r["expected"], r["got"]))
    n = len(pairs)
    if not n:
        return {"n": 0}
    agree = sum(1 for e, g in pairs if e == g) / n
    labels = sorted({x for p in pairs for x in p})
    pe = sum((sum(1 for e, _ in pairs if e == l) / n) * (sum(1 for _, g in pairs if g == l) / n) for l in labels)
    kappa = (agree - pe) / (1 - pe) if pe < 1 else 1.0
    models = Counter(r["judge_model"] for r in db.q("SELECT judge_model FROM impact_findings WHERE reason='prose_judged' AND judge_model IS NOT NULL"))
    return {"n": n, "agreement": agree, "kappa": kappa, "judge_models": dict(models)}


def main() -> None:
    t0 = time.time()
    scored = []
    for cid in HISTORY_CORRECTIONS:
        if cid not in KEY["corrections"]:
            continue
        found = findings_for(cid)
        nset, ncount = naive_sets(cid)
        s = score(cid, found, nset, ncount); s["baselines"] = baseline_scores(cid, nset); scored.append(s)

    def live():
        from trackback import live as L
        out = []
        for cid in LIVE_ORDER:
            if cid not in KEY["corrections"]:
                continue
            if cid == "E11":
                flow = L.drop_e11(); res = flow["correction"]
                e22 = {"draft1_period_locked": bool(db.q1("SELECT 1 FROM events WHERE kind='period_locked' AND detail_json IS NULL AND summary LIKE 'JE-je_e11_dedupe_v1%'") or db.q1("SELECT 1 FROM events WHERE kind='period_locked' AND summary LIKE 'JE-je_e11_dedupe_v1%'")), "self_approval_rejected_by_schema": "approval_error" in flow["draft1"]["result"],
                       "controller_rejected": bool(db.q1("SELECT 1 FROM approvals WHERE action_id='JE-je_e11_dedupe_v1' AND decision='rejected'")),
                       "redraft_posting_period": (db.q1("SELECT params_json FROM actions WHERE action_id='JE-je_e11_dedupe_v2'") or {"params_json": "{}"})["params_json"]}
            elif cid == "E20":
                flow = L.scenario_b(); res = flow["correction"]
            else:
                res = corrections.apply_correction(cid)
            found = {f["artifact_id"]: f for f in res["findings"]}
            nset, ncount = set(res["naive_set"]), res["naive_count"]
            s = score(cid, found, nset, ncount); s["baselines"] = baseline_scores(cid, nset); s["materiality_verdict"] = res["materiality_verdict"]
            s["compensations_found"] = [f.get("compensation") for f in res["findings"] if f.get("compensation")]
            if cid == "E11":
                s["e22"] = e22
            s["values"] = {k: (res_find["new_value"]) for k, res_find in found.items() if k in ("ttm_adj_ebitda_2026_q1", "leverage_2026_q1", "gm_bonus_q1_G4", "gm_bonus_q1_G1", "q2_estimated_tax_2026")}
            out.append(s)
        return out
    scored += with_scratch_db(live)
    for s in scored:
        s["materiality_match"] = (s.get("materiality_verdict") or (db.q1("SELECT materiality_verdict FROM corrections WHERE correction_id=?", (s["correction"],)) or {"materiality_verdict": None})["materiality_verdict"]) == s["expected_materiality"]
        # compensation correctness: expected kinds vs proposed kinds for this correction
        exp = [(c["for"], c["kind"]) for c in KEY["corrections"][s["correction"]].get("compensations", []) if c["kind"] != "redraft"]
        redraft = [c["for"] for c in KEY["corrections"][s["correction"]].get("compensations", []) if c["kind"] == "redraft"]
        s["redraft_ok"] = all((db.q1("SELECT state FROM actions WHERE action_id=?", (a,)) or {"state": None})["state"] in ("stale", "blocked") for a in redraft)
        got_rows = db.q("SELECT kind, params_json FROM actions WHERE run_id=?", (f"correction:{s['correction']}",))
        got = [(json.loads(r["params_json"]).get("compensates"), r["kind"]) for r in got_rows] or [((c or {}).get("params", {}).get("compensates"), (c or {}).get("kind")) for c in s.get("compensations_found", []) if c and c.get("kind") != "redraft"]
        s["compensations"] = {"expected": exp, "got": got, "correct": sorted(exp) == sorted(got) and s["redraft_ok"]}
    # aggregates
    TP = sum(s["tp"] for s in scored); FP = sum(s["fp"] for s in scored); FN = sum(s["fn"] for s in scored); TN = sum(s["tn"] for s in scored)
    prec = TP / (TP + FP) if TP + FP else 1.0; rec = TP / (TP + FN) if TP + FN else 1.0
    decoys = sum(s["decoys"] for s in scored); decoys_ok = sum(s["decoys_cleared"] for s in scored)
    true_aff = sum(s["true_affected"] for s in scored); tb_flag = sum(s["trackback_flagged"] for s in scored); naive_flag = sum(s["naive_flagged"] or 0 for s in scored)
    reason_conf = defaultdict(Counter)
    for s in scored:
        for e, g in s["reason_pairs"]:
            reason_conf[e][g] += 1
    b1p = [s["baselines"]["B1"]["precision"] for s in scored]; b1r = [s["baselines"]["B1"]["recall"] for s in scored]
    b3p = [s["baselines"]["B3"]["precision"] for s in scored]; b3r = [s["baselines"]["B3"]["recall"] for s in scored]
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "llm_mode": gateway.mode(), "answer_key": key_hash(),
        "n_corrections": len(scored), "n_artifacts": db.q1("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts")["n"], "n_edges": db.q1("SELECT COUNT(*) n FROM justifications")["n"],
        "n_findings": db.q1("SELECT COUNT(*) n FROM impact_findings")["n"], "n_claim_versions": db.q1("SELECT COUNT(*) n FROM claim_versions")["n"],
        "invalidated": {"tp": TP, "fp": FP, "fn": FN, "tn": TN, "precision": prec, "recall": rec, "f1": (2 * prec * rec / (prec + rec)) if prec + rec else 0.0},
        "specificity_on_decoys": {"decoys": decoys, "cleared": decoys_ok, "specificity": decoys_ok / decoys if decoys else 1.0},
        "over_invalidation": {"true_affected": true_aff, "trackback_flagged": tb_flag, "trackback_ratio": tb_flag / true_aff if true_aff else None, "B1_flagged": naive_flag, "B1_ratio": naive_flag / true_aff if true_aff else None},
        "verdict_accuracy": {"expected": sum(s["n_expected"] for s in scored), "matched": sum(s["verdict_matches"] for s in scored)},
        "reason_accuracy": {"n": sum(s["n_reasons"] for s in scored), "matched": sum(s["reason_matches"] for s in scored)},
        "reason_confusion": {e: dict(c) for e, c in reason_conf.items()},
        "materiality_matches": sum(1 for s in scored if s["materiality_match"]),
        # corrections that expect or produce a compensation, and how many of those got exactly the expected set
        "compensation_total": sum(1 for s in scored if KEY["corrections"][s["correction"]].get("compensations") or s["compensations"]["got"]),
        "compensation_correct": sum(1 for s in scored if (KEY["corrections"][s["correction"]].get("compensations") or s["compensations"]["got"]) and s["compensations"]["correct"]),
        "baselines": {"B1": {"precision_mean": sum(b1p) / len(b1p), "recall_mean": sum(b1r) / len(b1r)}, "B2": {"precision": 0.0, "recall": 0.0},
                      "B3": {"precision_mean": sum(b3p) / len(b3p), "recall_mean": sum(b3r) / len(b3r), "mode": gateway.mode(), "note": "scripted mode uses a keyword stand-in for the agent; re-run with TRACKBACK_LLM_MODE=record for the real baseline" if gateway.mode() != "record" else "real model"}},
        "memento_leak_test": with_scratch_db(leak_test),   # the adversarial fetches log reads; keep them out of the working database
        "replay_fidelity": replay_fidelity(),
        "judge_agreement": judge_agreement(scored),
        "per_correction": scored,
        "real_vs_simulated": {"real": ["claim graph, propagation engine, early cutoff and materiality logic", "Memento service, TimeMaps, pin enforcement and refusals", "typed-tool provenance capture, LLM judge (cached)", "ledger, compensations, approvals with schema-enforced segregation of duties", "Lyft, Feb 13, 2024: the release as filed (500 basis points), the CFO's correction on the call (50), the tape"],
                              "simulated": ["Tidewall Climbing Co., its gyms, vendors, customers and people", "bank feed, ACH processor, billing system, AP inbox", "the 23 planted errors (designed from cited accounting rules)", "lender, credit agreement and covenant definition", "agent runs: recorded Claude responses where cache keys match, otherwise the labeled scripted stand-in (see cache counts on the proof page)", "Lyft finance-team documents and outside dependents (reconstructed from the public numbers)"]},
        "seconds": time.time() - t0,
    }
    config.EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.EVAL_PATH.write_text(json.dumps(out, indent=1, default=str))
    inv = out["invalidated"]
    print(f"eval: {out['n_corrections']} corrections, invalidated precision {inv['precision']:.3f} recall {inv['recall']:.3f} f1 {inv['f1']:.3f}; decoy specificity {out['specificity_on_decoys']['specificity']:.3f}; "
          f"over-invalidation Trackback {out['over_invalidation']['trackback_ratio']} vs B1 {out['over_invalidation']['B1_ratio']}; verdicts {out['verdict_accuracy']['matched']}/{out['verdict_accuracy']['expected']}; "
          f"reasons {out['reason_accuracy']['matched']}/{out['reason_accuracy']['n']}; leaks {out['memento_leak_test']['leaked']}/{out['memento_leak_test']['attempts']}; replay {out['replay_fidelity']['identical']}/{out['replay_fidelity']['artifacts']}")
    for s in scored:
        bad = [r for r in s["per_artifact"] if not r["match"] or (r["reason_match"] is False)]
        print(f"  {s['correction']:<17} P={s['precision']:.2f} R={s['recall']:.2f} verdicts {s['verdict_matches']}/{s['n_expected']} reasons {s['reason_matches']}/{s['n_reasons']} naive={s['naive_flagged']} comp_ok={s['compensations']['correct']} mat_ok={s['materiality_match']}")
        for r in bad[:12]:
            print(f"      {r['artifact']:<36} expected {r['expected']}/{r['expected_reason']}  got {r['got']}/{r['got_reason']}")


if __name__ == "__main__":
    main()
