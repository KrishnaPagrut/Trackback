"""Build the Tidewall world: generate, write every file, write the answer key, load SQLite (ledger + versioned sources)."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
from pathlib import Path

from .. import config as C
from ..core import db
from . import answer_key as AK
from . import files as F
from . import generator as G
from . import human_files as H

# logical source -> [(file name, captured_at, title)]
SOURCES = {
    "billing_release_lines": ("billing", "Billing system: annual-plan release lines (line-level export)", [
        ("billing_release_lines_2026-04-09.csv", "2026-04-09T18:00:00-07:00"), ("billing_release_lines_2026-07-08.csv", "2026-07-08T08:00:00-07:00")]),
    "gl_import_log": ("gl", "GL import log (billing summary imports into 4010)", [
        ("gl_import_log_2026-04-09.csv", "2026-04-09T18:00:00-07:00"), ("gl_import_log_2026-07-08.csv", "2026-07-08T08:00:00-07:00")]),
    "gl_detail_export": ("gl", "General ledger detail export", [("gl_detail_export.csv", "2026-07-08T08:00:00-07:00")]),
    "bank_statement_2026_06": ("bank", "Bank statement, June 2026 (Redwood Commercial operating account)", [("bank_statement_2026-06.csv", "2026-07-02T08:00:00-07:00")]),
    "cash_book_2026_06": ("gl", "Cash book, June 2026", [("cash_book_2026-06.csv", "2026-07-03T08:00:00-07:00")]),
    "ar_open_invoices_2026_06": ("ar", "AR open invoices, June 2026 (corporate wellness)", [("ar_open_invoices_2026-06.csv", "2026-07-01T08:00:00-07:00")]),
    "customers": ("ar", "Customer master (legal names and aliases)", [("customers.csv", "2026-06-01T08:00:00-07:00")]),
    "ar_payment_history": ("ar", "AR payment history, 12 months", [("ar_payment_history.csv", "2026-07-01T08:00:00-07:00")]),
    "ap_invoices": ("ap", "AP invoice register (AP inbox)", [("ap_invoices_2026-04-09.csv", "2026-04-09T18:00:00-07:00"), ("ap_invoices.csv", "2026-07-08T08:00:00-07:00")]),
    "vendors": ("ap", "Vendor master", [("vendors.csv", "2026-01-05T09:00:00-08:00")]),
    "accruals": ("gl", "Accrual register", [("accruals.csv", "2026-04-10T16:30:00-07:00")]),
    "misstatement_log": ("controller", "Uncorrected misstatement log (Dana Ortiz)", [("misstatement_log.csv", "2026-04-10T17:30:00-07:00")]),
    "materiality_memo": ("controller", "FY2026 materiality memo (Dana Ortiz)", [("materiality_memo.json", "2026-01-15T09:00:00-08:00")]),
    "credit_agreement": ("contracts", "Term Loan Credit Agreement (Redwood Commercial Bank)", [("credit_agreement.json", "2025-04-01T09:00:00-07:00")]),
    "comp_plan": ("hr", "FY2026 GM bonus plan", [("comp_plan.json", "2026-01-05T09:30:00-08:00")]),
    "people": ("hr", "People and approval roles", [("people.json", "2026-01-05T09:00:00-08:00")]),
    "gyms": ("ops", "Gyms and regions", [("gyms.csv", "2026-01-05T09:00:00-08:00")]),
    "covenant_workbook": ("human", "Covenant_Q1-26_PN.xlsx (Priya Nair, May 12)", [("human/Covenant_Q1-26_PN.xlsx", "2026-05-12T16:00:00-07:00")]),
    "board_deck": ("human", "Board_Deck_Q1-26.pptx (Apr 24)", [("human/Board_Deck_Q1-26.pptx", "2026-04-24T15:00:00-07:00")]),
    "compliance_certificate": ("human", "Compliance_Certificate_Q1-26_signed.pdf (May 15, signed by Sam Whitfield)", [("human/Compliance_Certificate_Q1-26_signed.pdf", "2026-05-15T10:00:00-07:00")]),
    "billing_rec_incomplete": ("human", "Billing_to_GL_rec_Mar26_PN_INCOMPLETE.xlsx (Priya's handoff)", [("human/Billing_to_GL_rec_Mar26_PN_INCOMPLETE.xlsx", "2026-06-19T17:00:00-07:00")]),
}
HUMAN_SOURCE = {"Covenant_Q1-26_PN.xlsx": "covenant_workbook", "Board_Deck_Q1-26.pptx": "board_deck", "Compliance_Certificate_Q1-26_signed.pdf": "compliance_certificate"}


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)


def generate() -> dict:
    """Write data/world/files/* and data/world/answer_key.json. Returns the in-memory world for loading."""
    t0 = time.time()
    w = G.build()
    files = F.build_files(w)
    if C.FILES_DIR.exists():
        shutil.rmtree(C.FILES_DIR)
    C.HUMAN_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        if name.startswith("_"):
            continue
        p = C.FILES_DIR / name
        if name.endswith(".csv"):
            _write_csv(p, data)
        else:
            p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8", newline="\n")
    items, _ = H.build_items(w.entries, w.targets)
    H.write_workbook(C.HUMAN_DIR / "Covenant_Q1-26_PN.xlsx", items, w.targets)
    H.write_deck(C.HUMAN_DIR / "Board_Deck_Q1-26.pptx", items)
    H.write_certificate(C.HUMAN_DIR / "Compliance_Certificate_Q1-26_signed.pdf", items)
    H.write_incomplete_rec(C.HUMAN_DIR / "Billing_to_GL_rec_Mar26_PN_INCOMPLETE.xlsx", files["_batch_totals_mar"])
    key = AK.build(w, items, files)
    C.WORLD_DIR.mkdir(parents=True, exist_ok=True)
    C.ANSWER_KEY_V3.write_text(json.dumps(key, indent=1, default=str), encoding="utf-8", newline="\n")
    print(f"generated Tidewall: {len(w.entries)} ledger lines, {len(w.members)} annual-plan members, {len(items)} lineage truths, key {AK.key_hash(key)[:12]} ({time.time() - t0:.1f}s)")
    return {"world": w, "files": files, "items": items, "key": key}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(gen: dict) -> None:
    """Load the ledger and every source version into the current database (config.DB_PATH)."""
    w = gen["world"]
    conn = db.get_conn()
    conn.execute("BEGIN")
    conn.executemany("INSERT INTO gl_entries(entry_id, txn_id, posted_at, eff_date, period, orig_period, entity, account, amount_cents, memo, source_ref, import_id, correction_id, approval_id, world) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,'tidewall')",
                     [(e["entry_id"], e["txn_id"], e["posted_at"], e["eff_date"], e["period"], e["orig_period"], e["entity"], e["account"], e["amount_cents"], e["memo"], e["source_ref"], e["import_id"])
                      for e in w.entries])
    for sid, (system, title, versions) in SOURCES.items():
        db.insert("sources", {"source_id": sid, "uri_r": f"/r/{sid}", "system": system, "kind": "file", "title": title})
        prev = None
        for i, (fname, captured) in enumerate(versions):
            path = C.FILES_DIR / fname
            vid = f"{sid}@v{i + 1}"
            body = {"path": fname, "format": path.suffix.lstrip("."), "title": title, "synthetic": True, "bytes": path.stat().st_size}
            if path.suffix == ".csv":
                with open(path, encoding="utf-8") as fh:
                    body["rows"] = sum(1 for _ in fh) - 1
            db.insert("source_versions", {"version_id": vid, "source_id": sid, "body": json.dumps(body), "content_hash": _sha(path), "document_date": captured[:10],
                                          "tx_from": db.norm_ts(captured), "tx_to": C.TX_CURRENT, "supersedes": prev, "correction_id": None})
            if prev:
                conn.execute("UPDATE source_versions SET tx_to=? WHERE version_id=?", (db.norm_ts(captured), prev))
            prev = vid
    for p in C.LOCKED_PERIODS:
        db.insert("periods", {"period": p, "locked": 1, "locked_at": "2026-04-10T17:00:00-07:00" if p <= "2026-03" else f"{G.next_month(p)}-10T17:00:00-07:00", "locked_by": "Dana Ortiz"})
    db.insert("periods", {"period": C.OPEN_PERIOD, "locked": 0, "locked_at": None, "locked_by": None})
    db.insert("kv", {"key": "tidewall.targets", "value": json.dumps({r: v / 100 for r, v in w.targets.items()})})
    db.insert("kv", {"key": "tidewall.facts", "value": json.dumps(w.facts, default=str)})
    db.insert("kv", {"key": "clock.tidewall", "value": C.KEY_DATES["now"]})
    conn.execute("COMMIT")


def load_entries(world: str = "tidewall") -> list[dict]:
    return [dict(r) for r in db.q("SELECT entry_id, txn_id, posted_at, eff_date, period, orig_period, entity, account, amount_cents, memo, source_ref, import_id, correction_id "
                                  "FROM gl_entries WHERE world=? ORDER BY posted_at, entry_id", (world,))]


def targets() -> dict[str, float]:
    r = db.q1("SELECT value FROM kv WHERE key='tidewall.targets'")
    return json.loads(r["value"]) if r else {}
