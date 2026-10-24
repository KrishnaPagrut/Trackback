"""The airplane-mode check (SPEC.md CP9): replay forced, every non-loopback connection refused in-process, every Stage beat and judge door
exercised for both worlds against a scratch copy of the canonical snapshot. Exits non-zero on any failure."""
from __future__ import annotations

import os
import shutil
import socket
import sys
import time

from . import config as C
from .core import db

SCRATCH = C.DATA_DIR / "build" / "check.sqlite"
_real_connect = socket.socket.connect


def _guard(self, address):
    host = address[0] if isinstance(address, tuple) else str(address)
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ConnectionRefusedError(f"offline check: outside connection to {host} refused")
    return _real_connect(self, address)


def main() -> None:
    os.environ["TRACKBACK_LLM_MODE"] = "replay"
    socket.socket.connect = _guard
    SCRATCH.parent.mkdir(parents=True, exist_ok=True)
    for p in (SCRATCH,):
        if p.exists():
            p.unlink()
    shutil.copy(C.SNAPSHOT_PATH, SCRATCH)
    C.DB_PATH = SCRATCH
    C.SNAPSHOT_PATH = SCRATCH.with_name("check_snapshot.sqlite")
    shutil.copy(SCRATCH, C.SNAPSHOT_PATH)
    db.reset_connection()
    from fastapi.testclient import TestClient
    from .main import app
    c = TestClient(app)
    fails: list[str] = []
    t0 = time.time()

    def ok(cond: bool, what: str) -> None:
        print(("  ok   " if cond else "  FAIL ") + what)
        if not cond:
            fails.append(what)

    print("Tidewall")
    s = c.get("/api/stage").json()
    ok(abs(s["title"]["leverage"] - 2.95) < 1e-9, f"title: leverage {s['title']['leverage']:.2f}x, headroom ${s['title']['headroom']:,.0f}")
    ok(len(s["exceptions"]) == 6 and s["hero"]["kind"] == "duplicate_import", "reconcile: six exceptions, the hero is the $750,000 duplicate import")
    ok(s["evidence"]["deck"]["status"] == "stale", "evidence: the deck's $32.6M is stale; the workbook and certificate are linked")
    rc = s["ripple"]["counts"]
    ok((rc["invalidated"], rc["still_valid"], rc["compensations"]) == (40, 23, 5), f"ripple: {rc['invalidated']} invalidated, {rc['still_valid']} still valid, {rc['compensations']} compensations")
    pings = {p["agent"]: p for p in s["ripple"]["wave"]["pings"]}
    ok(set(pings) == {"close_accountant", "covenant_comp", "reporting_analyst"}, "pings: all three agent lanes")
    ok(any(i["verdict"] == "still_valid" for i in pings["reporting_analyst"]["items"]), "pings: a still_valid answer with a reason")
    ok(any(sk["node_id"] == "RA.cash_forecast.opening" for sk in s["ripple"]["wave"]["skipped"]), "pings: the cash forecast is skipped (no material change)")
    jade = {j["claim_key"]: j["verdict"] for j in s["evaluation"]["jade"]}
    ok(jade.get("q5_matters") == "overrule" and jade.get("q7_fix.approvers.lender_document") == "flag", "Jade: overrules materiality, flags lender routing")
    ok(abs(s["materiality"]["aggregate"]["iron_curtain"] - 1_118_000) < 1 and abs(s["materiality"]["aggregate"]["rollover"] - 662_000) < 1, "materiality: $662,000 rollover / $1,118,000 iron curtain")
    r = c.post("/api/people/dana/act").json()
    rej = next((x for x in r["results"] if x["decision"] == "rejected"), None)
    ok(rej is not None and rej.get("redraft"), "approvals: Dana rejects the March-dated entry; the agent re-drafts")
    sa = c.post(f"/api/approvals/{rej['redraft']}/decision", json={"person": "close_accountant", "decision": "approved"})
    ok(sa.status_code == 409, "approvals: self-approval refused by the schema")
    held = c.get("/api/approvals").json()["holds"]
    ok(sum(1 for h in held if h["state"] == "held" and "bonus run" in h["target"]) == 3, "holds: Jul 15 bonus run held for R1, R2, R4")
    tm = c.get("/api/memento/timemap/billing_release_lines").json()
    at = c.post("/api/replay/attempt", json={"source": "billing_release_lines", "pin": C.KEY_DATES["q1_close"], "version_id": tm["versions"][-1]["version_id"]}).json()
    ok(at.get("refused") and at["status"] == 403, "replay: the Jul 8 export is refused at the Apr 10 pin (403, both timestamps)")
    g = c.get(f"/api/memento/timegate/billing_release_lines?at={C.KEY_DATES['draft_tb']}").json()
    ok(g["version"]["version_id"] == "billing_release_lines@v1", "replay: Apr 9 reads billing export v1")
    ok(c.get("/api/scorecard").status_code == 200, "scorecard: data/eval/latest.json present")
    m = c.get(f"/api/memo/{s['hero']['exception_id']}").json()
    ok("Quantification" in m["markdown"] and "<table>" in m["html"], "memo renders (Markdown and HTML)")
    j = c.post("/api/corrections", json={"free_text": "March legal is $90k higher; the invoice was in the inbox before the close"}).json()
    ok(j["ripple"]["counts"]["invalidated"] > 0 and "final" in j, f"change any number: {j['ripple']['counts']['invalidated']} invalidated, material after Jade: {j['final']['q5_matters']['material']}")
    s1 = c.post("/api/s1").json()
    ok([p["agent"] for p in s1["pings"]] == ["reporting_analyst"], "S1: a self-revision pings only the Reporting Analyst")
    w = c.get("/api/decision/ACT-cert-q1").json()
    ok(len(w["inputs"]) >= 2, "why on that date: the certificate's inputs as of May 15")
    print("Lyft")
    L = c.get("/api/stage?world=lyft").json()
    ok(L["hero"]["kind"] == "figure_mismatch", f"trace: {L['hero']['title']}")
    ok(L["fence"] is not None and L["fence"]["stale"][0]["stated"] == 500, "inside: the fence blocks the release (500 vs 50)")
    lp = sorted(p["agent"] for p in L["ripple"]["wave"]["pings"])
    ok(lp == ["newsroom", "street_analyst"], "ripple: only the newsroom and the sell-side desk are pinged")
    lj = {x["claim_key"]: x["verdict"] for x in L["evaluation"]["jade"]}
    ok(lj.get("q5_matters") == "overrule", "Jade: overrules 'immaterial' (qualitative)")
    gc = c.post("/api/people/general_counsel/act?world=lyft").json()
    ok(any(x["decision"] == "rejected" and x.get("redraft") for x in gc["results"]), "the General Counsel rejects the silent fix; the agent re-drafts")
    ok(c.post("/api/reset").json()["reset"], "reset restores the canonical snapshot")
    print(f"{len(fails)} failures, {time.time() - t0:.1f}s, outside connections refused in-process, LLM mode replay")
    socket.socket.connect = _real_connect
    sys.exit(1 if fails else 0)
