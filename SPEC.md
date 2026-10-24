# Trackback v3: build spec

Hand this whole file to the coding agent (Claude Code or Codex) working in https://github.com/KrishnaPagrut/Trackback. It is standalone: it replaces the earlier build prompt and iteration 2 (the multi-agent, ping-protocol version). If `DESIGN.md` is in the repo, use it for visual details; where it conflicts with Section 14 here, this file wins.

Cal Hacks 13.0 is underway. Submission is due Sunday, October 25, 2026 at 9:00 am PT. Build in checkpoints so the project is demoable after every one (Section 15).

---

## 0. How you work

- You are the only engineer. Krishna checks in occasionally; teammates do slides and video. Don't stop to ask questions. When something is ambiguous, pick the simplest option consistent with this spec, log one line in `DECISIONS.md`, and keep going.
- Save this file as `SPEC.md` at the repo root. Create `CLAUDE.md` (or `AGENTS.md` for Codex) containing: "Before each milestone, re-read SPEC.md and STATUS.md. The spec is final: don't brainstorm, don't wait for approval. Commit every 45 minutes. Never commit .env. The demo must run offline."
- Keep `STATUS.md` current: the checkpoint you're on, what works (with the command that proves it), what's broken, the next three tasks.
- Commit often, tag each checkpoint (`cp1-recon` and so on), never rewrite history.
- Timebox any bug to 45 minutes, then take the documented fallback or simplify.
- Tests define done. Each checkpoint has acceptance checks; don't move on until they pass.
- Never invent real-world facts. Tidewall is synthetic and must be labeled synthetic everywhere.
- The LLM is optional at runtime. Every feature must work and demo with no API key (deterministic text). With `ANTHROPIC_API_KEY` set, Claude writes the narratives, the root-cause wording and Jade's critique. Use model names from config (`claude-sonnet-5-5` for the agent, `claude-opus-5-5` for Jade). Cache every LLM response so the demo replays offline.

---

## 1. What Trackback is

One seat on a finance team: the close accountant's error review.

When two sources disagree, Trackback works out which one is right, finds everything the wrong number touched (including spreadsheets, decks and certificates people made by hand), decides whether it matters the way an accountant would, drafts the fix and a memo, and routes them to the right human. It never posts or sends anything itself. A second AI, Jade, reviews its work like a manager would, and the agent learns from what Jade and the humans correct.

Seat line (use verbatim on Devpost and in the pitch): "Trackback does the close accountant's error review: when sources disagree, it finds what broke, sizes it, drafts the fix and the memo, and never posts anything without the controller."

Tagline: "Hyphenate traces any number back. Trackback traces any correction forward." The name comes from TrackBack, the 2002 blogging protocol that let a page notify everything that referenced it.

### The Hyphenate brief, and how Trackback answers each question

Hyphenate track: $8,000 / $5,000 / $3,000, top 5 get expedited interviews. Hyphenate only sells to companies with more than $100M in revenue, so the company is sized accordingly.

| Judging question | Trackback's answer |
|---|---|
| Is it real enough? Realistic data, a messy problem, proof it works | A $185M company with ordinary mess left in (timing, rounding, aliases, bundled payments, a half-finished reconciliation), human files with hardcoded numbers, planted errors with an answer key, and a per-step scorecard against baselines |
| Would you hire it? Which seat; limited access, clean record, knowing when to ask | One seat. Read-only on source systems; drafts entries and documents but never posts or sends; segregation of duties enforced in the database; every claim cites evidence; routes each decision to the right person, holds risky actions while waiting |
| Did we see something new? | Evaluating an error after it's found: tracing it into hand-made files nobody linked, judging materiality with SAB 108's two methods plus qualitative tests, an independent reviewer that is itself scored, and an agent that improves from approved lessons |
| The moment | Catches what others missed (a $750k error a 5% rule ignores breaks the loan covenant), recovers (the controller rejects the first entry, it re-drafts), defends a decision (Memento shows exactly what the books held on a past date), and Jade overrules the agent's own mistake |

The brief's hard parts, each covered explicitly: sources that disagree (system-of-record reasoning on every exception), time (Memento and learned habits), working with others (approvals, an out-of-office delegate, holds, reminders, escalation, a half-finished handoff), limits (read-only, SoD), explainable (evidence on every line, the memo).

Submission must include: a demo video that opens with the moment, a live demo that runs for real (judges may try their own scenario), the seat line, and proof (what's real, what's simulated, how you know).

---

## 2. What judges see (the target the build serves)

| Time | On screen | Presenter says |
|---|---|---|
| 0:00 | Title card: "Tidewall told its bank leverage was 2.95x." | "48 climbing gyms, $185 million revenue, a $105 million loan, and about half a million dollars of room under its limit." |
| 0:15 | Reconciliations run. Hundreds of lines match; a few dozen differences clear with reasons (timing, rounding, a bundled wire, a known short-pay); one row turns red | "Most differences are noise. This one isn't: the billing migration double-counted $750,000." |
| 0:40 | Side by side: the billing export row, the two ledger imports, and cell B7 in Priya's covenant workbook, linked | "Nobody linked this spreadsheet to the books. Trackback found where every number came from." |
| 1:00 | The ripple: red items with old and new values, green items with reasons | "These are now wrong, including the certificate already sent to the bank. These it checked and cleared." |
| 1:25 | The agent's draft says "immaterial". Jade's pane flags it: rollover $662k passes, iron curtain $1.118M fails, leverage 3.02x breaches; overruled | "Under 5% of profit, so a simple rule shrugs. Its reviewer didn't: this breaks the loan." |
| 1:50 | Approvals: Dana rejects the first entry ("Q1 is locked"); the agent re-drafts in June with an out-of-period tag; the July 15 bonus run is on hold | "It drafts, it never posts, and it handles being told no." |
| 2:10 | Scrub back to April 9: the duplicate was already visible | "It owns the miss: here's what the books showed that day." |
| 2:25 | Scorecard | "Our planted cases, step by step, versus a 5% rule and versus the agent without its reviewer." |
| 2:45 | The memo and the seat line | "It writes the memo your auditor will ask for." |

Then hand the judge the keyboard: "Change any number, or paste your own correction."

---

## 3. Architecture

Pipeline per review run (pinned to the demo clock, July 8, 2026 09:00 PT):

1. Detect: four reconciliations produce matched items, cleared differences (each with a reason) and exceptions.
2. Trust: each exception names its system of record and why.
3. Trace: the lineage tracer links every number in the human files to the books; the ripple engine walks the context graph from the correction.
4. Evaluate: the agent writes an Error Evaluation (seven questions) per exception, as structured claims.
5. Review: Jade verifies every claim and approves, overrules or escalates.
6. Ask: corrections and compensations go to the right approvers; risky actions are held.
7. Report: an error memo per material exception; the scorecard over all planted cases.
8. Learn: mistakes caught by Jade or humans become proposed lessons; approved lessons pass a regression gate before going live.

Where AI is and isn't used (say this to judges): math decides what matches and what it's worth; AI handles judgment and language, and everything it says gets checked.

| Component | How it works |
|---|---|
| Reconciliation matching | Code: normalization, candidate scoring, Hungarian assignment (scipy `linear_sum_assignment`), subset-sum for bundled payments, learned lag windows and short-pay habits from history |
| Lineage tracer | Code: file parsing, formula evaluation, value matching at displayed precision, label scoring, version (as-of) matching, small-sum reconstruction. Optional LLM tie-breaker only for links below 0.6 confidence |
| Ripple | Code: structural reach, recompute, early cutoff, conclusion checks |
| Materiality | Code: thresholds, SAB 108 rollover and iron curtain, qualitative tests via the graph, aggregation |
| Agent | A playbook (versioned policy) drives decisions deterministically; the LLM writes root-cause text, explanations and the memo prose |
| Jade | Code checks every numeric, evidence, policy and authority claim; the LLM critiques only judgment claims |

---

## 4. Stack and layout

Python 3.11+, FastAPI, SQLite (one file, append-only ledger), openpyxl, python-pptx, pypdf, reportlab, numpy, scipy. Frontend: React + Vite + TypeScript, `@xyflow/react` with a dagre layout, plain CSS variables for the design tokens. One process serves the API and the built frontend on `http://localhost:8000`. Commit the built frontend (`web/`) so `make demo` needs no npm on stage.

```
backend/trackback/
  config.py            # demo clock, company, people, accounts, materiality, covenant, key dates
  db.py                # schema: source_versions, ledger_entries (append-only triggers), approvals (CHECK proposer<>approver), lessons, audit_log
  world/generator.py   # seeded synthetic world + answer key; world/refcalc.py (independent arithmetic for the key); world/human_files.py
  engine/books.py      # Books(as_of, adjustments), Slice, MetricLibrary, evaluate()
  engine/memento.py    # TimeMap, TimeGate with time-pinning, refusals
  engine/recon.py      # billing_to_gl, bank_to_book, cash_application, ap_review
  engine/lineage.py    # extraction, workbook formula evaluator, Tracer
  engine/graph.py      # Ripple: reach, verdicts, actions, compensations, naive baseline, graph JSON
  engine/materiality.py
  agent/playbook.py    # versioned policy + lessons
  agent/agent.py       # builds Error Evaluations
  agent/llm.py         # gateway: record | replay | off
  jade.py  workflow.py  memo.py  lessons.py
  eval/cases.py  eval/scorecard.py
  api.py  cli.py
backend/tests/
frontend/   web/   data/world/ (generated)   docs/screenshots/
Makefile    # setup, world, test, eval, demo, reset
```

---

## 5. The world: Tidewall Climbing Co. (synthetic)

48 indoor climbing gyms in six regions (8 each): R1 Bay Area, R2 Southern California, R3 Pacific Northwest, R4 Rockies, R5 Central Valley, R6 Desert Southwest. Plus HQ (corporate wellness contracts, HQ payroll, legal, depreciation, interest) and WALL (a wall-building division). About $185M annual revenue.

### 5.1 Calibration targets (assert all of these in tests)

| Item | Value |
|---|---|
| Trailing-four-quarter Adjusted EBITDA to Mar 31, 2026, as of the Q1 close (Apr 10, 17:00) | exactly $32,000,000.00 (use a single plug entry in HQ other opex in Oct 2025 to hit it) |
| Same, as of the Apr 9 18:00 draft (before the two close accruals) | exactly $32,600,000.00 |
| Q1 close accruals posted Apr 10 | route setting $410,000 (6300), utilities $190,000 (6200), both HQ |
| Term loan (2500) | $105,000,000, drawn Apr 1, 2025 |
| Cash (1010) at Mar 31, 2026 | exactly $10,600,000 (monthly treasury plug) |
| Net debt / leverage as reported | $94,400,000 / 2.95x |
| Covenant | net leverage at or below 3.00x; Adjusted EBITDA excludes depreciation (6800), FX (7100), interest (7500), tax (8100) |
| Materiality memo (Dana, Jan 15) | overall $800,000 (5% of $16.0M budgeted pretax), performance $250,000, clearly trivial $25,000, flux 10% and $250,000 |
| Tax | Q2 estimated payment = 26% of Q1 pretax, paid Jun 15 |
| Bonuses | 4% of regional Q1 EBITDA above target, paid May 31. Targets are set so R1 is $400k above, R2 $300k above, R4 $250k above, R6 $150k above, R3 $200k below, R5 $100k below |

Effects the tests must confirm after generation:
- Removing the $750k duplicate: TTM Adjusted EBITDA $31.25M, leverage 3.0208x (breach). With X2 and P1 too: 3.0681x.
- Bonuses overpaid: R1 $8,400, R2 $7,200, R4 $4,800; R3 and R5 stay $0; R6 untouched.
- Q2 tax overpaid by $195,000 from X1 alone.
- Aggregate misstatement: rollover $662,000 (below $800k), iron curtain $1,118,000 (above $800k).

### 5.2 Ledger

Accounts: 1010 Cash, 1200 AR Corporate, 1210 AR Members, 1500 Equipment, 1590 Accum. depreciation, 2010 AP, 2100 Accrued expenses, 2150 Accrued bonus, 2300 Deferred revenue (annual memberships), 2500 Term loan, 3900 Retained earnings, 4000 Membership revenue (monthly dues), 4010 Membership revenue (annual plans), 4100 Day pass and retail, 4200 Corporate wellness, 4300 Wall build revenue, 5300 Wall build cost, 6000 Payroll, 6100 Rent, 6200 Utilities, 6300 Route setting, 6400 Legal, 6500 Bank and merchant fees, 6600 Bonus, 6700 Other opex, 6800 Depreciation, 7100 FX, 7500 Interest, 8100 Income tax.

Each entry: entry_id, txn_id, posted_at (system time), eff_date, period (YYYY-MM), orig_period (for out-of-period corrections), entity (gym id, HQ, WALL), account, amount_cents (debit positive), memo, source_ref, import_id. Periods Apr 2025 to Jun 2026, monthly entries per gym per account, posted on the 3rd of the next month. Use one fixed UTC offset string for posted_at so string comparison orders correctly. The ledger table has UPDATE and DELETE triggers that abort: corrections are new entries.

Monthly gym figures (multiply by a per-gym factor 0.86 to 1.14, add small noise and winter seasonality): dues about $168k, day passes about $55k, payroll $118k, rent $68k, utilities $12.5k (summer) to $16k (winter), route setting $8.5k, other $6.5k, card fees 1.4% of revenue. HQ: wellness revenue $1.2M, payroll $780k, legal $130k, depreciation $750k, interest $612.5k. WALL: revenue about $1.65M at 70% cost.

### 5.3 Annual plans and the hero error (X1)

About 17,800 annual-plan members, each with a monthly release (about $90, $102 or $115) and a billing batch. GL account 4010 is fed by batch-level imports from the billing system's summary export: one transaction per batch per month (credit 4010 per gym, debit 2300), with an import_id like `IMP-202603-B07-1`.

- Batch 7 is the February migration cohort, spread across R1 to R5. Its March release per region is exactly R1 $210k, R2 $180k, R3 $150k, R4 $120k, R5 $90k (total $750,000; R6 none). Use a final prorated member per region to hit the totals exactly.
- The March import of batch 7 ran twice: `IMP-202603-B07-1` posted Apr 3, and `IMP-202603-B07-2` posted Apr 6 at 22:14 after a timeout and retry. The import log says "ok (retry after timeout)". Billing released the batch once.
- Billing line-level export versions: one captured Apr 9 18:00 (Jan to Mar), one captured Jul 8 (Jan to Jun). The Apr 9 version already shows batch 7 once: the error was knowable before the close.

### 5.4 The other planted cases

| ID | What | Correct answer |
|---|---|---|
| X2 | Brightline Kessler LLP invoice BRK-26-0331, $140,000, March employment-counsel work, received in the AP inbox Apr 2 08:41, never processed (assigned to Priya) | Error (knowable before close). Correct in the open period tagged to March. Alone it's below performance materiality, but it aggregates with X1. Approver Dana |
| X3 | Cragline Route Setters invoice CRX-5521, $468,000, received May 20, vs the $410,000 March accrual. Already handled in May (accrual reversed, invoice booked, $58k true-up) | Change in estimate, not an error. No action. Trap: an agent that restates Q1 is wrong |
| X4 | Summit Mats Supply invoices "INV-2231" and "2231", same vendor, same $18,750, same PO 4471; both paid on the Jun 12 AP run | Error. Request a vendor credit and hold the next payment to that vendor. Below clearly trivial, so excluded from the materiality aggregate. Approver Marco (AP) |
| X5 | Bank shows an R01 return of $2,310 from the Jun 1 dues batch; the cash book doesn't | Fact update. Reverse the receipt, reinstate member receivables. R01 may be re-presented once by policy; R05, R07, R10 never. Approver Dana |
| X6 | Bank analysis fee $312.40 on Jun 30, not in the cash book | Fact update, trivial. Draft the entry. Approver Dana |
| P1 | Already on the uncorrected misstatement log (Dana, Apr 10): 380 December 2025 promo plans ($1,200 each, $456k) recognized at sale instead of over 2026 ($38k a month). Rollover YTD effect -$228k, iron curtain +$228k, TTM EBITDA effect +$342k | Known item. Recon must recognize it (billing batch 9 lines with no GL import) as known, not new. It must be included in the aggregate |
| H1 | Board deck slide 2 shows "Adj. EBITDA (TTM): $32.6M", typed from the Apr 9 draft. The books said $32.0M when the deck was made (Apr 24) | Human-file finding: stale number. Flag it even before any correction |

Ordinary mess that must clear without alarms (the "noise" in the answer key):
- 12 card deposits in transit (card batches settle 2 days later; Jun 29 and 30 land in July).
- 3 outstanding checks.
- One euro wire with a $0.01 conversion rounding difference.
- Northgate Biotech pays three invoices ($62,000 + $74,400 + $50,000) with one $186,400 wire: find it by subset-sum.
- Pacific Lumen Labs short-pays $25: its history shows it short-pays 11 of 12 wires by $15 to $35 (intermediary fees), so clear the $25 to bank fees by the learned habit.
- Sierra State University pays as "SSU FOUNDATION ACCTS PAYABLE": identify by acronym plus exact invoice amount, and suggest adding the alias.
- Billing batch 9 (P1) for each 2026 month: known item.

### 5.5 People and calendar

Dana Ortiz (Controller: approves entries, the misstatement log, lessons), Sam Whitfield (CFO: signs anything to the lender), Priya Nair (Assistant Controller; out of office Jun 20 to Jul 13; delegate Marco), Marco Bell (Senior Accountant, AP: vendor refunds and holds), Lena Park (HR: compensation adjustments).

Key dates (2026): Apr 9 18:00 draft trial balance; Apr 10 17:00 Q1 close (Q1 locked; April and May are also closed; June is open); Apr 24 board deck; May 12 covenant workbook; May 15 certificate sent; May 20 route invoice; May 31 bonuses paid; Jun 12 AP run; Jun 15 tax paid; Jun 20 Priya leaves; Jul 8 09:00 demo "now"; Jul 15 next bonus run.

### 5.6 Files (in `data/world/files/`, each registered as a source version with a captured_at)

- `billing_release_lines_2026-04-09.csv`, `billing_release_lines_2026-07-08.csv`: period, member_id, gym_id, region, batch, plan_price, release_amount.
- `gl_import_log.csv`, `gl_detail_export.csv`.
- `bank_statement_2026-06.csv` (bank_id, date, description, amount, trace: the bank's own trace numbers, not book refs) and `cash_book_2026-06.csv` (book_id, date, description, amount, ref).
- `ar_open_invoices_2026-06.csv`, `customers.csv` (legal_name, aliases), `ar_payment_history.csv` (12 months; the learned habits come from here).
- `ap_invoices.csv` (with received_at, service_period, status, assigned_to, po), `accruals.csv`, `misstatement_log.csv`.
- `materiality_memo.json`, `credit_agreement.json` (including the correction clause: materially misstated statements require corrected statements and a corrected compliance certificate), `comp_plan.json` (targets; overpayments offset against the next bonus, no ad-hoc payroll deductions), `people.json`, `gyms.csv`.
- Human files in `human/`:
  - `Covenant_Q1-26_PN.xlsx` (Priya, May 12). Sheet Covenant: B6 Revenue TTM (hardcode), B7 Adjusted EBITDA TTM (hardcode 32,000,000.00), B9 term loan, B10 cash, B11 `=B9-B10`, B12 `=B11/B7`, B13 3.00, B14 `=IF(B12<=B13,"Compliant","BREACH")`, B15 `=B7-B11/B13`. Sheet Bonus: one row per region with Q1 EBITDA (hardcode), Target (hardcode), Excess `=MAX(0,B-C)`, Bonus `=D*0.04`, and a Total row. Sheet Tax: B1 Q1 pretax (hardcode), B2 0.26, B3 `=B1*B2`. Write formulas without cached values; the tracer must evaluate them itself.
  - `Board_Deck_Q1-26.pptx` (Apr 24). Slide 2 lines: "Revenue (Q1): $48.1M", "Adj. EBITDA (TTM): $32.6M" (stale), "Membership revenue (Q1): $31.5M, up 2.8% vs Q4", "Net leverage: 2.95x (covenant max 3.00x)", "Gym revenue (Q1, dues plus day passes): $38.9M" (no single metric: must be reconstructed as 4000 + 4010 + 4100). Slide 3: "We remain within our 3.00x net leverage covenant at 2.95x." Slide 4: Q1 EBITDA by region in $K. Use the generated values; the figures above are what the prototype produced.
  - `Compliance_Certificate_Q1-26_signed.pdf` (May 15, signed by Sam): numbered lines for Adjusted EBITDA, Net Debt, Leverage 2.95 to 1.00, Maximum 3.00 to 1.00, and "The Borrower is in compliance with Section 7.1".
  - `Billing_to_GL_rec_Mar26_PN_INCOMPLETE.xlsx`: batches B01 to B06 marked "Tied", B07 to B09 blank, note "Out of office 6/20 to 7/13. Batches 7 to 9 still to tie. B07 is the February migration cohort. PN".

### 5.7 Answer key

The generator writes `answer_key.json` using its own reference arithmetic (`refcalc.py`), never the engines it grades. It contains: the exceptions with classification, knowable_at, materiality and reasons, rollover and iron curtain, treatment and approver; the noise list; the lineage truth for every number in the human files (file, locator, value, acceptable metric ids); the X1 impact sets (Appendix A); the compensations; the aggregate materiality numbers; the H1 finding.

---

## 6. Engines

### 6.1 Books and the metric library

`Books(entries, as_of=None, adjustments=None)`: entries with posted_at at or before as_of, plus hypothetical correcting entries placed in their orig_period. `Slice(accounts, periods, scope, balance)` where scope is `company`, `region:R1` or `entity:HQ`; `touches(account, period, region, entity)` is the structural test the ripple uses.

Each `Metric` has an id, label, synonyms, unit (usd, ratio, pct, status), the slices it reads, the metrics it depends on, a compute function, an optional conclusion (`threshold_max` for leverage at 3.00, `categorical` for covenant status, `sign` for growth, `zero_or_positive` for bonuses) and a family (pl, account, balance, derived, policy). Metrics to include: revenue, membership revenue, EBITDA, pretax and every revenue and opex account per quarter (2025Q2 to 2026Q2); regional EBITDA per quarter; TTM revenue and TTM Adjusted EBITDA (Q1 and Q2 2026); cash, term loan, deferred revenue, net debt at quarter ends; leverage, covenant status, covenant headroom; membership growth vs prior quarter; bonus per region (deps: regional EBITDA, target); Q2 tax installment; policy constants (max leverage, facility amount, tax rate, bonus targets). Provide topological order and a dependents map.

### 6.2 Memento (RFC 7089) with a time-pinning profile

Every source version has a captured_at (Memento-Datetime). Implement TimeMap (all versions), TimeGate (latest version at or before a pinned time) and fetch by version id. The profile deviates from plain RFC 7089 on purpose: a lookup pinned at T never returns a version captured after T (plain Memento would return the nearest one); a pinned lookup before the first version refuses instead of returning the first version; refusals return 403 or 404 with an `application/problem+json` body (type `https://trackback.local/problems/temporal-pin-violation`, fields pinned_at, requested, first_available). Don't send HTTP 425 on the wire; it means TLS early-data replay. Expose `/r/{source}`, `/tg/{source}` (Accept-Datetime header), `/m/{version}`, `/tm/{source}` with Link headers. Ledger "as of" is `posted_at <= T`.

Memento answers the estimate-versus-error question: was the fact in any system when the original number was made?

### 6.3 Reconciliations

All four run at the pinned time and return matched items, cleared items (each with a reason and detail) and exceptions (each with evidence, system of record, knowable info and a proposed correction as balanced adjusting entries).

1. Billing to GL (annual plans, Jan to Jun). Aggregate billing lines by (period, batch); group 4010 entries by import_id into (period, batch) totals. One import equal to billing: matched. More than one import, one equal to billing, the rest identical gym-by-gym: `duplicate_import` exception whose correction reverses the extra import line by line. No import: if the batch is on the misstatement log (B09 = P1), clear as `known_item`, else `missing_import`. Differences of $1 or less: `rounding`. Also load Priya's incomplete workbook, re-check each batch she marked "Tied", and report the handoff ("confirmed her batches 1 to 6, finished 7 to 9").
2. Bank to cash book (June). Categorize lines (card, ACH dues, payroll, wire, check, other). Pass 1: learn the settlement lag per category from unambiguous exact-amount pairs (card: 2 days). Pass 2: candidates need amount within $0.05 and a lag inside the learned window plus or minus one day; score = amount (1.0 exact, 0.7 within $0.05) + date (1.0 inside window, 0.6 edge) + text similarity (token Jaccard, floor 0.3 for same category); cost = 3 minus score; solve with `linear_sum_assignment`. Unmatched book items: card receipts dated Jun 28 or later are `deposit_in_transit`, checks are `outstanding_check`. Matched pairs with a cent-level difference are `fx_rounding`. Unmatched bank items: "RETURN R01" is the `ach_return` exception, service charges are `unbooked_bank_fee`, anything else `unmatched_bank_item`.
3. Cash application (incoming wires vs open invoices). Identify the customer by token similarity to legal name and aliases, or by acronym (SSU). Exact single-invoice match first. Otherwise subset-sum over that customer's open invoices (combinations of 2 to 5, in cents). Otherwise compare with the nearest invoice: if the shortfall falls inside the customer's learned habit (6 or more past short-pays; range min to max plus $5), clear as `known_short_pay` to 6500; otherwise `short_payment` exception routed to a person as a possible dispute.
4. AP review. Duplicates: group by vendor id, digits-only invoice number, amount and PO; any group with two paid invoices is `duplicate_vendor_invoice`. Unaccrued: unprocessed invoices whose service period is in a closed period with no accrual for that vendor and period are `unaccrued_invoice` (knowable at received_at). True-ups: each accrual vs its invoice gives `accrual_true_up` with the delta, received date and whether it's already booked.

### 6.4 Lineage tracer (the most original piece)

Extraction:
- xlsx: load with formulas, not cached values. For every numeric or formula cell outside column A, take the label from column A (and the column header for table-shaped sheets), skip Total rows, evaluate formulas with your own small evaluator (cell refs, ranges, SUM, MAX, MIN, IF with comparisons, string literals; build the expression from a whitelist, never eval raw text), and record the referenced cells.
- pptx: first text box is the slide title, the second is the body; each paragraph is a line (locator `slide N, line M`). Parse numbers with display precision: `$48.1M` means 48,100,000 plus or minus 50,000; `$1,544K` plus or minus 500; `2.95x` plus or minus 0.005; `2.8%` plus or minus 0.05. Skip years, list numbers and day-of-month after a month name. Lines asserting compliance ("within our ... covenant", "in compliance") become status claims (`Compliant`).
- pdf: extract text with pypdf; numbered lines become items (locator `line N`); the compliance sentence becomes a status claim.

Matching each item:
- Evaluate the whole metric library at three ledger snapshots: Apr 9 18:00 draft, Apr 10 17:00 close, Jul 8 now. The file's own snapshot is the latest at or before its creation time.
- Candidates are metrics whose value is within the item's tolerance, with compatible units. Never treat a zero from an empty or future period as evidence.
- Label score = 0.5 x (overlap / metric tokens) + 0.5 x Jaccard, over the item's label and context against the metric label and synonyms, after removing stopwords. Hints: TTM or trailing words favor ttm_ metrics; region names favor that region and penalize others; "March 31" favors quarter-end balances.
- Version score: 1.0 if it matches at the file's own snapshot, 0.4 if it only matches an earlier one.
- Accept the best candidate if its raw label score is 0.3 or more (or 0.15 with strong hints). Confidence = 0.35 + 0.3 x raw label + 0.15 x label-with-hints + 0.1 x version + 0.2 x margin over the runner-up, capped at 0.99.
- If the best match only fits an earlier snapshot, mark the item `stale` and explain ("typed from the Apr 9 draft; the books already said $32.0M when the deck was made"). That's H1.
- Formula cells with no metric match are `derived`: their provenance flows from the cells they reference.
- Hardcodes with no single match: reconstruct small sums (2 or 3 positive account totals for the same quarter) that hit the value within tolerance; link to `sum:acct.4000@2026Q1+acct.4010@2026Q1+acct.4100@2026Q1` with confidence 0.8.
- Otherwise `unlinked`, listing near misses (within 5%), and route to a human.

Target on the generated world: every lineage truth in the answer key correct (47 on the prototype world: every hardcode and typed number linked to the right metric, the deck's $32.6M stale, the gym-revenue line reconstructed, policy constants linked to policy), plus the six Excess cells marked derived. The prototype tracer extracted 57 items in total.

### 6.5 Context graph and the ripple

Nodes: the correction, ledger slices (account and period), metrics, artifacts (every traced item) and executed actions:

| Action | Depends on | Compensation | Approver |
|---|---|---|---|
| Q1 compliance certificate sent to Redwood (May 15) | covenant status | corrected certificate and lender notice under the correction clause | Sam |
| Q2 estimated tax paid (Jun 15) | tax installment | reduce the Q3 installment by the overpayment | Dana |
| Q1 bonus paid, one per region (May 31) | that region's bonus | offset against the Q2 bonus (plan terms) | Lena |

Algorithm for a correction (a list of balanced adjusting entries with orig_period):
1. Reach: seeds are metrics with a slice that `touches` any correction line; then everything downstream through the dependents map. Anything not reached is cleared structurally with no recompute.
2. Recompute: evaluate before and after (`Books(as_of=snapshot)` vs the same plus the correction) for each snapshot artifacts were built from. Metrics whose value doesn't move are early cutoffs.
3. Artifact verdicts, each with a reason from this vocabulary: `value_changed`, `conclusion_flipped`, `stale_and_value_changed`, `input_changed` (derived cells), `display_unchanged` (moves, but not at the precision shown), `value_unchanged`, `conclusion_unchanged` (e.g., a bonus that was $0 and stays $0), `not_consumed` (e.g., built only from Desert Southwest gyms), `different_line_item` (reads other accounts, e.g., cash or the term loan), `policy` (a contract or policy term), `inputs_unchanged`, `unlinked` (needs review).
4. Action verdicts: amount changes give the over or underpayment and the compensation with its amount; a status flip on the certificate gives the lender compensation.
5. Ripple order for animation: correction, ledger, metrics by dependency depth, artifacts, actions.
6. Naive baseline count (source-level): every artifact whose metric reads any corrected account in any period or scope, plus every action. Show it next to Trackback's counts.

Target for X1 on the generated world: 40 invalidated, 23 still valid (Appendix A), 5 actions needing compensation, about 29 of 155 metrics recomputed, in well under a second. For X4 and X6: nothing in the human files invalidated. For X2: TTM EBITDA, leverage, headroom, pretax, tax and the deck's leverage invalidated, and the covenant still compliant on its own (2.96x).

### 6.6 Materiality

Inputs: the exceptions found in this review, the uncorrected misstatement log, the materiality memo and the ripple results.
- Per item: rollover = sum of the correction's P&L amounts whose orig_period falls in the current fiscal year (positive means income overstated); iron curtain = minus the sum of the correction's asset and liability amounts (positive means net assets overstated). Prior-year items (P1) use their logged values.
- Exclude items below clearly trivial ($25k) from aggregation, and say so.
- Quantitative tests: each item and the aggregate, under both methods, against overall materiality ($800k); also each item against performance materiality ($250k). SAB 108: material if material under either method.
- Qualitative tests (SAB 99 factors, computed through the graph, not guessed): flips covenant compliance; changes management compensation; reverses a trend (sign of growth); turns a loss into income; affects a document delivered to a lender or the board; known items left uncorrected.
- Decision: material or not, with the list of triggers. Treatment decision tree: material to a previously issued Q1 package means correct in the open period (Q1 is locked; post in June tagged to March), reissue the Q1 lender package and certificate (Sam), and notify the board; immaterial to prior periods but material if booked in the current period means a revision of comparatives; otherwise an out-of-period adjustment. Estimate changes are never restatements.

Target numbers: aggregate rollover $662,000 (passes), iron curtain $1,118,000 (fails), leverage 3.02x with X1 and 3.07x with everything known, triggers include covenant and compensation. The X1 item alone: $750k under both methods, 4.7% of annual budgeted pretax, above performance materiality.

---

## 7. The agent

A single agent runs the review. Its decisions come from a versioned playbook (`agent/playbook.py`), so behavior is reproducible and lessons can change it.

Playbook v1 deliberately contains four weaknesses that real junior accountants have. These are the planted agent mistakes in the answer key:
1. Materiality: applies only the 5% of annual pretax rule, rollover method only, no qualitative tests, no aggregation. It calls X1 immaterial.
2. Classification: treats any invoice for a closed period's service as an error, without checking when the information arrived. It wants to restate Q1 for X3.
3. Posting: dates correcting entries in the original period. Dana rejects the X1 entry (Q1 is locked).
4. Routing: sends lender documents to the controller instead of the CFO.

For each exception the agent produces an Error Evaluation, a list of structured claims answering seven questions:

```json
{
  "exception_id": "EX-01", "title": "...", "playbook_version": "v1",
  "q1_what": {"kind": "duplicate_import", "root_cause": "Import job retried after a timeout; both runs posted", "evidence": ["..."]},
  "q2_trust": {"trusted": "Billing line-level export", "over": "GL 4010 imports", "why": "..."},
  "q3_classification": {"value": "error", "knowable_at": "2026-04-09T18:00", "original_made_at": "2026-04-10T17:00", "evidence": "memento:billing_release_lines@2026-04-09"},
  "q4_size": {"amount": 750000, "rollover": 750000, "iron_curtain": 750000, "by_region": {"R1": 210000, "...": 0}},
  "q5_matters": {"material": false, "tests": [...], "triggers": [...]},
  "q6_touched": {"invalidated": [...], "still_valid": [...], "actions": [...]},
  "q7_fix": {"entries": [...], "posting_period": "2026-03", "documents_to_reissue": [...], "compensations": [...], "approvers": {...}},
  "confidence": {"overall": 0.0, "per_claim": {...}, "needs_human": [...]}
}
```

Every claim carries the evidence ids it rests on. With an API key, the LLM writes root_cause and the explanation strings from the evidence; without one, templates do. The LLM never produces a number.

---

## 8. Jade, the reviewer

Jade checks the Error Evaluation claim by claim and returns approve, overrule (with the corrected claim and why) or escalate:
- Numeric claims: recompute from the engines and compare.
- Evidence claims: the cited record exists and says what the claim says.
- Classification: query Memento for when the underlying fact first appeared versus when the original number was made.
- Materiality: always runs the full framework (both SAB 108 methods, qualitative tests, aggregation with the log) and compares with the agent's call.
- Posting: the period is open; out-of-period entries carry orig_period.
- Authority: each item goes to an approver whose role allows it (lender documents to the CFO), and the proposer is never the approver.
- Judgment claims (root cause wording, still-valid reasons on prose): LLM critique if a key is set; otherwise accept and mark "not independently verified".

Jade's findings on the v1 agent for the Tidewall review must include: overrule X1 materiality (immaterial to material: iron curtain aggregate over $800k, covenant flips to 3.02x, compensation affected); overrule X3 classification (error to estimate change: the invoice arrived May 20, after the Apr 10 close; already booked in May); flag the lender-document routing (controller to CFO). The locked-period posting is caught by Dana, not Jade, so the demo shows both a machine reviewer and a human saying no.

---

## 9. Workflow: approvals, holds and people

- Approvals table with `CHECK (proposer <> approver)`. Attempting self-approval must raise from SQLite, and the UI shows the error in the event log.
- Routing by item kind: journal entries and the misstatement log to Dana; lender documents to Sam; compensation offsets to Lena (with Dana informed); vendor refunds and holds to Marco; Priya's items go to her delegate Marco while she's out of office (show the automatic reassignment).
- Holds: while the X1 bonus offsets are pending, hold the Jul 15 bonus run for R1, R2 and R4; while the vendor credit is pending, hold the next Summit Mats payment.
- Busy approvers on a simulated clock: a reminder after 4 business hours, escalation to the next role up after 24 hours (Dana to Sam). A "fast-forward clock" control in the UI shows this.
- Simulated people for the demo (each also clickable live): Dana rejects any entry dated in a locked period with "Q1 is locked. Book it in June with an out-of-period tag; restate the lender package separately", otherwise approves after Jade signs off; Sam approves the corrected certificate after Jade signs off; Lena approves offsets; Marco approves vendor credits.
- After Dana's rejection the agent re-drafts: posting period 2026-06, orig_period 2026-03, memo references the original import. Both drafts and the rejection reason are kept and replayable.

---

## 10. The error memo

One per material exception, in the format a controller hands to an auditor: summary; background and root cause; classification with the Memento evidence; quantification under both methods by region; materiality analysis (quantitative table, qualitative factors, aggregation with the misstatement log, conclusion); affected documents and executed actions; correcting entries and compensations with approvers and status; controls going forward (for X1: block duplicate import ids per period and batch; reconcile billing to GL monthly after migrations); Jade's review notes. Every line links to its evidence. Render as HTML in the UI and downloadable Markdown.

---

## 11. Learning from mistakes

Mistake signals (never the agent grading itself): Jade overrules; a human rejects or edits a draft; a flagged difference is dismissed as noise; an item cleared as valid later turns out affected; a lineage link is corrected by a person; a case fails on the scorecard.

Each mistake becomes a proposed lesson: mistake kind, the rule, the case evidence, and how it's enforced. Prefer turning lessons into checks in the playbook (for example "never conclude immaterial without the qualitative tests and both SAB 108 methods"; "classify by when the information arrived, using Memento, not by service period"; "post corrections in the open period with orig_period"; "lender documents go to the CFO"); otherwise keep it as guidance text pulled into the LLM context for similar cases.

Governance: lessons start as proposed and need Dana's approval (a lesson changes how controls operate, so it applies prospectively only). Regression gate: before activation, rerun the whole scorecard with the lesson; reject it if any previously passing case fails, and show the result.

Proof: split the case library (Section 12) into a training half and a held-out half, stratified by family. Run playbook v1 on the training half, collect mistakes, propose lessons, pass the gate, approve, then run v2 on the held-out half. Show v1 vs v2 scores on held-out cases and the lessons that were rejected by the gate. The four planted weaknesses map to four lessons.

---

## 12. Evaluation and the scorecard

Case library (`eval/cases.py`): the six Tidewall exceptions plus the noise, plus about 30 generated variants applied to the same world, each with its expected labels written by the generator's own rules:
- Duplicate imports of different sizes and regions (some flip the covenant, some don't, some hit only R6).
- Unaccrued invoices received before the close (errors) and after (estimate changes).
- Accrual true-ups (estimate changes; the trap is restating).
- Classification errors with no income effect (e.g., expense booked to the wrong opex account): rollover 0, iron curtain 0.
- FX corrections on capex (excluded from Adjusted EBITDA: covenant untouched).
- Prior-year items (rollover and iron curtain with opposite signs).
- Trivial items below $25k (excluded from aggregation).
- Pure noise: timing, rounding, aliases, bundled payments (expected: zero exceptions).

Metrics per step, each computed from logs against the key, never typed:
| Step | Metric |
|---|---|
| Detect | precision and recall of exceptions; false alarms on noise |
| Classify | error vs estimate vs fact accuracy |
| Size | exact match on rollover and iron curtain |
| Materiality | accuracy of the material call, reported separately for "small but covenant-breaking" cases |
| Trace | lineage link precision and recall against the answer key's lineage truths; stale detection |
| Impact | precision and recall of invalidated vs still valid against Appendix A; over-flagging vs the naive count |
| Fix | correct treatment, entries balance, right approver |
| Jade | catch rate on planted agent mistakes; false overrule rate on correct claims |
| Learning | v1 vs v2 on held-out cases |
| Memento | future reads leaked (target 0) in an adversarial test |

Baselines: a naive "under 5% of annual pretax is immaterial" rule; the agent without Jade; the agent with Jade (v1); the agent with Jade after approved lessons (v2). Optional with an API key: "ask the LLM what this correction affects" over the raw files. Write `data/eval/latest.json`; the UI's proof page reads only that file. Show what's real (the engines, Jade, scoring, file parsing) vs simulated (Tidewall's books, people and files).

---

## 13. API (FastAPI)

`GET /api/state` (company, clock, people, holds) · `POST /api/review/run` · `GET /api/recons` · `GET /api/exceptions` · `GET /api/evaluations/{id}` (agent claims plus Jade's verdicts) · `GET /api/lineage` (all items and links, by file) · `GET /api/files/{source}` (rendered workbook cells, deck lines, certificate lines, with highlights) · `GET /api/ripple/{exception_id}` (counts, order, verdicts, graph JSON) · `GET /api/materiality` · `GET /api/approvals`, `POST /api/approvals/{id}/decision` · `POST /api/clock/advance` · `GET /api/memo/{exception_id}` (HTML and Markdown) · `GET /api/memento/timemap/{source}`, `GET /api/memento/timegate/{source}?at=` (refusals as problem+json) · `GET /api/ledger?as_of=` (trial balance) · `GET /api/scorecard` · `GET /api/lessons`, `POST /api/lessons/{id}/approve` · `POST /api/corrections` (judge's own scenario: pick a source line or ledger slice, a new value, and "when did this fact first exist?"; also accept a pasted sentence parsed into that form and shown for confirmation) · `POST /api/reset`.

---

## 14. UI

Two modes. The app opens in Stage mode; `D` toggles Deep mode without losing state.

Stage mode follows Section 2 beat by beat on `Space` (Backspace goes back, R resets): title card; reconciliation sweep with counters (matched, cleared by reason, exceptions); evidence side by side (billing row, both ledger imports, the workbook cell, the deck line, the certificate line, each highlighted in a rendered view of the real file); the ripple (red with old and new values, green with reasons, about 150 ms per hop, at most about 12 nodes on screen with "+N cleared"); Jade's overrule card (rollover passes, iron curtain fails, covenant 3.02x, compensation); approvals with Dana's rejection, the re-draft and the hold; Memento scrub to Apr 9 with a "not knowable after" wall and a refusal stamp if the judge tries to open the Jul 8 export; the scorecard; the memo; the payoff screen with the seat line. All numbers come from the API, never from text in the UI.

Deep mode tabs: Reconcile (four recons, filters by reason, the Priya handoff panel); Trace (files with highlighted cells and their links, confidence, stale flags; "Built on / Built upon" toggle per item); Graph (React Flow lanes: Sources, Ledger, Metrics, Human files, Actions; dotted background; fixed dagre layout); Evaluate (the seven questions with Jade's verdict on each claim); Approvals (inbox, holds, clock); Memo; Time travel (TimeMap per source, ledger as of any date); Scorecard; Lessons (proposed, gate result, approve); Access (what the agent can read, what it can only draft, what it can never touch).

Design: "the ledger and the recall notice". Warm paper background `#F7F4EE`, ink `#1C1B19`, muted `#6B675F`, hairlines `#E3DED4`, recall red `#C62828` (invalidated), cleared green `#2E7D32`, caution amber `#B26A00` (needs a human), action blue `#1F5FBF`. Serif display (Newsreader), UI sans (IBM Plex Sans), mono with tabular numbers for every figure (IBM Plex Mono), all via `@fontsource` packages bundled locally. Every state has an icon and a pattern, not just a color. Body text at least 16 px, node labels at least 18 px, Stage text at least 22 px. Light theme only. No gradients, no default component-library look. A footer bar with live counts and keyboard hints.

Judge doors: "Change any number" (the correction form above), "Why did you do this on that date?" (pick an executed action, replay its inputs as of then), "Try to make it peek" (request a future version: refused with both timestamps). One-key reset to the canonical state. Kiosk: after 60 seconds idle, Stage mode plays itself with captions; any input hands control back.

---

## 15. Checkpoints (each one leaves a demoable project)

| Checkpoint | Contents | Acceptance |
|---|---|---|
| CP1 world | Generator, refcalc, human files, answer key, database load | All Section 5.1 targets asserted in tests; `make world` under 30 s |
| CP2 detect | Four reconciliations with learned lags and habits, subset-sum, Priya handoff | Exactly six exceptions (X1 to X6), P1 recognized as known, all noise cleared with the right reasons |
| CP3 trace | Memento, lineage tracer, ripple | Every lineage truth correct; H1 stale; X1 impact matches Appendix A; Memento refuses future reads |
| CP4 judge | Materiality engine, agent playbook v1, Error Evaluations, Jade | Jade overrules X1 materiality and X3 classification and flags lender routing; aggregate $662k / $1.118M |
| CP5 act | Approvals, SoD CHECK, holds, reminders, escalation, simulated people, re-draft, memo | Dana rejects the Q1-dated entry, the agent re-drafts in June, self-approval raises, bonus run held; memo renders |
| CP6 prove | Case library, scorecard, baselines | `make eval` writes latest.json with every metric |
| CP7 learn | Lessons, approval, regression gate, held-out v1 vs v2 | Four lessons proposed, gate results shown, v2 beats v1 on held-out |
| CP8 UI | Stage and Deep modes, all tabs, design tokens, judge doors | The full Section 2 sequence runs from the keyboard offline |
| CP9 polish | Kiosk, screenshots at 1280x720 and 1920x1080, README, PITCH.md, DEVPOST.md | Demo check passes with the network off |

Cut in this order if behind: kiosk; the optional LLM baseline; the clock fast-forward; the Access tab; generated variants beyond 15; the held-out learning experiment (keep lessons and the gate). Never cut: X1 end to end with the human files, Jade's overrule, Dana's rejection and re-draft, the Memento replay, the scorecard from real runs, offline replay, the reset.

---

## 16. Definition of done

- `make setup && make world && make test && make eval && make demo` works on a fresh clone of the repo on macOS (Apple Silicon), with no network after setup.
- The Stage sequence runs end to end from the keyboard with numbers from the API.
- The scorecard shows real metrics, the baselines and v1 vs v2.
- README covers: what it is, how to run, architecture, where AI is and isn't used, Memento's time-pinning deviations and why not 425, real vs simulated. PITCH.md has the 3-minute script with real numbers and the Q&A in Appendix B. DEVPOST.md is ready to paste.

---

## 17. A /goal for Claude Code (paste after saving this file as SPEC.md)

```
/goal Build Trackback v3 per SPEC.md, checkpoint by checkpoint (Section 15). Never ask questions or wait for approval; follow CLAUDE.md. The goal is met only when all of these have been shown in this conversation by running the command and pasting its output: (1) `make test` exits 0 and prints the Section 5.1 calibration assertions passing; (2) the reconciliation run prints exactly six exceptions X1 to X6 and P1 as a known item; (3) the tracer prints every answer-key lineage truth correct and the deck's $32.6M flagged stale; (4) the X1 ripple prints 40 invalidated, 23 still valid and 5 compensations, matching Appendix A; (5) the materiality output prints rollover 662000 and iron curtain 1118000 and leverage 3.0208; (6) Jade's review prints the three overrules or flags in Section 8; (7) the approvals demo prints Dana's rejection, the June re-draft and a raised self-approval error; (8) `make eval` writes data/eval/latest.json and you print it; (9) a Playwright screenshot of each Stage beat exists under docs/screenshots/ and you describe each one; (10) STATUS.md lists every checkpoint as done. Commit every 45 minutes. Run `TZ=America/Los_Angeles date` at each checkpoint; if it is 2026-10-25 04:00 or later, stop new work, freeze, update STATUS.md and consider the goal met.
```

---

## Appendix A. X1 impact answer key (artifact ids as in the generator's lineage truth)

Invalidated (on the prototype world: 30 traced numbers and claims, the 5 derived Excess cells for R1 to R5, and 5 actions, so 40 in total):
- Certificate: Adjusted EBITDA (32.0M to 31.25M), leverage (2.95x to 3.02x), compliance statement (Compliant to BREACH).
- Workbook: Revenue TTM, Adjusted EBITDA TTM, leverage, status, headroom ($533k to minus $217k), regional EBITDA R1 to R5, bonus R1 ($15,988 to $7,588), R2 ($12,015 to $4,815), R4 ($9,993 to $5,193), Q1 pretax, Q2 tax installment.
- Deck: Q1 revenue, Adj. EBITDA (stale and changed), membership revenue, membership growth (2.8% to 0.4%), leverage, gym revenue (reconstructed sum), the covenant sentence, regional EBITDA R1 to R5.
- Actions: certificate sent (corrected certificate and lender notice, Sam), bonus paid R1 ($8,400), R2 ($7,200), R4 ($4,800) (offset next bonus, Lena), tax paid ($195,000, reduce next installment, Dana).

Still valid (with reasons):
- Bonus R3 and R5, and their paid actions: conclusion_unchanged ($0 before and after).
- Regional EBITDA R6, bonus R6, deck R6, bonus paid R6: not_consumed (Desert Southwest gyms only).
- Term loan, cash, net debt (workbook and certificate): different_line_item.
- Max leverage (workbook, deck, certificate), all six targets, tax rate: policy.
- Excess R6: inputs_unchanged.

## Appendix B. Hard questions and answers

- "Is this just an LLM?" No. A matching engine finds the error, the graph finds what it touched, code decides whether it matters, and the LLM explains and gets checked. The scorecard shows the plain-LLM baseline losing.
- "Isn't a context graph common?" Yes, and we use one as plumbing. The new parts are recovering links for hand-typed numbers nobody linked, the accounting judgment (SAB 108 both ways, qualitative tests, aggregation), and a reviewer that is itself scored.
- "Workiva and DataSnipper do this." Workiva propagates links people set up by hand; DataSnipper helps auditors match numbers to documents. We find the links nobody drew and tell you whether the break matters.
- "Why isn't X3 a restatement?" The invoice arrived May 20, after the Apr 10 close; the accrual was the best estimate then. Memento shows it. That's a change in estimate, booked in May.
- "3.7% or 4.7% is immaterial." Under a naive 5% rule, yes. Rollover passes at $662k; iron curtain fails at $1.118M; SAB 108 requires both. And it flips the covenant, which SAB 99 names as a qualitative factor.
- "How do you know the unaffected items are right?" Most are structural (different region, different accounts, policy terms); the rest are arithmetic (recomputed and the value or conclusion didn't move). Only prose goes to the LLM, and it's labeled.
- "Does it learn?" From Jade's overrules and humans' rejections, as lessons the controller approves, gated by a full regression run, measured on held-out cases.
- "What stops it from doing damage?" Read-only on sources, drafts only, segregation of duties in the database schema, holds on risky actions, and every claim cites evidence.
