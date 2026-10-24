"""Jade and the learning experiment, scored from runs, never typed. Writes the `learning` block into data/eval/latest.json and adds
its headline numbers to the `headline` block.

On a scratch copy of the canonical snapshot (live E11 and E20 applied, so the planted agent mistakes exist):
1. Jade: for every evaluated case under playbook v1, which claims are wrong (against the engines and the frozen answer key's kind and
   materiality), and whether Jade overruled exactly those: catch rate on planted mistakes, false-overrule rate on correct claims.
2. Learning, held out: cases split by kind (even/odd within each kind) into a training half and a held-out half. v1 runs on the
   training half; its mistakes propose lessons; each lesson goes through the regression gate on the training half; the Controller
   approves the ones that pass; v2 runs on the held-out half. Reported: v1 vs v2 claim accuracy on held-out cases, the lessons
   approved, the lessons the gate rejected (with the cases that would have flipped).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TRACKBACK_LLM_MODE", "replay")

from trackback import config, db  # noqa: E402

KEY = yaml.safe_load(config.ANSWER_KEY_PATH.read_text())
MATERIAL = {"escalate", "book_and_evaluate", "little_r", "big_r"}


def with_scratch_db(fn):
    scratch = config.DATA_DIR / "eval" / "scratch_learning.sqlite"
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


def key_truth(cid: str, facts: dict) -> dict:
    """Independent of the engines where the key speaks: kind and expected materiality from the frozen answer key."""
    k = KEY["corrections"].get(cid, {})
    kind = k.get("kind") or facts["kind"]
    mat = k.get("expected_materiality")
    return {"classification": "error" if kind == "error" else "new information", "material": (mat in MATERIAL) if mat else (facts["engine_verdict"] in MATERIAL)}


def claim_right(claim: str, claims: dict, facts: dict, kt: dict) -> bool:
    from trackback import review
    if claim == "classification":
        return claims["classification"]["value"] == kt["classification"]
    if claim == "materiality":
        return bool(claims["materiality"]["value"]) == kt["material"]
    if claim == "posting":
        return not review._locked(claims["posting"]["value"])
    if claim == "routing":
        need = review.truth(facts)["approvers"]
        return all(r in claims["routing"]["value"] for r in need)
    raise KeyError(claim)


def main() -> None:
    t0 = time.time()
    from trackback import lessons, live, review

    def run():
        live.drop_e11(); live.scenario_b()
        cases = [r["correction_id"] for r in db.q("SELECT correction_id FROM corrections WHERE correction_id NOT LIKE 'REV-%' AND correction_id<>'LYFT_TYPO' ORDER BY tx_time")]
        facts = {c: review.case_facts(c) for c in cases}
        facts = {c: f for c, f in facts.items() if f}
        # ---- 1. Jade on playbook v1
        jade = {"cases": 0, "claims": 0, "planted_mistakes": 0, "caught": 0, "correct_claims": 0, "false_overrules": 0, "by_claim": defaultdict(lambda: {"mistakes": 0, "caught": 0}), "detail": []}
        for c, f in facts.items():
            kt = key_truth(c, f)
            claims = review.playbook_claims(f, set())
            j = review.jade_review(f, claims)
            jade["cases"] += 1
            for k in review.CLAIMS:
                right = claim_right(k, claims, f, kt)
                over = j[k]["verdict"] == "overrule"
                jade["claims"] += 1
                if right:
                    jade["correct_claims"] += 1
                    if over:
                        jade["false_overrules"] += 1
                else:
                    jade["planted_mistakes"] += 1; jade["by_claim"][k]["mistakes"] += 1
                    if over:
                        jade["caught"] += 1; jade["by_claim"][k]["caught"] += 1
                if not right or over:
                    jade["detail"].append({"case": c, "claim": k, "agent": claims[k]["value"], "jade": j[k]["jade"], "agent_right": right, "jade_overruled": over})
        jade["catch_rate"] = jade["caught"] / jade["planted_mistakes"] if jade["planted_mistakes"] else 1.0
        jade["false_overrule_rate"] = jade["false_overrules"] / jade["correct_claims"] if jade["correct_claims"] else 0.0
        jade["by_claim"] = dict(jade["by_claim"])
        # ---- 2. held-out learning
        by_kind = defaultdict(list)
        for c in facts:
            by_kind[facts[c]["kind"]].append(c)
        train, held = [], []
        for kind in sorted(by_kind):
            for i, c in enumerate(sorted(by_kind[kind], key=lambda x: facts[x]["tx_time"])):
                (train if i % 2 == 0 else held).append(c)
        conn = db.get_conn(); conn.execute("DELETE FROM lessons"); conn.execute("DELETE FROM evaluations"); conn.commit()
        sigs = {c: review.signature(f) for c, f in facts.items()}
        for c in train:                       # v1 on the training half, in time order; overrules propose lessons
            claims = review.playbook_claims(facts[c], set())
            j = review.jade_review(facts[c], claims)
            for k in j["summary"]["overruled_claims"]:
                lessons.propose_from_overrule(k, c, j[k], sigs[c], facts[c]["tx_time"])
        # the Controller's rejection of the E11 first draft is a human signal (narrow and broad lessons)
        if "E11" in train or "E11" in held:
            lessons.signal_rejection("E11", "JE-je_e11_dedupe_v1", config.PEOPLE["controller"], live.E22_REASON, "2026-07-08T09:12:00-07:00")
        gate_results = {}
        approved, rejected = [], []
        for l in lessons.all_lessons():
            g = lessons.gate(l["lesson_id"], "2026-07-08T10:00:00-07:00", baseline=set(x for x in lessons.active_checks()), cases=train)
            gate_results[l["lesson_id"]] = {k: g[k] for k in ("cases", "pass_before", "pass_after", "newly_failing", "newly_passing", "passed")}
            if g["passed"]:
                lessons.approve(l["lesson_id"], config.PEOPLE["controller"], "2026-07-08T10:00:00-07:00"); approved.append(l["lesson_id"])
            else:
                rejected.append(l["lesson_id"])
        v2 = lessons.active_checks()

        def score(cases, active):
            acc = {k: {"right": 0, "n": 0} for k in review.CLAIMS}
            for c in cases:
                kt = key_truth(c, facts[c]); claims = review.playbook_claims(facts[c], active)
                for k in review.CLAIMS:
                    acc[k]["n"] += 1; acc[k]["right"] += int(claim_right(k, claims, facts[c], kt))
            tot_r = sum(a["right"] for a in acc.values()); tot_n = sum(a["n"] for a in acc.values())
            return {"by_claim": acc, "right": tot_r, "n": tot_n, "accuracy": tot_r / tot_n if tot_n else 1.0}

        learning = {"split": {"train": train, "held_out": held, "rule": "by kind, even/odd in time order"},
                    "v1_held_out": score(held, set()), "v2_held_out": score(held, v2), "v1_train": score(train, set()), "v2_train": score(train, v2),
                    "lessons_approved": approved, "lessons_rejected_by_gate": rejected, "gate": gate_results, "active_checks": sorted(v2), "playbook_version": review.playbook_version(v2)}
        return {"jade": jade, "learning": learning, "n_cases": len(facts)}

    out = with_scratch_db(run)
    out["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S"); out["seconds"] = round(time.time() - t0, 1)
    latest_p = config.DATA_DIR / "eval" / "latest.json"
    latest = json.loads(latest_p.read_text()) if latest_p.exists() else {}
    latest["learning"] = out
    h = latest.setdefault("headline", {})
    h.update({"jade_catch_rate": out["jade"]["catch_rate"], "jade_planted_mistakes": out["jade"]["planted_mistakes"], "jade_caught": out["jade"]["caught"],
              "jade_false_overrule_rate": out["jade"]["false_overrule_rate"], "jade_correct_claims": out["jade"]["correct_claims"],
              "learning_v1_held_out": out["learning"]["v1_held_out"]["accuracy"], "learning_v2_held_out": out["learning"]["v2_held_out"]["accuracy"],
              "learning_held_out_claims": out["learning"]["v1_held_out"]["n"], "lessons_approved": len(out["learning"]["lessons_approved"]), "lessons_rejected_by_gate": len(out["learning"]["lessons_rejected_by_gate"])})
    latest_p.write_text(json.dumps(latest, indent=1, default=str))
    j, L = out["jade"], out["learning"]
    print(f"Jade on playbook v1: {j['caught']} of {j['planted_mistakes']} planted mistakes caught (catch rate {j['catch_rate']:.3f}); false overrules {j['false_overrules']} of {j['correct_claims']} correct claims ({j['false_overrule_rate']:.3f})")
    print(f"  by claim: " + ", ".join(f"{k} {v['caught']}/{v['mistakes']}" for k, v in j["by_claim"].items()))
    print(f"Learning, held out ({len(L['split']['held_out'])} cases, {L['v1_held_out']['n']} claims): v1 {L['v1_held_out']['right']}/{L['v1_held_out']['n']} = {L['v1_held_out']['accuracy']:.3f} -> v2 {L['v2_held_out']['right']}/{L['v2_held_out']['n']} = {L['v2_held_out']['accuracy']:.3f} (playbook {L['playbook_version']})")
    print(f"  lessons approved: {', '.join(L['lessons_approved'])}; rejected by the gate: {', '.join(L['lessons_rejected_by_gate']) or 'none'}")
    for lid in L["lessons_rejected_by_gate"]:
        print(f"    {lid}: would flip " + ", ".join(f"{x['case_id']}:{x['claim']}" for x in L["gate"][lid]["newly_failing"][:5]))
    print(f"wrote {latest_p} in {out['seconds']}s")


if __name__ == "__main__":
    main()
