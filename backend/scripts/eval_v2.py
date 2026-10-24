"""Iteration-2 evaluation: the rules-based key (answer_key_v2.yaml) resolved against whatever artifacts exist, plus the multi-agent
metrics: ping precision/recall/F1, false still_valid rate, unnecessary rework, inspection fraction, preservation, rework correctness,
cross-agent consistency, cost (LLM calls vs rerun-all), convergence, compensation precision/recall, replay fidelity. Baselines
B0 (no tracking), B1 (rerun all agents), B2 (ping every descendant). Everything comes from SQLite logs and the key; nothing typed.
Writes data/eval/latest_v2.json (eval.py's latest.json keeps the iteration-1 per-artifact scores)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import config, corrections, scenarios  # noqa: E402
from trackback.core import db, graph  # noqa: E402
from trackback.core.llm import gateway  # noqa: E402

KEY_PATH = config.DATA_DIR / "answer_key" / "answer_key_v2.yaml"
KEY = yaml.safe_load(KEY_PATH.read_text())
OUT = config.DATA_DIR / "eval" / "latest_v2.json"
LIVE = ["E11", "E20", "E26"]


def key_hash() -> dict:
    try:
        commit = subprocess.run(["git", "log", "-1", "--format=%H %cI", "--", str(KEY_PATH)], capture_output=True, text=True, cwd=config.ROOT).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = ""
    return {"sha256": hashlib.sha256(KEY_PATH.read_bytes()).hexdigest(), "frozen": KEY.get("frozen"), "git": commit}


def with_scratch(fn):
    scratch = config.DATA_DIR / "eval" / "scratch_v2.sqlite"
    src = config.SNAPSHOT_PATH if config.SNAPSHOT_PATH.exists() else config.DB_PATH
    db.reset_connection()
    s = sqlite3.connect(str(src)); d = sqlite3.connect(str(scratch)); s.backup(d); d.close(); s.close()
    real = config.DB_PATH; config.DB_PATH = scratch; db.reset_connection()
    try:
        return fn()
    finally:
        config.DB_PATH = real; db.reset_connection()
        for suf in ("", "-wal", "-shm"):
            Path(str(scratch) + suf).unlink(missing_ok=True)


def resolve_cid(key_id: str) -> str | None:
    spec = KEY["corrections"][key_id]
    if spec.get("correction_id_prefix"):
        r = db.q1("SELECT correction_id FROM corrections WHERE correction_id LIKE ? ORDER BY tx_time LIMIT 1", (spec["correction_id_prefix"] + "%",))
        return r["correction_id"] if r else None
    if spec.get("wave_of"):
        return spec["wave_of"]
    return key_id


def pings_for(cid: str) -> list[dict]:
    out = []
    for p in db.q("SELECT * FROM pings WHERE correction_id=? ORDER BY created_at", (cid,)):
        d = dict(p); d["items"] = [i["artifact_id"] for i in json.loads(p["payload_json"])["data"]["your_nodes"]]
        r = db.q1("SELECT items_json FROM ping_responses WHERE ping_id=? ORDER BY responded_at DESC LIMIT 1", (p["ping_id"],))
        d["responses"] = json.loads(r["items_json"]) if r else []
        out.append(d)
    return out


def findings_for(cid: str) -> dict[str, dict]:
    return {r["artifact_id"]: dict(r) for r in db.q("SELECT * FROM impact_findings WHERE correction_id=?", (cid,))}


def score_one(key_id: str) -> dict:
    spec = KEY["corrections"][key_id]
    cid = resolve_cid(key_id)
    if cid is None:
        return {"key": key_id, "missing": True}
    found = findings_for(cid)
    pings = pings_for(cid)
    pinged_agents = {p["target_agent_id"] for p in pings if p["state"] != "refused"}
    pinged_nodes = {a for p in pings if p["state"] != "refused" for a in p["items"]}
    verdict_by_node = {r["artifact_id"]: r["verdict"] for p in pings for r in p["responses"]}
    exp_agents = {a for a, v in (spec.get("must_ping") or {}).items() if v}
    must_nodes = set(spec.get("must_ping_nodes") or [])
    must_not = set(spec.get("must_not_ping_nodes") or [])
    # ping precision/recall by node against must_ping_nodes (nodes the key says must be pinged) and must_not_ping_nodes
    tp = len(pinged_nodes & must_nodes); fp = len(pinged_nodes & must_not); fn = len(must_nodes - pinged_nodes)
    # false still_valid: nodes the key expects reworked/needs_human that the agent cleared as still_valid
    must_change = set(spec.get("reworked_expected") or []) | set(spec.get("needs_human_expected") or [])
    false_sv = [n for n in must_change if verdict_by_node.get(n) == "still_valid"]
    # unnecessary rework: reworked nodes that were in must_stay (must_not) or whose hash did not change
    unnecessary = []
    for n, v in verdict_by_node.items():
        if v == "reworked":
            vs = db.q("SELECT content_hash FROM artifacts WHERE artifact_id=? ORDER BY version DESC LIMIT 2", (n,))
            if n in must_not or (len(vs) == 2 and vs[0]["content_hash"] == vs[1]["content_hash"]):
                unnecessary.append(n)
    # preservation: must_not nodes whose current hash equals the hash before the correction (no new version at/after tx)
    corr = db.q1("SELECT tx_time FROM corrections WHERE correction_id=?", (cid,))
    ping_runs = [f"ping:{p['ping_id']}" for p in pings]
    writers = [f"correction:{cid}"] + ping_runs
    preserved = [n for n in must_not if not db.q1(f"SELECT 1 FROM artifacts WHERE artifact_id=? AND run_id IN ({','.join('?' * len(writers))}) AND origin IN ('rework','source_correction')", (n, *writers))] if corr else []
    # rework correctness: expected values and conclusion labels
    values_ok, values_n = 0, 0
    for aid, exp in (spec.get("expected_values") or {}).items():
        values_n += 1
        f = found.get(aid)
        if f and f.get("new_value") is not None and abs(f["new_value"] - exp) <= max(0.005, abs(exp) * 0.001):
            values_ok += 1
    # compensations
    exp_comp = {(c["deliverable"], c["compensation"]) for c in spec.get("required_compensations") or []}
    got_rows = db.q("SELECT kind, params_json FROM actions WHERE run_id=?", (f"correction:{cid}",))
    got_comp = {((db.q1("SELECT artifact_id FROM actions WHERE action_id=?", (json.loads(r["params_json"]).get("compensates"),)) or {"artifact_id": None})["artifact_id"], r["kind"]) for r in got_rows}
    comp_tp = len(exp_comp & got_comp); comp_fp = len(got_comp - exp_comp); comp_fn = len(exp_comp - got_comp)
    amounts_ok = all(any(abs((json.loads(r["params_json"]).get("amount") or 0) - c["amount"]) < 1 for r in got_rows if r["kind"] == c["compensation"]) for c in (spec.get("required_compensations") or []) if c.get("amount"))
    # inspection fraction and cost
    total_nodes = db.q1("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts WHERE tx_from<=?", (corr["tx_time"],))["n"] if corr else 0
    inspected = sum(1 for f in found.values() if f["reason"] not in ("different_period", "different_line_item", "claim_unchanged"))
    waves = [dict(w) for w in db.q("SELECT * FROM waves WHERE correction_id=?", (cid,))]
    llm_calls = db.q1("SELECT COUNT(*) n FROM llm_calls WHERE ping_id IN (SELECT ping_id FROM pings WHERE correction_id=?) AND cache_hit=0", (cid,))["n"]
    stats = [json.loads(w["stats_json"]) for w in waves if w["stats_json"]]
    rerun_all_calls = db.q1("SELECT COUNT(*) n FROM llm_cache WHERE request_json LIKE '%\"purpose\":\"agent:%'")["n"]
    unprovable_ok = all(found.get(n, {}).get("verdict") == "unprovable" for n in spec.get("unprovable_expected") or [])
    return {"key": key_id, "correction_id": cid, "title": spec.get("title"), "category": spec.get("category"),
            "pinged_agents": sorted(pinged_agents), "expected_agents": sorted(exp_agents), "agents_match": pinged_agents == exp_agents,
            "ping_tp": tp, "ping_fp": fp, "ping_fn": fn, "ping_precision": tp / (tp + fp) if tp + fp else 1.0, "ping_recall": tp / (tp + fn) if tp + fn else 1.0,
            "pinged_nodes": sorted(pinged_nodes), "verdicts": verdict_by_node, "false_still_valid": false_sv, "must_change_n": len(must_change),
            "unnecessary_rework": unnecessary, "reworked_n": sum(1 for v in verdict_by_node.values() if v == "reworked"),
            "preserved": len(preserved), "must_stay_n": len(must_not),
            "values_ok": values_ok, "values_n": values_n, "unprovable_ok": unprovable_ok,
            "comp_tp": comp_tp, "comp_fp": comp_fp, "comp_fn": comp_fn, "comp_amounts_ok": amounts_ok, "compensations_got": sorted(got_comp),
            "inspected": inspected, "total_nodes": total_nodes, "inspection_fraction": inspected / total_nodes if total_nodes else None,
            "waves": len(waves), "waves_max": spec.get("waves_max"), "llm_calls_live": llm_calls, "llm_calls_in_wave": sum(s.get("llm_calls", 0) for s in stats), "rerun_all_calls": rerun_all_calls,
            "counts": {v: sum(1 for f in found.values() if f["verdict"] == v) for v in ("invalidated", "unaffected", "needs_review", "unprovable")}}


def baselines(scored: list[dict]) -> dict:
    """B0 no tracking: stale artifacts left behind = nodes the key expects changed. B1 rerun all: every agent pinged on every event, every node
    reworked (cost = all agent runs). B2 ping every descendant: no cutoff, no field relevance."""
    b0_stale = sum(s["must_change_n"] + s["values_n"] for s in scored if not s.get("missing"))
    b1 = {"agents_pinged_per_event": 3, "precision_agents": None, "cost_calls_per_event": None}
    n_runs = db.q1("SELECT COUNT(*) n FROM runs WHERE trigger IS NULL OR trigger<>'ping'")["n"]
    b1["cost_calls_per_event"] = db.q1("SELECT COUNT(*) n FROM llm_cache WHERE request_json LIKE '%\"purpose\":\"agent:%'")["n"]
    b2_fp = 0; b2_tp = 0; b2_fn = 0
    for s in scored:
        if s.get("missing"):
            continue
        spec = KEY["corrections"][s["key"]]
        cid = s["correction_id"]
        # every descendant of the seeds (findings with hop>=0 that are prose/action), regardless of materiality
        desc = {f["artifact_id"] for f in db.q("SELECT artifact_id FROM impact_findings WHERE correction_id=?", (cid,)) if (db.artifact_current(f["artifact_id"]) or {"kind": ""})["kind"] in ("sentence", "action")}
        must = set(spec.get("must_ping_nodes") or []); must_not = set(spec.get("must_not_ping_nodes") or [])
        b2_tp += len(desc & must); b2_fp += len(desc & must_not); b2_fn += len(must - desc)
    exp_agent_events = sum(len([a for a, v in (KEY["corrections"][s["key"]].get("must_ping") or {}).items() if v]) for s in scored if not s.get("missing"))
    return {"B0_no_tracking": {"stale_artifacts_left": b0_stale, "pings": 0},
            "B1_rerun_all": {"agents_pinged_per_event": 3, "agent_ping_precision": exp_agent_events / (3 * len(scored)) if scored else None, "llm_calls": b1["cost_calls_per_event"], "runs": n_runs},
            "B2_ping_every_descendant": {"ping_tp": b2_tp, "ping_fp": b2_fp, "ping_fn": b2_fn, "precision": b2_tp / (b2_tp + b2_fp) if b2_tp + b2_fp else 1.0, "recall": b2_tp / (b2_tp + b2_fn) if b2_tp + b2_fn else 1.0}}


def replay_fidelity() -> dict:
    """Memento reconstruction: re-run every recorded run in replay mode on a fresh copy; byte-identical artifacts required."""
    from trackback.agents import base, workorders as wo
    orders = [wo.with_handoffs(f()) for f in wo.HISTORY_RUNS] + [wo.with_handoffs(wo.r7_ap_run(pin="2026-06-12T09:35:00-07:00", suffix="_v2"))] + [wo.with_handoffs(f()) for f in wo.FOLLOWUPS.values()]
    results = []
    import os
    for o in orders:
        def go(o=o):
            prev = os.environ.get("TRACKBACK_LLM_MODE"); os.environ["TRACKBACK_LLM_MODE"] = "replay"
            try:
                orig = {r["artifact_id"]: (r["value_num"], r["content"]) for r in db.q("SELECT artifact_id, value_num, content FROM artifacts WHERE run_id=? AND version=(SELECT MIN(version) FROM artifacts a2 WHERE a2.artifact_id=artifacts.artifact_id)", (o["run_id"],))}
                try:
                    r = base.run_agent(run_id=o["run_id"], agent=o["agent"], task=o["task"], pinned_at=o["pinned_at"], required_outputs=wo.required_outputs_text(o), script=o["steps"])
                    same = sum(1 for k, v in r["produced"].items() if k in orig and (row := db.q1("SELECT value_num, content FROM artifacts WHERE artifact_id=? AND version=?", (k, v))) and
                               ((row["value_num"] is None) == (orig[k][0] is None)) and (row["value_num"] is None or abs(row["value_num"] - orig[k][0]) < 1e-9) and (row["content"] or "").split(" [recalculated")[0] == (orig[k][1] or "").split(" [recalculated")[0])
                    results.append({"run": o["run_id"], "artifacts": len(orig), "identical": same, "cache_misses": 0})
                except gateway.CacheMiss as e:
                    results.append({"run": o["run_id"], "artifacts": len(orig), "identical": 0, "cache_misses": 1, "error": str(e)[:100]})
            finally:
                if prev is None: os.environ.pop("TRACKBACK_LLM_MODE", None)
                else: os.environ["TRACKBACK_LLM_MODE"] = prev
        with_scratch(go)
    total = sum(r["artifacts"] for r in results); ident = sum(r["identical"] for r in results)
    return {"runs": results, "artifacts": total, "identical": ident, "fidelity": ident / total if total else 0.0, "cache_misses": sum(r["cache_misses"] for r in results)}


def merge_into_latest(agg: dict) -> None:
    """data/eval/latest.json is the one file the proof page and the goal read: the per-artifact scorer writes it, this adds the
    multi-agent block and a headline block whose every value is copied from a computed field (never typed)."""
    latest_p = config.DATA_DIR / "eval" / "latest.json"
    latest = json.loads(latest_p.read_text()) if latest_p.exists() else {}
    pr = agg["ping_precision_recall"]; fsv = agg["false_still_valid"]; cost = agg["cost"]
    oi = latest.get("over_invalidation", {}); leak = latest.get("memento_leak_test", {}); rep = latest.get("replay_fidelity", {})
    latest["multi_agent"] = {k: agg[k] for k in ("generated_at", "answer_key_v2", "n_events", "ping_precision_recall", "agents_match", "false_still_valid", "unnecessary_rework",
                                                 "preservation", "rework_correctness", "compensations", "inspection_fraction_mean", "convergence", "cost", "tie_outs", "baselines", "replay_fidelity")}
    latest["headline"] = {
        "ping_precision": pr["precision"], "ping_recall": pr["recall"],
        "false_still_valid_rate": (fsv["n"] / fsv["of"]) if fsv["of"] else 0.0, "false_still_valid": f"{fsv['n']} of {fsv['of']}",
        "over_invalidation_trackback": oi.get("trackback_ratio"), "over_invalidation_B1": oi.get("B1_ratio"),
        "llm_calls_in_waves": cost.get("llm_calls_in_waves"), "llm_calls_rerun_all": cost.get("rerun_all_calls"),
        "memento_leaks": leak.get("leaked"), "memento_attempts": leak.get("attempts"),
        "replay_fidelity": rep.get("fidelity"), "replay_identical": rep.get("identical"), "replay_artifacts": rep.get("artifacts"),
        "multi_agent_replay_fidelity": agg["replay_fidelity"].get("fidelity"),
        "sources": "copied from computed fields of this file and latest_v2.json by backend/scripts/eval_v2.py",
    }
    latest_p.write_text(json.dumps(latest, indent=1, default=str))


def main() -> None:
    t0 = time.time()
    history_keys = [k for k in KEY["corrections"] if k not in LIVE and not str(k).startswith("X3")]
    scored = [score_one(k) for k in history_keys]

    def live():
        from trackback import live as L
        out = []
        flow = L.drop_e11(); out.append(score_one("E11"))
        out[-1]["e22"] = {"draft1_period_locked": bool(db.q1("SELECT 1 FROM events WHERE kind='period_locked' AND summary LIKE 'JE-je_e11_dedupe_v1%'")),
                          "self_approval_rejected_by_schema": "approval_error" in flow["draft1"]["result"], "controller_rejected": bool(db.q1("SELECT 1 FROM approvals WHERE action_id='JE-je_e11_dedupe_v1' AND decision='rejected'"))}
        ch = db.q1("SELECT state, correction_id FROM upstream_challenges WHERE from_agent_id='reporting_analyst' ORDER BY created_at DESC LIMIT 1")
        out[-1]["x3"] = {"filed": ch is not None, "state": ch["state"] if ch else None, "started_wave": bool(ch and ch["correction_id"])}
        L.scenario_b(); out.append(score_one("E20"))
        corrections.apply_correction("E26"); out.append(score_one("E26"))
        return out
    scored += with_scratch(live)
    ok = [s for s in scored if not s.get("missing")]
    agg = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "llm_mode": gateway.mode(), "answer_key_v2": key_hash(),
        "n_events": len(ok),
        "ping_precision_recall": {"tp": sum(s["ping_tp"] for s in ok), "fp": sum(s["ping_fp"] for s in ok), "fn": sum(s["ping_fn"] for s in ok)},
        "agents_match": sum(1 for s in ok if s["agents_match"]),
        "false_still_valid": {"n": sum(len(s["false_still_valid"]) for s in ok), "of": sum(s["must_change_n"] for s in ok), "cases": [(s["key"], x) for s in ok for x in s["false_still_valid"]]},
        "unnecessary_rework": {"n": sum(len(s["unnecessary_rework"]) for s in ok), "of": sum(s["reworked_n"] for s in ok)},
        "preservation": {"preserved": sum(s["preserved"] for s in ok), "of": sum(s["must_stay_n"] for s in ok)},
        "rework_correctness": {"values_ok": sum(s["values_ok"] for s in ok), "values_n": sum(s["values_n"] for s in ok), "unprovable_ok": all(s["unprovable_ok"] for s in ok)},
        "compensations": {"tp": sum(s["comp_tp"] for s in ok), "fp": sum(s["comp_fp"] for s in ok), "fn": sum(s["comp_fn"] for s in ok), "amounts_ok": all(s["comp_amounts_ok"] for s in ok)},
        "inspection_fraction_mean": sum(s["inspection_fraction"] or 0 for s in ok) / len(ok) if ok else None,
        "convergence": {"max_waves": max(s["waves"] for s in ok) if ok else 0, "events_over_cap": sum(1 for s in ok if s["waves_max"] and s["waves"] > s["waves_max"])},
        "cost": {"llm_calls_in_waves": sum(s["llm_calls_in_wave"] for s in ok), "rerun_all_calls": ok[0]["rerun_all_calls"] if ok else None},
        "tie_outs": with_scratch(tie_outs),
        "baselines": baselines(ok),
        "replay_fidelity": replay_fidelity(),
        "per_event": scored, "seconds": time.time() - t0,
    }
    pr = agg["ping_precision_recall"]; pr["precision"] = pr["tp"] / (pr["tp"] + pr["fp"]) if pr["tp"] + pr["fp"] else 1.0; pr["recall"] = pr["tp"] / (pr["tp"] + pr["fn"]) if pr["tp"] + pr["fn"] else 1.0
    OUT.write_text(json.dumps(agg, indent=1, default=str))
    merge_into_latest(agg)
    print(f"eval v2: {agg['n_events']} events; ping P={pr['precision']:.3f} R={pr['recall']:.3f}; agents match {agg['agents_match']}/{agg['n_events']}; false still_valid {agg['false_still_valid']['n']}/{agg['false_still_valid']['of']}; "
          f"unnecessary rework {agg['unnecessary_rework']['n']}/{agg['unnecessary_rework']['of']}; preserved {agg['preservation']['preserved']}/{agg['preservation']['of']}; comps tp/fp/fn {agg['compensations']['tp']}/{agg['compensations']['fp']}/{agg['compensations']['fn']} amounts_ok {agg['compensations']['amounts_ok']}; "
          f"inspection {agg['inspection_fraction_mean']:.2f}; waves max {agg['convergence']['max_waves']}; replay {agg['replay_fidelity']['identical']}/{agg['replay_fidelity']['artifacts']}")
    for s in scored:
        if s.get("missing"):
            print(f"  {s['key']:<18} MISSING"); continue
        flag = "" if (s["agents_match"] and not s["ping_fp"] and not s["ping_fn"] and not s["false_still_valid"] and s["comp_fp"] == 0 and s["comp_fn"] == 0) else "  <-- check"
        print(f"  {s['key']:<18} agents {s['pinged_agents']} vs {s['expected_agents']} | nodes tp/fp/fn {s['ping_tp']}/{s['ping_fp']}/{s['ping_fn']} | fsv {len(s['false_still_valid'])} | comps {s['comp_tp']}/{s['comp_fp']}/{s['comp_fn']} | waves {s['waves']}{flag}")


def tie_outs() -> dict:
    from trackback.core.domain import get_domain
    dom = get_domain()
    arts = [graph.artifact_dict(r) for r in db.q("SELECT a.* FROM artifacts a WHERE a.version=(SELECT MAX(version) FROM artifacts b WHERE b.artifact_id=a.artifact_id) AND a.kind IN ('number','forecast_cell')")]
    checks = dom.tie_out_checks(arts)
    return {"n": len(checks), "ok": sum(1 for c in checks if c["ok"]), "failed": [c["name"] for c in checks if not c["ok"]][:20]}


if __name__ == "__main__":
    main()
