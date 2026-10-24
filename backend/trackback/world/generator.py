"""Tidewall Climbing Co. (synthetic): a seeded world with ordinary mess left in and six planted exceptions (SPEC.md Section 5).

Everything here is deterministic from config.SEED. The generator writes the ledger, the source files a finance team would have,
the human files (via human_files.py) and the answer key (via refcalc.py, which never calls the engines it grades).

Calibration (Section 5.1) is hit by construction:
- one plug entry in HQ other opex (6700) in October 2025 makes trailing-four-quarter Adjusted EBITDA to Mar 31, 2026, as of the
  Q1 close (Apr 10 17:00), exactly $32,000,000.00; the two close accruals ($600k) posted on Apr 10 make the Apr 9 draft $32,600,000.00;
- a monthly treasury entry (1010 against 3900) puts cash at Mar 31, 2026 at exactly $10,600,000.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from .. import config as C

MONTHS = C.PERIODS                                  # 2025-04 .. 2026-06
WINTER = {"11", "12", "01", "02", "03"}


def cents(x: float) -> int:
    return int(round(x * 100))


def next_month(period: str) -> str:
    y, m = int(period[:4]), int(period[5:])
    return f"{y + (m == 12)}-{(m % 12) + 1:02d}"


def month_end(period: str) -> str:
    y, m = int(period[:4]), int(period[5:])
    days = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return f"{period}-{days:02d}"


def posted(period: str, day: int = 3, hm: str = "06:00") -> str:
    """Monthly entries post on the 3rd of the next month (system time)."""
    return f"{next_month(period)}-{day:02d}T{hm}:00{C.TZ}"


@dataclass
class World:
    entries: list[dict] = field(default_factory=list)
    members: list[dict] = field(default_factory=list)        # annual-plan members (B01..B09)
    import_log: list[dict] = field(default_factory=list)
    gyms: dict = field(default_factory=dict)
    targets: dict = field(default_factory=dict)              # bonus targets per region
    facts: dict = field(default_factory=dict)                 # values the generator itself knows (for the answer key)
    files: dict = field(default_factory=dict)                 # name -> rows or dict
    _seq: int = 0

    def txn(self, *, posted_at: str, eff_date: str, period: str, lines: list[tuple], memo: str, source_ref: str = "",
            import_id: str | None = None, orig_period: str | None = None, txn_id: str | None = None) -> str:
        """lines: (entity, account, amount_cents). Debit positive. Every transaction must balance."""
        assert sum(a for _e, _acct, a in lines) == 0, f"unbalanced txn {memo}: {sum(a for _e, _acct, a in lines)}"
        self._seq += 1
        tid = txn_id or f"T{self._seq:06d}"
        for i, (ent, acct, amt) in enumerate(lines):
            if amt == 0:
                continue
            self.entries.append({"entry_id": f"{tid}-{i + 1:02d}", "txn_id": tid, "posted_at": posted_at, "eff_date": eff_date, "period": period,
                                 "orig_period": orig_period or period, "entity": ent, "account": acct, "amount_cents": int(amt), "memo": memo,
                                 "source_ref": source_ref, "import_id": import_id})
        return tid


# ------------------------------------------------------------------------------------------------------------------------- helpers
def _ttm_adj_ebitda(entries: list[dict], as_of: str, months: list[str]) -> int:
    ms = set(months)
    tot = 0
    for e in entries:
        if e["posted_at"] <= as_of and e["period"] in ms and C.ACCOUNTS[e["account"]][1] in ("revenue", "expense") and e["account"] not in C.EBITDA_EXCLUDED:
            tot -= e["amount_cents"]
    return tot


def _region_ebitda(entries: list[dict], as_of: str, months: list[str], region: str) -> int:
    ms = set(months)
    tot = 0
    for e in entries:
        if e["posted_at"] <= as_of and e["period"] in ms and C.GYM_REGION.get(e["entity"]) == region and \
                C.ACCOUNTS[e["account"]][1] in ("revenue", "expense") and e["account"] not in C.EBITDA_EXCLUDED:
            tot -= e["amount_cents"]
    return tot


def _membership(entries: list[dict], as_of: str, months: list[str]) -> int:
    ms = set(months)
    return -sum(e["amount_cents"] for e in entries if e["posted_at"] <= as_of and e["period"] in ms and e["account"] in C.MEMBERSHIP_ACCTS)


TTM_Q1 = C.PERIODS[:12]          # 2025-04 .. 2026-03


# ------------------------------------------------------------------------------------------------------------------------- build
def build(seed: int = C.SEED) -> World:
    rng = random.Random(seed)
    w = World()
    gyms = {g: {"region": r, "city": city, "factor": round(rng.uniform(0.86, 1.14), 4), "name": f"Tidewall {city}"} for g, (r, city) in C.GYM_IDS.items()}
    w.gyms = gyms
    _members(w, rng)
    _opening(w)
    for p in MONTHS:
        _gym_month(w, rng, p)
        _hq_month(w, rng, p)
        _annual_plan_imports(w, p)
    _promo_p1(w)
    _quarterly_tax_and_bonus_history(w, rng)
    _close_accruals(w)
    _x3_route_invoice(w)
    _utilities_true_up(w)
    _ap_june(w)
    _calibrate_q1_membership_growth(w)
    _plug_ttm(w)
    _bonus_targets_and_payouts(w)
    _q2_tax(w)
    _treasury(w)
    w.facts["n_entries"] = len(w.entries)
    return w


# ------------------------------------------------------------------------------------------------------------------------- members
B07_TARGET = {"R1": 210_000_00, "R2": 180_000_00, "R3": 150_000_00, "R4": 120_000_00, "R5": 90_000_00}   # cents, March release (every month)
PRICES = [9000, 10200, 11500]          # monthly release in cents
TOTAL_MEMBERS = 17_800
P1_MEMBERS = 380


def _members(w: World, rng: random.Random) -> None:
    mid = 0
    region_gyms = defaultdict(list)
    for g, info in w.gyms.items():
        region_gyms[info["region"]].append(g)
    # batch 7: the February migration cohort, R1 to R5; a final prorated member per region hits the totals exactly
    for r, target in B07_TARGET.items():
        tot = 0
        while True:
            price = rng.choice(PRICES)
            if tot + price > target:
                break
            mid += 1
            w.members.append({"member_id": f"M{mid:06d}", "gym_id": rng.choice(region_gyms[r]), "region": r, "batch": "B07", "release_cents": price, "plan_price_cents": price * 12})
            tot += price
        rem = target - tot
        if rem > 0:
            mid += 1
            w.members.append({"member_id": f"M{mid:06d}", "gym_id": region_gyms[r][0], "region": r, "batch": "B07", "release_cents": rem, "plan_price_cents": rem * 12, "prorated": True})
    n07 = len(w.members)
    others = ["B01", "B02", "B03", "B04", "B05", "B06", "B08"]
    all_gyms = list(w.gyms)
    for i in range(TOTAL_MEMBERS - n07):
        mid += 1
        g = rng.choice(all_gyms)
        price = rng.choice(PRICES)
        w.members.append({"member_id": f"M{mid:06d}", "gym_id": g, "region": w.gyms[g]["region"], "batch": others[i % len(others)], "release_cents": price, "plan_price_cents": price * 12})
    # P1: 380 December 2025 promo plans at $1,200, recognized at sale (should be $100 a month over 2026): billing batch 9
    for _ in range(P1_MEMBERS):
        mid += 1
        g = rng.choice(all_gyms)
        w.members.append({"member_id": f"M{mid:06d}", "gym_id": g, "region": w.gyms[g]["region"], "batch": "B09", "release_cents": 10000, "plan_price_cents": 120000, "promo": True})
    w.facts["members_total"] = TOTAL_MEMBERS
    w.facts["b07_members"] = n07
    w.facts["b07_by_region"] = {r: v / 100 for r, v in B07_TARGET.items()}


def batch_gym_release(w: World, batch: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for m in w.members:
        if m["batch"] == batch:
            out[m["gym_id"]] += m["release_cents"]
    return dict(out)


# ------------------------------------------------------------------------------------------------------------------------- ledger
def _opening(w: World) -> None:
    ts = f"2025-04-01T08:00:00{C.TZ}"
    monthly_release = sum(m["release_cents"] for m in w.members if m["batch"] != "B09")
    w.facts["monthly_annual_release"] = monthly_release / 100
    defrev = monthly_release * 6
    w.txn(posted_at=ts, eff_date="2025-04-01", period="2025-04", memo="Term loan drawn (Redwood Commercial Bank)", source_ref="credit_agreement",
          lines=[("HQ", "1010", cents(105_000_000)), ("HQ", "2500", -cents(105_000_000))])
    w.txn(posted_at=ts, eff_date="2025-04-01", period="2025-04", memo="Opening balances (acquisition of the 48-gym portfolio, prior deferred revenue)",
          lines=[("HQ", "1500", cents(118_000_000)), ("HQ", "1590", -cents(9_000_000)), ("HQ", "1010", -cents(96_500_000)), ("HQ", "2300", -defrev),
                 ("HQ", "1200", cents(2_400_000)), ("HQ", "3900", cents(96_500_000) - cents(118_000_000) + cents(9_000_000) + defrev - cents(2_400_000) + 0)])


def _season_dues(p: str) -> float:
    m = p[5:]
    return {"04": 0.965, "05": 0.95, "06": 0.935, "07": 0.93, "08": 0.94, "09": 0.965, "10": 0.985, "11": 1.0, "12": 1.0, "01": 1.03, "02": 1.03, "03": 1.03}[m]


def _season_util(p: str) -> float:
    m = int(p[5:])
    return {12: 16000, 1: 16000, 2: 16000, 11: 15000, 3: 15000, 10: 13500, 4: 13500, 5: 13000, 6: 12500, 7: 12500, 8: 12500, 9: 12500}[m]


def _gym_month(w: World, rng: random.Random, p: str) -> None:
    ts = posted(p)
    eff = month_end(p)
    trend = 1.0 + 0.002 * MONTHS.index(p)
    annual_by_gym: dict[str, int] = defaultdict(int)
    for m in w.members:
        if m["batch"] != "B09":
            annual_by_gym[m["gym_id"]] += m["release_cents"]
    for g, info in w.gyms.items():
        f = info["factor"]
        dues = cents(168_000 * f * _season_dues(p) * trend * rng.uniform(0.99, 1.01))
        dayp = cents(55_000 * f * (0.95 if p[5:] in WINTER else 1.05) * rng.uniform(0.98, 1.02))
        payroll = cents(118_000 * f * rng.uniform(0.995, 1.005))
        rent = cents(68_000 * f)
        util = cents(_season_util(p) * f * rng.uniform(0.97, 1.03))
        route = cents(8_500 * f * rng.uniform(0.95, 1.05))
        other = cents(6_500 * f * rng.uniform(0.9, 1.1))
        fees = int(round((dues + dayp + annual_by_gym[g]) * 0.014))
        w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"{info['name']} monthly revenue and operating costs ({p})", source_ref=f"gym_close:{g}:{p}",
              lines=[(g, "4000", -dues), (g, "4100", -dayp), (g, "1010", dues + dayp),
                     (g, "6000", payroll), (g, "6100", rent), (g, "6200", util), (g, "6300", route), (g, "6700", other), (g, "6500", fees),
                     (g, "1010", -(payroll + rent + util + route + other + fees))])


def _hq_month(w: World, rng: random.Random, p: str) -> None:
    ts = posted(p)
    eff = month_end(p)
    wellness = cents(1_200_000 * rng.uniform(0.985, 1.015))
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Corporate wellness billings ({p})", source_ref=f"ar_billing:{p}",
          lines=[("HQ", "4200", -wellness), ("HQ", "1200", wellness)])
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Corporate wellness collections ({p})", source_ref=f"ar_collections:{p}",
          lines=[("HQ", "1010", wellness), ("HQ", "1200", -wellness)])
    payroll = cents(780_000 * rng.uniform(0.995, 1.005))
    legal = cents(130_000)
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"HQ payroll ({p})", source_ref=f"payroll:{p}", lines=[("HQ", "6000", payroll), ("HQ", "1010", -payroll)])
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Brightline Kessler LLP monthly retainer ({p})", source_ref=f"ap:BRK-retainer-{p}", lines=[("HQ", "6400", legal), ("HQ", "2010", -legal)])
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"AP payment: Brightline Kessler retainer ({p})", source_ref=f"ap_pay:BRK-retainer-{p}", lines=[("HQ", "2010", legal), ("HQ", "1010", -legal)])
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Depreciation ({p})", source_ref="fixed_assets", lines=[("HQ", "6800", cents(750_000)), ("HQ", "1590", -cents(750_000))])
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Term loan interest ({p})", source_ref="credit_agreement", lines=[("HQ", "7500", cents(612_500)), ("HQ", "1010", -cents(612_500))])
    wall = cents(1_650_000 * rng.uniform(0.94, 1.06))
    cost = int(round(wall * 0.70))
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Wall build revenue and cost ({p})", source_ref=f"wallbuild:{p}",
          lines=[("WALL", "4300", -wall), ("WALL", "1010", wall - cost), ("WALL", "5300", cost)])
    fx = cents(rng.uniform(-4_000, 4_000))
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"FX revaluation, EUR holds supplier ({p})", source_ref="fx", lines=[("HQ", "7100", fx), ("HQ", "1010", -fx)])
    # annual-plan renewals collected: cash in, deferred revenue up (equal to the release, so the balance is steady)
    rel = sum(m["release_cents"] for m in w.members if m["batch"] != "B09")
    w.txn(posted_at=ts, eff_date=eff, period=p, memo=f"Annual plan renewals collected ({p})", source_ref=f"billing:renewals:{p}", lines=[("HQ", "1010", rel), ("HQ", "2300", -rel)])


BATCHES = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08"]


def _annual_plan_imports(w: World, p: str) -> None:
    """GL 4010 is fed by batch-level imports from the billing summary export: one transaction per batch per month (credit 4010 per gym,
    debit 2300 per gym). The March import of batch 7 ran twice (timeout, retry); billing released the batch once."""
    for b in BATCHES:
        rel = batch_gym_release(w, b)
        lines = []
        for g in sorted(rel):
            lines += [(g, "2300", rel[g]), (g, "4010", -rel[g])]
        imp = f"IMP-{p.replace('-', '')}-{b}-1"
        ts = posted(p, 3, "05:00")
        w.txn(posted_at=ts, eff_date=month_end(p), period=p, memo=f"Annual plan release import {b} ({p})", source_ref=f"billing_summary:{b}:{p}", import_id=imp, lines=lines)
        w.import_log.append({"import_id": imp, "batch": b, "period": p, "posted_at": ts, "status": "ok", "lines": len(lines), "total": sum(rel.values()) / 100})
        if p == "2026-03" and b == "B07":
            imp2 = f"IMP-{p.replace('-', '')}-{b}-2"
            ts2 = f"2026-04-06T22:14:00{C.TZ}"
            w.txn(posted_at=ts2, eff_date=month_end(p), period=p, memo=f"Annual plan release import {b} ({p})", source_ref=f"billing_summary:{b}:{p}", import_id=imp2, lines=lines)
            w.import_log.append({"import_id": imp2, "batch": b, "period": p, "posted_at": ts2, "status": "ok (retry after timeout)", "lines": len(lines), "total": sum(rel.values()) / 100})
            w.facts["x1_import"] = imp2
            w.facts["x1_lines"] = [{"entity": g, "account": a, "amount_cents": amt} for g, a, amt in lines]


def _promo_p1(w: World) -> None:
    """P1: 380 December 2025 promo plans ($1,200 each, $456k) recognized at sale instead of over 2026."""
    by_gym: dict[str, int] = defaultdict(int)
    for m in w.members:
        if m["batch"] == "B09":
            by_gym[m["gym_id"]] += m["plan_price_cents"]
    lines = []
    for g in sorted(by_gym):
        lines += [(g, "1010", by_gym[g]), (g, "4010", -by_gym[g])]
    w.txn(posted_at=posted("2025-12"), eff_date="2025-12-31", period="2025-12", memo="December promo annual plans (B09), recognized at sale", source_ref="billing:B09:2025-12", lines=lines)
    w.facts["p1_total"] = sum(by_gym.values()) / 100


def _quarterly_tax_and_bonus_history(w: World, rng: random.Random) -> None:
    for d, amt in [("2025-06-15", 1_010_000), ("2025-09-15", 1_020_000), ("2025-12-15", 1_005_000), ("2026-04-15", 1_030_000)]:
        p = d[:7]
        w.txn(posted_at=f"{d}T10:00:00{C.TZ}", eff_date=d, period=p, memo=f"Federal estimated tax payment ({d})", source_ref="tax", lines=[("HQ", "8100", cents(amt)), ("HQ", "1010", -cents(amt))])
    for d in ["2025-08-29", "2025-11-28", "2026-02-27"]:
        amt = cents(rng.uniform(52_000, 61_000))
        w.txn(posted_at=f"{d}T09:00:00{C.TZ}", eff_date=d, period=d[:7], memo=f"Quarterly GM bonus run ({d})", source_ref="comp", lines=[("HQ", "6600", amt), ("HQ", "1010", -amt)])


def _close_accruals(w: World) -> None:
    ts = f"2026-04-10T16:30:00{C.TZ}"
    w.txn(posted_at=ts, eff_date="2026-03-31", period="2026-03", memo="Q1 close accrual: route setting (Cragline Route Setters, March)", source_ref="accrual:ACR-0326-CRAG",
          lines=[("HQ", "6300", cents(410_000)), ("HQ", "2100", -cents(410_000))])
    w.txn(posted_at=ts, eff_date="2026-03-31", period="2026-03", memo="Q1 close accrual: utilities (Bayline Power, March)", source_ref="accrual:ACR-0326-BAYL",
          lines=[("HQ", "6200", cents(190_000)), ("HQ", "2100", -cents(190_000))])


def _x3_route_invoice(w: World) -> None:
    """X3: CRX-5521 $468,000 received May 20 vs the $410,000 March accrual; already handled in May (reverse, book, $58k true-up)."""
    w.txn(posted_at=posted("2026-05"), eff_date="2026-05-20", period="2026-05", memo="Cragline CRX-5521: reverse March accrual, book invoice, $58,000 true-up (change in estimate)",
          source_ref="ap:CRX-5521", lines=[("HQ", "2100", cents(410_000)), ("HQ", "6300", cents(58_000)), ("HQ", "2010", -cents(468_000))])
    w.txn(posted_at=f"2026-06-12T09:30:00{C.TZ}", eff_date="2026-06-12", period="2026-06", memo="AP run Jun 12: Cragline CRX-5521", source_ref="ap_pay:CRX-5521",
          lines=[("HQ", "2010", cents(468_000)), ("HQ", "1010", -cents(468_000))])


def _utilities_true_up(w: World) -> None:
    w.txn(posted_at=posted("2026-04"), eff_date="2026-04-14", period="2026-04", memo="Bayline Power March invoices: reverse accrual, book invoices (true-up $0)", source_ref="ap:BAYL-0326",
          lines=[("HQ", "2100", cents(190_000)), ("HQ", "2010", -cents(190_000))])


def _ap_june(w: World) -> None:
    """X4: Summit Mats 'INV-2231' and '2231', same vendor, amount and PO; both booked and both paid on the Jun 12 AP run."""
    for inv in ("INV-2231", "2231"):
        w.txn(posted_at=f"2026-06-04T11:00:00{C.TZ}", eff_date="2026-06-02", period="2026-06", memo=f"Summit Mats Supply {inv} (PO 4471)", source_ref=f"ap:{inv}",
              lines=[("HQ", "6700", cents(18_750)), ("HQ", "2010", -cents(18_750))])
        w.txn(posted_at=f"2026-06-12T09:30:00{C.TZ}", eff_date="2026-06-12", period="2026-06", memo=f"AP run Jun 12: Summit Mats {inv}", source_ref=f"ap_pay:{inv}",
              lines=[("HQ", "2010", cents(18_750)), ("HQ", "1010", -cents(18_750))])


def _calibrate_q1_membership_growth(w: World) -> None:
    """Keep Q1 membership revenue about 2.8% above Q4 (the deck says so) by a uniform winter-dues lift; deterministic."""
    close = C.KEY_DATES["q1_close"]
    q4, q1 = _membership(w.entries, close, C.QUARTERS["2025Q4"]), _membership(w.entries, close, C.QUARTERS["2026Q1"])
    want = int(round(q4 * 1.028))
    gap = want - q1
    dues_q1 = [e for e in w.entries if e["account"] == "4000" and e["period"] in C.QUARTERS["2026Q1"]]
    tot = -sum(e["amount_cents"] for e in dues_q1)
    if gap == 0:
        return
    # scale each Q1 dues line and its cash line together (same txn), keeping every txn balanced
    by_txn = defaultdict(list)
    for e in w.entries:
        by_txn[e["txn_id"]].append(e)
    acc = 0
    for i, e in enumerate(dues_q1):
        add = int(round(gap * (-e["amount_cents"]) / tot)) if i < len(dues_q1) - 1 else gap - acc
        acc += add
        e["amount_cents"] -= add
        cash = next(x for x in by_txn[e["txn_id"]] if x["account"] == "1010" and x["amount_cents"] > 0)
        cash["amount_cents"] += add


def _plug_ttm(w: World) -> None:
    close = C.KEY_DATES["q1_close"]
    ttm = _ttm_adj_ebitda(w.entries, close, TTM_Q1)
    plug = ttm - cents(32_000_000)
    w.txn(posted_at=posted("2025-10"), eff_date="2025-10-31", period="2025-10", memo="HQ other opex: consulting and systems (October)", source_ref="ap:HQ-OCT-OPEX",
          lines=[("HQ", "6700", plug), ("HQ", "2010", -plug)])
    w.txn(posted_at=posted("2025-10"), eff_date="2025-10-31", period="2025-10", memo="AP payment: HQ consulting and systems (October)", source_ref="ap_pay:HQ-OCT-OPEX",
          lines=[("HQ", "2010", plug), ("HQ", "1010", -plug)])
    w.facts["ttm_plug"] = plug / 100
    assert _ttm_adj_ebitda(w.entries, close, TTM_Q1) == cents(32_000_000)
    assert _ttm_adj_ebitda(w.entries, C.KEY_DATES["draft_tb"], TTM_Q1) == cents(32_600_000)


def _bonus_targets_and_payouts(w: World) -> None:
    close = C.KEY_DATES["q1_close"]
    pay: dict[str, int] = {}
    for r, off in C.BONUS_OFFSET_FROM_TARGET.items():
        e = _region_ebitda(w.entries, close, C.QUARTERS["2026Q1"], r)
        target = int(round((e - off * 100) / 100_000)) * 100_000          # comp plan states targets to the nearest $1,000
        w.targets[r] = target
        pay[r] = int(round(max(0, e - target) * C.BONUS_RATE))
    w.facts["bonus_paid"] = {r: v / 100 for r, v in pay.items()}
    for r, amt in pay.items():
        if amt:
            w.txn(posted_at=f"2026-05-31T09:00:00{C.TZ}", eff_date="2026-05-31", period="2026-05", memo=f"Q1 GM bonus, {C.REGIONS[r]} ({r})", source_ref=f"ACT-bonus-{r}",
                  lines=[("HQ", "6600", amt), ("HQ", "1010", -amt)])


def _q2_tax(w: World) -> None:
    close = C.KEY_DATES["q1_close"]
    pretax = -sum(e["amount_cents"] for e in w.entries if e["posted_at"] <= close and e["period"] in C.QUARTERS["2026Q1"]
                  and C.ACCOUNTS[e["account"]][1] in ("revenue", "expense") and e["account"] != "8100")
    tax = int(round(pretax * C.TAX_RATE))
    w.facts["q1_pretax_at_close"] = pretax / 100
    w.facts["q2_tax_paid"] = tax / 100
    w.txn(posted_at=f"2026-06-15T10:00:00{C.TZ}", eff_date="2026-06-15", period="2026-06", memo="Q2 federal estimated tax payment (26% of Q1 pretax)", source_ref="ACT-tax-q2",
          lines=[("HQ", "8100", tax), ("HQ", "1010", -tax)])


CASH_PATH = {"2025-04": 11.2, "2025-05": 11.0, "2025-06": 10.8, "2025-07": 10.9, "2025-08": 11.1, "2025-09": 10.7, "2025-10": 10.9, "2025-11": 11.0,
             "2025-12": 10.4, "2026-01": 10.5, "2026-02": 10.8, "2026-03": 10.6, "2026-04": 10.9, "2026-05": 11.2, "2026-06": 10.75}


def _treasury(w: World) -> None:
    """Monthly treasury sweep (1010 against 3900) so period-end cash follows CASH_PATH; Mar 31, 2026 is exactly $10,600,000."""
    for p in MONTHS:
        bal = sum(e["amount_cents"] for e in w.entries if e["account"] == "1010" and e["period"] <= p)
        target = cents(CASH_PATH[p] * 1_000_000)
        amt = target - bal
        w.txn(posted_at=posted(p, 3, "07:00"), eff_date=month_end(p), period=p, memo=f"Treasury sweep to target operating cash ({p})", source_ref="treasury",
              lines=[("HQ", "1010", amt), ("HQ", "3900", -amt)])
    w.facts["cash_q1"] = CASH_PATH["2026-03"] * 1_000_000
