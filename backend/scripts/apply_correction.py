"""CLI: apply any correction id and print the impact set.
Usage: backend/.venv/bin/python backend/scripts/apply_correction.py E11 [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import corrections, scenarios  # noqa: E402
from trackback.engine.propagate import REASON_LABEL  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in scenarios.CORRECTIONS:
        print("usage: apply_correction.py <id> [--dry-run]; ids:", ", ".join(scenarios.CORRECTIONS)); sys.exit(2)
    cid = sys.argv[1]
    dry = "--dry-run" in sys.argv
    r = corrections.apply_correction(cid, dry_run=dry)
    c = r["counts"]
    print(f"{cid} ({r['kind']}, knowable {r['knowable_at'][:10]}) {'DRY RUN ' if dry else ''}-> {r['materiality_verdict']}; naive {r['naive_count']}; "
          f"invalidated {c['invalidated']}, cleared {c['unaffected']}, needs review {c['needs_review']}, unprovable {c['unprovable']}")
    for f in r["findings"]:
        mark = {"invalidated": "X", "unaffected": "ok", "needs_review": "!", "unprovable": "?"}[f["verdict"]]
        delta = f"  {f['old_value']:,.2f} -> {f['new_value']:,.2f}" if f.get("old_value") is not None and f.get("new_value") is not None and f["old_value"] != f["new_value"] else ""
        comp = f"  [{f['compensation']['kind']}]" if f.get("compensation") else ""
        print(f"  {mark:>2} hop{f['hop']} {f['artifact_id']:<38} {REASON_LABEL.get(f['reason'], f['reason'])}{delta}{comp}")


if __name__ == "__main__":
    main()
