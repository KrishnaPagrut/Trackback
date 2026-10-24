"""Lyft, February 13, 2024 (the real-world scenario), through every v3 step and every iteration-2 behaviour.

REAL: the Q4 and full-year 2023 release furnished as Exhibit 99.1 to the 8-K at 16:06 ET ("Adjusted EBITDA margin expansion ... of approximately
500 basis points year-over-year"); the CFO's correction on the 4:30 pm ET call (50); Business Wire's CORRECTING and REPLACING release; the tape.
RECONSTRUCTED (labeled everywhere): the finance team's own documents (the close pack, the FP&A guidance model), the agents, and the outside
world that built on the release (a newsroom, a sell-side desk). Every number inside them is a public one from the release.

The same engines run it: the claims are loaded as a small ledger (world 'lyft') so Books, the metric library, the ripple, the hub and the
rework handler are the ones Tidewall uses. People are roles, not names.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import uuid
from pathlib import Path

from .. import config as C
from ..core import db, graph as G, pings as P
from ..engine.books import Books, Metric, MetricLibrary, Slice

ET = "-05:00"
T = {"pack": f"2024-02-08T17:00:00{ET}", "model": f"2024-02-09T18:00:00{ET}", "fpa_run": f"2024-02-09T18:30:00{ET}", "ir_run": f"2024-02-12T15:00:00{ET}",
     "disc_run": f"2024-02-13T09:00:00{ET}", "cfo_approves": f"2024-02-13T15:30:00{ET}", "filed": f"2024-02-13T16:06:00{ET}", "news_run": f"2024-02-13T16:15:00{ET}",
     "news_pub": f"2024-02-13T16:18:00{ET}", "street_run": f"2024-02-13T16:20:00{ET}", "order": f"2024-02-13T16:25:00{ET}", "call": f"2024-02-13T16:30:00{ET}",
     "correction": f"2024-02-13T17:00:00{ET}", "review": f"2024-02-13T17:05:00{ET}"}
SNAPSHOTS = {"close": T["filed"], "now": T["review"]}
EXHIBIT = C.PUBLIC_DIR / "lyft" / "lyft_ex991_20240213_as_filed.htm"
LYFT_DIR = C.WORLD_DIR / "lyft"
PEOPLE = {"cfo": "Lyft CFO", "general_counsel": "Lyft General Counsel", "editor": "Newsroom editor (outside)", "pm": "Portfolio manager (outside)"}
AGENTS = {"lyft_fpa": ("FP&A (inside)", "Owns the FY2024 guidance model and the margin bridge."),
          "lyft_ir": ("Reporting and IR (inside)", "Drafts the release highlights and the CFO's prepared remarks; proposes publication for the CFO's sign-off."),
          "lyft_disclosure": ("Disclosure (inside)", "Prepares the Form 8-K that furnishes the release."),
          "newsroom": ("Newsroom (outside)", "Writes and publishes the earnings headline and story from the company's release."),
          "street_analyst": ("Sell-side desk (outside)", "Writes the flash note with the implied numbers and routes the order to the PM.")}
TAPE = {"release_filed": T["filed"], "call_start": T["call"], "after_hours_peak_pct": 67, "at_1752_pct": 20, "next_close_pct": 35.1, "next_close_px": 16.39, "next_close_date": "2024-02-14",
        "sources": ["SEC EDGAR 0001759509-24-000011, Exhibit 99.1 (as filed)", "Business Wire: CORRECTING and REPLACING (Feb 13, 2024)",
                    "Bloomberg, Feb 13, 2024: 'Lyft Corrects Earnings Margin Gain to 50 Basis Points From 500'", "CNBC, Feb 14, 2024; Investor's Business Daily, Feb 14, 2024"]}

# public figures from the as-filed exhibit (the reconstructed close pack carries them at the precision the release shows)
PACK = {"q4_gb": 3.7e9, "q4_gb_growth": 17.0, "q4_rev": 1.2e9, "q4_rev_growth": 4.0, "q4_net_loss": 26.3e6, "q4_adj_ebitda": 66.6e6, "q4_22_net_loss": 588.1e6, "q4_22_adj_ebitda": -248.3e6, "q4_margin": 1.8,
        "q4_22_margin": -7.8, "fy_gb": 13.8e9, "fy_gb_growth": 14.0, "fy_rev": 4.4e9, "fy_rev_growth": 8.0, "fy_adj_ebitda": 222.4e6, "fy22_adj_ebitda": -416.5e6, "fy_margin": 1.6, "fy22_margin": -3.5}
MODEL = {"fy23_margin": 1.6, "fy24_margin_target": 2.1, "q1_gb_low": 3.5e9, "q1_gb_high": 3.6e9, "q1_ebitda_low": 50e6, "q1_ebitda_high": 55e6, "q1_margin_low": 1.4, "q1_margin_high": 1.5}
LABELS = {"q4_22_net_loss": ("Net loss, Q4 2022", "usd", ["net loss compares with"]), "q4_gb": ("Gross Bookings, Q4 2023", "usd", ["fourth quarter gross bookings", "gross bookings"]), "q4_gb_growth": ("Gross Bookings growth, Q4 2023 year-over-year", "pct", ["gross bookings grew", "growth"]),
          "q4_rev": ("Revenue, Q4 2023", "usd", ["fourth quarter revenue", "revenue"]), "q4_rev_growth": ("Revenue growth, Q4 2023", "pct", ["revenue grew"]),
          "q4_net_loss": ("Net loss, Q4 2023", "usd", ["net loss"]), "q4_adj_ebitda": ("Adjusted EBITDA, Q4 2023", "usd", ["adjusted ebitda"]),
          "q4_22_adj_ebitda": ("Adjusted EBITDA, Q4 2022", "usd", ["adjusted ebitda compares with", "q4 22"]), "q4_margin": ("Adjusted EBITDA margin, Q4 2023", "pct", ["adjusted ebitda margin was"]),
          "q4_22_margin": ("Adjusted EBITDA margin, Q4 2022", "pct", ["compares with in q4 22"]), "fy_gb": ("Gross Bookings, full-year 2023", "usd", ["full-year gross bookings"]),
          "fy_gb_growth": ("Gross Bookings growth, full-year 2023", "pct", ["grew year-over-year"]), "fy_rev": ("Revenue, full-year 2023", "usd", ["full-year revenue"]),
          "fy_rev_growth": ("Revenue growth, full-year 2023", "pct", ["revenue grew"]), "fy_adj_ebitda": ("Adjusted EBITDA, full-year 2023", "usd", ["adjusted ebitda"]),
          "fy22_adj_ebitda": ("Adjusted EBITDA, full-year 2022", "usd", ["full-year 2022"]), "fy_margin": ("Adjusted EBITDA margin, full-year 2023", "pct", ["adjusted ebitda margin was"]),
          "fy22_margin": ("Adjusted EBITDA margin, full-year 2022", "pct", ["full-year 2022"]),
          "fy23_margin": ("FY2023 Adjusted EBITDA margin (guidance model)", "pct", ["2023 margin"]), "fy24_margin_target": ("FY2024 Adjusted EBITDA margin target (guidance model)", "pct", ["2024 target"]),
          "q1_gb_low": ("Q1 2024 Gross Bookings outlook, low", "usd", ["gross bookings of approximately"]), "q1_gb_high": ("Q1 2024 Gross Bookings outlook, high", "usd", ["gross bookings"]),
          "q1_ebitda_low": ("Q1 2024 Adjusted EBITDA outlook, low", "usd", ["adjusted ebitda of"]), "q1_ebitda_high": ("Q1 2024 Adjusted EBITDA outlook, high", "usd", ["adjusted ebitda"]),
          "q1_margin_low": ("Q1 2024 Adjusted EBITDA margin outlook, low", "pct", ["margin of approximately"]), "q1_margin_high": ("Q1 2024 Adjusted EBITDA margin outlook, high", "pct", ["margin"])}
TRACE_PHRASES = ["Gross Bookings of $3.7 billion", "Revenue of $1.2 billion", "Net loss of $26.3 million", "Adjusted EBITDA of $66.6 million", "was 1.8% and compares",
                 "Gross Bookings of $13.8 billion", "Revenue of $4.4 billion", "Adjusted EBITDA of $222.4 million", "was 1.6% and compares",
                 "approximately $3.5 billion to $3.6 billion", "Adjusted EBITDA of $50 million to $55 million", "approximately 500 basis points"]


def _a(account: str) -> Slice:
    return Slice((account,), ("2024",), "company", False, 1)


def library(trace_only: bool = False) -> MetricLibrary:
    """Lyft's calc nodes. trace_only: just the systems of record (close pack and guidance model), for the tracer."""
    ms: list[Metric] = []
    for k in PACK:
        lab, unit, syn = LABELS[k]
        ms.append(Metric(f"lyft.{k}", lab, unit, "pl", {"x": _a(f"PACK.{k}")}, synonyms=syn))
    for k in MODEL:
        lab, unit, syn = LABELS[k]
        ms.append(Metric(f"lyft.{k}", lab, unit, "pl", {"x": _a(f"MODEL.{k}")}, synonyms=syn))
    ms.append(Metric("lyft.margin_expansion_bps", "FY2024 Adjusted EBITDA margin expansion, basis points (guidance model)", "bps", "derived", deps=["lyft.fy24_margin_target", "lyft.fy23_margin"],
                     compute=lambda c: round((c["lyft.fy24_margin_target"] - c["lyft.fy23_margin"]) * 100, 6), synonyms=["margin expansion", "basis points", "adjusted ebitda margin expansion"]))
    if not trace_only:
        ms.append(Metric("release.margin_expansion_bps", "Margin expansion stated in the public release, basis points", "bps", "pl", {"x": _a("REL.bps")}, synonyms=["release basis points"]))
        ms.append(Metric("release.fy23_margin", "FY2023 margin stated in the release", "pct", "pl", {"x": _a("REL.fy23_margin")}))
        ms.append(Metric("release.fy23_gb", "FY2023 Gross Bookings stated in the release", "usd", "pl", {"x": _a("REL.fy23_gb")}))
        ms.append(Metric("release.q4_gb", "Q4 Gross Bookings stated in the release", "usd", "pl", {"x": _a("REL.q4_gb")}))
        ms.append(Metric("release.q4_rev", "Q4 revenue stated in the release", "usd", "pl", {"x": _a("REL.q4_rev")}))
        ms.append(Metric("street.implied_fy24_margin", "Implied FY2024 Adjusted EBITDA margin (sell-side)", "pct", "derived", deps=["release.fy23_margin", "release.margin_expansion_bps"],
                         compute=lambda c: c["release.fy23_margin"] + c["release.margin_expansion_bps"] / 100))
        ms.append(Metric("street.implied_fy24_gb", "Implied FY2024 Gross Bookings at 15% growth (sell-side)", "usd", "derived", deps=["release.fy23_gb"], compute=lambda c: c["release.fy23_gb"] * 1.15))
        ms.append(Metric("street.implied_fy24_adj_ebitda", "Implied FY2024 Adjusted EBITDA (sell-side)", "usd", "derived", deps=["street.implied_fy24_gb", "street.implied_fy24_margin"],
                         compute=lambda c: c["street.implied_fy24_gb"] * c["street.implied_fy24_margin"] / 100))
    return MetricLibrary(ms)


def entries() -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM gl_entries WHERE world='lyft' ORDER BY posted_at, entry_id")]


def _post(account: str, value: float, ts: str, memo: str, correction: str | None = None) -> None:
    eid = f"LY-{account}-{uuid.uuid4().hex[:6]}"
    db.insert("gl_entries", {"entry_id": eid, "txn_id": eid, "posted_at": ts, "eff_date": ts[:10], "period": "2024", "orig_period": "2024", "entity": "LYFT", "account": account,
                             "amount_cents": int(round(value * 100)), "memo": memo, "source_ref": account.split(".")[0], "import_id": None, "correction_id": correction, "approval_id": None, "world": "lyft"})


def values(at: str, extra: list[dict] | None = None) -> dict:
    return library().evaluate(Books([e for e in entries()], at, extra))


# ------------------------------------------------------------------------------------------------------------------ sources
def _source(sid: str, system: str, title: str, versions: list[tuple[str, str, str]]) -> None:
    db.insert("sources", {"source_id": sid, "uri_r": f"/r/{sid}", "system": system, "kind": "file", "title": title})
    prev = None
    for i, (path, captured, note) in enumerate(versions):
        p = Path(path)
        vid = f"{sid}@v{i + 1}"
        body = {"path": str(p.relative_to(C.DATA_DIR)) if p.is_absolute() else path, "format": p.suffix.lstrip("."), "title": title, "note": note, "world": "lyft"}
        import hashlib
        db.insert("source_versions", {"version_id": vid, "source_id": sid, "body": json.dumps(body), "content_hash": hashlib.sha256(p.read_bytes()).hexdigest(), "document_date": captured[:10],
                                      "tx_from": db.norm_ts(captured), "tx_to": C.TX_CURRENT, "supersedes": prev, "correction_id": "LY-CORR" if i else None})
        if prev:
            db.get_conn().execute("UPDATE source_versions SET tx_to=? WHERE version_id=?", (db.norm_ts(captured), prev))
        prev = vid


def write_sources() -> None:
    LYFT_DIR.mkdir(parents=True, exist_ok=True)
    (LYFT_DIR / "lyft_close_pack_q4_2023.json").write_text(json.dumps({"title": "RECONSTRUCTION: Lyft Q4 2023 close pack (figures as later published in the release)", "reconstruction": True,
                                                                       "figures": PACK}, indent=1), encoding="utf-8", newline="\n")
    (LYFT_DIR / "lyft_fpa_guidance_model_fy2024.json").write_text(json.dumps({"title": "RECONSTRUCTION: FP&A FY2024 guidance model (margin bridge), Feb 9, 2024", "reconstruction": True,
                                                                              "figures": MODEL, "bridge": "FY2023 margin 1.6% -> FY2024 target 2.1%: +50 bps"}, indent=1), encoding="utf-8", newline="\n")
    shutil.copy(EXHIBIT, LYFT_DIR / "lyft_ex991_20240213_as_filed.htm")
    raw = EXHIBIT.read_text(encoding="utf-8", errors="ignore")
    corrected = raw.replace("approximately 500 basis points", "approximately 50 basis points", 1)
    corrected = re.sub(r"(<body[^>]*>)", r"\1<p><b>CORRECTING and REPLACING</b> (rendering of the public correction: 500 basis points reads 50; Trackback demo file)</p>", corrected, count=1)
    (LYFT_DIR / "lyft_ex991_20240213_corrected.htm").write_text(corrected, encoding="utf-8", newline="\n")
    _source("lyft_close_pack", "close_pack", "RECONSTRUCTION: Q4 2023 close pack", [(str(LYFT_DIR / "lyft_close_pack_q4_2023.json"), T["pack"], "reconstruction")])
    _source("lyft_fpa_model", "fpa_model", "RECONSTRUCTION: FP&A FY2024 guidance model", [(str(LYFT_DIR / "lyft_fpa_guidance_model_fy2024.json"), T["model"], "reconstruction")])
    _source("lyft_release", "press_release", "REAL: Lyft Q4 and full-year 2023 results, Exhibit 99.1 (as filed 16:06 ET, then as corrected)",
            [(str(LYFT_DIR / "lyft_ex991_20240213_as_filed.htm"), T["filed"], "as filed (real)"), (str(LYFT_DIR / "lyft_ex991_20240213_corrected.htm"), T["correction"], "CORRECTING and REPLACING")])
    for k, v in PACK.items():
        _post(f"PACK.{k}", v, T["pack"], "close pack (reconstruction)")
    for k, v in MODEL.items():
        _post(f"MODEL.{k}", v, T["model"], "guidance model (reconstruction)")
    for acct, v in (("REL.bps", 500.0), ("REL.fy23_margin", 1.6), ("REL.fy23_gb", 13.8e9), ("REL.q4_gb", 3.7e9), ("REL.q4_rev", 1.2e9)):
        _post(acct, v, T["filed"], "as filed (real)")


# ------------------------------------------------------------------------------------------------------------------ agents' work
def _calc(metric: str, at: str) -> tuple[str, int]:
    val = values(at)[metric]
    aid = f"M:{metric}"
    cur = db.artifact_current(aid)
    if cur is not None and cur["value_num"] is not None and abs(cur["value_num"] - val) < 1e-9:
        return aid, cur["version"]
    if cur is not None:
        db.close_tx("artifacts", "artifact_id", aid, db.norm_ts(at), " AND version=?", (cur["version"],))
    lib = library()
    v = G.new_artifact(artifact_id=aid, kind="number", run_id="trackback:calc", pinned_at=db.norm_ts(at), period="2024", line_item=metric, content=lib.metrics[metric].label, value_num=val,
                       formula=None, conclusions=None, agent_id="trackback", node_kind="calc", origin="initial" if cur is None else "recalc", metric=metric, world="lyft")
    return aid, v


def _emit(aid: str, run: str, agent: str, at: str, kind: str, content: str, consumes: list[str], value: float | None = None, fields: dict | None = None, conclusions: dict | None = None) -> int:
    v = G.new_artifact(artifact_id=aid, kind=kind, run_id=run, pinned_at=db.norm_ts(at), period="2024", line_item=aid, content=content, value_num=value, formula=None, conclusions=conclusions,
                       agent_id=agent, origin="initial", fields=fields, world="lyft")
    for m in consumes:
        cid, cv = _calc(m, at)
        G.add_edge(consumer_id=aid, consumer_version=v, supporter_kind="artifact", supporter_id=cid, supporter_version=str(cv), dep_kind="numeric", capture="tool_log")
    return v


def _run(rid: str, agent: str, task: str, at: str) -> str:
    db.insert("runs", {"run_id": rid, "agent": agent, "task": task, "pinned_at": db.norm_ts(at), "mode": "history", "status": "done", "started_at": db.norm_ts(at), "finished_at": db.norm_ts(at),
                       "turns": 1, "note": "reconstruction", "trigger": "schedule", "ping_id": None, "goal": task, "deliverables_json": None, "model": C.AGENT_MODEL, "prompt_version": "v3"})
    return rid


def _act(aid: str, kind: str, params: dict, run: str, proposer: str, approver: str, at: str, summary: str, execute: bool) -> None:
    G.new_action(action_id=aid, artifact_id=aid, kind=kind, params=params, run_id=run, proposer=proposer, approver_role=approver, created_at=at)
    db.get_conn().execute("UPDATE actions SET world='lyft', assignee=?, summary=? WHERE action_id=?", (approver, summary, aid))
    if execute:
        db.insert("approvals", {"approval_id": f"APR-{aid}", "action_id": aid, "proposer": proposer, "approver": approver, "decision": "approved", "reason": "approved at the time", "ts": db.norm_ts(at)})
        G.set_action_state(aid, "executed", db.norm_ts(at), executed_at=at)


def history() -> dict:
    for aid, (name, seat) in AGENTS.items():
        if db.q1("SELECT 1 FROM agents WHERE agent_id=?", (aid,)) is None:
            db.insert("agents", {"agent_id": aid, "display_name": name, "ping_endpoint": f"/agents/{aid}/trackback", "model": C.AGENT_MODEL, "prompt_version": "v3", "seat": seat})
    # inside the finance team (with Trackback)
    r1 = _run("RL_FPA", "lyft_fpa", "Summarize the FY2024 guidance model", T["fpa_run"])
    _emit("LY.fpa.model_note", r1, "lyft_fpa", T["fpa_run"], "sentence", "The 2024 plan targets a 2.1% Adjusted EBITDA margin, 50 basis points above 2023's 1.6%.",
          ["lyft.margin_expansion_bps", "lyft.fy24_margin_target", "lyft.fy23_margin"])
    r2 = _run("RL_IR", "lyft_ir", "Draft the Q4 release highlights and the CFO's prepared remarks", T["ir_run"])
    _emit("LY.ir.q4_bookings", r2, "lyft_ir", T["ir_run"], "sentence", "Gross Bookings of $3.7 billion grew 17% year-over-year.", ["lyft.q4_gb", "lyft.q4_gb_growth"])
    _emit("LY.ir.outlook_margin", r2, "lyft_ir", T["ir_run"], "sentence",
          "Adjusted EBITDA margin expansion (calculated as a percentage of Gross Bookings) of approximately 500 basis points year-over-year.", ["lyft.margin_expansion_bps"],
          fields={"artifacts": ["M:lyft.margin_expansion_bps"]})
    _emit("LY.ir.call_script", r2, "lyft_ir", T["ir_run"], "sentence", "Prepared remarks: for the full year we expect roughly 50 basis points of Adjusted EBITDA margin expansion.", ["lyft.margin_expansion_bps"],
          fields={"artifacts": ["M:lyft.margin_expansion_bps"]})
    _emit("LY.ir.publish_release", r2, "lyft_ir", T["ir_run"], "action", "Issue the Q4 release on Business Wire at 4:05 pm ET and furnish it on Form 8-K", ["lyft.margin_expansion_bps"])
    _act("LY.ir.publish_release", "release_publish", {"summary": "Issue the release and furnish it on Form 8-K"}, r2, "lyft_ir", "cfo", T["ir_run"], "Publish the Q4 2023 release (4:05 pm ET)", False)
    r3 = _run("RL_DISC", "lyft_disclosure", "Prepare the Form 8-K", T["disc_run"])
    _act("LY.disc.file_8k", "sec_filing", {"summary": "Furnish the release as Exhibit 99.1 (Items 2.02, 7.01, 9.01)"}, r3, "lyft_disclosure", "general_counsel", T["disc_run"], "File the 8-K", False)
    # the CFO approves at 15:30; Trackback's pre-execution fence checks every sentence against the figure it cites
    from ..core import approvals as AP, fence
    AP.decide("LY.ir.publish_release", "cfo", "approved", "approved for 4:05 pm ET release", db.norm_ts(T["cfo_approves"]))
    fm = fence.figure_mismatch(db.artifact_current("LY.ir.outlook_margin"))
    blocked = None
    if fm:
        G.set_action_state("LY.ir.publish_release", "blocked", db.norm_ts(T["cfo_approves"]))
        fix = re.sub(r"(?<![\d.])500(?![\d])", "50", db.artifact_current("LY.ir.outlook_margin")["content"], count=1)
        blocked = {"action": "LY.ir.publish_release", "mismatch": fm, "fix": fix, "at": T["cfo_approves"]}
        db.log_event("fence_block", f"Pre-execution fence blocked LY.ir.publish_release: the outlook sentence {fm['message']}", actor="trackback:fence", ts=db.norm_ts(T["cfo_approves"]),
                     detail={"stale": [{"problem": "figure_mismatch", "stated": fm["stated"], "cited_value": fm["cited_value"], "artifact": "LY.ir.outlook_margin"}], "fix": fix, "world": "lyft"})
    # the outside world, built on the release as filed (real release, reconstructed dependents)
    r4 = _run("RL_NEWS", "newsroom", "Write the earnings headline and story and publish", T["news_run"])
    _emit("LY.news.headline", r4, "newsroom", T["news_run"], "sentence", "Lyft shares surge after it forecasts 500 basis points of margin expansion in 2024.", ["release.margin_expansion_bps"],
          fields={"template": "Lyft forecasts {release.margin_expansion_bps} basis points of margin expansion in 2024.", "unit": "bps"})
    _emit("LY.news.story_q4", r4, "newsroom", T["news_run"], "sentence", "Fourth-quarter gross bookings rose 17% to $3.7 billion.", ["release.q4_gb"])
    _emit("LY.news.publish", r4, "newsroom", T["news_run"], "action", "Publish the earnings story and push the headline alert", ["release.margin_expansion_bps"])
    _act("LY.news.publish", "publish_story", {"summary": "Publish the story and the headline alert"}, r4, "newsroom", "editor", T["news_pub"], "Story published 16:18 ET", True)
    r5 = _run("RL_STREET", "street_analyst", "Flash note on the release and route an order", T["street_run"])
    v = values(T["street_run"])
    _emit("LY.street.note", r5, "street_analyst", T["street_run"], "sentence",
          f"Guidance implies a {v['street.implied_fy24_margin']:.1f}% Adjusted EBITDA margin and about ${v['street.implied_fy24_adj_ebitda'] / 1e9:.2f}B of Adjusted EBITDA in 2024; we raise our target.",
          ["street.implied_fy24_margin", "street.implied_fy24_adj_ebitda"])
    _emit("LY.street.q4_beat", r5, "street_analyst", T["street_run"], "sentence", "Q4 Gross Bookings of $3.7 billion and revenue of $1.2 billion were ahead of consensus.", ["release.q4_gb", "release.q4_rev"])
    _emit("LY.street.order", r5, "street_analyst", T["street_run"], "action", "Buy 200,000 LYFT at the after-hours print on the margin guide", ["street.implied_fy24_adj_ebitda"],
          value=v["street.implied_fy24_adj_ebitda"])
    _act("LY.street.order", "order", {"summary": "Buy 200,000 LYFT", "shares": 200000}, r5, "street_analyst", "pm", T["order"], "200,000-share buy filled 16:25 ET", True)
    # the correction: CORRECTING and REPLACING, 17:00 ET (the CFO said 50 on the 4:30 call)
    _post("REL.bps", -450.0, T["correction"], "CORRECTING and REPLACING: 500 basis points reads 50", correction="LY-CORR")
    db.insert("corrections", {"correction_id": "LY-CORR", "source_id": "lyft_release", "old_version": "lyft_release@v1", "new_version": "lyft_release@v2", "kind": "error",
                              "knowable_at": db.norm_ts(T["call"]), "materiality_verdict": None, "booking_period": "2024-02", "tx_time": db.norm_ts(T["correction"]),
                              "note": "Clerical error in the release: 500 basis points should read 50. Knowable from the 4:30 pm ET call."})
    db.commit()
    return {"blocked": blocked}


# ------------------------------------------------------------------------------------------------------------------ the review at 17:05
def trace(run_id: str | None = None, path: Path | None = None, phrases: list[str] | None = None, text_override: str | None = None) -> list[dict]:
    from ..engine import lineage as L
    lib = library(trace_only=True)
    p = path or (LYFT_DIR / "lyft_ex991_20240213_as_filed.htm")
    if text_override is not None:
        tmp = C.DATA_DIR / "build" / "lyft_variant.htm"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text_override, encoding="utf-8")
        p = tmp
    items = L.extract_html_lines(p, "REL", phrases or TRACE_PHRASES)
    snap = {"pack": T["pack"], "model": T["model"], "close": T["filed"]}
    vals = {k: lib.evaluate(Books(entries(), t)) for k, t in snap.items()}
    links = L.match(items, lib, vals, {p.name: "close"}, ["pack", "model", "close"], {p.name: None}, None, {"close": "close pack and guidance model"})
    for l in links:
        l["owner"] = "lyft_ir"
    return links


def detect(links: list[dict]) -> dict:
    """release_to_sources: every figure in the release against its system of record. A figure that matches no source but matches one at another
    power of ten is the extra-zero signature."""
    out = {"recon": "release_to_sources", "title": "Release figures vs the close pack and the guidance model", "matched": [], "cleared": [], "exceptions": []}
    for l in links:
        if l["status"] in ("linked", "policy"):
            out["matched"].append({"reason": "ties", "item": l["item_id"], "label": l["label"][:80], "metric": l["metric_id"], "display": l.get("display"), "confidence": l.get("confidence")})
        elif l["status"] == "unlinked":
            pow10 = next((n for n in l.get("near_misses", []) if n.get("power_of_ten")), None)
            near = next((n for n in l.get("near_misses", []) if "diff_pct" in n), None)
            kind = "figure_mismatch" if pow10 else "unsupported_figure"
            src = pow10 or near or {}
            exc = {"recon": "release_to_sources", "kind": kind, "item": l["item_id"], "label": l["label"], "stated": l["value"], "source_metric": src.get("metric"), "source_value": src.get("value"),
                   "power_of_ten": src.get("power_of_ten"), "amount": abs((l["value"] or 0) - (src.get("value") or 0)),
                   "title": (f"Release states {l['value']:g} but the guidance model says {src.get('value'):g} (same digits, another power of ten)" if pow10 else
                             f"Release figure {l.get('display') or l['value']} has no source" + (f" (nearest: {src.get('metric')} = {src.get('value'):,.4g})" if src else "")),
                   "evidence": [{"what": "release line", "item": l["item_id"], "text": l["label"][:200]}, {"what": "source", "metric": src.get("metric"), "value": src.get("value")}],
                   "system_of_record": "lyft_fpa_model" if (src.get("metric") or "").startswith(("lyft.margin", "lyft.fy24", "lyft.fy23", "lyft.q1_")) else "lyft_close_pack",
                   "trust": {"trusted": "The FP&A guidance model (and the CFO's prepared remarks, which say 50)" if pow10 else "The close pack", "over": "the release text",
                             "why": "The release is drafted from the model; the model said 50 basis points from Feb 9, and the call script said 50."},
                   "knowable": {"at": T["model"], "fact": "the guidance model captured Feb 9 18:00 ET already said 50 basis points"},
                   "correction": {"lines": [{"entity": "LYFT", "account": "REL.bps", "amount_cents": int(round(((src.get("value") or 0) - (l["value"] or 0)) * 100)), "orig_period": "2024"}] if pow10 else [],
                                  "orig_period": "2024", "memo": "CORRECTING and REPLACING release"}}
            out["exceptions"].append(exc)
    for n, e in enumerate(out["exceptions"], start=1):
        e["exception_id"] = f"LY-{n:02d}"
    out["counts"] = {"matched": len(out["matched"]), "cleared": len(out["cleared"]), "exceptions": len(out["exceptions"])}
    out["cleared_by_reason"] = {"display_rounding": len(out["cleared"])} if out["cleared"] else {}
    return out


def agent_nodes() -> list[dict]:
    nodes = []
    for aid, snap in (("LY.news.headline", "close"), ("LY.news.story_q4", "close"), ("LY.street.note", "close"), ("LY.street.q4_beat", "close")):
        cur = db.artifact_current(aid)
        cons = [db.q1("SELECT line_item FROM artifacts WHERE artifact_id=? AND version=?", (e["supporter_id"], int(e["supporter_version"])))["line_item"] for e in G.supporters_of(aid, cur["version"])]
        nodes.append({"id": aid, "owner": cur["agent_id"], "kind": "prose", "label": aid, "content": cur["content"], "consumes": cons, "snapshot": snap, "tolerance": 0.5})
    return nodes


ACTIONS = [{"id": "LY.news.publish", "label": "Story and headline alert published (16:18 ET)", "kind": "publish_story", "metric": "release.margin_expansion_bps", "owner": "newsroom",
            "executed_at": T["news_pub"], "compensation": "correction_note", "comp_approver": "editor"},
           {"id": "LY.street.order", "label": "200,000-share buy filled at the after-hours print (16:25 ET)", "kind": "order", "metric": "street.implied_fy24_adj_ebitda", "owner": "street_analyst",
            "executed_at": T["order"], "compensation": "unwind_order", "comp_approver": "pm"}]


def ripple(exc: dict) -> dict:
    from ..engine import graph as GR
    corr = {"id": exc["exception_id"], "title": exc["title"], "lines": exc["correction"]["lines"]}
    return GR.ripple(correction=corr, lib=library(), entries=[e for e in entries() if not e.get("correction_id")], snapshots=SNAPSHOTS, links=[], actions=ACTIONS, agent_nodes=agent_nodes())


def evaluate(exc: dict, rp: dict, pb: dict, pin: str) -> dict:
    """The seven questions for a disclosure error. Playbook v1's weaknesses apply here too: the 5% rule sees no P&L effect and calls it
    immaterial; the fix goes to the controller rather than the CFO and General Counsel."""
    from ..agent import llm
    eid = exc["exception_id"]
    facts = {"stated": f"{exc['stated']:g}", "source": f"{exc.get('source_value') or 0:g}", "title": exc["title"]}
    rc = llm.write(f"lyft:root_cause:{eid}", "Write the root cause in one sentence for the error memo.", facts,
                   "The release draft typed {stated} where the guidance model and the CFO's prepared remarks say {source}: a clerical error (an extra zero) that the publication sign-off did not catch.", pin)
    v1 = pb["materiality"]["rule"] == "five_percent_pretax"
    q5 = ({"material": False, "method": "5% of annual pretax, rollover only", "why": "a guidance sentence has no financial-statement effect: 0% of pretax income, immaterial", "triggers": []} if v1 else
          {"material": True, "method": "SAB 99 qualitative", "triggers": ["public_guidance", "outside_reliance", "magnitude_x10"],
           "qualitative": [{"factor": "public_guidance", "label": "Misstates forward-looking guidance in a furnished release"},
                           {"factor": "outside_reliance", "label": f"{len([n for n in rp['agent_nodes'].values() if n['verdict'] == 'suspect'])} outside work products and {rp['counts']['compensations']} executed actions rest on it"},
                           {"factor": "magnitude_x10", "label": "Ten times the true figure (500 vs 50 basis points)"}],
           "why": "Material: a tenfold misstatement of headline guidance in a public release that outside parties acted on within minutes"})
    approver = {"disclosure": "controller" if pb["routing"]["lender_document"] == "controller" else "cfo"}
    return {"exception_id": eid, "title": exc["title"], "kind": exc["kind"], "playbook_version": pb["version"], "world": "lyft",
            "q1_what": {"kind": exc["kind"], "root_cause": rc["text"], "root_cause_model": rc["model"], "evidence": [exc["item"], "lyft_fpa_model", "LY.ir.call_script"]},
            "q2_trust": {**exc["trust"], "system_of_record": exc["system_of_record"], "evidence": [f"source:{exc['system_of_record']}"]},
            "q3_classification": {"value": "error", "rule": "the model said 50 before the release was drafted: a clerical error", "knowable_at": db.norm_ts(T["model"]), "original_made_at": db.norm_ts(T["filed"]),
                                  "evidence": "replay:lyft_fpa_model@v1", "fact": exc["knowable"]["fact"]},
            "q4_size": {"amount": exc["amount"], "stated": exc["stated"], "true": exc.get("source_value"), "rollover": 0.0, "iron_curtain": 0.0, "by_region": {},
                        "implied_ebitda_overstated": rp["metrics"].get("street.implied_fy24_adj_ebitda", {}).get("old", 0) - rp["metrics"].get("street.implied_fy24_adj_ebitda", {}).get("new", 0),
                        "evidence": [f"correction:{eid}"]},
            "q5_matters": {**q5, "evidence": [f"ripple:{eid}"]},
            "q6_touched": {"invalidated": [], "still_valid": {}, "actions": {i: {"verdict": v["verdict"], "reason": v["reason"], "compensation": v.get("compensation")} for i, v in rp["actions"].items()},
                           "agent_work": {i: v["verdict"] for i, v in rp["agent_nodes"].items()}, "counts": rp["counts"], "evidence": [f"ripple:{eid}"]},
            "q7_fix": {"entries": [], "treatment": "silent_fix" if v1 else "correcting_and_replacing", "posting_period": None,
                       "why": "replace the figure in the release on the website" if v1 else "issue a CORRECTING and REPLACING release, amend Exhibit 99.1, say it on the call, and tell the outside parties",
                       "documents_to_reissue": ["Exhibit 99.1"], "compensations": [{"action_id": a, **v["compensation"]} for a, v in rp["actions"].items() if v.get("compensation")],
                       "approvers": {"disclosure": "controller" if approver["disclosure"] == "controller" else "cfo", **({} if v1 else {"filing": "general_counsel"})}, "evidence": [f"correction:{eid}"]},
            "confidence": {"overall": 0.8 if v1 else 0.9, "per_claim": {}, "needs_human": []}}


def jade(ev: dict, exc: dict, rp: dict, pin: str) -> list[dict]:
    from ..agent import llm
    out = []
    pow10 = exc.get("power_of_ten")
    out.append({"claim_key": "q4_size", "verdict": "approve", "why": f"recomputed: stated {exc['stated']:g}, source {exc.get('source_value'):g}" + (f" (x{pow10:g})" if pow10 else ""), "method": "code",
                "agent_value": ev["q4_size"]["amount"], "corrected": None})
    out.append({"claim_key": "q3_classification", "verdict": "approve", "why": "Replay: the guidance model captured Feb 9 18:00 ET said 50, before the release was drafted: an error", "method": "code",
                "agent_value": "error", "corrected": None})
    if not ev["q5_matters"]["material"]:
        out.append({"claim_key": "q5_matters", "verdict": "overrule", "agent_value": False, "method": "code", "corrected": {"material": True, "triggers": ["public_guidance", "outside_reliance", "magnitude_x10"]},
                    "why": f"No P&L effect, so a 5% rule shrugs; but it states headline guidance at ten times the model in a furnished release, and {rp['counts']['compensations']} executed actions outside the company "
                           "already rest on it (SAB 99: misleads investors; market-moving)."})
    else:
        out.append({"claim_key": "q5_matters", "verdict": "approve", "why": "qualitative: public guidance, outside reliance, magnitude", "method": "code", "agent_value": True, "corrected": None})
    who = ev["q7_fix"]["approvers"].get("disclosure")
    if who != "cfo":
        out.append({"claim_key": "q7_fix.approvers.disclosure", "verdict": "flag", "agent_value": who, "method": "code", "corrected": {"approver": "cfo", "filing": "general_counsel"},
                    "why": "public disclosures go to the CFO, with the General Counsel for the 8-K exhibit; the controller cannot correct a furnished release"})
    if ev["q7_fix"]["treatment"] == "silent_fix":
        out.append({"claim_key": "q7_fix.treatment", "verdict": "escalate", "agent_value": "silent_fix", "method": "code", "corrected": None,
                    "why": "a furnished release cannot be edited silently; the General Counsel decides the correction (routed)"})
    cr = llm.critique(f"jade:{ev['exception_id']}:root_cause", ev["q1_what"]["root_cause"], {"title": exc["title"]}, pin)
    out.append({"claim_key": "q1_what.root_cause", "verdict": cr["verdict"], "why": cr["why"] if cr["verified"] else "accepted; not independently verified (no model)", "method": "llm" if cr["verified"] else "accept",
                "agent_value": None, "corrected": None})
    return out


def run_review(pin: str | None = None) -> dict:
    """The review at 17:05 ET: trace, detect, evaluate (v1), Jade, the ripple and the wave, proposals (the General Counsel will reject the silent fix), the memo."""
    from .. import hub, jade as J
    from ..agent import playbook as PB
    pin = pin or T["review"]
    rid = f"RVL-{uuid.uuid4().hex[:8]}"
    db.insert("review_runs", {"run_id": rid, "world": "lyft", "pinned_at": db.norm_ts(pin), "playbook_version": "v1", "status": "running", "started_at": db.norm_ts(pin), "finished_at": None, "summary_json": None})
    links = trace(rid)
    det = detect(links)
    for l in links:
        db.insert("trace_items", {"item_id": l["item_id"], "run_id": rid, "world": "lyft", "file": l["file"], "locator": l["locator"], "label": (l.get("context") or l["label"])[:400], "kind": l["kind"],
                                  "value_num": l["value"] if isinstance(l["value"], (int, float)) else None, "value_text": None, "unit": l["unit"], "tolerance": l.get("tolerance"),
                                  "display": l.get("display"), "owner": "lyft_ir", "refs_json": "[]"})
        db.insert("trace_links", {"item_id": l["item_id"], "run_id": rid, "status": l["status"], "metric_id": l.get("metric_id"), "snapshot": l.get("snapshot"), "method": l.get("method"),
                                  "confidence": l.get("confidence"), "explanation": l.get("explanation"), "candidates_json": json.dumps(l.get("candidates", []) + ([{"near_misses": l["near_misses"]}] if l.get("near_misses") else [])),
                                  "confirmed_by": None, "confirmed_at": None})
    out = {"run_id": rid, "links": links, "detect": det, "evaluations": {}, "jade": {}, "final": {}, "ripples": {}, "waves": {}}
    pb = PB.V1
    for e in det["exceptions"]:
        db.insert("exceptions", {"exception_id": e["exception_id"], "run_id": rid, "world": "lyft", "recon": e["recon"], "kind": e["kind"], "title": e["title"], "amount": e["amount"],
                                 "system_of_record": e["system_of_record"], "trust_why": json.dumps(e["trust"]), "knowable_at": e["knowable"]["at"], "evidence_json": json.dumps(e["evidence"], default=str),
                                 "correction_json": json.dumps(e["correction"]), "detail_json": json.dumps(e, default=str)})
        if not e["correction"]["lines"]:
            continue
        rp = ripple(e)
        db.insert("ripples", {"ripple_id": f"RP-{rid}-{e['exception_id']}", "run_id": rid, "world": "lyft", "exception_id": e["exception_id"], "created_at": db.norm_ts(pin),
                              "counts_json": json.dumps(rp["counts"]), "result_json": json.dumps(rp, default=str)})
        ev = evaluate(e, rp, pb, pin)
        jf = jade(ev, e, rp, pin)
        fin = J.apply(ev, [f for f in jf if f["claim_key"] != "q7_fix.approvers.disclosure"])
        for f in jf:
            if f["claim_key"] == "q7_fix.approvers.disclosure" and f.get("corrected"):
                fin["q7_fix"]["approvers"] = {"disclosure": "cfo", "filing": "general_counsel"}
        for k, v in (("", ev), ("-J", fin)):
            db.insert("evaluations", {"eval_id": f"EV-{rid}-{e['exception_id']}{k}", "run_id": rid, "world": "lyft", "exception_id": e["exception_id"], "playbook_version": "v1" + ("+jade" if k else ""),
                                      "claims_json": json.dumps(v, default=str), "created_at": db.norm_ts(pin), "superseded_by": None})
        J.store(f"EV-{rid}-{e['exception_id']}", jf, pin)
        w = hub.dispatch(rp, db.norm_ts(T["correction"]), people_notices=False)
        out["evaluations"][e["exception_id"]], out["jade"][e["exception_id"]], out["final"][e["exception_id"]], out["ripples"][e["exception_id"]], out["waves"][e["exception_id"]] = ev, jf, fin, rp, w
        _propose(e, fin, pin)
        build_memo(rid, e, fin, rp, jf, pin)
    db.insert("kv", {"key": f"waves.{rid}", "value": json.dumps(out["waves"], default=str)})
    db.get_conn().execute("UPDATE review_runs SET status='done', finished_at=?, summary_json=? WHERE run_id=?", (db.norm_ts(pin), json.dumps({"exceptions": len(det["exceptions"]), "links": len(links)}), rid))
    k = db.q1("SELECT 1 FROM kv WHERE key='review.latest.lyft'")
    if k:
        db.get_conn().execute("UPDATE kv SET value=? WHERE key='review.latest.lyft'", (rid,))
    else:
        db.insert("kv", {"key": "review.latest.lyft", "value": rid})
    db.commit()
    print(f"lyft review {rid}: {len(links)} release figures traced, {det['counts']}, waves {[(k, v['stats']) for k, v in out['waves'].items()]}")
    return out


GC_REJECT = "It was furnished on an 8-K at 4:06 pm. A silent web fix is not allowed: issue a CORRECTING and REPLACING release, amend Exhibit 99.1, and say it on the call."


def _propose(e: dict, fin: dict, pin: str) -> None:
    eid = e["exception_id"]
    G.new_action(action_id=f"LY-FIX-{eid}-1", artifact_id=f"LY-FIX-{eid}-1", kind="disclosure_fix", params={"treatment": "silent_fix", "text": "Replace '500 basis points' with '50 basis points' on the website copy"},
                 run_id=f"review:{eid}", proposer="lyft_ir", approver_role="general_counsel", created_at=db.norm_ts(pin))
    db.get_conn().execute("UPDATE actions SET world='lyft', assignee='general_counsel', exception_id=?, draft_no=1, summary=? WHERE action_id=?",
                          (eid, "Fix the figure on the website copy of the release (first draft)", f"LY-FIX-{eid}-1"))
    for c in fin["q7_fix"]["compensations"]:
        aid = f"LY-COMP-{c['action_id'].split('.')[-1]}"
        G.new_action(action_id=aid, artifact_id=c["action_id"], kind=c["kind"], params={"compensates": c["action_id"], "title": c["title"]}, run_id=f"review:{eid}", proposer="trackback",
                     approver_role=c["approver"], created_at=db.norm_ts(T["correction"]))
        db.get_conn().execute("UPDATE actions SET world='lyft', assignee=?, exception_id=?, summary=? WHERE action_id=?", (c["approver"], eid, f"{c['title']} ({c['action_id']})", aid))
    db.commit()


def decide(action_id: str, person: str, decision: str, reason: str, ts: str | None = None) -> dict:
    """The General Counsel rejects the silent fix; the agent re-drafts a CORRECTING and REPLACING release; the CFO then approves it."""
    from ..core import approvals as AP
    ts = db.norm_ts(ts or T["review"])
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    apr = AP.decide(action_id, person, decision, reason, ts)
    out = {"action_id": action_id, "decision": decision, "approval_id": apr}
    if decision == "rejected" and a["kind"] == "disclosure_fix":
        new = action_id.rsplit("-", 1)[0] + f"-{(a['draft_no'] or 1) + 1}"
        G.new_action(action_id=new, artifact_id=new, kind="disclosure_fix", params={"treatment": "correcting_and_replacing", "supersedes": action_id, "rejection": reason,
                     "text": "CORRECTING and REPLACING: ... Adjusted EBITDA margin expansion (calculated as a percentage of Gross Bookings) of approximately 50 basis points year-over-year.",
                     "also": ["amend Exhibit 99.1 (8-K/A)", "CFO states the correction on the call", "notify the outside parties that relied on the release"]},
                     run_id=a["run_id"], proposer="lyft_ir", approver_role="cfo", created_at=ts)
        db.get_conn().execute("UPDATE actions SET world='lyft', assignee='cfo', exception_id=?, draft_no=?, summary=? WHERE action_id=?",
                              (a["exception_id"], (a["draft_no"] or 1) + 1, "CORRECTING and REPLACING release and amended Exhibit 99.1 (re-draft)", new))
        db.log_event("redraft", f"lyft_ir re-drafted {action_id} as {new} after the General Counsel's rejection", actor="lyft_ir", ts=ts, detail={"from": action_id, "to": new, "reason": reason})
        out["redraft"] = new
    elif decision == "approved":
        G.set_action_state(action_id, "executed", ts, executed_at=ts)
    db.commit()
    return out


def simulate(person: str, ts: str | None = None) -> list[dict]:
    out = []
    for a in db.q("SELECT * FROM actions WHERE world='lyft' AND state='proposed' AND assignee=? ORDER BY created_at, action_id", (person,)):
        p = json.loads(a["params_json"])
        if a["kind"] == "disclosure_fix" and p.get("treatment") == "silent_fix":
            out.append(decide(a["action_id"], person, "rejected", GC_REJECT, ts))
        else:
            out.append(decide(a["action_id"], person, "approved", "Approved: correcting release and amended exhibit." if a["kind"] == "disclosure_fix" else "Approved.", ts))
    return out


def build_memo(rid: str, e: dict, fin: dict, rp: dict, jf: list[dict], pin: str) -> str:
    L = [f"# Error memo: {e['title']}", "Lyft, February 13, 2024. Release as filed: REAL. Close pack, guidance model, agents and outside dependents: RECONSTRUCTION (labeled).",
         "\n## 1. Summary", f"The Q4 2023 release furnished at 4:06 pm ET stated approximately {e['stated']:g} basis points of FY2024 Adjusted EBITDA margin expansion; the FP&A guidance model "
         f"and the CFO's prepared remarks said {e.get('source_value'):g}. It is a clerical error, material on qualitative grounds, and the outside world acted on it within minutes. [ev:{e['item']}]",
         "\n## 2. Background and root cause", fin["q1_what"]["root_cause"] + " [ev:lyft_fpa_model] [ev:LY.ir.call_script]",
         "\n## 3. Classification", f"**Error.** {fin['q3_classification']['fact']}. [ev:replay:lyft_fpa_model@v1]",
         "\n## 4. Quantification", "| Measure | Value |\n|---|---|", f"| Stated | {e['stated']:g} bps |", f"| Source | {e.get('source_value'):g} bps |",
         f"| Implied FY2024 Adjusted EBITDA overstated (sell-side arithmetic) | ${fin['q4_size']['implied_ebitda_overstated'] / 1e6:,.0f}M |",
         "\n## 5. Materiality", "No financial-statement effect, so the 5% rule calls it immaterial. SAB 99 qualitative factors make it material:"]
    for q in (fin["q5_matters"].get("qualitative") or [{"label": t} for t in fin["q5_matters"].get("triggers", [])]):
        L.append(f"- {q['label']}")
    L.append("\n## 6. Who built on it (pings at 17:00 ET)")
    for i, v in rp["agent_nodes"].items():
        L.append(f"- {i}: {v['verdict']} ({v['reason']})")
    for i, v in rp["actions"].items():
        L.append(f"- {v['label']}: {v.get('compensation', {}).get('title', v['reason'])} [ev:{i}]")
    L += ["\n## 7. Fix and approvals", "| Item | Approver | Status |\n|---|---|---|"]
    for a in db.q("SELECT * FROM actions WHERE world='lyft' AND exception_id=? ORDER BY created_at, action_id", (e["exception_id"],)):
        L.append(f"| {a['summary']} | {PEOPLE.get(a['assignee'] or '', a['assignee'])} | {a['state']} |")
    L += ["\n## 8. Controls going forward", "- Before publication, tie every figure in a release to the model or close pack it cites (the pre-execution fence: a sentence must show the figure it rests on).",
          "- Same digits at another power of ten is a block, not a warning.", "\n## 9. Jade's review notes"]
    for f in jf:
        if f["verdict"] != "approve":
            L.append(f"- {f['claim_key']}: **{f['verdict']}**. {f['why']}")
    md = "\n".join(L)
    n = (db.q1("SELECT MAX(version) v FROM memos WHERE memo_id=?", (f"MEMO-{e['exception_id']}",))["v"] or 0) + 1
    db.insert("memos", {"memo_id": f"MEMO-{e['exception_id']}", "version": n, "world": "lyft", "exception_id": e["exception_id"], "markdown": md, "created_at": db.norm_ts(pin)})
    return md


def build_all() -> dict:
    write_sources()
    h = history()
    r = run_review()
    db.insert("kv", {"key": "lyft.history", "value": json.dumps(h, default=str)})
    db.commit()
    return {"history": h, "review": {k: v for k, v in r.items() if k in ("run_id",)}}


# ------------------------------------------------------------------------------------------------------------------ cases for the scorecard
VARIANTS = [
    ("LY-REAL", "the real release: approximately 500 basis points", None, "figure_mismatch"),
    ("LY-REV-X10", "Revenue typed as $12 billion (another power of ten)", ("Revenue of $1.2 billion grew 4%", "Revenue of $12 billion grew 4%"), "figure_mismatch"),
    ("LY-EBITDA-DIGIT", "Adjusted EBITDA typed as $66.0 million", ("Adjusted EBITDA of $66.6 million", "Adjusted EBITDA of $66.0 million"), "unsupported_figure"),
    ("LY-GROWTH-SWAP", "Gross Bookings growth typed as 71%", ("Gross Bookings of $3.7 billion grew 17%", "Gross Bookings of $3.7 billion grew 71%"), "unsupported_figure"),
    ("LY-CORRECT", "the corrected release (expected: nothing but the figures that tie)", ("approximately 500 basis points", "approximately 50 basis points"), None),
]


def variant_detect(case: tuple) -> dict:
    cid, title, swap, kind = case
    real = cid == "LY-REAL"
    raw = (LYFT_DIR / ("lyft_ex991_20240213_as_filed.htm" if real else "lyft_ex991_20240213_corrected.htm")).read_text(encoding="utf-8", errors="ignore")
    phrases = [p if real else p.replace("500 basis", "50 basis") for p in TRACE_PHRASES]
    if cid == "LY-CORRECT":
        swap = None
    if swap:
        raw = raw.replace(swap[0], swap[1], 1)
        phrases = [p.replace(swap[0].split(" grew")[0], swap[1].split(" grew")[0]) if swap[0].split(" grew")[0] in p else p for p in phrases]
        phrases = [("approximately 50 basis points" if p == "approximately 500 basis points" and "50 basis" in swap[1] else p) for p in phrases]
    links = trace(text_override=raw, phrases=phrases)
    det = detect(links)
    found = [e["kind"] for e in det["exceptions"]]
    ok = (found == [kind]) if kind else (found == [])
    return {"case": cid, "title": title, "expected": kind, "found": found, "ok": ok, "matched": det["counts"]["matched"] + det["counts"]["cleared"]}
