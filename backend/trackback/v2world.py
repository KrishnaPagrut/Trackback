"""Tidewall Climbing Co. numeric design (all synthetic). Shared by the generator, the scripted agents and tests."""
from __future__ import annotations

GYMS = ["G1", "G2", "G3", "G4", "G5", "G6"]
GYM_NAMES = {"G1": "Oakland", "G2": "San Jose", "G3": "Sacramento", "G4": "Fresno", "G5": "Santa Cruz", "G6": "Berkeley"}

# Q1 2026 membership revenue per gym as reported (includes the E11 duplicate annual release in March)
E11_DUP = {"G1": 26_000, "G2": 0, "G3": 22_000, "G4": 32_000, "G5": 18_000, "G6": 20_000}  # sums to 118,000
MEMBERSHIP_Q1_REPORTED = {"G1": 1_530_000, "G2": 1_150_000, "G3": 1_160_000, "G4": 1_340_000, "G5": 1_020_000, "G6": 1_218_000}  # 7,418,000
# monthly split: dues (monthly ACH) vs annual-prepaid release, true values. March annual release is what the migration duplicated.
ANNUAL_RELEASE_TRUE = {"G1": 26_000, "G2": 0, "G3": 22_000, "G4": 32_000, "G5": 18_000, "G6": 20_000}
# monthly dues per gym (Jan, Feb, Mar) chosen so that dues*3 + annual_release*3 + dup = reported
def membership_split(g: str) -> dict:
    rep = MEMBERSHIP_Q1_REPORTED[g]
    true_total = rep - E11_DUP[g]
    ann = ANNUAL_RELEASE_TRUE[g]
    dues_total = true_total - 3 * ann
    base = dues_total // 3
    jan, feb = base, base
    mar = dues_total - 2 * base
    return {"dues": {"2026-01": jan, "2026-02": feb, "2026-03": mar}, "annual": ann}

DAYPASS_Q1 = {"G1": 490_000, "G2": 430_000, "G3": 400_000, "G4": 460_000, "G5": 350_000, "G6": 414_000}  # 2,544,000
GYM_OPEX_Q1 = {"G1": 1_590_000, "G2": 1_280_000, "G3": 1_280_000, "G4": 1_410_000, "G5": 1_150_000, "G6": 1_352_000}
GYM_EBITDA_TARGET_Q1 = {"G1": 380_000, "G2": 280_000, "G3": 310_000, "G4": 340_000, "G5": 240_000, "G6": 310_000}
GM_BONUS_RATE = 0.04
COMMISSION_RATE = 0.08

WELLNESS_NORTHGATE_MONTHLY = 12_000          # 200 seats x $60
WELLNESS_NORTHGATE_BLENDED = 14_250          # after E06, from June 2026
WELLNESS_OTHER_MONTHLY = 20_000              # other wellness customers
WALLBUILD_PRICE_V1, WALLBUILD_COST_V1 = 900_000, 600_000
WALLBUILD_PRICE_V2, WALLBUILD_COST_V2 = 1_050_000, 660_000
WALLBUILD_INCURRED_Q1 = 240_000

ROUTE_SETTING_MONTHLY = {"2026-01": 40_000, "2026-02": 38_000, "2026-03": 37_300}   # 115,300 reported; E02 adds 22,500 to March
ROUTE_SETTING_Q4_2025 = 140_600                                                    # (140,600-115,300)/140,600 = 18.0%
LEGAL_MONTHLY = {"2026-01": 10_000, "2026-02": 11_000, "2026-03": 10_000}           # 31,000; E10 adds 14,000 to March
CORP_PAYROLL_Q1 = 440_000
CORP_GA_Q1 = 129_700
UTILITIES_Q1 = {  # per gym per month; G3 March is the accrual (E01: invoice 51,900 arrives Apr 12)
    "G1": {"2026-01": 31_000, "2026-02": 29_500, "2026-03": 27_000},
    "G2": {"2026-01": 27_000, "2026-02": 26_000, "2026-03": 24_000},
    "G3": {"2026-01": 52_000, "2026-02": 50_500, "2026-03": 48_000},
    "G4": {"2026-01": 33_000, "2026-02": 31_000, "2026-03": 28_000},
    "G5": {"2026-01": 21_000, "2026-02": 20_000, "2026-03": 18_500},
    "G6": {"2026-01": 29_000, "2026-02": 28_000, "2026-03": 25_500},
}
G3_MARCH_ACCRUAL, G3_MARCH_INVOICE = 48_000, 51_900
PAYROLL_TAX_MONTHLY_2026 = 60_000           # Jan..Jun; E18 adds 6,200 YTD (1,033.33/month)
DEPRECIATION_Q1, INTEREST_Q1 = 310_000, 270_000

Q1_EBITDA_REPORTED = 1_400_000
Q1_PRETAX_REPORTED = 820_000
FY2025_QUARTER_EBITDA = {"2025-Q1": 1_350_000, "2025-Q2": 1_350_000, "2025-Q3": 1_450_000, "2025-Q4": 1_400_000}
FY2025_REVENUE, FY2025_PRETAX, Q1_2025_REVENUE = 39_100_000, 3_150_000, 9_820_000
FY2025_MEMBERSHIP_DEC = 2_480_000
E20_AMOUNT = 95_000
TERM_LOAN, CASH_2026_03_31 = 18_000_000, 1_500_000
NET_DEBT_2025_12_31 = 15_900_000
COVENANT_MAX = 3.00

BUDGET = {"revenue": 42_000_000, "ebitda": 6_000_000, "pretax": 3_200_000,
          "q1_revenue": 10_500_000, "q1_membership": 7_350_000, "q1_utilities": 540_000, "q1_route_setting": 120_000,
          "q1_legal": 30_000, "q1_payroll_tax": 190_000, "q1_ebitda": 1_500_000}
MATERIALITY = {"annual": 160_000, "quarterly_performance": 60_000, "clearly_trivial": 8_000, "flux_pct": 0.10,
               "flux_abs": 25_000, "cash_tolerance": 1_000}

# Cash, June
CASH_2026_05_31_V1, CASH_2026_05_31_V2 = 1_620_000, 1_580_000
MAY_COLLECTED_V1, MAY_COLLECTED_V2 = 3_310_000, 3_270_000
E05_WIRE = 40_000
JUNE_DUES_BILLED = 990_000
ACH_0601_COLLECTED_V1 = 987_000
E03_R01_COUNT, E03_R01_AMOUNT = 14, 2_310
E04_R10_AMOUNT = 189
E17_FEE_V1, E17_FEE_V2 = 25.00, 25.40
E14_INVOICE = 18_750
E16_INVOICE = 18_000
E21_INVOICE, E21_RECEIVED = 24_000, 22_965
E09_EUR, E09_RATE_V1, E09_RATE_V2 = 85_000, 1.0280, 1.0820
E13_SEATS, E13_LIST_PRICE, E13_ACTUAL_PRICE = 50, 60, 45
E18_YTD_TRUEUP = 6_200
E08_CREDIT = 6_500
MEMBERS_TOTAL = 9_400
TAX_RATE = 0.21
