"""Lyft, February 13, 2024: the "500 basis points" typo.

Real (public, as filed): the Q4 2023 earnings release furnished as Exhibit 99.1 to the 8-K at 16:06 ET said "Adjusted EBITDA margin
expansion ... of approximately 500 basis points year-over-year"; on the 4:30 pm ET call the CFO corrected it to 50; Business Wire
issued a CORRECTING and REPLACING release that evening; the stock rose as much as ~67% after hours, was up ~20% at 5:52 pm and
closed up 35.1% at $16.39 the next day (Bloomberg, CNBC, Investor's Business Daily).

Reconstructed (labeled as such everywhere it is shown): what Lyft's own finance team would have had in front of it: the FP&A guidance
model that says 50, the IR draft that says 500, the 8-K prep, and the outside world that built on the release (a sell-side note and
order, a newsroom headline). Those documents are ours; the numbers inside them are the public ones.
"""
from __future__ import annotations

from .. import approvals, corrections, db
from ..agents import base, workorders as wo
from ..core import claims as CL

ET = "-05:00"
REL = "lyft_q4_2023_release"            # real: EX-99.1 as filed, then as corrected
MODEL = "lyft_fpa_guidance_model_fy2024"  # reconstruction: the FP&A model the release was drafted from
PACK = "lyft_q4_2023_close_pack"         # reconstruction: the close pack with the Q4/FY figures (same numbers as the release)
CORR = "LYFT_TYPO"

FACTS = {  # public figures from the as-filed exhibit (USD unless noted; margins in percent; bps as a number)
    "fy23_gross_bookings": 13_800_000_000, "fy23_revenue": 4_400_000_000, "fy23_adj_ebitda": 222_400_000, "fy23_adj_ebitda_margin": 1.6,
    "q4_gross_bookings": 3_700_000_000, "q4_revenue": 1_200_000_000, "q4_adj_ebitda": 66_600_000, "q4_adj_ebitda_margin": 1.8,
    "q1_24_adj_ebitda_low": 50_000_000, "q1_24_adj_ebitda_high": 55_000_000,
}
TAPE = {  # real, for display only (not a source any agent consumes)
    "release_filed": "2024-02-13T16:06:00-05:00", "call_start": "2024-02-13T16:30:00-05:00", "after_hours_peak_pct": 67, "at_1752_pct": 20,
    "next_close_pct": 35.1, "next_close_px": 16.39, "next_close_date": "2024-02-14",
    "sources": ["SEC EDGAR 0001759509-24-000011, Exhibit 99.1 (as filed)", "Business Wire: CORRECTING and REPLACING (Feb 13, 2024)",
                "Bloomberg, Feb 13, 2024: 'Lyft Corrects Earnings Margin Gain to 50 Basis Points From 500'", "CNBC, Feb 14, 2024; Investor's Business Daily, Feb 14, 2024"],
}


def _c(entity, line, start, end, unit, v):
    return {"entity": entity, "line_item": line, "unit": unit, "period_start": start, "period_end": end, "value_num": v, "value_text": None, "account": None}


def _release_claims(bps: float) -> list[dict]:
    f = FACTS
    return [_c("LYFT", "gross_bookings", "2023-01-01", "2023-12-31", "USD", f["fy23_gross_bookings"]), _c("LYFT", "revenue", "2023-01-01", "2023-12-31", "USD", f["fy23_revenue"]),
            _c("LYFT", "adj_ebitda", "2023-01-01", "2023-12-31", "USD", f["fy23_adj_ebitda"]), _c("LYFT", "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct", f["fy23_adj_ebitda_margin"]),
            _c("LYFT", "gross_bookings", "2023-10-01", "2023-12-31", "USD", f["q4_gross_bookings"]), _c("LYFT", "revenue", "2023-10-01", "2023-12-31", "USD", f["q4_revenue"]),
            _c("LYFT", "adj_ebitda", "2023-10-01", "2023-12-31", "USD", f["q4_adj_ebitda"]), _c("LYFT", "adj_ebitda_margin", "2023-10-01", "2023-12-31", "pct", f["q4_adj_ebitda_margin"]),
            _c("LYFT", "adj_ebitda_low", "2024-01-01", "2024-03-31", "USD", f["q1_24_adj_ebitda_low"]), _c("LYFT", "adj_ebitda_high", "2024-01-01", "2024-03-31", "USD", f["q1_24_adj_ebitda_high"]),
            _c("LYFT", "margin_expansion_bps", "2024-01-01", "2024-12-31", "bps", bps)]


def cid(doc, line, start, end, unit):
    return CL.claim_id_for(doc, "LYFT", line, start, end, unit)


def _src(source_id, system, title):
    if db.q1("SELECT 1 FROM sources WHERE source_id=?", (source_id,)) is None:
        db.insert("sources", {"source_id": source_id, "uri_r": f"/r/{source_id}", "system": system, "kind": "generic", "title": title})


# ---- work orders (scripted steps; the real model gets the same required outputs) ----------------------------------------------
def r_fpa() -> dict:
    m23 = cid(MODEL, "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct"); t24 = cid(MODEL, "adj_ebitda_margin_target", "2024-01-01", "2024-12-31", "pct")
    s = [wo.read(MODEL),
         wo.num("lyft_fy23_adj_ebitda_margin", "m", {"m": m23}, "2023", "margin", {"display_decimals": 1}, "FY2023 Adjusted EBITDA margin, % of Gross Bookings"),
         wo.num("lyft_fy24_margin_target", "t", {"t": t24}, "2024", "margin", {"display_decimals": 1}, "FY2024 plan: Adjusted EBITDA margin target, % of Gross Bookings"),
         wo.num("lyft_margin_expansion_bps", "(t-m)*100", {"t": t24, "m": m23}, "2024", "margin_expansion_bps", {"display_decimals": 0}, "FY2024 guided margin expansion, basis points"),
         wo.sent("lyft_s_model_note", "The 2024 plan targets a 2.1% Adjusted EBITDA margin, 50 basis points above 2023's 1.6%.", [m23, t24], "2024", "margin_expansion_bps",
                 ["lyft_margin_expansion_bps", "lyft_fy24_margin_target", "lyft_fy23_adj_ebitda_margin"]),
         wo.finish("FY2024 guidance model summarized: 2.1% margin target, 50 bps of expansion.")]
    return {"run_id": "R_LYFT_FPA", "agent": "lyft_fpa", "pinned_at": f"2024-02-09T18:30:00{ET}",
            "task": "Summarize the FY2024 guidance model: last year's Adjusted EBITDA margin, the 2024 target, and the implied expansion in basis points.", "steps": s}


def r_ir() -> dict:
    gb4 = cid(PACK, "gross_bookings", "2023-10-01", "2023-12-31", "USD"); gb4p = cid(PACK, "gross_bookings", "2022-10-01", "2022-12-31", "USD")
    m23 = cid(PACK, "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct"); m22 = cid(PACK, "adj_ebitda_margin", "2022-01-01", "2022-12-31", "pct")
    s = [wo.read(PACK),
         wo.num("lyft_q4_gross_bookings_growth", "(g-p)/p*100", {"g": gb4, "p": gb4p}, "2023-Q4", "growth", {"display_decimals": 0}, "Q4 Gross Bookings growth, %"),
         wo.sent("lyft_s_q4_bookings", "Gross Bookings of $3.7 billion grew 17% year-over-year.", [gb4, gb4p], "2023-Q4", "gross_bookings", ["lyft_q4_gross_bookings_growth"]),
         wo.sent("lyft_s_fy23_margin", "Adjusted EBITDA margin (calculated as a percentage of Gross Bookings) was 1.6% and compares with (3.5%) in full-year 2022.", [m23, m22], "2023", "margin"),
         # the typo, placed where it actually appeared: the sentence rests on the model's 50 and says 500
         wo.sent("lyft_s_outlook_margin", "Adjusted EBITDA margin expansion (calculated as a percentage of Gross Bookings) of approximately 500 basis points year-over-year.",
                 [], "2024", "margin_expansion_bps", ["lyft_margin_expansion_bps"]),
         wo.sent("lyft_s_call_script_margin", "Prepared remarks: for the full year we expect roughly 50 basis points of Adjusted EBITDA margin expansion.", [], "2024", "margin_expansion_bps", ["lyft_margin_expansion_bps"]),
         wo.act("lyft_publish_release", "release_publish", {"summary": "Issue the Q4 and full-year 2023 earnings release on Business Wire at 4:05 pm ET and furnish it on Form 8-K"},
                ["lyft_s_q4_bookings", "lyft_s_fy23_margin", "lyft_s_outlook_margin"], "cfo", period="2023-Q4", line="release_publish"),
         wo.finish("Release draft and call script prepared; publication proposed for the CFO's sign-off.")]
    return {"run_id": "R_LYFT_IR", "agent": "lyft_ir", "pinned_at": f"2024-02-12T15:00:00{ET}",
            "task": "Draft the Q4 2023 earnings release highlights and the CFO's prepared remarks from the close pack and the FP&A guidance model, then propose publication.", "steps": s}


def r_disclosure() -> dict:
    s = [wo.act("lyft_file_8k", "sec_filing", {"summary": "Furnish the earnings release as Exhibit 99.1 to a Form 8-K (Items 2.02, 7.01, 9.01)"}, ["lyft_publish_release"], "general_counsel", period="2023-Q4", line="sec_filing"),
         wo.finish("8-K prepared; filing proposed for General Counsel sign-off after the release is issued.")]
    return {"run_id": "R_LYFT_DISCLOSURE", "agent": "lyft_disclosure", "pinned_at": f"2024-02-13T09:00:00{ET}",
            "task": "Prepare the Form 8-K that furnishes the earnings release, resting on the approved release.", "steps": s}


def r_street() -> dict:
    gb23 = cid(REL, "gross_bookings", "2023-01-01", "2023-12-31", "USD"); m23 = cid(REL, "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct")
    bps = cid(REL, "margin_expansion_bps", "2024-01-01", "2024-12-31", "bps"); gb4 = cid(REL, "gross_bookings", "2023-10-01", "2023-12-31", "USD"); r4 = cid(REL, "revenue", "2023-10-01", "2023-12-31", "USD")
    s = [wo.read(REL),
         wo.num("lyft_ext_fy24_margin", "m+b/100", {"m": m23, "b": bps}, "2024", "margin", {"display_decimals": 1}, "Implied FY2024 Adjusted EBITDA margin, %"),
         wo.num("lyft_ext_fy24_gross_bookings", "g*1.15", {"g": gb23}, "2024", "gross_bookings", {"display_decimals": 0}, "FY2024 Gross Bookings at mid-teens growth (15%)"),
         wo.num("lyft_ext_fy24_adj_ebitda", "gb*mg/100", {"gb": "lyft_ext_fy24_gross_bookings", "mg": "lyft_ext_fy24_margin"}, "2024", "adj_ebitda", {"display_decimals": 0}, "Implied FY2024 Adjusted EBITDA, USD"),
         wo.sent("lyft_ext_s_note", "Guidance implies a 6.6% Adjusted EBITDA margin and about $1.05B of Adjusted EBITDA in 2024, 500 basis points of expansion; we raise our target.",
                 [bps, m23], "2024", "adj_ebitda", ["lyft_ext_fy24_margin", "lyft_ext_fy24_adj_ebitda"]),
         wo.sent("lyft_ext_s_q4_beat", "Q4 Gross Bookings of $3.7 billion and revenue of $1.2 billion were ahead of consensus.", [gb4, r4], "2023-Q4", "gross_bookings"),
         wo.act("lyft_ext_buy_order", "order", {"summary": "Buy 200,000 LYFT at the after-hours print on the margin guide", "amount": 200000, "value_from": "lyft_ext_fy24_adj_ebitda"},
                ["lyft_ext_fy24_adj_ebitda"], "pm", period="2024", line="order"),
         wo.finish("Flash note written on the release; order routed to the PM.")]
    return {"run_id": "R_LYFT_STREET", "agent": "street_analyst", "pinned_at": f"2024-02-13T16:20:00{ET}",
            "task": "Write a flash note on Lyft's Q4 2023 release: implied 2024 margin and Adjusted EBITDA from the guidance, the Q4 beat, and route a buy order to the PM.", "steps": s}


def r_newsroom() -> dict:
    bps = cid(REL, "margin_expansion_bps", "2024-01-01", "2024-12-31", "bps"); gb4 = cid(REL, "gross_bookings", "2023-10-01", "2023-12-31", "USD")
    s = [wo.read(REL),
         wo.sent("lyft_ext_headline", "Lyft shares surge after it forecasts 500 basis points of margin expansion in 2024.", [bps], "2024", "margin_expansion_bps"),
         wo.sent("lyft_ext_s_story_q4", "Fourth-quarter gross bookings rose 17% to $3.7 billion.", [gb4], "2023-Q4", "gross_bookings"),
         wo.act("lyft_ext_publish_story", "publish_brief", {"summary": "Publish the earnings story and push the headline alert"}, ["lyft_ext_headline", "lyft_ext_s_story_q4"], "editor", period="2024", line="publish_brief"),
         wo.finish("Story published.")]
    return {"run_id": "R_LYFT_NEWS", "agent": "newsroom", "pinned_at": f"2024-02-13T16:15:00{ET}",
            "task": "Write the earnings headline and story from Lyft's release and publish it.", "steps": s}


def _run(order: dict) -> dict:
    o = wo.with_handoffs(order)
    return base.run_agent(run_id=o["run_id"], agent=o["agent"], task=o["task"], pinned_at=o["pinned_at"], required_outputs=wo.required_outputs_text(o), script=o["steps"])


def _approve_execute(action_id: str, approver: str, ts: str, reason: str) -> dict:
    approvals.decide(action_id, approver, "approved", reason, ts)
    return corrections.execute_action(action_id, ts)


def build(mode: str) -> str:
    if db.q1("SELECT 1 FROM sources WHERE source_id=?", (REL,)) is not None:
        return "Lyft: already loaded"
    f = FACTS
    # --- reconstructed internal documents (numbers are the public ones) ---
    _src(MODEL, "fpa_model", "RECONSTRUCTION: FP&A FY2024 guidance model (margin bridge), as of Feb 9, 2024")
    CL.load_version(MODEL, f"{MODEL}@v1", "generic", {"title": "FY2024 guidance model: Adjusted EBITDA margin bridge", "reconstruction": True,
                    "claims": [_c("LYFT", "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct", f["fy23_adj_ebitda_margin"]),
                               _c("LYFT", "adj_ebitda_margin_target", "2024-01-01", "2024-12-31", "pct", 2.1),
                               _c("LYFT", "gross_bookings_growth_target", "2024-01-01", "2024-12-31", "pct", 15.0)]},
                    f"2024-02-09T18:00:00{ET}", document_date="2024-02-09", supersedes=None, correction_id=None)
    _src(PACK, "close_pack", "RECONSTRUCTION: Q4 2023 close pack (figures as later published in the release)")
    CL.load_version(PACK, f"{PACK}@v1", "generic", {"title": "Q4 2023 close pack", "reconstruction": True,
                    "claims": [_c("LYFT", "gross_bookings", "2023-10-01", "2023-12-31", "USD", f["q4_gross_bookings"]), _c("LYFT", "gross_bookings", "2022-10-01", "2022-12-31", "USD", 3_162_000_000),
                               _c("LYFT", "revenue", "2023-10-01", "2023-12-31", "USD", f["q4_revenue"]), _c("LYFT", "adj_ebitda", "2023-10-01", "2023-12-31", "USD", f["q4_adj_ebitda"]),
                               _c("LYFT", "adj_ebitda_margin", "2023-01-01", "2023-12-31", "pct", f["fy23_adj_ebitda_margin"]), _c("LYFT", "adj_ebitda_margin", "2022-01-01", "2022-12-31", "pct", -3.5)]},
                    f"2024-02-08T17:00:00{ET}", document_date="2024-02-08", supersedes=None, correction_id=None)
    db.commit()
    # --- inside the finance team, with Trackback ---
    r1 = _run(r_fpa()); r2 = _run(r_ir()); r3 = _run(r_disclosure())
    res = _approve_execute("ACT-lyft_publish_release", "cfo", f"2024-02-13T15:30:00{ET}", "approved for 4:05 pm ET release")
    blocked = not res["executed"]
    # --- the real release, as filed, and the outside world that built on it ---
    _src(REL, "press_release", "REAL: Lyft Q4 and full-year 2023 results, Exhibit 99.1 to the 8-K filed Feb 13, 2024 (as filed, then as corrected)")
    CL.load_version(REL, f"{REL}@v1", "generic", {"title": "Lyft Announces Fourth Quarter and Full Year 2023 Results (as filed 16:06 ET)", "claims": _release_claims(500.0),
                    "excerpt": "Adjusted EBITDA margin expansion (calculated as a percentage of Gross Bookings) of approximately 500 basis points year-over-year.",
                    "source": "SEC EDGAR 0001759509-24-000011 / lyft-2023x12x31pressreleas.htm"},
                    TAPE["release_filed"], document_date="2024-02-13", supersedes=None, correction_id=None)
    db.commit()
    r4 = _run(r_newsroom()); r5 = _run(r_street())
    _approve_execute("ACT-lyft_ext_publish_story", "editor", f"2024-02-13T16:18:00{ET}", "published")
    _approve_execute("ACT-lyft_ext_buy_order", "pm", f"2024-02-13T16:25:00{ET}", "filled at the after-hours print")
    corrections.apply_correction(CORR, body={"title": "CORRECTING and REPLACING: Lyft Announces Fourth Quarter and Full Year 2023 Results", "claims": _release_claims(50.0),
                                             "excerpt": "Adjusted EBITDA margin expansion (calculated as a percentage of Gross Bookings) of approximately 50 basis points year-over-year.",
                                             "note": "CFO on the 4:30 pm ET call: 'This is actually a correction from the press release. In my prepared remarks, I referenced 50 basis points of margin expansion.'",
                                             "document_date": "2024-02-13"},
                                 tx_time=f"2024-02-13T17:00:00{ET}", kind="error", knowable_at=f"2024-02-13T16:30:00{ET}", source_id=REL, version_id=f"{REL}@v2",
                                 note="Clerical error in the release: 500 basis points should read 50. Knowable to the outside world from the 4:30 pm ET call.", booking_period="2024-02")
    return (f"Lyft loaded: inside runs {r1['turns']}/{r2['turns']}/{r3['turns']} turns, release publication {'BLOCKED by the fence' if blocked else 'executed (fence did not fire!)'}; "
            f"outside runs {r4['turns']}/{r5['turns']} turns; {CORR} applied")
