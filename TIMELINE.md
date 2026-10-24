# Trackback timeline (all 2026, Pacific time unless noted)

Demo "now" is pinned to **2026-07-08 09:00 PT**. Rule 13 from the build spec: every correction's
transaction time is later than every artifact it touches, and no history event is later than "now".
The live events (E11 group, then Scenario B E20) happen on stage after 09:00.

Runs are pinned agent runs (`runs.pinned_at`). Corrections are `corrections.tx_time`.

| When (PT) | Kind | Id | What | Reaches (expected) |
|---|---|---|---|---|
| 2025-03-15 10:00 | Run | R11 `mpwr_note` | Reporting Analyst writes the MPWR FY2024 analyst note from the original 10-K facts (Real world tab) | — |
| 2026-02-13 10:00 | Action | `cert_q4_2025` | Q4 2025 compliance certificate sent (history fixture, executed) | — |
| 04-10 17:00 | Run | R1 `q1_close` | Close Accountant: Q1 hard close. Membership revenue per gym from billing exports (v1 has the duplicated March rows), accruals (G3 utilities $48,000), wall build at 40%, gym EBITDA, Q1 EBITDA $1.40M, pretax, TTM $5.60M. Q1 locked | — |
| 04-12 09:00 | Correction | E01 | Bayline invoice $51,900 vs $48,000 accrual. Estimate change, knowable 04-12. +$3,900 booked in April | Q1 utilities: cleared (estimate_change / below trivial) |
| 04-20 11:00 | Correction | E07 | UC Sierra change order: price +$150k, cost +$60k. Prospective, knowable 04-20. Catch-up +$21,818 in April | Q1 wall build: cleared (estimate_change) |
| 04-24 15:00 | Run | R2 `q1_board_deck` | Reporting Analyst: KPI tiles, BvA lines, 8 commentary sentences, FY2025 comparatives. Deck published (action) | — |
| 05-15 10:00 | Run | R3 `q1_covenant_cert` | Covenant agent: net debt $16.5M, TTM Adj. EBITDA $5.60M, leverage 2.95x, certificate sent (CFO signed) | — |
| 05-20 14:00 | Correction | E10 | March employment-counsel invoice $14,000 found un-accrued. Error, knowable 03-28. OOP entry in May tagged March, misstatement log | Legal/EBITDA/pretax/TTM recalculated; leverage 2.954x conclusion_unchanged; certificate touched, still valid |
| 05-27 10:00 | Correction | E02 | March route-setting invoice $22,500 dated 04-03; timesheets existed 03-31. Error. OOP entry tagged March | Deck sentence "fell 18% QoQ" invalidated (now 2%); leverage 2.966x conclusion_unchanged; revenue tiles untouched |
| 05-29 09:00 | Run | R4 `q1_gm_bonus` | Covenant & comp agent: gym EBITDA vs target, bonuses (G1 $2,000, G2 $800, G4 $2,000, others $0), payout action approved by HR + Controller | — |
| 05-31 09:00 | Action | `bonus_payout_q1` | GM bonuses paid (executed) | — |
| 06-02 09:00 | Run | R5 `cash_refresh_0602` | Reporting Analyst: 13-week cash forecast (weeks 23–35), opening balance from May statement v1, week-23 actual from the 06-01 ACH batch v1, May cash collected KPI, AR aging | — |
| 06-03 16:00 | Correction | E03 | 06-01 dues batch: 14 R01 returns, $2,310. Fact update, knowable 06-03 | Week-23 actual cell invalidated; member AR recalculated; P&L untouched. Compensation: reverse 1015→1210, retry per company policy |
| 06-04 09:00 | Correction | E17 | Bank feed revises a 06-02 fee $25.00 → $25.40 | Recon line auto-adjusted; nothing else (week-23 cell below tolerance) |
| 06-05 10:00 | Run | R6 `h2_forecast` | Reporting Analyst: H2 revenue forecast cells (membership, wellness from the Northgate contract v1), YTD wellness actual. E19 (ALFRED vintage) is cut: no vintages on disk | — |
| 06-09 11:00 | Correction | E06 | Northgate amendment (signed 05-15, effective 06-01, +50 seats at $45) captured. Prospective modification: $14,250/month from June | Jun–Dec wellness forecast cells invalidated; Jan–May cells cleared (claim unchanged); Q1 untouched |
| 06-10 09:30 | Refused | E15 | Email "from Kletterwerk" (domain kletterwerk-gmbh.co) asks to change the IBAN. Correction refused: sender domain does not match the vendor master; callback required | Nothing. Vendor master unchanged |
| 06-12 09:00 | Run | R7 `ap_run_0612` | Close Accountant: AP payment run. Pre-execution fence finds AP aging v2 (2231 flagged duplicate of INV-2231, captured 09:20) and blocks the duplicate: E14. Cash-floor check (min buffer $500k) | — |
| 06-15 10:00 | Run | R8 `q2_est_tax` | Covenant & comp agent: Q2 federal estimated payment = 21% of current Q1 pretax; paid (executed) | — |
| 06-16 09:00 | Run | R5b `cash_refresh_0616` | Reporting Analyst: weekly refresh (weeks 25–37), AR past-due by customer using the customer master (net-30), dunning email to Pacific Lumen on day 31 (executed action) | — |
| 06-16 14:00 | Correction | E05 | Bank issues a corrected May statement: $40,000 wire credited 05-30 to Northgate was misdirected. Fact update | May cash rec, 13-week opening balance, May cash collected KPI invalidated; AP-run cash floor conclusion_unchanged; Northgate AR needs_review (over 60 days); May revenue untouched |
| 06-19 09:00 | Run | R9 `june_commissions` | Covenant & comp agent: commission on the Northgate amendment from the order form v1 (list $60): $2,880. Paid in June payroll 06-20 (executed) | — |
| 06-22 10:00 | Correction | E16 | Contract says net-45; customer master said net-30. Master corrected (owner approves) | Dunning action → retraction; AR past-due recalculated; collection-timing cells moved; revenue untouched |
| 06-24 10:00 | Correction | E13 | Order form corrected to the actual $45 seat price. Commission should be $2,160; $720 overpaid | Commission record invalidated → offset next commission (VP Sales + Controller) |
| 06-26 09:00 | Correction | E18 | State revises the 2026 SUI rate retroactive to January (+$6,200 YTD). Estimate change (new information) | Q1 payroll tax BvA cleared (estimate_change); revenue commentary and covenant untouched |
| 06-30 09:00 | Norm | N2 | Pacific Lumen short-pay norm (11 of 12 wires short by $15–$35) approved by the Controller, valid from 06-30 | — |
| 07-02 10:00 | Correction | E09 | Kletterwerk €85,000 holds invoice (03-20) converted at 1.0280; vendor corrects the rate to 1.0820 (+$4,590). Error from a bad input fact | Capex register and depreciation schedule recalculated (exact lines); revenue and covenant EBITDA untouched |
| 07-06 11:00 | Event | E21 | Pacific Lumen short-pays $1,035 on the June 30 wire | Handled in R10 with norm N2: $35 to bank fees, $1,000 routed to a person |
| 07-07 15:00 | Correction | E04 | $189 06-01 debit returned R10 with a signed WSUD (36 days, inside the 60-day window) | Member AR recalculated; July cash below tolerance; never re-present (deny-list) |
| 07-08 08:00 | Run | R10 `june_close` | Close Accountant (in progress): April–June BvA lines (incl. April utilities with the E01 true-up, H1 payroll tax with E18), June accruals (Bayline factor 1.0: June is not a winter month), E21 split, E08 SLA credit to 4900, E03/E04 reversals, misstatement log | — |
| 07-08 08:30 | Norm | N1 | Bayline winter accrual factor 1.08 proposed from ten winter months (median +7.8%); waiting for the Controller | — |
| 07-08 09:00 | Now | — | Demo "now" | — |
| 07-08 09:05 | Live | E11 | Billing export March v2: the February migration duplicated the March annual-prepaid release. $118,000 across G1 $26k, G3 $22k, G4 $32k, G5 $18k, G6 $20k, G2 $0. Error, knowable 04-09 | Covenant 3.03x breach; revenue and EBITDA tiles; membership flux sentence; G1/G4 bonuses (E12); Q2 estimated tax (E23); cash artifacts cleared; G2/G3/G5/G6 bonuses cleared |
| 07-08 09:10 | Live | E22 | Agent's first correcting JE dated 03-31 (locked) with approver = proposer: schema CHECK rejects; Controller rejects the date; agent re-drafts in Q2 with an OOP tag | — |
| 07-08 09:30 | Live (Scenario B) | E20 | December 2025 annual memberships ($95,000 of 2026 service) fully recognized in December 2025. Prior-year error, little r | FY2025 comparatives invalidated; Q4 2025 certificate conclusion_unchanged (2.915x); Q2 P&L untouched. Trap: Q2 OOP entry rejected by the Controller |
