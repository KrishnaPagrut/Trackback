"""Finance domain pack for Trackback: materiality, period locks, estimate-vs-error, "not affected" reasons, the compensation
catalog, approver roles, tie-outs, the ledger effect and the norms miner. Registers itself with the core on import."""
from __future__ import annotations

import json
from typing import Any

from ... import config
from ...core import db
from ...core.conclusions import boolean_part, conclusion_state
from ...core.domain import register
from . import ledger, materiality as M

MENU = {
    "journal_entry": ("correcting_je", "controller", "Current-period correcting entry referencing the original entry and period"),
    "deck_publish": ("artifact_supersession", "controller", "Deck v2 with a 'corrected' banner and diff; original recipients notified; v1 kept replayable"),
    "certificate_send": ("corrected_certificate", "cfo", "Corrected compliance certificate and lender notice; waiver request drafted (Section 6.02(f))"),
    "bonus_payout": ("offset_next_bonus", "hr+controller", "Offset the overpayment against the next quarterly bonus per plan terms; notify the GM; no ad-hoc payroll deduction"),
    "commission_payout": ("offset_next_commission", "vp_sales+controller", "Offset the overpayment against the next commission per plan terms"),
    "payment_run": ("request_credit_hold_next", "ap+controller", "Request a credit for the duplicate and hold the next payment to the vendor"),
    "tax_payment": ("reduce_next_installment", "controller", "Reduce the next estimated-tax installment by the overpayment (company policy; tax advisor notified)"),
    "dunning_email": ("retraction_notice", "ap", "Send a retraction to the customer and re-age the receivable under the contract terms"),
    "collections_task": ("collections_task", "ap", "Open a collections task"),
    "member_services_case": ("member_services_case", "controller", "Member Services case"),
    "control_proposal": ("control_proposal", "controller", "Control proposal"),
    "publish_brief": ("issue_correction_note", "editor", "Issue a correction note"),
    "release_publish": ("corrected_release", "cfo", "Issue a CORRECTING and REPLACING release and furnish the corrected exhibit on Form 8-K/A"),
    "sec_filing": ("filing_amendment", "general_counsel", "File an amendment carrying the corrected exhibit"),
    "order": ("position_review", "pm", "Review the filled order against the corrected guidance; unwind or hold is the PM's call"),
}
QUALITATIVE_SIGN_LINES = ("growth", "route_setting_growth", "margin", "headroom", "revenue")


class FinancePack:
    name = "finance"

    # ---- materiality -------------------------------------------------------------------
    def evaluate_number(self, node: dict, old: float | None, new: float | None, conclusions: dict | None) -> tuple[str, str, dict]:
        """(verdict, reason, detail): verdict in invalidated | unaffected | unprovable."""
        cj = json.dumps(conclusions) if conclusions else None
        return M.numeric_verdict(old, new, node.get("line_item"), node.get("kind", "number"), cj, M.memo())

    def is_material(self, node: dict, old_value: float | None, new_value: float | None, conclusions: dict | None) -> tuple[bool, str]:
        verdict, reason, _ = self.evaluate_number(node, old_value, new_value, conclusions)
        return verdict == "invalidated", reason

    def line_profile(self, node: dict) -> dict:
        li = node.get("line_item")
        return {"exact": M.is_exact(li), "ratio": M.is_ratio(li), "threshold": M.threshold_for(li, node.get("kind", "number"), M.memo())}

    def is_qualitative_flip(self, node: dict, conclusions: dict | None) -> bool:
        """SAB 99 qualitative factors: covenant compliance, compensation tiers, the sign of a reported trend."""
        c = conclusions or {}
        li = (node.get("line_item") or "").lower()
        return bool(c.get("covenant_max") is not None or c.get("tiers") or (c.get("sign") and li in QUALITATIVE_SIGN_LINES))

    # ---- classification -----------------------------------------------------------------
    def classify_correction(self, correction: dict, knowable_at: str, original_artifact_time: str | None) -> str:
        """ASC 250: a fact that existed when the original number was made is an error; new information is an estimate change."""
        t = correction.get("correction_type") or ""
        if t in ("bank_revision", "duplicate_removal", "fx_fix", "retraction") and original_artifact_time and knowable_at > original_artifact_time:
            return "fact_update"
        if original_artifact_time and knowable_at <= original_artifact_time:
            return "error"
        return "estimate"

    def correction_verdict(self, correction: dict, impact: float, flips: bool, prior_period: bool) -> str:
        return M.classify_correction(impact, M.memo(), correction.get("kind", "error"), prior_period, flips)

    def unaffected_reason(self, node: dict, change: dict) -> str | None:
        """estimate_change for closed periods under an estimate-kind change (ASC 250); different_period / different_line_item structurally."""
        from ...core import periods
        pend = periods.period_end(node.get("period"))
        if change.get("kind") == "estimate" and pend and pend < (change.get("knowable_at") or "")[:10] and not self._is_balance_line(node):
            return "estimate_change"
        if "changed_months" in change:
            months = [m for m in change["changed_months"] if m]
            if node.get("period") and months and not any(periods.overlaps(node["period"], m) for m in months):
                return "different_period"
            return "different_line_item"
        return None

    def _is_balance_line(self, node: dict) -> bool:
        li = (node.get("line_item") or "").lower()
        return node.get("kind") == "forecast_cell" or any(k in li for k in ("ar_", "capex", "deferred", "depreciation_schedule", "forecast", "recon", "member_ar"))

    # ---- compensations and approvals ----------------------------------------------------------
    def compensation_for(self, action: dict) -> dict:
        kind = action.get("kind")
        if kind not in MENU:
            return {}
        ck, approver, desc = MENU[kind]
        return {"kind": ck, "approver": approver, "description": desc}

    def approver_for(self, action_or_compensation: dict) -> str:
        c = self.compensation_for(action_or_compensation)
        return c.get("approver") or action_or_compensation.get("approver_role") or "controller"

    def can_post(self, entry: dict) -> tuple[bool, str]:
        period = entry.get("period") or entry.get("posting_period")
        if period and ledger.period_locked(period):
            return False, f"period {period} is locked (policy C-1: only the Controller unlocks; book in the open period with an out-of-period tag)"
        return True, "open"

    def execute_effect(self, action: dict, params: dict, ts: str, approval_id: str | None) -> dict:
        if action.get("kind") == "journal_entry":
            lines = [(l["account"], int(l["amount_cents"]), l.get("gym")) for l in params["lines"]]
            tx_id = ledger.post_entry(lines, period=params["posting_period"], orig_period=params["orig_period"], memo=params["memo"], ts=ts,
                                      action_id=action["action_id"], approval_id=approval_id, correction_id=params.get("correction_id"))
            observed = [{"account": r["account"], "amount_cents": r["amount_cents"]} for r in db.q("SELECT account, amount_cents FROM ledger_entries WHERE tx_id=? ORDER BY line", (tx_id,))]
            return {"ledger_tx_id": tx_id, "effect_spec": [{"account": l["account"], "amount_cents": int(l["amount_cents"])} for l in params["lines"]], "observed_effect": observed}
        return {"ledger_tx_id": None, "effect_spec": {"kind": action.get("kind"), "params": params}, "observed_effect": {"kind": action.get("kind"), "executed": True}}

    def log_unbooked(self, correction_id: str, period: str, line_item: str, amount: float, booked: bool, note: str, ts: str) -> None:
        eid = f"MS-{correction_id}-{db.hid(period, line_item, amount)}"
        if db.q1("SELECT 1 FROM misstatement_log WHERE entry_id=?", (eid,)):
            return
        db.insert("misstatement_log", {"entry_id": eid, "correction_id": correction_id, "period": period, "line_item": line_item, "amount": amount,
                                       "booked": 1 if booked else 0, "note": note, "ts": db.norm_ts(ts)})

    # ---- tie-outs (cross-agent consistency) ----------------------------------------------------
    def tie_out_checks(self, artifact_versions: list[dict]) -> list[dict]:
        """Cross-agent consistency: every number must equal its formula evaluated over the *effective* values of what it rests on
        (current claim values, recursively), within its line's threshold. Backdated cells may differ by at most their threshold."""
        from ...core import formula as F, graph
        memo: dict[str, float | None] = {}
        recomputed: dict[str, bool] = {}

        def effective(aid: str) -> float | None:
            """What the engine currently holds for a node: the latest finding's recomputed value if there is one (backdated cells
            keep their version but carry the new value forward), else the stored value."""
            if aid in memo:
                return memo[aid]
            cur = db.artifact_current(aid)
            if cur is None:
                memo[aid] = None; return None
            # only findings that actually recomputed the node carry its value forward; "unchanged" findings restate the stored value
            f = db.q1("SELECT new_value FROM impact_findings WHERE artifact_id=? AND artifact_version=? AND new_value IS NOT NULL "
                      "AND reason IN ('value_changed','below_materiality','conclusion_unchanged','conclusion_flipped') ORDER BY rowid DESC LIMIT 1", (aid, cur["version"]))
            v = f["new_value"] if f else cur["value_num"]
            recomputed[aid] = f is not None
            memo[aid] = v
            return v

        def expected(cur) -> float | None:
            fm = json.loads(cur["formula"]) if cur["formula"] else None
            if not fm or not fm.get("expr") or fm.get("value_from"):
                return None
            vals = {}
            effective(cur["artifact_id"])
            live = recomputed.get(cur["artifact_id"], False)   # recomputed against current facts, or left resting (prospective treatment)
            for alias, ref in (fm.get("inputs") or {}).items():
                if ref["kind"] == "claim":
                    if live:
                        cv = db.claim_version_current(ref["id"]); vals[alias] = cv["value_num"] if cv else None
                    else:
                        vals[alias] = graph.claim_value(ref["version"])
                else:
                    vals[alias] = effective(ref["id"])
            try:
                return F.evaluate(fm["expr"], vals) if all(x is not None for x in vals.values()) else None
            except F.FormulaError:
                return None
        out = []
        for a in artifact_versions:
            if a.get("kind") not in ("number", "forecast_cell") or not a.get("formula") or a["formula"].get("value_from"):
                continue
            cur = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (a["artifact_id"], a["version"])) if a.get("version") else db.artifact_current(a["artifact_id"])
            exp = expected(cur) if cur is not None else None
            held = effective(a["artifact_id"])
            thr = M.threshold_for(a.get("line_item"), a.get("kind", "number"), M.memo())
            ok = exp is not None and held is not None and abs(exp - held) <= max(thr, 1.0)
            out.append({"name": f"tie_out:{a['artifact_id']}", "ok": ok, "detail": {"expected": exp, "held": held, "stated": a.get("value_num"), "tolerance": max(thr, 1.0)}})
        return out


PACK = FinancePack()
register(PACK)
