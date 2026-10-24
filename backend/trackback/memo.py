"""The error memo (SPEC.md Section 10): one per material exception, in the format a controller hands an auditor. Every line cites its evidence
([ev:...] markers the UI turns into links). Numbers come from the engines; the LLM, when present, writes the summary and background prose."""
from __future__ import annotations

import html
import json
import re

from . import config as C
from .agent import llm
from .core import db

CONTROLS = {
    "duplicate_import": ["Block duplicate import ids per period and batch in the GL import job (reject a second import of the same batch and period).",
                         "Reconcile billing to GL monthly, and always after a migration; no batch left untied at the close."],
    "unaccrued_invoice": ["Route AP inbox items to a delegate automatically when the assignee is out of office.", "Before the close, search the AP inbox for unprocessed invoices with service in the closing period."],
}


def _m(v) -> str:
    return f"${v:,.0f}" if isinstance(v, (int, float)) else str(v)


def build(run_id: str, exception_id: str, ts: str) -> str:
    ev = json.loads(db.q1("SELECT claims_json FROM evaluations WHERE run_id=? AND exception_id=? AND playbook_version LIKE '%+jade'", (run_id, exception_id))["claims_json"])
    v1 = json.loads(db.q1("SELECT claims_json FROM evaluations WHERE run_id=? AND exception_id=? AND playbook_version NOT LIKE '%+jade'", (run_id, exception_id))["claims_json"])
    exc = json.loads(db.q1("SELECT detail_json FROM exceptions WHERE run_id=? AND exception_id=?", (run_id, exception_id))["detail_json"])
    rp = db.q1("SELECT result_json FROM ripples WHERE run_id=? AND exception_id=?", (run_id, exception_id))
    rp = json.loads(rp["result_json"]) if rp else {"items": {}, "actions": {}, "metrics": {}, "counts": {}}
    mat = json.loads(db.q1("SELECT value FROM kv WHERE key=?", (f"materiality.{run_id}",))["value"])
    jade = [dict(r) for r in db.q("SELECT * FROM jade_reviews WHERE eval_id=? ORDER BY rowid", (f"EV-{run_id}-{exception_id}",))]
    acts = [dict(r) for r in db.q("SELECT * FROM actions WHERE exception_id=? AND world='tidewall' ORDER BY created_at, action_id", (exception_id,))]
    q3, q4, q5, q7 = ev["q3_classification"], ev["q4_size"], ev["q5_matters"], ev["q7_fix"]
    lev = rp["metrics"].get("leverage@2026Q1")
    facts = {"title": exc["title"], "amount": _m(exc["amount"]), "classification": q3["value"].replace("_", " "), "material": "material" if q5.get("material") else "not material",
             "leverage": f"{lev['old']:.2f}x to {lev['new']:.2f}x" if lev else "unchanged", "root_cause": ev["q1_what"]["root_cause"],
             "invalidated": rp.get("counts", {}).get("invalidated", 0), "compensations": rp.get("counts", {}).get("compensations", 0)}
    summ = llm.write(f"memo:{exception_id}:summary", "Write a three-sentence summary for an error memo to the auditor: what happened, whether it matters and why, and what is being done.", facts,
                     "{title} ({amount}). It is an {classification}, {material} after aggregation and qualitative review; net leverage moves {leverage}. "
                     "{invalidated} figures and actions rested on it; correcting entries and {compensations} compensations are routed for approval.", ts, max_tokens=300)
    L: list[str] = []
    L.append(f"# Error memo: {exc['title']}")
    L.append(f"Tidewall Climbing Co. (synthetic). Prepared by the Close Accountant agent, reviewed by Jade. As of {ts[:10]}. Exception {exception_id}. [ev:recon:{exc['recon']}:{exception_id}]")
    L.append("\n## 1. Summary\n" + summ["text"])
    L.append("\n## 2. Background and root cause\n" + ev["q1_what"]["root_cause"] + f" [ev:recon:{exc['recon']}:{exception_id}]")
    for e in exc.get("evidence", [])[:4]:
        if isinstance(e, dict):
            L.append("- " + ", ".join(f"{k}: {v}" for k, v in e.items() if k != "what" and v is not None)[:220] + f" [ev:{e.get('import_id') or e.get('invoice_no') or e.get('source') or 'evidence'}]")
    L.append(f"\nSystem of record: {ev['q2_trust']['trusted']} over {ev['q2_trust']['over']}. {ev['q2_trust']['why']} [ev:source:{ev['q2_trust'].get('system_of_record')}]")
    L.append("\n## 3. Classification\n" + f"**{q3['value'].replace('_', ' ').capitalize()}.** {q3.get('rule', '')} Replay: {q3.get('fact', '')}. Knowable at {q3.get('knowable_at', '')[:16].replace('T', ' ')} UTC; "
             f"the original figures were made at the Q1 close ({C.KEY_DATES['q1_close'][:16].replace('T', ' ')} PT). [ev:{q3.get('evidence')}]")
    L.append("\n## 4. Quantification\n| Method | Amount |\n|---|---|\n" + f"| Rollover (current-year P&L) | {_m(q4['rollover'])} |\n| Iron curtain (balance sheet) | {_m(q4['iron_curtain'])} |")
    if q4.get("by_region"):
        L.append("\n| Region | Amount |\n|---|---|\n" + "\n".join(f"| {C.REGIONS.get(r, r)} ({r}) | {_m(v)} |" for r, v in q4["by_region"].items()))
    L.append(f"[ev:correction:{exception_id}]")
    agg = mat["aggregate"]
    L.append("\n## 5. Materiality\n" + f"Thresholds (Dana Ortiz's memo, Jan 15): overall {_m(mat['thresholds']['overall'])}, performance {_m(mat['thresholds']['performance'])}, clearly trivial {_m(mat['thresholds']['clearly_trivial'])}. [ev:materiality_memo]")
    L.append("\n| Item | Rollover | Iron curtain | Source |\n|---|---|---|---|\n" + "\n".join(f"| {r['id']} | {_m(r['rollover'])} | {_m(r['iron_curtain'])} | {r['source']}{' (clearly trivial, not accumulated)' if r.get('trivial') else ''} |" for r in mat["rows"])
             + f"\n| **Aggregate** | **{_m(agg['rollover'])}** ({'passes' if agg['rollover_passes'] else 'fails'}) | **{_m(agg['iron_curtain'])}** ({'fails' if agg['iron_curtain_fails'] else 'passes'}) | X1, X2 and the logged P1 |")
    for q in q5.get("qualitative", []):
        L.append(f"- Qualitative (SAB 99): {q['label']}" + (f": {q['detail']}" if q.get("detail") else "") + f" [ev:ripple:{exception_id}]")
    L.append(f"\n**Conclusion:** {'Material' if q5.get('material') else 'Not material'}. SAB 108 requires both methods: the rollover method alone would have passed it. "
             f"The agent's first draft concluded immaterial under a 5% rule ({v1['q5_matters']['why']}); Jade overruled it. [ev:jade:{exception_id}]")
    inv = [i for i, v in rp["items"].items() if v["verdict"] == "invalidated"]
    L.append(f"\n## 6. Affected documents and executed actions\n{len(inv)} figures in documents changed; {sum(1 for v in rp['items'].values() if v['verdict'] == 'still_valid')} were checked and still hold. [ev:ripple:{exception_id}]")
    for f in sorted({v["file"] for v in rp["items"].values() if v["verdict"] == "invalidated"}):
        n = sum(1 for v in rp["items"].values() if v["verdict"] == "invalidated" and v["file"] == f)
        L.append(f"- {f}: {n} figures")
    for a, v in rp["actions"].items():
        if v["verdict"] == "invalidated":
            c = v.get("compensation") or {}
            L.append(f"- {v['label']}: {c.get('title', '')}" + (f", {_m(c['amount'])} {c.get('direction', '')}" if c.get("amount") else "") + f" [ev:{a}]")
    L.append("\n## 7. Correcting entries and compensations\n| Item | Approver | Status |\n|---|---|---|")
    for a in acts:
        if a["kind"] in ("certificate_sent", "bonus_paid", "tax_paid"):
            continue
        L.append(f"| {a['summary'] or a['action_id']} | {C.PEOPLE_V3.get(a['assignee'] or '', {}).get('name', a['assignee'])} | {a['state']} |")
    if q7.get("entries"):
        L.append("\nEntries (" + f"posting {q7.get('posting_period')}, orig_period {q7.get('orig_period')}):")
        for l in q7["entries"][:12]:
            L.append(f"- {l['entity']} {l['account']} {C.ACCOUNTS[l['account']][0]}: {'Dr' if l['amount_cents'] > 0 else 'Cr'} {_m(abs(l['amount_cents']) / 100)}")
        if len(q7["entries"]) > 12:
            L.append(f"- ... {len(q7['entries']) - 12} more lines (gym by gym)")
    L.append("\n## 8. Controls going forward")
    for c in CONTROLS.get(exc["kind"], ["Add a reconciliation check for this pattern."]):
        L.append(f"- {c}")
    L.append("\n## 9. Jade's review notes")
    for j in jade:
        if j["verdict"] != "approve" or j["claim_key"].startswith("q5") or j["claim_key"].startswith("q3"):
            L.append(f"- {j['claim_key']}: **{j['verdict']}**. {j['why']}")
    md = "\n".join(L)
    n = (db.q1("SELECT MAX(version) v FROM memos WHERE memo_id=?", (f"MEMO-{exception_id}",))["v"] or 0) + 1
    db.insert("memos", {"memo_id": f"MEMO-{exception_id}", "version": n, "world": "tidewall", "exception_id": exception_id, "markdown": md, "created_at": db.norm_ts(ts)})
    return md


def to_html(md: str) -> str:
    """A small Markdown renderer (headings, tables, bullets, bold, evidence markers) so the memo needs no library offline."""
    out, table = [], []

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"\[ev:([^\]]+)\]", r'<a class="ev" data-ev="\1">[\1]</a>', s)

    def flush():
        if table:
            rows = [r for r in table if not re.match(r"^\|[-| ]+\|$", r)]
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:]) + "</tbody></table>")
            table.clear()

    for line in md.split("\n"):
        if line.startswith("|"):
            table.append(line)
            continue
        flush()
        if line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("- "):
            out.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    flush()
    return "\n".join(out)
