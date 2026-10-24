"""Books, slices and the metric library (SPEC.md Section 6.1).

Books(entries, as_of=None, adjustments=None): the ledger as the system held it at `as_of` (posted_at <= T), plus hypothetical
correcting entries placed in their orig_period. A Slice names accounts, months, a scope (company, region:R1 or entity:HQ) and whether it
is a balance (cumulative through the last month). `touches(account, period, region, entity)` is the structural test the ripple uses.

Every Metric has an id, label, synonyms, unit (usd, ratio, pct, status), the slices it reads, the metrics it depends on, a compute
function, an optional conclusion (threshold_max, categorical, sign, zero_or_positive) and a family (pl, account, balance, derived, policy).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import config as C

QLABEL = {"2025Q2": "Q2 2025", "2025Q3": "Q3 2025", "2025Q4": "Q4 2025", "2026Q1": "Q1 2026", "2026Q2": "Q2 2026"}
QEND = {"2025Q2": "June 30, 2025", "2025Q3": "September 30, 2025", "2025Q4": "December 31, 2025", "2026Q1": "March 31, 2026", "2026Q2": "June 30, 2026"}
PREV_Q = {"2025Q3": "2025Q2", "2025Q4": "2025Q3", "2026Q1": "2025Q4", "2026Q2": "2026Q1"}
CREDIT_NORMAL = {a for a, (_n, t) in C.ACCOUNTS.items() if t in ("revenue", "liability", "equity")}


@dataclass(frozen=True)
class Slice:
    accounts: tuple[str, ...]
    periods: tuple[str, ...]
    scope: str = "company"            # company | region:R1 | entity:HQ
    balance: bool = False             # balance: every month up to and including the last period
    sign: int = 1                     # -1 reads credit-normal accounts as positive numbers

    def touches(self, account: str, period: str, region: str | None, entity: str | None) -> bool:
        if account not in self.accounts:
            return False
        if self.balance:
            if period > self.periods[-1]:
                return False
        elif period not in self.periods:
            return False
        if self.scope == "company":
            return True
        kind, val = self.scope.split(":", 1)
        return (region == val) if kind == "region" else (entity == val)

    def describe(self) -> str:
        p = f"through {self.periods[-1]}" if self.balance else (self.periods[0] if len(self.periods) == 1 else f"{self.periods[0]}..{self.periods[-1]}")
        return f"{'+'.join(self.accounts)} {p} {self.scope}"


class Books:
    """Aggregates by (account, period, scope key): one pass over the entries, then O(accounts x months) per slice."""

    def __init__(self, entries: list[dict], as_of: str | None = None, adjustments: list[dict] | None = None):
        self.as_of = as_of
        self.agg: dict[tuple, int] = defaultdict(int)
        for e in entries:
            if as_of is not None and e["posted_at"] > as_of:
                continue
            self._add(e["account"], e["period"], e["entity"], e["amount_cents"])
        for a in adjustments or []:
            self._add(a["account"], a.get("orig_period") or a["period"], a["entity"], int(a["amount_cents"]))

    def _add(self, account: str, period: str, entity: str, cents: int) -> None:
        self.agg[(account, period, "company")] += cents
        self.agg[(account, period, f"entity:{entity}")] += cents
        r = C.GYM_REGION.get(entity)
        if r:
            self.agg[(account, period, f"region:{r}")] += cents

    def value(self, s: Slice) -> float:
        months = [p for p in C.PERIODS if p <= s.periods[-1]] if s.balance else s.periods
        tot = 0
        for a in s.accounts:
            for p in months:
                tot += self.agg.get((a, p, s.scope), 0)
        return s.sign * tot / 100

    def trial_balance(self, period_upto: str) -> list[dict]:
        out = []
        for a, (name, typ) in C.ACCOUNTS.items():
            bal = sum(v for (acct, p, sc), v in self.agg.items() if acct == a and sc == "company" and p <= period_upto)
            out.append({"account": a, "name": name, "type": typ, "balance": bal / 100})
        return out


@dataclass
class Metric:
    id: str
    label: str
    unit: str                                   # usd | ratio | pct | status
    family: str                                 # pl | account | balance | derived | policy
    slices: dict[str, Slice] = field(default_factory=dict)
    deps: list[str] = field(default_factory=list)
    compute: Callable[[dict], Any] | None = None
    conclusion: dict | None = None              # {"type": threshold_max|categorical|sign|zero_or_positive, "value": ...}
    synonyms: list[str] = field(default_factory=list)
    quarter: str | None = None
    region: str | None = None
    policy_value: Any = None

    def touches(self, account: str, period: str, region: str | None, entity: str | None) -> bool:
        return any(s.touches(account, period, region, entity) for s in self.slices.values())


def conclusion_state(metric: Metric, value: Any) -> str | None:
    c = metric.conclusion
    if not c or value is None:
        return None
    t = c["type"]
    if t == "threshold_max":
        return "within" if value <= c["value"] + 1e-12 else "above"
    if t == "categorical":
        return str(value)
    if t == "sign":
        return "positive" if value > 0 else ("zero" if value == 0 else "negative")
    if t == "zero_or_positive":
        return "zero" if abs(value) < 0.005 else "positive"
    return None


class MetricLibrary:
    def __init__(self, metrics: list[Metric]):
        self.metrics = {m.id: m for m in metrics}
        self.order = self._topo()
        self.dependents: dict[str, list[str]] = defaultdict(list)
        for m in metrics:
            for d in m.deps:
                self.dependents[d].append(m.id)

    def _topo(self) -> list[str]:
        seen, order = set(), []

        def visit(i: str):
            if i in seen:
                return
            seen.add(i)
            for d in self.metrics[i].deps:
                visit(d)
            order.append(i)

        for i in sorted(self.metrics):
            visit(i)
        return order

    def evaluate(self, books: Books, only: set[str] | None = None) -> dict[str, Any]:
        vals: dict[str, Any] = {}
        for i in self.order:
            if only is not None and i not in only:
                continue
            m = self.metrics[i]
            if m.family == "policy":
                vals[i] = m.policy_value
                continue
            ctx = {k: books.value(s) for k, s in m.slices.items()}
            ctx.update({d: vals[d] if d in vals else None for d in m.deps})
            vals[i] = m.compute(ctx) if m.compute else ctx.get("x")
        return vals

    def downstream(self, ids: set[str]) -> set[str]:
        out, stack = set(ids), list(ids)
        while stack:
            for d in self.dependents.get(stack.pop(), []):
                if d not in out:
                    out.add(d)
                    stack.append(d)
        return out

    def depth(self) -> dict[str, int]:
        dep: dict[str, int] = {}
        for i in self.order:
            dep[i] = 1 + max((dep[d] for d in self.metrics[i].deps), default=-1)
        return dep


# ------------------------------------------------------------------------------------------------------------------ the library
def _ttm(q: str) -> tuple[str, ...]:
    i = C.PERIODS.index(C.QUARTERS[q][-1])
    return tuple(C.PERIODS[max(0, i - 11): i + 1])


def _sl(accts, months, scope="company", balance=False) -> Slice:
    accts = tuple(accts)
    sign = -1 if all(a in CREDIT_NORMAL for a in accts) else 1
    return Slice(accts, tuple(months), scope, balance, sign)


EBITDA_ACCTS = tuple(a for a in C.PL_ACCTS if a not in C.EBITDA_EXCLUDED)
PRETAX_ACCTS = tuple(a for a in C.PL_ACCTS if a != "8100")


def tidewall_library(targets: dict[str, float]) -> MetricLibrary:
    """targets: bonus target per region in dollars (from the comp plan)."""
    ms: list[Metric] = []
    rev, exp = list(C.REVENUE_ACCTS), [a for a in C.PL_ACCTS if a not in C.REVENUE_ACCTS]

    def pl(slice_rev_accts, slice_exp_accts, months, scope="company"):
        sl = {}
        if slice_rev_accts:
            sl["rev"] = _sl(slice_rev_accts, months, scope)
        if slice_exp_accts:
            sl["exp"] = Slice(tuple(slice_exp_accts), tuple(months), scope, False, 1)
        return sl

    for q, months in C.QUARTERS.items():
        ql = QLABEL[q]
        ms.append(Metric(f"revenue@{q}", f"Revenue, {ql}", "usd", "pl", {"x": _sl(rev, months)}, quarter=q, synonyms=["revenue", "total revenue", "net revenue", "sales"]))
        ms.append(Metric(f"membership_revenue@{q}", f"Membership revenue, {ql}", "usd", "pl", {"x": _sl(C.MEMBERSHIP_ACCTS, months)}, quarter=q,
                         synonyms=["membership revenue", "membership", "dues and annual plans"]))
        ebitda_sl = pl([a for a in EBITDA_ACCTS if a in rev], [a for a in EBITDA_ACCTS if a not in rev], months)
        ms.append(Metric(f"ebitda@{q}", f"EBITDA, {ql}", "usd", "pl", ebitda_sl, compute=lambda c: c["rev"] - c["exp"], quarter=q, synonyms=["ebitda", "adjusted ebitda", "operating profit"]))
        pre_sl = pl([a for a in PRETAX_ACCTS if a in rev], [a for a in PRETAX_ACCTS if a not in rev], months)
        ms.append(Metric(f"pretax@{q}", f"Pretax income, {ql}", "usd", "pl", pre_sl, compute=lambda c: c["rev"] - c["exp"], quarter=q, synonyms=["pretax income", "income before tax", "pretax"]))
        for a in rev + exp:
            name = C.ACCOUNTS[a][0]
            ms.append(Metric(f"acct.{a}@{q}", f"{name} ({a}), {ql}", "usd", "account", {"x": _sl([a], months) if a in rev else Slice((a,), tuple(months), "company", False, 1)},
                             quarter=q, synonyms=[name.lower(), name.lower().split(" (")[0]]))
        for r, rname in C.REGIONS.items():
            rsl = pl([a for a in EBITDA_ACCTS if a in rev], [a for a in EBITDA_ACCTS if a not in rev], months, f"region:{r}")
            ms.append(Metric(f"ebitda.{r}@{q}", f"EBITDA, {rname} ({r}), {ql}", "usd", "pl", rsl, compute=lambda c: c["rev"] - c["exp"], quarter=q, region=r,
                             synonyms=[f"{rname.lower()} ebitda", "regional ebitda", f"{r.lower()} ebitda", rname.lower()]))
        qe = QEND[q]
        ms.append(Metric(f"cash@{q}", f"Cash, {qe}", "usd", "balance", {"x": Slice(("1010",), tuple(months), "company", True, 1)}, quarter=q, synonyms=["cash", "unrestricted cash", "cash balance"]))
        ms.append(Metric(f"term_loan@{q}", f"Term loan outstanding, {qe}", "usd", "balance", {"x": _sl(["2500"], months, balance=True)}, quarter=q, synonyms=["term loan", "funded debt", "loan outstanding", "debt"]))
        ms.append(Metric(f"deferred_revenue@{q}", f"Deferred revenue (annual memberships), {qe}", "usd", "balance", {"x": _sl(["2300"], months, balance=True)}, quarter=q,
                         synonyms=["deferred revenue", "unearned revenue"]))
        ms.append(Metric(f"net_debt@{q}", f"Net debt, {qe}", "usd", "derived", deps=[f"term_loan@{q}", f"cash@{q}"], compute=lambda c, q=q: c[f"term_loan@{q}"] - c[f"cash@{q}"], quarter=q,
                         synonyms=["net debt", "funded debt less cash"]))
        if q in PREV_Q:
            pq = PREV_Q[q]
            ms.append(Metric(f"membership_growth@{q}", f"Membership revenue growth, {ql} vs {QLABEL[pq]}", "pct", "derived", deps=[f"membership_revenue@{q}", f"membership_revenue@{pq}"],
                             compute=lambda c, q=q, pq=pq: (c[f"membership_revenue@{q}"] / c[f"membership_revenue@{pq}"] - 1) * 100, conclusion={"type": "sign"}, quarter=q,
                             synonyms=["membership growth", "growth vs prior quarter", "up vs q4", "membership revenue growth"]))
    for q in ("2026Q1", "2026Q2"):
        ttm = _ttm(q)
        qe = QEND[q]
        ms.append(Metric(f"ttm_revenue@{q}", f"Revenue, trailing four quarters to {qe}", "usd", "pl", {"x": _sl(rev, ttm)}, quarter=q,
                         synonyms=["revenue ttm", "trailing revenue", "trailing four quarters revenue", "ttm revenue"]))
        ms.append(Metric(f"ttm_adj_ebitda@{q}", f"Adjusted EBITDA, trailing four quarters to {qe}", "usd", "pl", pl([a for a in EBITDA_ACCTS if a in rev], [a for a in EBITDA_ACCTS if a not in rev], ttm),
                         compute=lambda c: c["rev"] - c["exp"], quarter=q, synonyms=["adjusted ebitda ttm", "adj ebitda ttm", "covenant ebitda", "trailing four quarters adjusted ebitda", "ttm ebitda", "four fiscal quarters"]))
        ms.append(Metric(f"leverage@{q}", f"Net leverage ratio, {qe}", "ratio", "derived", deps=[f"net_debt@{q}", f"ttm_adj_ebitda@{q}"],
                         compute=lambda c, q=q: c[f"net_debt@{q}"] / c[f"ttm_adj_ebitda@{q}"], conclusion={"type": "threshold_max", "value": C.COVENANT["max_leverage"]}, quarter=q,
                         synonyms=["net leverage", "leverage ratio", "net leverage ratio", "debt to ebitda"]))
        ms.append(Metric(f"covenant_status@{q}", f"Covenant status (Section 7.1), {qe}", "status", "derived", deps=[f"leverage@{q}", "policy.max_leverage"],
                         compute=lambda c, q=q: "Compliant" if c[f"leverage@{q}"] <= c["policy.max_leverage"] + 1e-12 else "BREACH", conclusion={"type": "categorical"}, quarter=q,
                         synonyms=["covenant status", "compliance", "in compliance", "within covenant"]))
        ms.append(Metric(f"covenant_headroom@{q}", f"Covenant headroom (EBITDA cushion), {qe}", "usd", "derived", deps=[f"ttm_adj_ebitda@{q}", f"net_debt@{q}", "policy.max_leverage"],
                         compute=lambda c, q=q: c[f"ttm_adj_ebitda@{q}"] - c[f"net_debt@{q}"] / c["policy.max_leverage"], conclusion={"type": "sign"}, quarter=q,
                         synonyms=["headroom", "ebitda cushion", "covenant headroom"]))
    for r, rname in C.REGIONS.items():
        ms.append(Metric(f"policy.bonus_target.{r}", f"Q1 bonus target, {rname} ({r})", "usd", "policy", policy_value=targets[r], region=r, synonyms=["target", "bonus target", rname.lower()]))
        ms.append(Metric(f"bonus.{r}@2026Q1", f"Q1 GM bonus, {rname} ({r})", "usd", "derived", deps=[f"ebitda.{r}@2026Q1", f"policy.bonus_target.{r}", "policy.bonus_rate"],
                         compute=lambda c, r=r: round(max(0.0, c[f"ebitda.{r}@2026Q1"] - c[f"policy.bonus_target.{r}"]) * c["policy.bonus_rate"], 2),
                         conclusion={"type": "zero_or_positive"}, quarter="2026Q1", region=r, synonyms=["bonus", "gm bonus", rname.lower()]))
    ms.append(Metric("tax_installment@2026Q2", "Q2 2026 estimated tax installment (26% of Q1 pretax)", "usd", "derived", deps=["pretax@2026Q1", "policy.tax_rate"],
                     compute=lambda c: round(c["pretax@2026Q1"] * c["policy.tax_rate"], 2), quarter="2026Q2", synonyms=["estimated tax", "q2 estimated payment", "tax installment"]))
    ms.append(Metric("policy.max_leverage", "Maximum net leverage (Section 7.1)", "ratio", "policy", policy_value=C.COVENANT["max_leverage"], synonyms=["maximum leverage", "covenant max", "maximum permitted"]))
    ms.append(Metric("policy.facility", "Term loan facility", "usd", "policy", policy_value=C.COVENANT["facility"], synonyms=["facility"]))
    ms.append(Metric("policy.tax_rate", "Estimated tax rate", "pct", "policy", policy_value=C.TAX_RATE, synonyms=["tax rate", "estimated tax rate"]))
    ms.append(Metric("policy.bonus_rate", "Bonus rate (4% of EBITDA above target)", "pct", "policy", policy_value=C.BONUS_RATE, synonyms=["bonus rate"]))
    return MetricLibrary(ms)
