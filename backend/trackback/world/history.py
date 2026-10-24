"""The agents' past work (iteration 2 inside v3): three agents built on each other before July 8, and every piece records what it read.

Runs (each pinned; the LLM, when present, writes the sentences; numbers always come from Trackback's calc nodes):
- Close Accountant, Apr 10 17:00 (Q1 close): the Q1 close memo (annual-plan release and deferred revenue) and the close accruals
- Reporting Analyst, Apr 24 15:00 (board deck): slide 3's covenant sentence and commentary, slide 4's regional EBITDA
- Covenant and Comp, May 15 10:00: the compliance certificate (lines 1 to 5), sent after the CFO signed (executed action)
- Covenant and Comp, May 31 09:00: Q1 GM bonuses, one payout per region (executed; HR approved)
- Covenant and Comp, Jun 15 10:00: the Q2 estimated tax payment (executed; Controller approved)
- Close Accountant, Jun 30 17:00: the June utilities accrual estimate (pre-close)
- Reporting Analyst, Jul 3 12:00: the 13-week cash forecast (opening cash, the week-29 utilities payment)

Every agent artifact gets a consumption receipt (hash of the consumed version, fields read) on each calc node or artifact it used, so a
ping can only travel along what the hub recorded at read time. Calc nodes are Trackback's own artifacts (agent `trackback`).
"""
from __future__ import annotations

import json

from .. import config as C
from ..agent import llm
from ..core import db, graph as G
from ..engine.books import Books

AGENTS = {
    "close_accountant": ("Close Accountant", "Senior accountant, close and error review at Tidewall (synthetic). Runs the close and the error review; drafts entries; never posts or approves its own work."),
    "reporting_analyst": ("Reporting Analyst", "Reporting analyst at Tidewall: board deck commentary, regional tables, the 13-week cash forecast."),
    "covenant_comp": ("Covenant and Comp", "Covenant and compensation analyst at Tidewall: drafts the lender compliance certificate (the CFO signs), computes GM bonuses (HR approves) and the estimated tax payment (the Controller approves)."),
}
FORECAST_TOLERANCE = 1_000.0


def _register_agents() -> None:
    for aid, (name, seat) in AGENTS.items():
        if db.q1("SELECT 1 FROM agents WHERE agent_id=?", (aid,)) is None:
            db.insert("agents", {"agent_id": aid, "display_name": name, "ping_endpoint": f"/agents/{aid}/trackback", "model": C.AGENT_MODEL, "prompt_version": "v3", "seat": seat})
    if db.q1("SELECT 1 FROM agents WHERE agent_id='trackback'") is None:
        db.insert("agents", {"agent_id": "trackback", "display_name": "Trackback (engine)", "ping_endpoint": None, "model": None, "prompt_version": None,
                             "seat": "The hub: recomputes every calc node itself and is the only thing that can create pings."})


def _run(run_id: str, agent: str, task: str, pin: str, goal: str, deliverables: list[str]) -> str:
    db.insert("runs", {"run_id": run_id, "agent": agent, "task": task, "pinned_at": db.norm_ts(pin), "mode": "history", "status": "done", "started_at": db.norm_ts(pin),
                       "finished_at": db.norm_ts(pin), "turns": 1, "note": None, "trigger": "schedule", "ping_id": None, "goal": goal, "deliverables_json": json.dumps(deliverables),
                       "model": C.AGENT_MODEL, "prompt_version": "v3"})
    return run_id


def calc_node(metric_id: str, pin: str) -> tuple[str, int, float | str]:
    """Trackback's calc artifact for a metric as of `pin`: a new version only when the value moved."""
    from ..review import ctx
    from ..engine.books import Books
    cx = ctx(pin)
    if metric_id.startswith("sum:"):
        vals = cx.lib.evaluate(Books(cx.entries))
        val = sum(vals[p] for p in metric_id[4:].split("+"))
    else:
        val = cx.lib.evaluate(Books(cx.entries))[metric_id]
    aid = f"M:{metric_id}"
    cur = db.artifact_current(aid)
    if cur is not None and ((cur["value_num"] is not None and isinstance(val, (int, float)) and abs(cur["value_num"] - val) < 0.005) or cur["content"] == str(val)):
        return aid, cur["version"], val
    m = cx.lib.metrics.get(metric_id)
    label = m.label if m else metric_id
    if cur is not None:
        db.close_tx("artifacts", "artifact_id", aid, db.norm_ts(pin), " AND version=?", (cur["version"],))
    v = G.new_artifact(artifact_id=aid, kind="number" if isinstance(val, (int, float)) else "sentence", run_id="trackback:calc", pinned_at=db.norm_ts(pin), period=(m.quarter if m else None),
                       line_item=metric_id, content=label if isinstance(val, (int, float)) else str(val), value_num=val if isinstance(val, (int, float)) else None, formula=None,
                       conclusions=None, agent_id="trackback", node_kind="calc", origin="initial" if cur is None else "recalc", metric=metric_id)
    return aid, v, val


def emit(*, artifact_id: str, run_id: str, agent: str, pin: str, kind: str, content: str, value: float | None, consumes: list[str], line_item: str | None = None,
         period: str | None = None, conclusions: dict | None = None, fields: dict | None = None, consumes_artifacts: list[str] | None = None, node_kind: str | None = None) -> int:
    """Write an agent artifact and its receipts (one per consumed calc node or artifact)."""
    v = G.new_artifact(artifact_id=artifact_id, kind=kind, run_id=run_id, pinned_at=db.norm_ts(pin), period=period, line_item=line_item, content=content, value_num=value,
                       formula=None, conclusions=conclusions, agent_id=agent, node_kind=node_kind or G.NODE_KIND.get(kind, kind), origin="initial", metric=line_item, fields=fields)
    for mid in consumes:
        cid, cv, _val = calc_node(mid, pin)
        G.add_edge(consumer_id=artifact_id, consumer_version=v, supporter_kind="artifact", supporter_id=cid, supporter_version=str(cv), dep_kind="numeric", capture="tool_log")
    for aid in consumes_artifacts or []:
        cur = db.artifact_current(aid)
        G.add_edge(consumer_id=artifact_id, consumer_version=v, supporter_kind="artifact", supporter_id=aid, supporter_version=str(cur["version"]), dep_kind="numeric", capture="tool_log")
    return v


def _fmt(v: float, unit: str = "usd") -> str:
    if unit == "ratio":
        return f"{v:.2f}x"
    if unit == "pct":
        return f"{v:.1f}%"
    return f"${v:,.0f}"


def _action(action_id: str, artifact_id: str, kind: str, params: dict, run_id: str, proposer: str, approver: str, executed_at: str, summary: str) -> None:
    G.new_action(action_id=action_id, artifact_id=artifact_id, kind=kind, params=params, run_id=run_id, proposer=proposer, approver_role=C.PEOPLE_V3[approver]["role"],
                 created_at=executed_at, state="proposed")
    db.get_conn().execute("UPDATE actions SET world='tidewall', assignee=?, summary=? WHERE action_id=?", (approver, summary, action_id))
    db.insert("approvals", {"approval_id": f"APR-{action_id}", "action_id": action_id, "proposer": proposer, "approver": approver, "decision": "approved",
                            "reason": "approved at the time (history)", "ts": db.norm_ts(executed_at)})
    G.set_action_state(action_id, "executed", db.norm_ts(executed_at), executed_at=executed_at)


def run_all() -> None:
    from ..review import ctx
    from ..world.human_files import ACTIONS
    _register_agents()
    items = {it["id"]: it for it in json.loads(C.ANSWER_KEY_V3.read_text(encoding="utf-8"))["lineage"]}
    # Close Accountant, Q1 close
    pin = C.KEY_DATES["q1_close"]
    r1 = _run("R1_q1_close", "close_accountant", "Q1 2026 hard close", pin, "Close Q1 2026 following the close calendar and company policies.", ["Q1 close memo", "close accruals", "misstatement log"])
    vals = ctx(pin).lib.evaluate(Books(ctx(pin).entries))
    facts = {"annual_release": _fmt(vals["acct.4010@2026Q1"]), "deferred": _fmt(vals["deferred_revenue@2026Q1"]), "batches": "nine"}
    memo = llm.write("history:CA.q1_close_memo", "Write one sentence for the Q1 close memo on annual-plan revenue released from deferred revenue.", facts,
                     "Q1 annual-plan revenue of {annual_release} was released from deferred revenue across the billing batches; deferred revenue at March 31 was {deferred}.", pin)
    emit(artifact_id="CA.q1_close_memo", run_id=r1, agent="close_accountant", pin=pin, kind="sentence", content=memo["text"], value=None,
         consumes=["acct.4010@2026Q1", "deferred_revenue@2026Q1"], line_item="q1_close_memo", period="2026Q1",
         fields={"template": "Q1 annual-plan revenue of {acct.4010@2026Q1} was released from deferred revenue across the billing batches; deferred revenue at March 31 was {deferred_revenue@2026Q1}."})
    emit(artifact_id="CA.q1_accruals", run_id=r1, agent="close_accountant", pin=pin, kind="sentence", content="Q1 close accruals: route setting $410,000 (Cragline, March) and utilities $190,000 (Bayline, March), both HQ.",
         value=None, consumes=["acct.6300@2026Q1", "acct.6200@2026Q1"], line_item="q1_accruals", period="2026Q1", node_kind="judgment")
    # Reporting Analyst, board deck slides 3 and 4 plus commentary
    pin = C.KEY_DATES["board_deck"]
    r2 = _run("R2_board_deck", "reporting_analyst", "Q1 board deck: covenant slide and regional table", pin, "Prepare the Q1 board deck from the latest close.",
              ["covenant sentence", "regional EBITDA table", "commentary"])
    emit(artifact_id="DECK.s3.l1", run_id=r2, agent="reporting_analyst", pin=pin, kind="sentence", content="We remain within our 3.00x net leverage covenant at 2.95x.", value=None,
         consumes=["covenant_status@2026Q1", "leverage@2026Q1"], line_item="covenant_status@2026Q1", period="2026Q1", conclusions={"covenant_status": "Compliant"},
         fields={"template": "We remain within our 3.00x net leverage covenant at {leverage@2026Q1}.", "file": "Board_Deck_Q1-26.pptx", "locator": "slide 3, line 1"})
    emit(artifact_id="RA.commentary.membership_growth", run_id=r2, agent="reporting_analyst", pin=pin, kind="sentence", content="Membership revenue grew quarter over quarter.", value=None,
         consumes=["membership_growth@2026Q1"], line_item="membership_growth@2026Q1", period="2026Q1", conclusions={"sign": "positive"}, fields={"file": "Board_Deck_Q1-26.pptx", "locator": "slide 3, line 2"})
    emit(artifact_id="RA.commentary.regions_profitable", run_id=r2, agent="reporting_analyst", pin=pin, kind="sentence", content="All six regions were profitable in Q1.", value=None,
         consumes=[f"ebitda.{r}@2026Q1" for r in C.REGIONS], line_item="regional_ebitda", period="2026Q1", conclusions={"all_positive": True}, fields={"file": "Board_Deck_Q1-26.pptx", "locator": "slide 3, line 3"})
    for i, r in enumerate(C.REGIONS):
        it = items[f"DECK.s4.l{i + 1}"]
        emit(artifact_id=f"DECK.s4.l{i + 1}", run_id=r2, agent="reporting_analyst", pin=pin, kind="number", content=f"{C.REGIONS[r]} ({r}): {it['display']}", value=it["value"],
             consumes=[f"ebitda.{r}@2026Q1"], line_item=f"ebitda.{r}@2026Q1", period="2026Q1", fields={"file": "Board_Deck_Q1-26.pptx", "locator": f"slide 4, line {i + 1}", "display_unit": "K"})
    # Covenant and Comp: certificate (May 15), bonuses (May 31), tax (Jun 15)
    pin = C.KEY_DATES["certificate_sent"]
    r3 = _run("R3_certificate", "covenant_comp", "Q1 lender compliance certificate", pin, "Prepare the Q1 lender compliance package.", ["compliance certificate"])
    cert = [("CERT.l1", "ttm_adj_ebitda@2026Q1"), ("CERT.l2", "net_debt@2026Q1"), ("CERT.l3", "leverage@2026Q1"), ("CERT.l4", "policy.max_leverage"), ("CERT.l5", "covenant_status@2026Q1")]
    for cid, mid in cert:
        it = items[cid]
        is_status = isinstance(it["value"], str)
        emit(artifact_id=cid, run_id=r3, agent="covenant_comp", pin=pin, kind="sentence" if is_status else "number", content=f"{it['label']}: {it['value']}", value=None if is_status else it["value"],
             consumes=[] if mid.startswith("policy.") else [mid], line_item=mid, period="2026Q1", conclusions={"covenant_status": it["value"]} if is_status else None,
             fields={"file": "Compliance_Certificate_Q1-26_signed.pdf", "locator": it["locator"]})
    by_act = {a["id"]: a for a in ACTIONS}
    a = by_act["ACT-cert-q1"]
    emit(artifact_id="ACT-cert-q1", run_id=r3, agent="covenant_comp", pin=pin, kind="action", content=a["label"], value=None, consumes=["covenant_status@2026Q1"], line_item="certificate_sent",
         period="2026Q1", conclusions={"covenant_status": "Compliant"}, consumes_artifacts=[c for c, _m in cert])
    _action("ACT-cert-q1", "ACT-cert-q1", "certificate_sent", {"to": "Redwood Commercial Bank", "leverage": "2.95 to 1.00"}, r3, "covenant_comp", "sam", pin, a["label"])
    pin = C.KEY_DATES["bonuses_paid"]
    r4 = _run("R4_bonuses", "covenant_comp", "Q1 GM bonus payouts", pin, "Compute and pay Q1 GM bonuses under the plan.", [f"bonus {r}" for r in C.REGIONS])
    vals = ctx(pin).lib.evaluate(Books(ctx(pin).entries))
    for r in C.REGIONS:
        a = by_act[f"ACT-bonus-{r}"]
        amt = vals[f"bonus.{r}@2026Q1"]
        emit(artifact_id=a["id"], run_id=r4, agent="covenant_comp", pin=pin, kind="action", content=f"{a['label']}: {_fmt(amt)}", value=amt, consumes=[f"bonus.{r}@2026Q1"], line_item=a["metric"], period="2026Q1")
        _action(a["id"], a["id"], "bonus_paid", {"region": r, "amount": amt}, r4, "covenant_comp", "lena", pin, f"{a['label']}: {_fmt(amt)}")
    pin = C.KEY_DATES["tax_paid"]
    r5 = _run("R5_tax", "covenant_comp", "Q2 estimated tax payment", pin, "Pay the Q2 federal estimated tax.", ["Q2 estimated tax"])
    vals = ctx(pin).lib.evaluate(Books(ctx(pin).entries))
    a = by_act["ACT-tax-q2"]
    emit(artifact_id=a["id"], run_id=r5, agent="covenant_comp", pin=pin, kind="action", content=f"{a['label']}: {_fmt(vals['tax_installment@2026Q2'])}", value=vals["tax_installment@2026Q2"],
         consumes=["tax_installment@2026Q2"], line_item=a["metric"], period="2026Q2")
    _action(a["id"], a["id"], "tax_paid", {"amount": vals["tax_installment@2026Q2"]}, r5, "covenant_comp", "dana", pin, f"{a['label']}: {_fmt(vals['tax_installment@2026Q2'])}")
    # Close Accountant: June utilities accrual estimate; Reporting Analyst: 13-week cash forecast built on it
    pin = "2026-06-30T17:00:00-07:00"
    r6 = _run("R6_june_accrual", "close_accountant", "June pre-close accrual estimates", pin, "Estimate June accruals before the June close.", ["utilities accrual"])
    emit(artifact_id="CA.june_accrual.utilities", run_id=r6, agent="close_accountant", pin=pin, kind="number", content="June utilities accrual (Bayline, June service): $180,000", value=180_000.0,
         consumes=[], line_item="june_utilities_accrual", period="2026-06", node_kind="judgment")
    pin = "2026-07-03T12:00:00-07:00"
    r7 = _run("R7_cash_forecast", "reporting_analyst", "13-week cash forecast", pin, "Refresh the 13-week cash forecast from the June books.", ["opening cash", "weekly payments"])
    cash = ctx(pin).lib.evaluate(Books(ctx(pin).entries))["cash@2026Q2"]
    emit(artifact_id="RA.cash_forecast.opening", run_id=r7, agent="reporting_analyst", pin=pin, kind="forecast_cell", content=f"13-week cash forecast, opening cash (Jun 30): {_fmt(cash)}", value=cash,
         consumes=["cash@2026Q2"], line_item="cash_forecast.opening", period="2026-07")
    emit(artifact_id="RA.cash_forecast.week29", run_id=r7, agent="reporting_analyst", pin=pin, kind="forecast_cell", content="13-week cash forecast, week 29 utilities payment (Bayline): $180,000", value=180_000.0,
         consumes=[], consumes_artifacts=["CA.june_accrual.utilities"], line_item="cash_forecast.week29", period="2026-07")
    db.commit()
    n_rc = db.q1("SELECT COUNT(*) n FROM consumption_receipts")["n"]
    n_ar = db.q1("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts")["n"]
    print(f"history: 7 agent runs, {n_ar} artifacts (agents + calc nodes), {n_rc} consumption receipts, 8 executed actions")


def agent_nodes() -> list[dict]:
    """The agents' own work products that are not traced file lines (the ripple marks them suspect when their inputs move materially)."""
    out = []
    for aid, snap, tol in [("CA.q1_close_memo", "close", None), ("CA.q1_accruals", "close", None), ("RA.commentary.membership_growth", "close", None),
                           ("RA.commentary.regions_profitable", "close", None), ("RA.cash_forecast.opening", "now", FORECAST_TOLERANCE)]:
        cur = db.artifact_current(aid)
        if cur is None:
            continue
        consumes = [db.q1("SELECT line_item FROM artifacts WHERE artifact_id=? AND version=?", (e["supporter_id"], int(e["supporter_version"])))["line_item"]
                    for e in G.supporters_of(aid, cur["version"]) if e["supporter_id"].startswith("M:")]
        out.append({"id": aid, "owner": cur["agent_id"], "kind": cur["node_kind"] or cur["kind"], "label": aid, "content": cur["content"], "consumes": consumes, "snapshot": snap, "tolerance": tol})
    return out
