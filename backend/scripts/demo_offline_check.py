"""Offline demo check: runs every demo beat against a scratch copy of the canonical snapshot, with the LLM gateway forced to
replay and every non-loopback network connection refused in-process. Prints one line per check and exits non-zero on any failure.

Checks: E11 pings all three agent lanes, a still_valid with a reason, a reworked reply, a compensation in the approvals inbox,
the 13-week cash forecast skipped, leverage 3.03x; E22 rejection and re-draft; the April 10 replay of billing export v1 and a 403
refusal for the July 8 export; X1 pinging only the Reporting Analyst; the Lyft real-world tab (release blocked by the fence,
outside agents pinged after the correction)."""
from __future__ import annotations

import ipaddress
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# ---- networking off: refuse every connection that is not loopback, for the whole process
_real_connect = socket.socket.connect


def _guarded_connect(self, address):  # noqa: ANN001
    host = address[0] if isinstance(address, tuple) else address
    try:
        ok = isinstance(host, str) and (host in ("localhost", "testserver") or ipaddress.ip_address(host).is_loopback)
    except ValueError:
        ok = False
    if not ok:
        raise OSError(f"network disabled by demo_offline_check: refused connection to {address}")
    return _real_connect(self, address)


socket.socket.connect = _guarded_connect  # type: ignore[assignment]
_real_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, *a, **k: (_real_getaddrinfo(host, *a, **k) if host in ("localhost", "127.0.0.1", "::1", "testserver", None) else (_ for _ in ()).throw(OSError(f"network disabled: DNS for {host}")))  # type: ignore[assignment]

tmp = Path(tempfile.mkdtemp(prefix="tb_offline_"))
snap = ROOT / "data" / "snapshots" / "canonical.sqlite"
work = tmp / "work.sqlite"
shutil.copy(snap, work)
os.environ["TRACKBACK_LLM_MODE"] = "replay"
os.environ["TRACKBACK_DB"] = str(work)
os.environ["TRACKBACK_SNAPSHOT"] = str(tmp / "snap.sqlite")
shutil.copy(snap, tmp / "snap.sqlite")
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from trackback import api, config  # noqa: E402
from trackback.core import db  # noqa: E402
from trackback.main import app  # noqa: E402

api.UNDO_DIR = tmp / "undo"

fails: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


def main() -> int:
    c = TestClient(app)
    st = c.get("/api/state").json()
    check(st.get("mode") == "replay", "LLM gateway in replay mode", st.get("mode"))
    try:
        socket.create_connection(("api.anthropic.com", 443), timeout=2)
        check(False, "networking off", "an outside connection succeeded")
    except OSError as e:
        check(True, "networking off", str(e)[:70])

    # ---------------- X1 from the canonical history (before anything live runs)
    x1 = db.q("SELECT DISTINCT target_agent_id FROM pings WHERE correction_id LIKE 'REV-%'")
    targets = sorted(r["target_agent_id"] for r in x1)
    check(targets == ["reporting_analyst"], "X1 (Close Accountant revises its own estimate) pings only the Reporting Analyst", ", ".join(targets) or "no pings")

    # ---------------- E11 from the canonical snapshot
    r = c.post("/api/live/e11")
    check(r.status_code == 200, "E11 applied from the canonical snapshot", f"HTTP {r.status_code}")
    p = c.get("/pings", params={"correction": "E11"}).json()
    pings = p["pings"]
    lanes = sorted({x["target_agent_id"] for x in pings})
    check(lanes == ["close_accountant", "covenant_comp", "reporting_analyst"], "E11 pings all three agent lanes", ", ".join(lanes))
    items = [(x["target_agent_id"], it) for x in pings for it in ((x.get("response") or {}).get("items") or [])]
    sv = [(a, it) for a, it in items if it.get("verdict") == "still_valid" and (it.get("reason") or "").strip()]
    check(bool(sv), "at least one still_valid with a reason", f"{sv[0][1]['artifact_id']} ({sv[0][0]}): {sv[0][1]['reason'][:80]}" if sv else "none")
    rw = [(a, it) for a, it in items if it.get("verdict") == "reworked"]
    check(bool(rw), "at least one reworked reply", ", ".join(f"{it['artifact_id']} ({a})" for a, it in rw[:4]) if rw else "none")
    ap = c.get("/api/approvals").json()["actions"]
    comps = [a for a in ap if a.get("run_id") == "correction:E11" and a["state"] == "proposed"]
    check(bool(comps), "compensation waiting in the approvals inbox", ", ".join(f"{a['kind']} for {a['approver_role']}" for a in comps[:4]) if comps else "none")
    g = c.get("/api/graph", params={"correction": "E11"}).json()
    cf = [n for n in g["nodes"] if n["id"].startswith("cf_2026_") or n["id"].startswith("cash_opening")]
    pinged_nodes = {it["artifact_id"] for _, it in items}
    cf_found = [n for n in cf if n.get("verdict")]
    skipped = cf_found and all(n["verdict"] == "unaffected" and n["id"] not in pinged_nodes for n in cf_found)
    check(bool(skipped), "13-week cash forecast skipped (no material change, never pinged)", f"{len(cf_found)} cash forecast nodes checked, 0 pinged, reasons: {sorted({n['reason'] for n in cf_found})}" if cf_found else "no cash forecast findings")
    lev = next((n for n in g["nodes"] if n["id"] == "leverage_2026_q1"), None)
    check(bool(lev and lev.get("new_value") and abs(lev["new_value"] - 3.03) < 0.005), "leverage recomputed to 3.03x",
          f"{lev['old_value']:.3f}x -> {lev['new_value']:.3f}x" if lev and lev.get("new_value") else "missing")

    # ---------------- E22: the first draft dated into locked Q1 is rejected, then re-drafted in June
    v1 = next((a for a in ap if a["action_id"] == "JE-je_e11_dedupe_v1"), None)
    rej = [x for x in (v1 or {}).get("approvals", []) if x["decision"] == "rejected"]
    v2 = next((a for a in ap if a["action_id"] == "JE-je_e11_dedupe_v2"), None)
    check(bool(rej), "E22: first correcting entry rejected by the Controller", f"{rej[0]['approver']}: {rej[0]['reason'][:70]}" if rej else "no rejection")
    check(bool(v2 and (v2.get("params") or {}).get("posting_period") == "2026-06"), "E22: re-drafted into June with an out-of-period tag",
          f"posting {(v2.get('params') or {}).get('posting_period')}, orig {(v2.get('params') or {}).get('orig_period')}" if v2 else "no re-draft")

    # ---------------- Jade and the lessons memory (V3)
    ev = c.get("/api/evaluations/E11")
    check(ev.status_code == 200, "Jade reviewed E11", f"HTTP {ev.status_code}")
    evj = ev.json() if ev.status_code == 200 else {}
    over = (evj.get("jade") or {}).get("summary", {}).get("overruled_claims", [])
    check("materiality" in over, "Jade overrules the agent's 'immaterial' call on E11", f"agent: {evj.get('headline', {}).get('agent')} | Jade: {evj.get('headline', {}).get('jade')}")
    ls = c.get("/api/lessons").json()
    byid = {l["lesson_id"]: l for l in ls["lessons"]}
    check(byid.get("L-materiality", {}).get("status") == "proposed", "materiality lesson proposed from Jade's overrule", byid.get("L-materiality", {}).get("status"))
    check("E11" in byid.get("L-posting", {}).get("cases", []) and byid.get("L-locked-means-estimate", {}).get("status") == "proposed", "the Controller's rejection adds evidence to the posting lesson and proposes the broad one",
          f"posting cases {byid.get('L-posting', {}).get('cases')}")
    check({byid.get(x, {}).get("status") for x in ("L-classification", "L-routing")} == {"active"}, "two lessons learned in history are active (classification, routing)", ls["playbook"]["version"])
    ap2 = c.post("/api/lessons/approve-pending", json={"approver": config.PEOPLE["controller"]}).json()
    st = {l["lesson_id"]: l["status"] for l in ap2["lessons"]}
    check(st.get("L-materiality") == "active" and st.get("L-posting") == "active", "the gate passes the narrow lessons and the Controller activates them", str(st))
    check(st.get("L-locked-means-estimate") == "rejected_by_gate", "the regression gate rejects the broad lesson (E10/E02 would flip)", str(st.get("L-locked-means-estimate")))
    check(ap2["playbook"]["version"] == "v2", "playbook is v2 with all four checks active", ap2["playbook"]["version"])
    bad = c.post("/api/lessons/L-materiality/approve", json={"approver": "agent:close_accountant"})
    check(bad.status_code == 403, "an agent cannot approve a lesson (403)", f"HTTP {bad.status_code}")

    # ---------------- Memento: April 10 replay and the future refusal
    m = c.get("/api/memento/billing_export_2026_03", params={"at": "2026-04-10T17:00:00-07:00"}).json()
    ver = (m.get("memento") or {}).get("version_id")
    check(ver == "billing_export_2026_03@v1", "April 10 replay serves billing export v1", ver or str(m)[:80])
    tm = c.get("/api/timemap/billing_export_2026_03").json()
    later = [v for v in tm["versions"] if v["tx_from"] > "2026-07-01"]
    ch = c.post("/api/cheat", json={"doc_id": "billing_export_2026_03", "pin": "2026-04-10T17:00:00-07:00", "version_id": later[-1]["version_id"] if later else None}).json()
    check(bool(ch.get("refused")) and ch.get("status") == 403, "the July 8 export is refused at the April 10 pin", f"HTTP {ch.get('status')}, published {ch.get('memento_datetime')}")

    # ---------------- the real-world tab: Lyft
    lyft = c.get("/api/realworld/lyft").json()
    fence = lyft["inside"]["fence"]
    mm = fence.get("mismatch") or {}
    check(bool(fence.get("blocked")) and mm.get("stated") == 500 and mm.get("cited_value") == 50, "Real world (Lyft): the release is blocked before publishing",
          f"states {mm.get('stated'):g}, cites {mm.get('cited_value'):g}" if mm else "no block")
    out_p = sorted({x["target_agent_id"] for x in lyft["outside"]["pings"]})
    check(out_p == ["newsroom", "street_analyst"], "Real world (Lyft): the correction pings the two outside agents", ", ".join(out_p))
    check(len(lyft["outside"]["compensations"]) >= 2, "Real world (Lyft): fixes proposed for the filled order and the published story",
          ", ".join(x["kind"] for x in lyft["outside"]["compensations"]))

    print(f"== {'PASS' if not fails else 'FAIL'} ({len(fails)} failed)")
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        db.reset_connection()
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(code)
