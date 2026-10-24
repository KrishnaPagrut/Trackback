"""Append-only ledger inside the same SQLite file. Integer cents, sum-to-zero per tx_id, locked periods."""
from __future__ import annotations

import uuid
from typing import Iterable

from ... import config
from ...core import db

Line = tuple[str, int, str | None]  # (account, amount_cents, gym)


def period_locked(period: str) -> bool:
    row = db.q1("SELECT locked FROM periods WHERE period=?", (period,))
    return bool(row and row["locked"])


def lock_period(period: str, at: str, by: str) -> None:
    if db.q1("SELECT 1 FROM periods WHERE period=?", (period,)):
        return
    db.insert("periods", {"period": period, "locked": 1, "locked_at": at, "locked_by": by})
    db.commit()


def post_entry(lines: Iterable[Line], *, period: str, orig_period: str | None, memo: str, ts: str,
               action_id: str | None = None, approval_id: str | None = None, correction_id: str | None = None,
               tx_id: str | None = None, enforce_lock: bool = True) -> str:
    lines = list(lines)
    if not lines:
        raise ValueError("empty entry")
    total = sum(int(a) for _, a, _ in lines)
    if total != 0:
        raise ValueError(f"entry does not sum to zero: {total} cents")
    if enforce_lock and period_locked(period):
        raise PermissionError(f"period {period} is locked")
    tx_id = tx_id or f"JE-{uuid.uuid4().hex[:8]}"
    conn = db.get_conn()
    for i, (account, amount, gym) in enumerate(lines, start=1):
        db.insert("ledger_entries", {
            "tx_id": tx_id, "line": i, "account": account, "amount_cents": int(amount), "period": period,
            "orig_period": orig_period or period, "memo": memo, "action_id": action_id, "approval_id": approval_id,
            "correction_id": correction_id, "ts": ts, "gym": gym,
        })
    conn.commit()
    return tx_id


def balanced(tx_id: str) -> bool:
    row = db.q1("SELECT SUM(amount_cents) AS s FROM ledger_entries WHERE tx_id=?", (tx_id,))
    return row is not None and row["s"] == 0


def all_balanced() -> list[str]:
    return [r["tx_id"] for r in db.q("SELECT tx_id, SUM(amount_cents) s FROM ledger_entries GROUP BY tx_id HAVING s<>0")]


def balance(account: str, period_to: str | None = None, gym: str | None = None) -> int:
    sql = "SELECT COALESCE(SUM(amount_cents),0) s FROM ledger_entries WHERE account=?"
    params: list = [account]
    if period_to:
        sql += " AND period<=?"; params.append(period_to)
    if gym:
        sql += " AND gym=?"; params.append(gym)
    return db.q1(sql, params)["s"]


def period_total(account: str, period: str, gym: str | None = None) -> int:
    sql = "SELECT COALESCE(SUM(amount_cents),0) s FROM ledger_entries WHERE account=? AND period=?"
    params: list = [account, period]
    if gym:
        sql += " AND gym=?"; params.append(gym)
    return db.q1(sql, params)["s"]
