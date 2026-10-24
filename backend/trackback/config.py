"""Central configuration. Nothing in the app reads the real wall clock except logs."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Demo clock, pinned (Section 2, rule 14).
DEMO_NOW = "2026-07-08T09:00:00-07:00"
TZ_OFFSET = "-07:00"

# Models (Section 2, rule 6)
AGENT_MODEL = os.environ.get("TRACKBACK_AGENT_MODEL", "claude-sonnet-5-5")
JUDGE_MODEL = os.environ.get("TRACKBACK_JUDGE_MODEL", "claude-opus-5-5")
MUSE_MODEL = "muse-spark-1.1"

# LLM gateway mode: record | replay | scripted
LLM_MODE = os.environ.get("TRACKBACK_LLM_MODE", "replay")
MAX_TOOL_TURNS = 25

# Paths
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("TRACKBACK_DB", str(DATA_DIR / "trackback.sqlite")))
PUBLIC_DIR = DATA_DIR / "public"
GENERATED_DIR = DATA_DIR / "generated"
ANSWER_KEY_PATH = DATA_DIR / "answer_key" / "answer_key.yaml"
SNAPSHOT_PATH = Path(os.environ.get("TRACKBACK_SNAPSHOT", str(DATA_DIR / "snapshots" / "canonical.sqlite")))
EVAL_PATH = DATA_DIR / "eval" / "latest.json"
LLM_CACHE_EXPORT = DATA_DIR / "llm_cache" / "cache.jsonl"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Materiality memo defaults (Section 5.2). The live values come from the memo claim.
MATERIALITY_DEFAULTS = {
    "annual": 160_000.0,
    "quarterly_performance": 60_000.0,
    "clearly_trivial": 8_000.0,
    "flux_pct": 0.10,
    "flux_abs": 25_000.0,
}

# Memento profile
PIN_HEADER = "Trackback-Pinned-At"
PROBLEM_TYPE = "https://trackback.local/problems/temporal-pin-violation"
TX_CURRENT = "9999-12-31T00:00:00+00:00"

# Company
COMPANY = "Tidewall Climbing Co."
GYMS = {
    "G1": "Oakland", "G2": "San Jose", "G3": "Sacramento",
    "G4": "Fresno", "G5": "Santa Cruz", "G6": "Berkeley",
}
PEOPLE = {
    "controller": "Dana Ortiz",
    "cfo": "Sam Whitfield",
    "ap": "Priya Nair",
    "vp_sales": "Leo Brandt",
    "hr": "Mei Tanaka",
}

# Packs the core can load by name (the core never imports one directly; see core/domain.py)
PACK_MODULES = {"finance": "trackback.domains.finance"}

# =====================================================================================================================
# v3: Tidewall Climbing Co. (synthetic), 48 gyms, ~$185M revenue. SPEC.md Section 5.
# =====================================================================================================================
WORLD_DIR = DATA_DIR / "world"
FILES_DIR = WORLD_DIR / "files"
HUMAN_DIR = FILES_DIR / "human"
ANSWER_KEY_V3 = WORLD_DIR / "answer_key.json"
WEB_DIST = ROOT / "web"
SEED = 2026
TZ = "-07:00"                      # one fixed offset string for every posted_at, so string comparison orders correctly

REGIONS = {"R1": "Bay Area", "R2": "Southern California", "R3": "Pacific Northwest",
           "R4": "Rockies", "R5": "Central Valley", "R6": "Desert Southwest"}
GYM_CITIES = {
    "R1": ["Oakland", "Berkeley", "San Jose", "Santa Clara", "Fremont", "Walnut Creek", "San Mateo", "Santa Rosa"],
    "R2": ["Pasadena", "Irvine", "Long Beach", "Santa Monica", "San Diego", "Riverside", "Burbank", "Torrance"],
    "R3": ["Portland", "Seattle", "Tacoma", "Bellevue", "Eugene", "Salem", "Spokane", "Bend"],
    "R4": ["Denver", "Boulder", "Fort Collins", "Colorado Springs", "Salt Lake City", "Provo", "Boise", "Golden"],
    "R5": ["Sacramento", "Fresno", "Modesto", "Stockton", "Bakersfield", "Visalia", "Merced", "Chico"],
    "R6": ["Phoenix", "Tempe", "Tucson", "Scottsdale", "Mesa", "Las Vegas", "Henderson", "Albuquerque"],
}
GYM_IDS = {f"G{(ri * 8 + i + 1):02d}": (r, city) for ri, r in enumerate(REGIONS) for i, city in enumerate(GYM_CITIES[r])}
GYM_REGION = {g: r for g, (r, _c) in GYM_IDS.items()}

ACCOUNTS = {
    "1010": ("Cash", "asset"), "1200": ("AR Corporate", "asset"), "1210": ("AR Members", "asset"), "1500": ("Equipment", "asset"),
    "1590": ("Accumulated depreciation", "asset"), "2010": ("Accounts payable", "liability"), "2100": ("Accrued expenses", "liability"),
    "2150": ("Accrued bonus", "liability"), "2300": ("Deferred revenue (annual memberships)", "liability"), "2500": ("Term loan", "liability"),
    "3900": ("Retained earnings and distributions", "equity"),
    "4000": ("Membership revenue (monthly dues)", "revenue"), "4010": ("Membership revenue (annual plans)", "revenue"),
    "4100": ("Day pass and retail", "revenue"), "4200": ("Corporate wellness", "revenue"), "4300": ("Wall build revenue", "revenue"),
    "5300": ("Wall build cost", "expense"), "6000": ("Payroll", "expense"), "6100": ("Rent", "expense"), "6200": ("Utilities", "expense"),
    "6300": ("Route setting", "expense"), "6400": ("Legal", "expense"), "6500": ("Bank and merchant fees", "expense"), "6600": ("Bonus", "expense"),
    "6700": ("Other opex", "expense"), "6800": ("Depreciation", "expense"), "7100": ("FX", "expense"), "7500": ("Interest", "expense"),
    "8100": ("Income tax", "expense"),
}
REVENUE_ACCTS = [a for a, (_n, t) in ACCOUNTS.items() if t == "revenue"]
PL_ACCTS = [a for a, (_n, t) in ACCOUNTS.items() if t in ("revenue", "expense")]
EBITDA_EXCLUDED = ["6800", "7100", "7500", "8100"]   # covenant Adjusted EBITDA excludes depreciation, FX, interest, tax
MEMBERSHIP_ACCTS = ["4000", "4010"]
GYM_REVENUE_ACCTS = ["4000", "4010", "4100"]

COMPANY_V3 = {"name": "Tidewall Climbing Co.", "synthetic": True, "gyms": 48, "regions": 6, "fiscal_year": "calendar",
              "lender": "Redwood Commercial Bank (synthetic)", "auditor": "Halvorsen & Pike LLP (synthetic)"}
PEOPLE_V3 = {
    "dana": {"name": "Dana Ortiz", "role": "controller", "title": "Controller", "approves": ["journal_entry", "misstatement_log", "lesson", "tax_offset", "fact_update"]},
    "sam": {"name": "Sam Whitfield", "role": "cfo", "title": "CFO", "approves": ["lender_document", "escalation"]},
    "priya": {"name": "Priya Nair", "role": "assistant_controller", "title": "Assistant Controller", "ooo": ["2026-06-20", "2026-07-13"], "delegate": "marco"},
    "marco": {"name": "Marco Bell", "role": "ap", "title": "Senior Accountant, AP", "approves": ["vendor_credit", "vendor_hold"]},
    "lena": {"name": "Lena Park", "role": "hr", "title": "HR", "approves": ["comp_offset"]},
}
ESCALATE_TO = {"controller": "cfo", "ap": "controller", "hr": "controller", "assistant_controller": "controller"}

MATERIALITY_V3 = {"overall": 800_000.0, "performance": 250_000.0, "clearly_trivial": 25_000.0, "flux_pct": 0.10, "flux_abs": 250_000.0,
                  "budgeted_pretax": 16_000_000.0, "basis": "5% of budgeted FY2026 pretax income ($16.0M)", "memo_date": "2026-01-15", "author": "Dana Ortiz"}
COVENANT = {"max_leverage": 3.00, "facility": 105_000_000.0, "section": "7.1", "definition": "Net Debt / trailing-four-quarter Adjusted EBITDA",
            "excludes": EBITDA_EXCLUDED, "lender": "Redwood Commercial Bank"}
TAX_RATE = 0.26
BONUS_RATE = 0.04
BONUS_OFFSET_FROM_TARGET = {"R1": 400_000, "R2": 300_000, "R3": -200_000, "R4": 250_000, "R5": -100_000, "R6": 150_000}

KEY_DATES = {
    "draft_tb": "2026-04-09T18:00:00-07:00", "q1_close": "2026-04-10T17:00:00-07:00", "board_deck": "2026-04-24T15:00:00-07:00",
    "covenant_workbook": "2026-05-12T16:00:00-07:00", "certificate_sent": "2026-05-15T10:00:00-07:00", "route_invoice": "2026-05-20T11:00:00-07:00",
    "bonuses_paid": "2026-05-31T09:00:00-07:00", "ap_run": "2026-06-12T09:00:00-07:00", "tax_paid": "2026-06-15T10:00:00-07:00",
    "priya_leaves": "2026-06-20T08:00:00-07:00", "now": "2026-07-08T09:00:00-07:00", "next_bonus_run": "2026-07-15T09:00:00-07:00",
    "billing_capture_1": "2026-04-09T18:00:00-07:00", "billing_capture_2": "2026-07-08T08:00:00-07:00",
}
SNAPSHOTS = {"draft": KEY_DATES["draft_tb"], "close": KEY_DATES["q1_close"], "now": KEY_DATES["now"]}
LOCKED_PERIODS = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
OPEN_PERIOD = "2026-06"
PERIODS = [f"{y}-{m:02d}" for y, m in [(2025, m) for m in range(4, 13)] + [(2026, m) for m in range(1, 7)]]
QUARTERS = {"2025Q2": ["2025-04", "2025-05", "2025-06"], "2025Q3": ["2025-07", "2025-08", "2025-09"], "2025Q4": ["2025-10", "2025-11", "2025-12"],
            "2026Q1": ["2026-01", "2026-02", "2026-03"], "2026Q2": ["2026-04", "2026-05", "2026-06"]}
