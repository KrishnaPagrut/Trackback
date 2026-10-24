"""Independent reference arithmetic for the answer key (SPEC.md Section 5.7).

This module never imports the engines it grades (engine/books, engine/graph, engine/materiality). It recomputes the handful of
quantities the answer key needs with plain loops over the raw entries, and applies the verdict rules stated in the spec:
value_changed, conclusion_flipped, stale_and_value_changed, input_changed, display_unchanged, value_unchanged,
conclusion_unchanged, not_consumed, different_line_item, policy, inputs_unchanged, unlinked.
"""
from __future__ import annotations

from collections import defaultdict

from .. import config as C

PL = {a for a, (_n, t) in C.ACCOUNTS.items() if t in ("revenue", "expense")}


class Ref:
    """Sums over (account, period, entity) as of a system time, optionally with correcting lines placed in their orig_period."""

    def __init__(self, entries: list[dict], as_of: str, adjustments: list[dict] | None = None):
        self.s: dict[tuple, int] = defaultdict(int)
        for e in entries:
            if e["posted_at"] <= as_of:
                self.s[(e["account"], e["period"], e["entity"])] += e["amount_cents"]
        for a in adjustments or []:
            self.s[(a["account"], a.get("orig_period") or a["period"], a["entity"])] += a["amount_cents"]

    def total(self, accounts, months, region: str | None = None, entity: str | None = None, upto: str | None = None) -> int:
        accts, ms = set(accounts), set(months or [])
        t = 0
        for (a, p, ent), v in self.s.items():
            if a not in accts:
                continue
            if upto is not None:
                if p > upto:
                    continue
            elif p not in ms:
                continue
            if region and C.GYM_REGION.get(ent) != region:
                continue
            if entity and ent != entity:
                continue
            t += v
        return t

    # ---- quantities (dollars)
    def revenue(self, q):
        return -self.total(C.REVENUE_ACCTS, C.QUARTERS[q]) / 100

    def acct(self, a, q):
        v = self.total([a], C.QUARTERS[q]) / 100
        return -v if C.ACCOUNTS[a][1] == "revenue" else v

    def membership(self, q):
        return -self.total(C.MEMBERSHIP_ACCTS, C.QUARTERS[q]) / 100

    def ebitda(self, q, region=None):
        accts = [a for a in PL if a not in C.EBITDA_EXCLUDED]
        return -self.total(accts, C.QUARTERS[q], region=region) / 100

    def pretax(self, q):
        return -self.total([a for a in PL if a != "8100"], C.QUARTERS[q]) / 100

    def ttm_months(self, q):
        i = C.PERIODS.index(C.QUARTERS[q][-1])
        return C.PERIODS[max(0, i - 11): i + 1]

    def ttm_revenue(self, q):
        return -self.total(C.REVENUE_ACCTS, self.ttm_months(q)) / 100

    def ttm_ebitda(self, q):
        return -self.total([a for a in PL if a not in C.EBITDA_EXCLUDED], self.ttm_months(q)) / 100

    def cash(self, q):
        return self.total(["1010"], None, upto=C.QUARTERS[q][-1]) / 100

    def term_loan(self, q):
        return -self.total(["2500"], None, upto=C.QUARTERS[q][-1]) / 100

    def net_debt(self, q):
        return self.term_loan(q) - self.cash(q)

    def leverage(self, q):
        return self.net_debt(q) / self.ttm_ebitda(q)

    def status(self, q):
        return "Compliant" if self.leverage(q) <= C.COVENANT["max_leverage"] + 1e-12 else "BREACH"

    def headroom(self, q):
        return self.ttm_ebitda(q) - self.net_debt(q) / C.COVENANT["max_leverage"]

    def growth(self, q, prev):
        return (self.membership(q) / self.membership(prev) - 1) * 100

    def bonus(self, r, targets):
        return round(max(0.0, self.ebitda("2026Q1", r) - targets[r] / 100) * C.BONUS_RATE, 2)

    def tax_installment(self):
        return round(self.pretax("2026Q1") * C.TAX_RATE, 2)


def metric_value(ref: Ref, metric: str, targets: dict) -> float | str:
    """The handful of metric ids the human files and actions rest on."""
    if metric.startswith("sum:"):
        return sum(metric_value(ref, m, targets) for m in metric[4:].split("+"))
    if metric.startswith("policy."):
        k = metric[7:]
        if k == "max_leverage":
            return C.COVENANT["max_leverage"]
        if k == "tax_rate":
            return C.TAX_RATE
        if k.startswith("bonus_target."):
            return targets[k.split(".")[1]] / 100
        raise KeyError(metric)
    name, q = metric.split("@")
    if name.startswith("acct."):
        return ref.acct(name[5:], q)
    if name.startswith("ebitda."):
        return ref.ebitda(q, name.split(".")[1])
    if name.startswith("bonus."):
        return ref.bonus(name.split(".")[1], targets)
    return {
        "revenue": lambda: ref.revenue(q), "membership_revenue": lambda: ref.membership(q), "ebitda": lambda: ref.ebitda(q),
        "pretax": lambda: ref.pretax(q), "ttm_revenue": lambda: ref.ttm_revenue(q), "ttm_adj_ebitda": lambda: ref.ttm_ebitda(q),
        "cash": lambda: ref.cash(q), "term_loan": lambda: ref.term_loan(q), "net_debt": lambda: ref.net_debt(q),
        "leverage": lambda: ref.leverage(q), "covenant_status": lambda: ref.status(q), "covenant_headroom": lambda: ref.headroom(q),
        "membership_growth": lambda: ref.growth(q, {"2026Q1": "2025Q4", "2026Q2": "2026Q1", "2025Q4": "2025Q3", "2025Q3": "2025Q2"}[q]),
        "tax_installment": lambda: ref.tax_installment(),
    }[name]()


# conclusions each metric family states (the same rules the engine is graded against)
def conclusion_of(metric: str, value) -> str | None:
    name = metric.split("@")[0]
    if name == "leverage":
        return "within" if value <= C.COVENANT["max_leverage"] + 1e-12 else "above"
    if name == "covenant_status":
        return str(value)
    if name == "covenant_headroom" or name.startswith("membership_growth"):
        return "positive" if value > 0 else ("zero" if value == 0 else "negative")
    if name.startswith("bonus."):
        return "zero" if abs(value) < 0.005 else "positive"
    return None


def region_of(metric: str) -> str | None:
    name = metric.split("@")[0]
    if name.startswith("ebitda.") or name.startswith("bonus."):
        return name.split(".")[1]
    return None


DIFFERENT_LINES = ("cash@", "term_loan@", "net_debt@")


def item_verdict(item: dict, before: dict, after: dict, regions_touched: set[str], invalid_items: set[str]) -> tuple[str, str]:
    """(verdict, reason) for one traced item. before/after: metric -> value at the item's snapshot."""
    kind = item["link"]
    if kind == "policy":
        return "still_valid", "policy"
    if kind == "derived":
        return ("invalidated", "input_changed") if any(r in invalid_items for r in item["refs"]) else ("still_valid", "inputs_unchanged")
    m = item["metric"]
    b, a = before[m], after[m]
    if isinstance(b, str) or isinstance(a, str):
        changed = b != a
        if not changed:
            return "still_valid", "conclusion_unchanged"
        return "invalidated", "conclusion_flipped"
    changed = abs(a - b) > 0.005
    if not changed:
        reg = region_of(m)
        if reg and reg not in regions_touched:
            return "still_valid", "not_consumed"
        if m.startswith(DIFFERENT_LINES):
            return "still_valid", "different_line_item"
        return "still_valid", "conclusion_unchanged" if conclusion_of(m, b) is not None else "value_unchanged"
    if item.get("stale"):
        return "invalidated", "stale_and_value_changed"
    cb, ca = conclusion_of(m, b), conclusion_of(m, a)
    if cb is not None and cb != ca:
        return "invalidated", "conclusion_flipped"
    tol = item.get("tolerance", 0.005)
    if not item.get("exact") and round(a / (2 * tol)) == round(b / (2 * tol)):
        return "still_valid", "display_unchanged"
    return "invalidated", "value_changed"
