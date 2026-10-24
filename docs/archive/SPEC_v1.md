# TRACKBACK: build prompt

Hacking has started. Build Trackback, end to end, from this document. Krishna (Penn State CS and Computational Math, two PayPal AI/ML internships) is the human on the team. He will check in occasionally, but you will often run unattended for hours, including overnight. His teammates do not write code; they handle slides and the video.

Part 1 (this part) is the authoritative build spec. Part 2 (the appendix) is the full design document written during ideation. It is the source of truth for accounting logic, the answer key, the schema and the pitch, but it predates some decisions. Wherever Part 1 and Part 2 disagree, Part 1 wins. Section 2 of Part 1 lists every known override.

---

## 0. The event and the rules you must respect

- Rule: Ideation (this document) was allowed. All code, the synthetic company generator and its data are created by you during the event. Public datasets Krishna downloaded in advance (SEC, FRED) are allowed and live in `data/public/`.
- Nobody on the team contacts sponsors or organizers for help. Don't suggest it.
- Venue Wi-Fi was bad last year. The final demo must run with the network off. Internet is used only during the build (package installs, recording LLM responses).
- Machine: Krishna's MacBook, Apple Silicon. Assume macOS with Homebrew, Python 3.11+, Node 20+, git. No Docker in the plan.

### Finance requirements

Build the system a finance team would bring on board. Pick a company and one corner of its finance team (a few seats). Build the autonomous system to fill them, and the company it works in: the software it uses, the people it answers to, and the mistakes hiding in its data. Be imaginative about the company and strict about how it works underneath.

What makes it hard:
- Sources that disagree: the bank, the ledger and the contract each tell a slightly different story. Acting well means knowing which one to trust, and saying why.
- Time: "What happened in March should change what the system does in June."
- Working with others: approvers are busy, colleagues hand work over half done, and the controller sometimes says no.
- Limits: whoever requests a payment can't be the one who approves it.
- Explainable and accountable: every call traces back to the data, rule or person behind it, no matter how long ago.

How they judge:
1. Is it real enough? Realistic data, a messy problem, proof it works.
2. Would you hire it? For which seats? Limited access, a clean record, knowing when to ask.
3. Did we see something new?
4. The moment: it catches what others missed, recovers from something going wrong, or defends a decision when questioned.

What to submit: a demo video that opens with the moment; a live demo running for real (judges may try a scenario of their own); one line on the seats the system fills; proof it works (what's real, what's simulated, how you know: planted errors with an answer key).

---

## 1. What Trackback is

Name: Trackback. It revives TrackBack, the 2002 Movable Type protocol that let a site notify another site when it referenced it. Trackback does that for numbers inside a company, in the forward direction. The replay feature is called Memento, after RFC 7089, the HTTP time-travel standard.

Tagline: "Trackback traces any correction forward."

One paragraph: Three AI agents do real record-to-report work for Tidewall Climbing Co., a fictional chain of six California climbing gyms. Every source they read is stored as versioned claims with two clocks (when the fact applies, and when the system learned it). Every number, report sentence, forecast cell and executed action they produce records exactly which claim versions it relied on. When a source is corrected, Trackback walks the dependency graph forward, recomputes numbers in plain code, stops where values or conclusions don't move enough to matter, asks an LLM only about prose, and returns a verdict for every touched artifact: invalidated, unaffected (with a reason), needs review, or unprovable. Actions that already moved money get a compensating action from a fixed menu, routed to a human approver who is not the preparer. Memento replays any past decision exactly as the system saw it, and refuses to serve anything published after the decision time.

Seats line (use verbatim on Devpost and in the pitch): "Trackback does the senior close accountant's and the reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign."

The hero moment (E11): on July 8 the billing system admits a February migration double-counted $118,000 of March revenue. A naive "under 5% of annual pretax" rule shrugs. Trackback follows it into the Q1 lender compliance certificate (leverage 2.95x becomes 3.03x against a 3.00x covenant, a breach), two board-deck tiles, one gym manager's bonus and the Q2 tax estimate, and shows a list of things it checked and cleared, each with a reason. Its first correcting entry is dated into locked Q1 and gets rejected by the controller; it re-drafts. Memento replays April 10 to show the duplicate was visible in the export the agent read, so Trackback owns the miss and proposes a dedupe control.

---

## 2. Locked decisions and overrides of Part 2

Treat every line here as final. Do not reopen these.

1. Product name is Trackback everywhere (UI, README, code package `trackback`, Devpost). In Part 2, "RECALL" is the old working name for Trackback. Ignore Part 2's naming section and its "Recall Notice" recommendation.
2. Keep the product-recall metaphor: every number carries a lot code chip (`LOT 7F3A`), and a correction arrives as a card titled "RECALL NOTICE". Trackback is the system; a recall notice is the event.
3. Problem stats for slides and pitch, in this order:
   - Headline: MemDerive (arXiv 2610.25373). Across four agent memory systems, on derived state every system fell behind simple BM25 retrieval, though the same answer model reached 96.01% when given the supporting events. Memory systems "rarely propagate implicit changes, which no new record states." The paper's three design principles: gather inputs along the derivation, store rules with their versions, maintain derived states through recorded dependencies. Trackback implements all three.
   - Backup: STALE (arXiv 2605.06527): the best evaluated model reached only 55.2% overall accuracy on stale-memory cases.
   - Never use the "91 to 100%" figure anywhere.
4. Team and roles: you build everything. Part 2's four-person plan (P1 to P4) becomes your own sequence of phases in Section 9. Krishna is the presenter.
5. Agents: three real agents doing record-to-report work (Section 6). The controller and CFO are humans, represented in the UI by an approvals inbox that Krishna or a judge clicks. Do not build agents that approve anything.
6. Runtime model: Claude through the Anthropic API, behind a record/replay cache. Agents use `claude-sonnet-5-5`. The LLM judge uses a different model, `claude-opus-5-5`, to avoid self-preference. Both names live in config. Use the Citations API for prose. If a quick test in phase 1 shows citations don't work with these models, switch to the claim-block-ID fallback in Section 7.4 and log it.
7. Muse Spark (Meta) is a stretch goal only: a provider adapter so the Reporting Analyst's prose can be generated by Muse Spark 1.1 to show "Trackback doesn't care which model wrote it." Attempt it only after the freeze-critical list in Section 10 is done, timebox it to 90 minutes, and drop it if the API key is missing or anything misbehaves.
8. Real-data scenario is a core feature, not a stretch: a "Real world" tab built from Monolithic Power's (MPWR) actual FY2024 restatement using SEC XBRL data (Section 8). Use Quantum Corp only as a written precedent, never on stage.
9. No x402, no crypto, no Convex, no XTDB, no Formance, no Docker, no pywb. SQLite plus a hand-rolled Memento service.
10. Do not send HTTP 425 on the wire. Refusals are 403 (version exists but postdates the pin) or 404 (nothing existed as of the pin) with an RFC 9457 `application/problem+json` body. Header name: `Trackback-Pinned-At`. Problem type: `https://trackback.local/problems/temporal-pin-violation`. 425 appears only as a joke on a slide, with the explanation from Part 2.
11. Present the future-refusal as Trackback's own time-pinning profile over RFC 7089 (plain RFC 7089 returns the nearest version, even a later one). The four deviations are in Part 2 and must be listed in the README.
12. Apply all five answer-key fixes from Part 2 ("Fixes the key needs before anyone builds it"): E04 dated July 7; E11 materiality wording; headroom is $63.5k after E02 and E10; E11 allocated across gyms (Section 5.4); unverified rules labeled "company policy".
13. Timeline consistency rule (new): every correction's transaction time must be later than every artifact it is supposed to invalidate or touch, and no later than the demo "now" of July 8, 2026, 09:00 PT. The E11 group (E11, E12, E22, E23) arrives live on July 8. Required dates are in Section 5.3.
14. Demo clock is pinned to 2026-07-08T09:00:00-07:00 in config. Nothing reads the real wall clock except logs.
15. One process for the demo: FastAPI serves the API, the Memento endpoints and the built frontend on `http://localhost:8000`.

---

## 3. How you work while unattended

- Never stop to ask a question. When something is ambiguous, pick the simplest option consistent with this spec, write one line in `DECISIONS.md` (what, why, alternative), and keep going.
- Work in a loop: pick the next item in Section 9, implement it, run tests, commit, update `STATUS.md`. Repeat.
- `STATUS.md` always holds: current phase, what works (with the command that proves it), what's broken, the next three tasks, and the time of the last update. Krishna reads this first when he checks in.
- Commit at least every 45 minutes and at every milestone, with clear messages. Tag milestones (`m1-schema`, `m2-world`, and so on). Never rewrite history.
- Timebox any single bug to 45 minutes. If it's still broken, take the fallback in this document or simplify, log it, move on.
- Tests are the definition of done. Each phase has acceptance checks. Don't mark a phase done until its checks pass.
- Don't touch anything outside the repo. No global config changes. No `sudo`. No deleting files outside the repo.
- Secrets live in `.env` (git-ignored). Provide `.env.example`. Never print keys in logs or commit them. Keys: `ANTHROPIC_API_KEY`, optional `META_API_KEY`, optional `FRED_API_KEY`.
- Network calls allowed during the build: package installs, Anthropic API (record mode), Meta API (stretch only). The app itself never calls any other external service. The final demo works in replay mode with networking disabled.
- Install every dependency in the first hour while the network works, and vendor fonts and libraries locally (no CDNs at runtime).
- Keep LLM spend sane: every call goes through the cache; never loop on live calls; cap agent turns per run.
- Never invent real-world facts. Synthetic numbers for Tidewall are fine and must be labeled synthetic. For MPWR, use only values parsed from the downloaded files, and fall back to the figures in Section 8 only if a file is missing, labeled as such.
- If a public data file Krishna was supposed to download is missing, log it in `STATUS.md` under "Needs Krishna" and continue with the fallback.

---

## 4. Repository layout

```
trackback/
  README.md            # what it is, how to run, the four Memento profile deviations, real vs simulated
  STATUS.md  DECISIONS.md  TIMELINE.md  PITCH.md  DEVPOST.md
  .env.example  .gitignore  Makefile
  backend/
    pyproject.toml
    trackback/
      config.py            # DEMO_NOW, model names, materiality memo defaults, paths, LLM mode
      db.py  schema.sql    # SQLite, append-only helpers, as-of query helpers
      memento.py           # /r /tg /m /tm endpoints plus the time-pinning profile
      tools.py             # the only data tools agents get (Section 7.2)
      llm/gateway.py       # record | replay | fallback cache, keyed per Part 2
      llm/anthropic_provider.py  llm/muse_provider.py (stretch)
      agents/base.py  agents/close_accountant.py  agents/reporting_analyst.py  agents/covenant_comp.py
      engine/diff.py  engine/propagate.py  engine/materiality.py  engine/compensation.py  engine/fence.py
      ledger.py  approvals.py  judge.py  norms.py
      realworld/mpwr.py  realworld/alfred.py
      api.py  main.py
    scripts/
      generate_tidewall.py   # deterministic, seeded synthetic world
      build_history.py       # runs the agents at their historical pinned times, applies pre-July-8 corrections
      apply_correction.py    # CLI: apply any correction id and print the impact set
      eval.py                # answer key vs findings, baselines, leak test, replay fidelity -> data/eval/latest.json
      snapshot.py            # write and restore data/snapshots/canonical.sqlite
      demo_check.sh          # airplane-mode readiness check
    tests/
  data/
    public/                # pre-downloaded: mpwr_companyfacts.json, mpwr_8k_20260226.htm, alfred vintages
    generated/             # Tidewall source documents and fixtures
    answer_key/answer_key.yaml   # frozen at milestone M3
    llm_cache/             # optional export of the cache table
    snapshots/
    eval/
  frontend/                # Vite + React + TypeScript, React Flow + dagre layout, Tailwind
```

Make targets: `make setup`, `make world` (generate plus history), `make test`, `make eval`, `make demo` (restore canonical snapshot, replay mode, serve on 8000), `make reset`.

---

## 5. The world: Tidewall Climbing Co.

Part 2 has the full company: numbers, calendar, systems, chart of accounts, people, segregation-of-duties rules and the 23-item answer key with correct handling and "must stay valid" columns. Build exactly that. This section adds what Part 2 leaves open.

### 5.1 Granularity

- FY2025 (January to December 2025): monthly summaries per gym per account, enough to compute trailing-twelve-month (TTM) EBITDA, FY2025 comparatives (E20), and the Bayline Power winter accrual history (E-norm needs ten winter months: Nov 2024 to Mar 2025 and Nov 2025 to Mar 2026).
- January to July 8, 2026: transaction-level for every account the answer key touches (dues batches, ACH returns, AP invoices, accruals, deferred revenue schedules, contract documents, FX rates, payroll and bonus records, the bank feed). Other accounts can stay monthly.
- Source documents are versioned text or JSON files (billing export CSV, bank statement, invoice text, contract amendment text, FX rate table, credit agreement text, materiality memo, comp plan). Each version becomes a memento with its own capture time.

### 5.2 Calibration targets (assert these in tests)

- Net debt $16.5M (term loan $18.0M, cash $1.5M).
- Q1 2026 as reported: TTM Adjusted EBITDA $5.600M, leverage 16.5 / 5.6 = 2.946, displayed 2.95x.
- After E02 ($22,500 route setting) and E10 ($14,000 legal): TTM EBITDA $5.5635M, leverage 2.966x, still compliant. Headroom $63.5k.
- After E11 as well ($118,000): TTM EBITDA $5.4455M, leverage 3.030x, breach of the 3.00x covenant.
- Adjusted EBITDA definition (write it into the synthetic credit agreement as a claim): includes legal and route-setting costs; excludes realized FX gains and losses and depreciation.
- FY2026 budget: revenue $42.0M, EBITDA $6.0M, pretax $3.2M. Materiality memo: annual $160k, quarterly performance $60k, clearly trivial $8k, flux threshold more than 10% and more than $25k.
- Every journal entry sums to zero (integer cents). No row is ever updated except to close `tx_to`.

### 5.3 Required timeline (all 2026, PT)

Write the full table into `TIMELINE.md` before generating data. Fixed points:

| When | Event |
|---|---|
| April 10 | Q1 hard close by the Close Accountant (pinned run). Q1 locked |
| April 20 | UC Sierra change order (E07) |
| April 24 | Board deck published by the Reporting Analyst (pinned run) |
| May 15 | Q1 compliance certificate drafted by the Covenant agent, signed by CFO, sent to the lender (executed action) |
| May 20 | E10 discovered: March employment-counsel invoice found un-accrued |
| May 27 | E02 discovered: March route-setting invoice (dated April 3) surfaces in the AP inbox |
| May 31 | GM quarterly bonuses paid (executed action) |
| June 3 | E03 R01 returns received |
| June 5 | Demand forecast run using the employment-series vintage available that day (E19) |
| June 12 | AP payment run (E14 duplicate blocked by the pre-execution fence) |
| June 15 | Q2 federal estimated tax paid (executed action) |
| July 7 | E04 R10 return received |
| July 8, 09:00 | Demo "now". June close in progress |
| July 8, live | E11 recall notice arrives on stage; E12, E23 follow from it; E22 happens during its correction |

Place the remaining items (E01, E05, E06, E08, E09, E13 to E18, E20, E21, E-norm) on dates that satisfy rule 13 in Section 2 and the accounting in Part 2. If an item's Part 2 description implies an impossible ordering, keep its accounting logic, move the date, and log it.

### 5.4 E11 allocation across gyms (fixes Part 2 issue four)

The $118,000 duplicate hits gyms as: G1 Oakland $26,000; G2 San Jose $0 (no annual prepaid members in the migrated batch); G3 Sacramento $22,000; G4 Fresno $32,000; G5 Santa Cruz $18,000; G6 Berkeley $20,000.

GM bonus = 4% of gym quarterly EBITDA above target. Set Q1 gym EBITDA versus target so that:
- G4 Fresno is above target by well over $32k, so its bonus is overpaid by $1,280 (invalidated, E12 offset).
- G1 Oakland is above target by well over $26k, overpaid by $1,040 (invalidated, same offset path).
- G3, G5 and G6 are below target both before and after, so their bonus was $0 and is still $0 (cleared, reason `conclusion_unchanged`).
- G2 is untouched (cleared, reason: did not consume the corrected claims).

The duplicate is a revenue-recognition entry (deferred revenue to revenue). No cash moved, so every cash artifact (13-week forecast, cash KPIs) must clear.

### 5.5 Answer key file

`data/answer_key/answer_key.yaml` lists, for every correction, every artifact the correction reaches through the graph, with the expected verdict (`invalidated`, `unaffected`, `needs_review`, `unprovable`), the expected reason, and any expected compensation (from the fixed menu) with its approver role. Write it from Part 2's table before tuning the engine. Freeze it at milestone M3: commit, tag `answer-key-frozen`, and write the commit hash and timestamp into `STATUS.md` and the proof page. Any later change goes in `data/answer_key/CHANGELOG.md` with a reason. Include the decoy categories Part 2 requires (different period, different line item, immaterial, offsetting, qualitative prose still true, sign flip, retraction with no replacement).

---

## 6. The three agents

All three run through `agents/base.py`: a tool-use loop over the Anthropic Messages API via the cache gateway. Each run has a `run_id` and a server-side `pinned_at`. Max 25 tool turns per run. Agents never see raw files or the database. They only have the tools in Section 7.2, and every read goes through the Memento service over HTTP on localhost. That is what makes provenance complete by construction.

1. Close Accountant (seat: Senior Accountant, Close and Reporting). Runs the Q1 close (April 10) and the June close (July 8). Drafts accruals (utilities, route setting, legal), applies norms the controller approved, books true-ups and out-of-period entries, maintains the misstatement log, drafts correcting entries when Trackback reports an invalidation. Proposes only. Never approves.
2. Reporting Analyst (seat: Reporting / FP&A Analyst). Builds the Q1 board deck (KPI tiles plus 6 to 10 commentary sentences), budget-versus-actuals lines, flux commentary, and the 13-week cash forecast. Every sentence is produced through the citations path; every number through `emit_number`.
3. Covenant and Comp agent (seat support: covenant certificate and payouts). Computes TTM Adjusted EBITDA and leverage from the credit agreement's definition, drafts the quarterly compliance certificate (an action executed only after the CFO approves), computes GM bonuses and sales commissions (payment actions approved by HR or VP Sales plus the controller), and computes the Q2 estimated tax payment.

Agent prompts must include: the seat description, the company's policies relevant to the task (as claims they read via tools, not pasted facts), the rule that numbers are only produced via `emit_number`, and the instruction to ask (route to `needs_review`) when timing or materiality is ambiguous.

Historical runs (`scripts/build_history.py`) execute each agent at its pinned time in timeline order, in record mode, so the graph and the cache fill up with real agent output. In the demo, `make demo` uses replay mode: identical outputs, no network.

Planted recovery (E22): when the Close Accountant drafts the E11 correcting entry, its first draft is dated March 31 (locked) and the workflow's auto-route tries to set approver = proposer. Make this deterministic: the E11 correction task tells the agent to "book the correction to the period it belongs to," and the JE tool's default date is the original period, so the first draft lands in Q1. The schema's `CHECK (proposer <> approver)` rejects the self-approval, and the error shows in the UI event log. The draft then sits in the controller's inbox flagged "period locked". The controller rejects with the reason from Part 2. The agent re-drafts in Q2 with an out-of-period tag, and the lender package correction goes to the CFO separately. Memento keeps both drafts and the rejection.

---

## 7. Engine and services

Build what Part 2's architecture section specifies: append-only bitemporal SQLite with the schema given there (rename nothing except the `Recall-Pinned-At` header and problem type URL), the Memento service with Pattern 2.1 and the four-deviation time-pinning profile, the propagation algorithm (claim diff, structural seeds, Kahn topological walk, early cutoff, materiality and conclusion checks, prose to the judge, actions to compensation, `unprovable` for retractions), the pre-execution fence, the ledger in the same file, approvals with the schema-level segregation-of-duties check, and the gateway where replay and the cache are the same mechanism. Additions and specifics:

### 7.1 Materiality

`engine/materiality.py` takes the delta, the artifact's line and period, and the artifact's stated conclusions (`conclusions_json`: covenant max, bonus tier or target, growth sign, rounding of displayed value), and returns a verdict plus reason. Thresholds come from the materiality memo claim, so changing the memo is itself a correction that propagates. Aggregate all unbooked items in the misstatement log and test them together.

### 7.2 Agent tools (the only door to data)

- `get_document(doc_id)`: returns the memento as of the run's pin, with memento URI, version id, Memento-Datetime and the claim ids it contains. Writes a `reads` row. Refusals are logged too.
- `search_claims(query, entity?, line_item?, period?)`: searches claims visible as of the pin.
- `get_claim(claim_id)`.
- `emit_number(name, formula, inputs, period, line_item, conclusions?)`: Trackback evaluates the formula with a safe expression evaluator (no `eval`) over the named inputs. Every input id must appear in this run's reads (or be an artifact produced in this run), or the call is rejected. The model never does arithmetic.
- `emit_sentence(text_request, claim_ids, period, line_item, conclusions?)`: triggers the separate citations call (Section 7.4) and stores the sentence with its citation edges.
- `propose_journal_entry(lines, posting_period, orig_period, memo, correction_id?)`.
- `propose_action(kind, params, supporters)`: for certificate send, bonus or commission payout, payment run, tax payment. Goes through the fence and into approvals.
- `route_to_human(reason, artifact_ids)`: the "knowing when to ask" path.

Also expose `get_document`, `search_claims` and `get_claim` through a small MCP server using the official Python MCP SDK if time allows (low priority, nice for the technical story).

### 7.3 Corrections input (judge's red pen)

`POST /api/corrections` takes a structured form: source or claim id, new value or new document version, correction type from a preset list (revised invoice, bank revision, FX fix, duplicate removal, contract amendment, retraction), and the required question "When did this fact first exist?" (before the original artifact was made, or after). The answer sets `kind` (error versus estimate) and `knowable_at`. An optional free-text box parses into the same form with the parse shown for confirmation. Validate numeric ranges. The deterministic impact set returns in under a second. Prose verdicts stream in afterwards labeled "drafting explanation".

### 7.4 Prose provenance

Primary: Anthropic Citations API with each claim passed as one block of a custom-content document, so a `content_block_location` citation maps one-to-one to a claim id. Citations can't be combined with structured outputs, so prose is its own call. Fallback (if citations fail in the phase 1 test, or for the Muse adapter): pass claims as numbered blocks with ids, require the model to append `[claim:ID]` markers, and validate every marker against the run's reads. Either way, flag any sentence with zero valid citations and any claim read but never cited (becomes "suspect, low priority" under a correction instead of invalidated).

### 7.5 LLM judge

Only for prose edges. Structured JSON output: verdict, rationale, proposed rewrite. Temperature 0, through the cache, model `claude-opus-5-5`. It never overrides a numeric verdict. Low confidence goes to `needs_review`. Deterministic precheck first: if the sentence literally contains the old number, propose a substitution without calling the model.

### 7.6 Learned norms

Build the norms miner from Part 2 ("Six norms Trackback can learn"). Minimum: the Bayline Power accrual factor (1.08 for November to March, from ten winter months of +7.8% median shortfall) and the Pacific Lumen Labs short-pay rule (auto-clear up to $50 to bank fees; the June $1,035 short-pay clears $35 and routes $1,000 to a person). Norms are claims with versions and provenance, inactive until the controller approves, valid from the approval date, never applied retroactively. Hard-coded deny-list shown in the UI: never learn a retry policy for R10, R05 or R07 returns. Stretch: the recursive beat (correct one Bayline invoice in the history and the norm goes back to `needs_review`).

---

## 8. Real-world tab: Monolithic Power's FY2024 restatement (core feature)

Purpose: prove the engine works on real data, and show the cleanest "touched, still valid" case. Revenue didn't change; net income and EPS did.

Inputs Krishna downloaded in advance to `data/public/`:
- `mpwr_companyfacts.json` from `https://data.sec.gov/api/xbrl/companyfacts/CIK0001280452.json`
- `mpwr_8k_20260226.htm`, the 8-K Item 4.02 filing
- Optional `companyfacts.zip` subset

Build:
1. Inspect the JSON and write down the actual field names in `DECISIONS.md` before coding (expected per fact: `val`, `accn`, `fy`, `fp`, `form`, `filed`, `frame`, `start`, `end`; verify).
2. Extract FY2024 facts for `Revenues` (or the revenue concept MPWR actually uses), `NetIncomeLoss`, `EarningsPerShareDiluted`, and dividends per share if present, from two filings: the original FY2024 10-K (filed in early 2025) and the later filing that carries the restated FY2024 values (filed in 2026). Also FY2023 values for growth comparisons. Each filing becomes a source version, with its `filed` date as the capture time. Same claim key, two vintages.
3. Pinned at a date after the original 10-K and before the restatement, the Reporting Analyst writes a short analyst note: revenue growth sentence, net income growth sentence (for example "net income more than doubled"), net margin number, diluted EPS growth number, dividend payout ratio if dividends are available, and one summary sentence.
4. Apply the restatement as a correction with `knowable_at` equal to the 8-K date (February 26, 2026), not earlier. From the analyst's point of view the error was not knowable before the company disclosed it, so Memento shows the note was right as of then.
5. Expected outcome (verify against the parsed data, don't hardcode): revenue-based artifacts cleared (`different_line_item` or claim unchanged); net margin, EPS growth and payout ratio invalidated; a "more than doubled" style sentence cleared with `conclusion_unchanged` if the restated value still satisfies it. Add these to the answer key as a separate scenario before the freeze.

Fallback only if the JSON is missing: use the 8-K's stated figures (FY2024 net income $1,786.7M restated to $1,592.1M; diluted EPS $36.59 to $32.60; revenue $2,207.1M unchanged; cause: deferred taxes on a one-time foreign tax incentive), label the tab "figures from the 8-K text", and log "Needs Krishna".

ALFRED (E19): if `data/public/` has the employment-series vintages, use them for the June 5 forecast and a later vintage as the correction. If not, cut E19 (E07 already covers "defends a decision").

---

## 9. Build sequence with acceptance checks

Hours are from the start of hacking. If you're ahead, move on; if you're behind, apply the cut list in Section 10.

| Milestone | By hour | Deliverable | Acceptance check |
|---|---|---|---|
| M0 setup | 1 | Repo, Makefile, deps installed (backend and frontend), `.env.example`, a one-call Anthropic test including one Citations API call, `STATUS.md` started | `make setup` passes; citations test result logged in `DECISIONS.md` |
| M1 schema and Memento | 5 | `schema.sql`, append-only helpers, as-of queries, Memento endpoints with the pinning profile and problem+json refusals | Tests: TimeMap lists versions; TimeGate 302s correctly; post-pin fetch gets 403; pre-existence gets 404; missing Accept-Datetime in a pinned session resolves to the pin; append-only and sum-to-zero invariants |
| M2 world | 10 | `TIMELINE.md`, `generate_tidewall.py` (seeded), all sources and versions for the 23 items plus the norm, MPWR loader | Tests: calibration targets in Section 5.2; every planted item exists in the data; every date obeys rule 13 |
| M3 answer key frozen | 11 | `answer_key.yaml` covering every correction and reached artifact, including MPWR | Tag `answer-key-frozen`; hash in `STATUS.md` |
| M4 engine | 15 | Claim diff, propagation with early cutoff and materiality, compensation menu, fence, approvals with SoD check, ledger | `apply_correction.py E11` prints the right invalidated and cleared sets on hand-built artifacts; E01, E02, E10 verdicts match the key |
| M5 agents and history | 20 | Three agents, tools, citations path, judge, `build_history.py` in record mode, cache populated | Full history builds; artifact count 60 to 150; every number has numeric edges; every sentence has citations; E14 blocked by the fence on June 12 |
| M6 E11 end to end | 23 | E11 live correction with E12, E23, E22 flow and compensations | Running E11 from the canonical snapshot yields 3.03x breach, the bonus results in Section 5.4, cash artifacts cleared, E22 reject and re-draft recorded |
| M7 UI | 28 | Three-pane UI, ripple, scrubber with the future wall, approvals inbox, norms panel, Real world tab, proof page, presenter mode | Full demo walkthrough works in the browser at 1280x720 |
| M8 eval and proof | 30 | `eval.py` with metrics and baselines B1 to B3 (B4 degraph optional), leak test, replay fidelity; proof page reads `data/eval/latest.json` | Numbers generated, not typed; zero leaks; replay fidelity reported honestly |
| Freeze | 30 | Feature freeze, canonical snapshot written | `make demo` runs with Wi-Fi off; `demo_check.sh` passes |
| Polish and docs | 30 to 34 | README, `PITCH.md` with real counts, `DEVPOST.md`, video shot list, bug fixes only | Krishna can run the whole demo from `PITCH.md` alone |

---

## 10. Cut list and never-cut list

Cut in this order when behind: Muse adapter; MCP server; degraph baseline B4; the recursive norm beat; ALFRED (E19); norms beyond Bayline and Pacific Lumen; the Citations API path (use the marker fallback); extra answer-key items beyond those carrying the demo (but keep at least 15 items in the eval).

Never cut: the E11 ripple with green cleared nodes and reasons; the E22 rejection and re-draft; the April 10 Memento replay and the future refusal; the MPWR Real world tab; the eval script driving the proof page; the one-key reset; replay mode that runs the whole demo offline.

---

## 11. UI spec

Follow Part 2's UI section (lot codes, recall-notice card, three panes, ripple timing, projector rules). Specifics:

- Header: "Trackback" wordmark, company switcher (Tidewall / Real world: MPWR), the pinned clock ("Today: July 8, 2026"), mode badge (Replay or Record).
- Left pane: ledger-style table of artifacts with lot chips and status badges (VALID, STALE, RECALCULATED, NEEDS REVIEW, COMPENSATION PROPOSED). Clicking a chip shows backward trace arrows.
- Center: React Flow graph, left to right, dagre layout, fixed and seeded. Max about 25 visible nodes in the hero view; collapse the rest into "+N more cleared".
- Bottom: time scrubber with TimeMap ticks per selected source, the as-of cursor, and a hatched "future wall" labeled "Not knowable on <date>". Refusals show a stamp with both timestamps.
- Right drawer tabs: Claim history (versions, diffs as strikethrough), Approvals inbox (proposer, approver, decision, reason; approve and reject buttons with prefilled reasons), Norms (proposals, evidence, deny-list), 2x2 bitemporal view, Event log.
- Ripple: precompute (node, status, delay) and animate 150 ms per hop; red X invalidated, green check cleared with reason on hover, amber "!" needs action. Corner counter: "Naive (source-level): N. Trackback: X invalidated, Y cleared, Z need action", computed from the real B1 baseline.
- Three judge doors from Part 2: "Pick any number and change it", "Why did you do this on that date?" (dropdown of executed actions), "Try to make it cheat" (paste a doc id, plus a canned case where a document's text claims an earlier date than its capture time).
- Presenter mode with hotkeys, shown in a small cheat sheet overlay on `?`: `R` reset to canonical snapshot, `N` drop the E11 recall notice, `A` open approvals, `T` jump scrubber to April 10, `C` cheat attempt, `P` proof page, `W` Real world tab, `U` undo last judge edit.
- Light theme, labels at least 18 px, every status has an icon and a pattern besides color, all fonts and libraries bundled locally.

---

## 12. Proof page and eval

Build the metrics, baselines and proof layout from Part 2's proof section: precision, recall, F1 of invalidated; specificity on decoys; over-invalidation ratio versus B1; per-reason confusion matrix; compensation correctness; Memento leak test with an adversarial agent told to use the latest information (target 0 leaks); replay fidelity (target 100%, report the real number); judge agreement on prose edges with n stated. Baselines: B1 source-level invalidation, B2 no tracking, B3 ask-the-agent. The proof page shows the frozen answer key hash and the real-versus-simulated table. Every number on the page comes from `data/eval/latest.json`. Never round up, never fill placeholders by hand.

---

## 13. Docs you write for the team

- `README.md`: one-paragraph pitch, how to run (`make setup`, `make world`, `make demo`), architecture diagram in text, the time-pinning profile's four deviations, why not 425, real versus simulated, the requirements mapping table.
- `PITCH.md`: the 3:00 script from Part 2 with Trackback naming and the MemDerive stat, with the real counts from the latest eval and the E11 run filled in, hotkey cues per beat, the hard Q&A list with answers from Part 2, and the $80k utilities judge drill both ways.
- `DEVPOST.md`: title "Trackback", tagline, seats line, what it does, how we built it, real versus simulated, proof numbers, the TrackBack (2002) and Memento (RFC 7089) story, challenges, what's next. Tailored paragraphs for Most Technically Advanced, Microsoft "Built for the Real World" and CRS.
- Video shot list from Part 2's video table, renamed, opening with the ripple.

---

## 14. Definition of done

- `make demo` on a fresh clone plus the canonical snapshot runs fully offline.
- Dropping the E11 recall notice shows the breach, the cleared nodes with reasons, the compensations, the E22 rejection and re-draft.
- Scrubbing to April 10 shows the duplicated rows in billing export v1, and trying the July 8 export is refused with 403 and both timestamps.
- The Real world tab shows MPWR revenue artifacts cleared and EPS-based artifacts invalidated from parsed SEC data.
- The proof page shows real eval numbers and the frozen key hash.
- `STATUS.md`, `README.md`, `PITCH.md` and `DEVPOST.md` are current.

Start with M0 now. Then work through the milestones in order without waiting for input.

---

## For Krishna (not for the builder): before Friday

Allowed before hacking: reading, setup, account signups, downloading public data. Not allowed: writing project code or creating the repo.

1. Install Homebrew, Python 3.11+, Node 20+, git, a SQLite browser on the Mac.
2. Create an Anthropic API key with credits; test one call. Optional: Meta Model API key for the Muse stretch; optional FRED API key.
3. Download into a folder you'll later copy to `data/public/`: `https://data.sec.gov/api/xbrl/companyfacts/CIK0001280452.json` (save as `mpwr_companyfacts.json`, use a browser or set a User-Agent with your email), the MPWR 8-K from February 26, 2026 (save as `mpwr_8k_20260226.htm`), and optionally a few ALFRED vintages of an employment series.
4. Search the fictional names (Tidewall Climbing, Bayline Power, Kletterwerk, Summit Mats Supply, Pacific Lumen Labs, Northgate Biotech, Redwood Commercial Credit, UC Sierra) and "Trackback" on Devpost to make sure nothing real or same-named collides.
5. At hacking start: create an empty folder, put `.env` with your keys and the `data/public/` files in it, start the coding agent there, paste this whole file, and say "Hacking has started. Begin."
6. Check `STATUS.md` every few hours. Rehearse the pitch from `PITCH.md` after the freeze.

---

# PART 2: APPENDIX. Full design document from ideation (reference)

Reminder: "RECALL" below means Trackback. Part 1 overrides anything here that conflicts with it, including naming, the four-person plan, the problem stats, the 425 header name, and the real-data scenario's priority.

# RECALL traces corrections forward, Memento replays decisions

Build RECALL as the record-to-report corner of a fictional climbing-gym chain's finance team, and make one moment carry the whole pitch. A billing-system export turns out to have double-counted $118,000 of March revenue. That's only 3.7% of the year's pretax income, so a naive materiality rule would shrug. But it pushes the lender's leverage ratio from 2.95x to 3.03x against a 3.00x covenant. RECALL catches it. It then marks exactly which artifacts are now wrong: the compliance certificate, two board-deck tiles, one gym manager's bonus and the next tax installment. It also shows, with a reason for each, which artifacts it checked and cleared. When the controller rejects its first correcting entry, it revises. And Memento replays April 10, the day the books closed, to show the duplicate was sitting in the export the agent read, so RECALL owns the miss instead of hiding it. Technically this is a truth maintenance system with build-system early cutoff, running over an append-only bitemporal SQLite store. Every read goes through a time-pinned Memento (RFC 7089) service. Numbers are computed by code from claim IDs, never by the model, and the LLM judges only prose. That's what makes it precise, deterministic and fully offline, which matters because venue Wi-Fi was spotty last year. The competitive gap is clear. Zep's Graphiti invalidates single facts, and Rillet recomputes inside one module. None of them publicly traces a correction forward into reports, forecasts and money that already moved, with a replay of what was knowable at the time. The verified problem stat is STALE's: the best model tested got only 55.2% of stale-memory cases right. The flashier "91 to 100%" figure stays off the headline until someone reads the actual paper. Everything in this document is ideation.

The fictional company, its numbers and the answer key are original design work built on the cited accounting rules, not sourced facts.

## The product: a close-and-reporting agent that knows what its numbers rest on

### What it does in one paragraph

RECALL is a claim graph with two clocks. Every source the finance agents read (a bank statement, a billing export, a contract amendment, an FX rate table, a vendor email) is stored as versioned claims. Each claim records when the fact applies (valid time, like "March utilities") and when the system learned it (transaction time, like "read April 9 at 14:02"). Every thing an agent produces is an artifact: a number, a report sentence, a forecast cell or an executed action like a journal entry or a payment run. Each artifact records exactly which claim versions it relied on, down to the version ID. When a source is corrected, RECALL diffs the old and new versions claim by claim and walks forward through the graph. It recomputes every number from its formula, stops wherever the recomputed value didn't move enough to matter, and asks an LLM only about prose. The result is a verdict for every touched artifact: invalidated, unaffected (with the reason), needs review, or unprovable. For artifacts that already acted on the world, it proposes a compensating action from a fixed menu and routes it to a human who isn't the preparer. Memento is the other half. Any past decision can be replayed exactly as the system saw it, because every read was pinned to a timestamp and anything published after that timestamp is refused, not silently swapped in.

### How it maps onto the requirements

The brief (as pasted) asks teams to pick a company and a corner of its finance team, and lists the hard parts: sources that disagree, time ("what happened in March should change what the system does in June"), working with others (approvers, "controller says no"), limits (segregation of duties) and explainability. The judging asks four questions. RECALL is designed so each one has a specific, demoable answer.

| Judging question | What RECALL shows |
|---|---|
| Real enough? | A complete synthetic company with a real chart of accounts, a close calendar, a lender covenant and 23 planted errors with a frozen answer key. Plus one scenario on real SEC data (Monolithic Power's restatement) and real ALFRED data vintages |
| Would you hire it? | Named seats (below). It only touches data through its own tools (limited access), every action carries its justification and approval (clean record), and it routes to a person whenever the correction's timing or materiality is ambiguous (knowing when to ask) |
| Something new? | Forward correction tracing with value-aware cutoff across reports, forecasts and executed actions, plus as-of replay with a time-pinning profile over Memento |
| The moment | Catches what others missed (E11, the covenant flip), recovers (E22, controller rejects and the agent re-drafts), defends a decision (E07 and E19 replays showing a past call was right given what was knowable) |

The submission asks for a demo video that opens with the moment, a real live demo where judges may try their own scenario, one line on seats, and proof it works (what's real vs simulated, and how you know). Each of those has its own section below.

### The seats it fills

The primary corner is record-to-report. Corrections land in the close and spread outward into reporting, which is exactly the path RECALL tracks, and this seat sees every correction type: invoice versus accrual, bank revisions and returns, late entries, FX fixes and prior-period errors. It also owns the artifacts that go stale: flux commentary, the board deck, the covenant certificate, bonus accruals and tax estimates. And it has a natural segregation-of-duties line, since the agent prepares and the controller approves.

| Seat | Who fills it | What it owns |
|---|---|---|
| Senior Accountant, Close and Reporting | RECALL (primary) | Accruals, true-ups, out-of-period adjustments, the misstatement log |
| Reporting / FP&A Analyst | RECALL (downstream) | Flux commentary, budget vs actuals, 13-week cash forecast, covenant certificate draft |
| Revenue Accountant | RECALL (secondary) | ASC 606 contract modifications for wellness contracts and wall builds |
| Controller | Human | Approver, materiality judge, the only one who can unlock a period |
| CFO | Human | Signs anything that goes to the lender |

Don't pitch replacing the controller. Accountability and segregation of duties both argue for a human signer. Pure FP&A is too weak, because it can't post to the ledger and so can't show a compensating entry. A pure revenue seat is too narrow for "sources disagree", because bank versus ledger falls outside it.

The seats line for the pitch and the Devpost page: "RECALL does the senior close accountant's and the reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign."

## Tidewall Climbing Co. is built to produce every correction type in scope

The company that makes this demo work is boring in exactly the right way. Tidewall Climbing Co. is a fictional, private, PE-backed Delaware corporation headquartered in Oakland, running six indoor climbing gyms in California plus a small Wall Build division that builds climbing walls for universities and other gyms. It's a design choice, not a sourced fact, and someone needs to search the name and every vendor name against real businesses before anything gets published.

It's a good pick because one small business naturally throws off every correction type the track cares about. Members pay monthly dues by ACH debit, so you get R01 and R10 returns. Corporate wellness contracts sell seats to employers, so you get ASC 606 contract modifications. Wall Build is construction-style revenue recognized over time, so you get cumulative catch-ups. Climbing holds are bought in euros, so you get FX corrections. Utilities and route-setting contractors need accruals. A term loan has a leverage covenant, and gym managers earn EBITDA-based bonuses. Judges also understand a climbing gym instantly, which you can't say for a SaaS company's deferred revenue waterfall.

### The company in numbers (all synthetic)

| Item | Value |
|---|---|
| Fiscal year | Calendar |
| FY2026 budget | Revenue $42.0M, EBITDA $6.0M, pretax income $3.2M |
| Gyms | G1 Oakland, G2 San Jose, G3 Sacramento, G4 Fresno, G5 Santa Cruz, G6 Berkeley |
| Members | About 9,400, on monthly ACH dues (about $105/month average) or annual prepaid |
| Revenue streams | Memberships (ratable), day passes and retail (point in time), Corporate Wellness seat contracts (ratable), Wall Build (over time, cost-to-cost) |
| Debt | $18.0M term loan from "Redwood Commercial Credit" (fictional). Cash $1.5M, so net debt $16.5M |
| Covenant | Net Leverage (net debt / TTM Adjusted EBITDA) at or below 3.00x, tested quarterly. Certificate due 45 days after quarter end |
| Q1 2026 as reported | TTM EBITDA $5.60M, ratio 2.95x. Deliberately thin headroom: the covenant breaks if TTM EBITDA falls below $5.50M |
| Materiality memo (controller) | Overall annual materiality $160k (5% of budgeted pretax). Quarterly performance materiality $60k. Clearly trivial $8k. Flux threshold: more than 10% and more than $25k vs prior quarter or budget. Qualitative overrides: covenant, bonus tier, sign change |

The materiality memo is itself a claim in the graph, with a version. If the controller changes the trivial threshold, that's a correction like any other and it propagates.

### The calendar, and the frozen "now"

| Date (2026) | Event |
|---|---|
| April 10 | Q1 hard close (business day 7). Q1 locked |
| Business day 12 after close | Board deck goes out |
| May 15 | Q1 compliance certificate sent to the lender |
| May 31 | Gym GM quarterly bonuses paid |
| June 15 | Q2 federal estimated tax paid |
| July 8 | Demo "now", during the June / Q2 close. Q1 is locked and reported |

Pin July 8 in config. The demo clock must never drift to the real date on stage.

### The systems, each one a claim source with versions

| System | What it holds | How it gets corrected |
|---|---|---|
| General ledger | Synthetic double-entry ledger with document date, posting date, period, and a locked flag per section (AR, AP, other GL) | Never edited. Corrections are new entries |
| Bank feed | BAI2/CSV-style daily feed plus statement PDFs | The bank can issue a corrected statement |
| ACH processor | Debit batches and return files with R-codes | Returns arrive days or weeks later |
| Membership and billing system | Source of deferred revenue schedules. Migrated in February 2026 | A corrected export replaces a bad one |
| Contracts repository | MSAs, order forms, amendments as text | Amendments and change orders |
| AP inbox | Emailed invoices and vendor emails | Duplicates, revised invoices, spoofed emails |
| FX rate table | Daily EUR/USD from a "rate vendor" | The vendor corrects a day's rate |
| HR and comp | GM bonus = 4% of gym EBITDA above target, paid quarterly, subject to true-up offset. Sales commission = 8% of first-year contract value, offset against future commissions allowed | Plan terms change rarely |
| Credit agreement | Covenant definitions, plus a synthetic clause requiring a corrected certificate if prior financials are corrected | Fixed for the demo |

The ERP split between document date and posting date is the bitemporal idea finance already uses every day: an invoice dated March 28 can land in the April period because March was locked. Use both dates in the synthetic ledger.

### Chart of accounts (the slice the demo needs)

| Acct | Name |
|---|---|
| 1010 | Cash, Operating (Redwood Bank) |
| 1015 | Cash, Clearing (ACH/merchant) |
| 1200 | Accounts Receivable, Corporate |
| 1210 | Accounts Receivable, Member Dues |
| 1290 | Allowance for Doubtful Accounts |
| 1310 | Contract Assets, Wall Build |
| 1500 | Climbing Equipment and Holds (fixed asset) |
| 1590 | Accumulated Depreciation |
| 2010 | Accounts Payable |
| 2100 | Accrued Expenses, Utilities |
| 2110 | Accrued Expenses, Contract Labor (route setting) |
| 2120 | Accrued Expenses, Professional Fees |
| 2150 | Accrued Bonus |
| 2160 | Accrued Commissions |
| 2300 | Deferred Revenue, Memberships |
| 2310 | Deferred Revenue, Corporate Wellness |
| 2320 | Contract Liabilities, Wall Build |
| 2500 | Term Loan |
| 3900 | Retained Earnings |
| 4000 | Membership Revenue |
| 4100 | Day Pass and Retail Revenue |
| 4200 | Corporate Wellness Revenue |
| 4300 | Wall Build Revenue |
| 4900 | Sales Credits and Allowances |
| 5300 | Wall Build Cost of Revenue |
| 6100 | Utilities |
| 6200 | Contract Labor, Route Setting |
| 6300 | Professional Fees, Legal |
| 6400 | Bank and Merchant Fees |
| 6500 | Payroll Taxes |
| 6600 | Bonus Expense |
| 6650 | Commission Expense |
| 6700 | Depreciation |
| 7100 | Realized FX Gain/Loss |
| 8100 | Income Tax Expense |

### The humans, and the rules RECALL can't break

The sim has five human roles: Dana Ortiz (Controller, approver, can reject), Sam Whitfield (CFO, signs lender documents), Priya Nair (AP Specialist, owns the vendor master), Leo Brandt (VP Sales, approves commission changes) and the gym GMs. Segregation of duties comes down to four hard rules. The agent prepares journal entries but never approves its own. Nobody who edits the vendor master can also release a payment to that vendor. Only the controller can unlock a period. Only the CFO signs lender documents. Enforce the first one in the database schema itself (a CHECK that proposer and approver differ), not just in the UI. When a judge asks "what stops the agent approving itself?", the answer is a line of SQL.

One more design choice to state openly: whether the covenant's Adjusted EBITDA excludes FX and one-time legal costs is up to us, since real credit agreements vary. Write the definition into the synthetic credit agreement so the engine reads it as a claim.

## Twenty-three planted errors, and the handful that carry the demo

The answer key is the backbone of "real enough" and of the proof slide. Each item lists the source event, how accounting classifies it, the correct handling, what it invalidates, and, just as important, what it must not invalidate. All amounts are synthetic. The rules behind the classifications are explained in the next section.

### The full key at a glance

| ID | Event | Classification | Correct handling | Invalidates | Must stay valid |
|---|---|---|---|---|---|
| E01 | G3 March utilities accrued at $48,000. Bayline Power invoice arrives April 12 at $51,900 (+8.1%) | Estimate change | Book +$3,900 in April. Don't reopen March. Under the $8k trivial line | April BvA utilities line | Q1 flux commentary, Q1 covenant certificate |
| E02 | March route-setting work ($22,500) invoiced April 3. Signed March timesheets existed in the contractor portal | Error (facts were knowable), out-of-period | Correcting JE in April tagged to March, plus a misstatement-log entry | Board-deck sentence "Route-setting costs fell 18% QoQ" (true figure about 2%). Send a corrected-commentary note | Q1 revenue tiles. Covenant (2.96x alone) |
| E03 | June 1 dues batch: 14 R01 returns, $2,310, received June 3 | Fact: cash never arrived | Reverse receipts (1015 to 1210), restore member AR, retry per company policy | 13-week forecast week-23 actuals, AR aging | P&L, flux commentary |
| E04 | A $189 June 1 debit returned R10 on July 7 with a signed unauthorized-debit statement | Fact plus authorization dispute | Reverse, suspend future debits, open a Member Services case, never re-present without new authorization | Member AR record, July cash forecast (trivial) | Everything else. Trap: default retry logic treats it like R01 |
| E05 | Bank issues a corrected May statement: a $40,000 wire credited May 30 to Northgate Biotech's AR was misdirected | Source fact correction | May is locked, so reverse on June 1 referencing May. Reinstate Northgate AR (now over 60 days, check reserve). Start collections | May cash rec, 13-week opening balance, "May cash collected" KPI, June 5 AP run's cash-floor check (recomputed: buffer still OK, note only) | May revenue (earned whether or not paid) |
| E06 | Northgate wellness contract (24 months from Jan 1, 200 seats at $60). Amendment signed May 15, effective June 1, adds 50 seats at $45 vs $60 standalone price | ASC 606 prospective modification | Blend over remaining 19 months: $228,000 remaining + $42,750 added = $270,750, or $14,250/month | Deferred revenue schedule from June, H2 revenue forecast | Jan to May revenue, Q1 artifacts. Trap: agent proposes restating Q1 |
| E07 | UC Sierra wall: $900,000 price, $600,000 estimated cost, $240,000 incurred at March 31 (40%), $360,000 recognized. April 20 change order adds $150,000 price and $60,000 cost to the same wall | ASC 606 cumulative catch-up | Progress becomes 240/660 = 36.36%. Cumulative revenue should be $381,818. Book +$21,818 in April | Q2 Wall Build margin commentary, contract asset balance | Q1 Wall Build revenue (the March estimate was right as of March) |
| E08 | June 18: $6,500 SLA credit to Northgate for G2's flood closure (May 10 to 24) | Variable consideration. The closure was known in May | Book in June to 4900 (immaterial), note the May omission in the misstatement log | G2 May commentary only if it cited revenue finer than $10k | Otherwise touched, still valid |
| E09 | €85,000 holds invoice from Kletterwerk GmbH, dated March 20, converted at 1.0280. Vendor corrects the rate to 1.0820 | Error from a bad input fact | In Q2, adjust asset 1500 by +$4,590, reclassify 7100, true up depreciation (trivial) | Capex tracker, depreciation schedule | Revenue artifacts, covenant EBITDA (FX and depreciation sit outside it) |
| E10 | April 22: March employment-counsel invoice ($14,000) found un-accrued | Error, out-of-period | Post in April tagged to March. Recompute covenant with E02: TTM EBITDA $5.5635M gives 2.966x | Nothing beyond the expense line | Covenant certificate: "touched, still valid", calculation attached. Don't alarm the lender |
| E11 | February billing migration duplicated the March deferred-revenue release for annual prepaid memberships. Q1 revenue and EBITDA overstated by $118,000 | Error, material on qualitative grounds | Escalate to Controller and CFO. Corrected Q1 internal package and compliance certificate (CFO signs). Draft lender notice and waiver request. Fix the schedule. Propose a dedupe control | Q1 board-deck revenue and EBITDA tiles, Q1 compliance certificate, GM bonus accruals (E12), Q2 estimated tax (E23), Q1 membership flux commentary | Other gyms' bonuses whose EBITDA didn't use the duplicated rows |
| E12 | G4 GM's Q1 bonus included $32,000 of E11 overstatement. Excess $1,280, paid May 31 | Downstream of E11 | Offset against the Q2 bonus per plan terms. HR and Controller approve. Notify the GM. No ad-hoc payroll deduction | G4 bonus record | Other GMs' bonuses |
| E13 | Commission on the E06 amendment computed at list: 50 x $60 x 12 x 8% = $2,880. Should be 50 x $45 x 12 x 8% = $2,160. $720 overpaid in June payroll | Error | Offset against the next commission. VP Sales and Controller approve | Rep's commission record | Everything else |
| E14 | Summit Mats Supply sends "INV-2231" and later "2231": same $18,750, same PO, same lines. Both queued for the June 12 run | Duplicate | Block the second before release. If already paid, request credit and hold the next payment. Agent flags, AP releases or holds | The payment run | The first, valid invoice |
| E15 | Email "from Kletterwerk" asks to change the IBAN. Domain is kletterwerk-gmbh.co, not kletterwerk.de | Unverified claim, likely fraud | Don't update the vendor master. Call back on the known number. Master change needs Priya, release needs someone else | Nothing. The right move is refusing the "correction" | The vendor master |
| E16 | Contract says net-45, customer master says net-30, so a dunning email went out on day 31 | Sources disagree | Contract wins. Fix the master (owner approves), send a retraction, re-age AR | Collections timing in the 13-week forecast | Revenue |
| E17 | June 2 bank feed revises a fee from $25.00 to $25.40 | Trivial fact update | Auto-adjust the recon line | Nothing beyond the recon. Tests over-alerting | Everything |
| E18 | State issues a revised 2026 unemployment insurance rate, retroactive to January (+$6,200 YTD) | Estimate change (new information) | Book the YTD true-up in June | H1 payroll tax BvA line | Revenue commentary, Q1 covenant |
| E19 | The membership-demand model used an employment series vintage pulled June 5. A later benchmark revision lowers it | New data vintage | Re-run the forecast forward | H2 forecast | The June budget decision record ("correct as of what was knowable"). Use real ALFRED vintages cached offline |
| E20 | Annual memberships sold December 2025 ($95,000 of service into 2026) were fully recognized in December 2025 | Prior-year error, little r | 3.0% of FY2025 pretax ($3.15M), but about 12% of Q2 2026 pretax (about $0.8M). Revise FY2025 comparatives in the lender package, adjust opening retained earnings (3900) and deferred revenue (2300), disclose. Recheck the Q4 2025 certificate | FY2025 comparatives | Q2 P&L. Trap: agent proposes a Q2 out-of-period entry, controller says no |
| E21 | Pacific Lumen Labs historically short-pays $15 to $35 (wire fees). In June it short-pays $1,035 | Partly learned norm, partly dispute | Auto-clear only $35 to bank fees. Route the $1,000 to a person as a likely dispute | AR for that customer | Trap: auto-writing off the whole $1,035 |
| E22 | The agent's first correcting JE for E11 is dated March 31 (locked), and the workflow would let it self-approve | Control failure the system must catch | Route to Controller. Controller rejects: "Q1 locked; book in Q2 with OOP tag; restate the lender package separately". Agent re-drafts | The draft JE | Memento keeps both versions and the rejection reason |
| E23 | The June 15 Q2 estimated payment used Q1 pretax that included E11 (+$118k) and excluded E02/E10 | Downstream of E11 | Reduce the Q3 installment instead of seeking a refund (verify the IRS rule). Notify the tax advisor | Q2 estimate workpaper | State sales-tax filings (memberships are a different tax base) |
| E-norm | Ten months of Bayline Power history show a +7.8% median winter accrual shortfall | Learned norm, not an error | Propose accrual factor 1.08 for November to March. Controller approves. Applies prospectively | Future accrual method | Past accruals |

### The items that carry the demo

E11 is the moment. Spell out the arithmetic on screen, because it's the whole argument. The overstatement is $118,000, which is 3.7% of the $3.2M budgeted pretax income and under the SAB 99 rule-of-thumb 5% line. A naive "is it under 5%?" check would book it quietly in Q2. But corrected TTM EBITDA is $5.60M minus $118k minus the $36.5k from E02 and E10, which gives $5.4455M. Net debt of $16.5M divided by that is 3.03x, over the 3.00x covenant. SAB 99 names covenant compliance as one of the qualitative factors that can make a small misstatement material ([SEC SAB 99](https://sec.gov/interps/account/sab99.htm)). So RECALL escalates. The Memento beat follows. Replay April 10, and the duplicated rows are visibly sitting in the billing export v1 the agent consumed. That makes it an error, not an estimate change, so RECALL says "this was knowable, and we missed it" and proposes the dedupe control. A system that defends itself when it was right and owns the miss when it wasn't is what "would you hire it" means.

E22 is the recovery. The first draft of the E11 fix is wrong in a realistic way: dated into a locked period, with a workflow hole that would allow self-approval. The schema blocks the self-approval, the controller rejects the date, and the agent re-drafts in Q2 with an out-of-period tag while the lender package gets restated separately. Memento records both drafts and the rejection reason. Should you plant a mistake in your own agent? Yes. The brief literally lists "controller says no", and a recovery the judges watch beats a claim of perfection.

E07 and E19 are the defenses. On E07, a judge (or the script) asks whether Q1 Wall Build revenue was wrong. Replay March 31: the change order didn't exist yet, the 40% progress estimate was right as of then, and the catch-up belongs in April. On E19, the June forecast used the employment-series vintage that existed on June 5. Real ALFRED data shows the later revision, and the replay proves the June call was correct as of what was knowable. These are the accounting version of look-ahead bias: blaming a decision for not knowing a correction that hadn't arrived.

E10, E17 and E18 are the "doesn't cry wolf" items. E10 touches the covenant certificate and leaves it valid at 2.966x, with the calculation attached. E17 is a 40-cent bank fee revision that should produce exactly one recon adjustment and zero alerts. E18 is a payroll tax change on a different line that must not touch revenue commentary. Show at least one of these green on stage. Precision is the pitch, and a system that flags everything is no better than rerunning everything.

E21 and E15 test judgment at the edges. E21 shows a learned norm applied correctly and stopping where the pattern ends: $35 is a wire fee, $1,000 is a dispute. E15 is a "correction" that RECALL must refuse, because an unverified email can't overwrite a vendor master. Sources that disagree aren't always resolved by taking the newest one.

### Fixes the key needs before anyone builds it

Five problems turned up when checking the arithmetic and dates. Fix them in the design before hacking starts.

First, E04's date is impossible. The original design dates the R10 return July 20, but the demo "now" is July 8, so the system would be reading the future. Move it to July 7 (36 days after the June 1 debit, inside the 60-day window for R10 returns per [Column's ACH docs](https://docs.column.com/ach/returns)).

Second, E11's materiality framing is shakier than it looks. At $118k it's under annual materiality ($160k) and under 5% of annual pretax, but it's above the $60k quarterly performance materiality, and against a quarter's pretax of roughly $0.8M (the figure E20 uses for Q2) it's around 15%. A sharp judge could say it's quantitatively material to Q1 anyway. The demo still works, because the covenant is the stated reason. But the key should say so plainly: "Under annual materiality and the 5% rule of thumb, which is the test a naive rule applies. Above performance materiality, so it must be booked and evaluated, not just logged. The covenant breach makes materiality unambiguous." Don't claim on stage that only the qualitative test catches it.

Third, the judge-scenario headroom number was off. The covenant breaks once TTM EBITDA drops below $5.50M. As reported, headroom is $100k. After E02 and E10, it's $63.5k. So a judge's extra EBITDA hit above roughly $64k flips the certificate, not $50k.

Fourth, E11 needs its $118,000 allocated across the six gyms in the data, since E12 only says $32,000 of it hit G4. That allocation decides which bonuses are invalidated and which are cleared. Put at least one affected gym below its EBITDA target: its bonus was zero before and is still zero after, which gives the ripple a natural "conclusion unchanged" green node. Note too that the duplicate was a revenue-recognition entry (deferred revenue to revenue), so no cash moved, and every cash artifact should clear.

Fifth, three rules in the key are unverified and should be labeled "company policy" in the sim until someone checks them: the NACHA limit on re-presenting R01 debits, the IRS rule for applying an estimated-tax overpayment to the next installment, and the "10% and $25k" flux threshold, which is common practice but has no published standard behind it.

## The accounting rules RECALL has to get right, in plain English

The good news is that the rules RECALL needs boil down to a handful of tests, and each one maps to a field or a branch in the engine.

### Rule 1: was it new information, or a fact you already had?

This is the single most important question, and it comes from ASC 250. If a later number differs because new information arrived, that's a change in estimate. You fix it now and going forward, and you don't touch earlier periods. "It is not an error merely because a later estimate differs from the old one" ([OnCourse CPA lesson on ASC 250](https://getoncourse.ai/lessons/cpa/select-transactions/accounting-changes-and-error-corrections)). If the fact already existed and was missed or misused, it's an error. The textbook case is an unpaid invoice for last year's services that never got recorded. That's an error, and fixing it reduces last year's income ([OnCourse](https://getoncourse.ai/lessons/cpa/select-transactions/accounting-changes-and-error-corrections)). A formula mistake or omitted data in an allowance calculation also counts as an error, not an estimate change ([Wipfli](https://www.wipfli.com/insights/articles/aa-asc-250-correcting-financial-statement-errors)).

For a CS student, here's the useful way to see it. This test is literally a question about the transaction-time axis. "Was the fact in the system, or obtainable, at the time the original number was made?" is exactly what Memento answers. E01 (the invoice simply came in higher) is an estimate change. E02 (the timesheets were sitting in the portal) is an error. The replay is the evidence.

### Rule 2: errors split three ways by size

Once something is an error, materiality decides where it gets fixed ([Wipfli](https://www.wipfli.com/insights/articles/aa-asc-250-correcting-financial-statement-errors); [Audit Analytics](https://blog.auditanalytics.com/error-corrections-a-look-at-adjustment-and-restatement-trends-2/)):

| Type | When | What you do |
|---|---|---|
| Big R restatement | Material to the prior period | Reissue the prior statements, label columns "restated", disclose the effect per line. Public companies file an 8-K Item 4.02 |
| Little r revision | Immaterial to the prior period, but booking it all now would distort the current period | Correct the prior-period comparatives next time you present them and disclose. Columns need not be relabeled |
| Out-of-period adjustment | Immaterial either way | Book it in the current period, tagged with the period it belongs to |

Most real corrections are the boring kind. Audit Analytics counted Big R restatements falling to a low of 85 in 2019, while out-of-period adjustments peaked at 327 in 2016 and were still 202 in 2019 ([Audit Analytics](https://blog.auditanalytics.com/error-corrections-a-look-at-adjustment-and-restatement-trends-2/)). That's why most of the answer key is true-ups and out-of-period entries, with one little r (E20) and one escalation (E11).

### Rule 3: materiality is a number plus a list of reasons a small number can still matter

SEC Staff Accounting Bulletin 99 accepts the 5% rule of thumb as a starting point and then lists qualitative factors that make a smaller misstatement material anyway. The factors that matter here: it comes from an estimate, it masks a change in earnings or trends, it turns a loss into income or the reverse, it "affects the registrant's compliance with loan covenants or other contractual requirements", and it increases management compensation ([SEC SAB 99](https://sec.gov/interps/account/sab99.htm)). SAB 99 also says you test each misstatement and the aggregate. Offsetting errors can't cancel a material one, and recurring small errors whose cumulative effect gets large count too ([SEC SAB 99](https://sec.gov/interps/account/sab99.htm)). Tidewall is private, so SAB 99 doesn't bind it, but it's the framework auditors and lenders reason with, and it's the right logic for the engine.

In engine terms, materiality is not one threshold. It's a function that takes the delta and the set of conclusions downstream of it (covenant pass or fail, bonus tier, sign of a growth rate) and returns a verdict. That's why E11 escalates and E10 doesn't, even though both hit EBITDA. It's also why RECALL keeps a misstatement log: everything it decides not to book still gets tested in aggregate.

### Rule 4: contract changes have three paths, and none of them restates the past

ASC 606 handles contract modifications three ways ([Deloitte DART Roadmap 9.2](https://dart.deloitte.com/USDART/home/codification/revenue/asc606-10/roadmap-revenue-recognition/chapter-9-contract-modifications/9-2-types-contract-modifications)):

1. Separate contract (606-10-25-12). Distinct goods added at their standalone selling price. The old contract is untouched.
2. Prospective (606-10-25-13(a)). The remaining goods are distinct but the price isn't standalone. Treat it as ending the old contract and starting a new one, and spread the unrecognized plus new consideration over what remains. Deloitte's Example 7 spreads $280,000 over 4 years, $70,000 a year. That's E06.
3. Cumulative catch-up (606-10-25-13(b)). The remaining work isn't distinct, because it's one partly finished performance obligation. Re-measure progress and book the difference now. Deloitte's Example 8 books a $91,200 catch-up at 51.2% progress. That's E07.

The trap in both E06 and E07 is an agent that "fixes" Q1. Unless the original accounting was wrong, a modification never reaches back.

### Rule 5: locked periods stay locked

In a real ledger like DualEntry, "A locked period is locked for everyone, including admins." Entries dated into a locked period get rejected, and a draft can't post "until the period is unlocked or the entry date is changed to an open period." Lock and unlock events go to an immutable audit trail, but unlocking doesn't ask for a reason, so the reason has to be documented separately ([DualEntry docs](https://docs.dualentry.com/accountants/core-financials/general-ledger/period-locking)). RECALL should behave the same way: post into the open period with a tag pointing at the original one, and when it does request a reopen, attach the reason itself.

### Rule 6: bank returns have deadlines, and some returns mean "never try again"

NACHA return codes split cleanly. R01 (insufficient funds), R02 (account closed) and several others must come back within 2 banking days. R05, R07 and R10 (unauthorized or revoked) have a 60-calendar-day window and require a signed Written Statement of Unauthorized Debit ([Column ACH docs](https://docs.column.com/ach/returns)). The first group is a funding failure you might retry. The second is an authorization dispute you must never retry without new authorization. That split is the basis for E03 versus E04, and for the rule that RECALL never learns a retry policy for R10.

### Rule 7: you compensate, you don't undo

Finance almost never edits history. The fixes are new entries in the open period that reference the original, reversals with a clear reference, re-approval by someone other than the preparer, notifying whoever relied on the artifact, and for money that already moved, a hold, an offset against the next payment, or a recovery request. RECALL's compensating-action menu is fixed, and every item needs a named approver who isn't the preparer:

| Compensation | Used for | Approver |
|---|---|---|
| Current-period correcting JE referencing the original JE and period | E02, E05, E10, E11 | Controller |
| Reversing entry plus re-entry | Wrong account or entity in an open period | Controller |
| Request to reopen a period, with documented reason | Rare. Only if unreported or the controller chooses to | Controller |
| Artifact supersession: v2 with a "corrected" banner and diff, original recipients notified, v1 kept replayable | E02 deck sentence, E11 tiles | Controller |
| Corrected compliance certificate and lender notice, waiver request drafted | E11 | CFO signs |
| Payment-side: block before release, request credit after, offset next payment, hold next bonus or commission | E12, E13, E14 | HR or VP Sales plus Controller |
| Reduce next tax installment | E23 (verify the rule) | Controller, tax advisor notified |
| Misstatement log entry | Anything not booked, so the aggregate gets tested | Controller reviews |

A note on bonuses. SEC Rule 10D-1 requires listed companies to claw back incentive pay after Big R or little r restatements, on a no-fault basis and looking back three fiscal years ([Covington](https://www.cov.com/en/news-and-insights/insights/2022/10/sec-requires-clawback-policies)). It doesn't apply to a private company like Tidewall, so the E12 bonus offset rests on Tidewall's own plan terms. Say that if asked, because it shows you know where the rule stops.

### Rule 8: what a correction should not invalidate

This is where RECALL earns its keep. A correction invalidates an artifact only if three things hold: the artifact consumed the corrected claim or something derived from it, for the same period and line, and the change is big enough to flip a conclusion the artifact states. Everything else gets marked "touched, still valid" with a reason. Six reasons cover almost every case:

1. Different period. A May correction doesn't touch a Q1 artifact unless Q1 consumed May data.
2. Different line item. A payroll tax fix doesn't touch revenue commentary.
3. Below the trivial threshold, or within display rounding (a "$5.6M" tile doesn't change for a $14k fix).
4. The conclusion doesn't flip. The covenant ratio moves but stays on the same side of the line.
5. Estimate change, not error. The past artifact was correct given what was knowable, and Memento proves it.
6. The error sits below the artifact's line. A revenue-only artifact survives a tax error.

That last one has a real precedent. In Monolithic Power's February 2026 restatement, FY2024 net income fell from $1,786.7M to $1,592.1M and diluted EPS from $36.59 to $32.60, all from deferred taxes on a foreign tax incentive. Revenue ($2,207.1M FY2024) and non-GAAP net income didn't change ([MPWR 8-K](https://www.sec.gov/Archives/edgar/data/1280452/000143774926006112/mpwr20260225_8k.htm)). Quantum's August 2025 Item 4.02 shows the opposite reach. Its non-reliance covered not just the quarter's statements but "related disclosures, earnings releases, investor presentations, and communications", and it restated one quarter (the one ended December 31, 2024, about $3.9M of revenue) while revising two immaterial ones in later comparatives ([Quantum 8-K](https://www.sec.gov/Archives/edgar/data/709283/000070928325000021/qtm-20250808.htm)). That's a Big R and a little r in the same filing, which is exactly RECALL's three-way decision.

### What the engine stores because of all this

Every correction node carries four fields, and downstream invalidation depends on all of them: kind (estimate, error or fact update), knowable_at (when the underlying fact first existed in any source), materiality_verdict, and booking_period. Every artifact carries the period and line it describes plus the conclusions it states (thresholds, signs, tiers), so the engine can test rule 8 mechanically.

Finance already thinks in two clocks, which helps the pitch. FRED's real-time periods mark "when facts were true or when information was known until it changed", and ALFRED lets you "retrieve information that was known as of a past period of history" ([FRED API docs](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)). Compustat Snapshot sells point-in-time data specifically to reduce "lag assumptions and look-ahead bias" ([UNC Kenan-Flagler](https://kenanflaglerresearchtools.web.unc.edu/research-resource/compustat-snapshot/)). For quant-minded judges, Memento is the accounting version of avoiding look-ahead bias.

## Learned norms turn the correction log into proposed policy

The idea: the correction log is training data. Every closed loop leaves a residual. An accrual is followed by an invoice and a variance. An expected receipt is followed by an actual receipt and maybe a return code. A contract is followed by an amendment and a catch-up. Collect those residuals per vendor, customer or account, look at the distribution, and turn a stable pattern into a proposed policy. Each proposal cites the history behind it and stays inactive until the controller approves it.

### Six norms RECALL can learn

| Norm | How it's computed | What it proposes | Answer-key link |
|---|---|---|---|
| Vendor accrual bias | Median of (invoice minus accrual) / accrual, per vendor and month type | "Bayline Power: +7.8% median over 10 winter months. Accrue at 1.08x, November to March" | E-norm, E01 |
| Customer short-pay pattern | Distribution of (invoice minus cash received) on wires | "Pacific Lumen Labs short-pays $15 to $35, 11 of 12 times, matching intermediary bank fees. Auto-clear to 6400 under $50" | E21 |
| Return-code behavior | Per-member R01 rate and retry success | Retry policy for funding failures only. Never for R10, R05 or R07 | E03, E04 |
| Late-invoice lag | Days from service end to invoice, per vendor | The list of vendors that must be accrued at close | E02 |
| March implies June | A Q1 true-up pattern, such as the route-setting contractor always invoicing three weeks late | Pre-accrue at June close | E02 |
| Recurring-error detector | Same root cause appearing more than once (migration duplicates, FX typos) | A new control, plus a misstatement-log entry so the aggregate gets tested | E09, E11 |

The "March implies June" row is the brief's own line made literal. The March miss (E02) is a fact in the graph, the June accrual policy cites it, and Memento shows both that the March decision was reasonable as of March and that the June policy came from March evidence.

### Why this isn't just "fit a model to the history"

Three accounting rules shape how learned norms behave, and saying them out loud is what separates this from a generic ML feature.

A learned accrual factor is a change in estimation method. Under ASC 250 a later estimate that differs from an earlier one is an estimate change, not an error ([OnCourse](https://getoncourse.ai/lessons/cpa/select-transactions/accounting-changes-and-error-corrections)). So a norm applies going forward, from the date the controller approves it, and never re-opens past accruals. The approval date becomes the norm's valid-from.

A bias you know about and don't fix becomes an aggregation problem. SAB 99 says estimates carry "inherent imprecision" and that recurring small misstatements must be evaluated together ([SEC SAB 99](https://sec.gov/interps/account/sab99.htm)). If Bayline runs 7.8% short every winter month, that's a pattern a controller should want fixed, not just a series of trivial true-ups.

Some patterns must never become policy. R10 returns are authorization disputes ([Column ACH docs](https://docs.column.com/ach/returns)), so no amount of "retry usually works" history can justify re-debiting. Hard-code a deny-list of norms the miner may not propose, and show it on the norms panel. Knowing what not to learn is part of "knowing when to ask".

### The recursive demo beat

Learned norms are claims in the same graph, with versions and provenance. So when a source in their history gets corrected, RECALL re-derives the norm. If one of Bayline's ten winter invoices turns out to have been a duplicate, the median moves, the proposed 1.08 factor goes back to "needs review", and the controller sees why. That's a ten-second beat that shows the whole system is one mechanism, not a pile of features. Build it only after the main flow works.

Guardrails for the miner, so it doesn't embarrass anyone: require a minimum sample (say 6 loops) before proposing anything, show the full distribution rather than just the median, cap the factor's range, and route every proposal through the controller with the evidence attached.

Every number in this section is synthetic. No published study gives real vendor accrual-bias rates or short-pay frequencies, so label them as simulated in the sim and on the proof slide.

## Architecture: one append-only SQLite file, two clocks, one deterministic engine

### The one-sentence version for technical judges

RECALL is a truth maintenance system with build-system early cutoff over bitemporal versions. Each piece is old and well understood, which is a strength. Doyle's 1979 truth maintenance system stored each belief with its justifications and retracted dependents when support disappeared ([Wikipedia: Reason maintenance](https://en.wikipedia.org/wiki/Reason_maintenance)). De Kleer's assumption-based version (1986) labels each node with the sets of assumptions it rests on, so several worlds can be held at once. Salsa, the incremental engine behind rust-analyzer, re-executes a function only when an input changed, and "backdates" the result when the new output equals the old one, so "even though the inputs changed, the output didn't" and nothing downstream re-runs ([Salsa algorithm](https://salsa-rs.github.io/salsa/reference/algorithm.html)). "Build systems à la carte" formalizes that early cutoff property ([Mokhov, Mitchell, Peyton Jones](https://www.microsoft.com/en-us/research/uploads/prod/2018/03/build-systems-a-la-carte.pdf)). The new parts are a value-aware materiality cutoff (a classic TMS treats support as on or off), finance-specific "not affected" reasons, and actions that can't be retracted, only compensated.

The mapping is direct. A TMS node is an artifact version. A justification is the set of edges recording which supporter versions it used. An assumption is a source version, like "billing export, March, v1". A correction retracts that assumption by closing its transaction-time interval. A source version known to be wrong is a "nogood", and anything resting on it is suspect. Use single-context propagation for the live recompute, and assumption labels for the UI panel that answers "which source versions does this sentence rest on?" and for counterfactual replay.

### Two clocks, one 2x2

The bitemporal model has two axes. Valid time is when a fact applies in the business (the fiscal period). Transaction time is when the system recorded it. A correction is a new row on the transaction axis with the same valid period. Memento replay is the transaction axis pinned to a moment. Snodgrass's textbook treatment defines exactly this split, with corrections as logical deletes plus inserts ([Snodgrass, Developing Time-Oriented Database Applications in SQL](https://www2.cs.arizona.edu/~rts/tdbbook.pdf)).

Put one 2x2 on stage and nothing more theoretical:

| | About then (valid = Q1) | About later (valid = H2) |
|---|---|---|
| Known then (tx = April 10) | What the Q1 close believed about Q1 | What the forecast believed about H2 |
| Known now (tx = July 8) | What we now know about Q1 | What we now know about H2 |

The pitch sentence: "Knowable-then versus true-then."

### The substrate: SQLite, append-only, with XTDB as the production answer

XTDB v2 is the impressive choice. It has native bitemporal SQL with system-maintained `_valid_from/_valid_to/_system_from/_system_to` columns, `FOR SYSTEM_TIME AS OF` queries, and a Postgres wire endpoint ([XTDB SQL overview](https://docs.xtdb.com/quickstart/sql-overview.html)). Don't use it at the hackathon. Docker plus a JVM plus a new SQL dialect is a real risk in 36 hours, and the release and image tag weren't checked. Datomic gives transaction time only, and Postgres has no native system-versioned tables. Use SQLite. It needs zero setup, works offline, and is a single file you can snapshot and reset between demo runs. The as-of query helper is about 30 lines. Every table is append-only, and the only UPDATE ever allowed closes a `tx_to`. Put "XTDB in production" on one slide.

### The schema

The `tx_from/tx_to` columns are transaction time and `valid_from/valid_to` are valid time. `tx_to = '9999-12-31'` means current. The finance-specific columns (period, line item, kind, knowable_at, materiality) are additions to the generic design so rule 8 from the accounting section can be tested mechanically.

```sql
CREATE TABLE sources(source_id TEXT PRIMARY KEY, uri_r TEXT, system TEXT, kind TEXT);
CREATE TABLE source_versions(version_id TEXT PRIMARY KEY, source_id TEXT, body TEXT, content_hash TEXT,
  document_date TEXT, tx_from TEXT, tx_to TEXT, supersedes TEXT, correction_id TEXT);  -- the mementos; Memento-Datetime = tx_from
CREATE TABLE claims(claim_id TEXT PRIMARY KEY, source_id TEXT, entity TEXT, account TEXT, line_item TEXT,
  unit TEXT, period_start TEXT, period_end TEXT);                  -- stable key: (entity, line_item, period, unit)
CREATE TABLE claim_versions(claim_version_id TEXT PRIMARY KEY, claim_id TEXT, source_version_id TEXT,
  value_num REAL, value_text TEXT, span_start INT, span_end INT,
  valid_from TEXT, valid_to TEXT, tx_from TEXT, tx_to TEXT);
CREATE TABLE artifacts(artifact_id TEXT, version INT,
  kind TEXT CHECK(kind IN ('number','sentence','forecast_cell','action')),
  run_id TEXT, pinned_at TEXT, period TEXT, line_item TEXT, content TEXT, value_num REAL, formula TEXT,
  conclusions_json TEXT,           -- e.g. {"covenant_max":3.00} or {"sign":"down","pct":18}
  status TEXT,                     -- valid | suspect | stale | unprovable | superseded | compensated
  tx_from TEXT, tx_to TEXT, PRIMARY KEY(artifact_id, version));
CREATE TABLE justifications(edge_id TEXT PRIMARY KEY, consumer_id TEXT, consumer_version INT,
  supporter_kind TEXT CHECK(supporter_kind IN ('claim','artifact')), supporter_id TEXT, supporter_version TEXT,
  dep_kind TEXT CHECK(dep_kind IN ('numeric','prose','control')),
  capture TEXT CHECK(capture IN ('tool_log','structured','citation')), validity_predicate TEXT);
CREATE TABLE reads(read_id TEXT PRIMARY KEY, run_id TEXT, tool_call_id TEXT, uri_m TEXT, source_version_id TEXT,
  memento_datetime TEXT, pinned_at TEXT, http_status INT, ts TEXT);   -- every read, refusals included
CREATE TABLE corrections(correction_id TEXT PRIMARY KEY, source_id TEXT, old_version TEXT, new_version TEXT,
  kind TEXT CHECK(kind IN ('estimate','error','fact_update')), knowable_at TEXT,
  materiality_verdict TEXT, booking_period TEXT, tx_time TEXT, note TEXT);
CREATE TABLE claim_diffs(correction_id TEXT, claim_id TEXT, old_cv TEXT, new_cv TEXT,
  change TEXT CHECK(change IN ('changed','unchanged','added','removed')));
CREATE TABLE impact_findings(correction_id TEXT, artifact_id TEXT, artifact_version INT,
  verdict TEXT CHECK(verdict IN ('invalidated','unaffected','needs_review','unprovable')),
  reason TEXT,   -- value_changed | early_cutoff | below_materiality | conclusion_unchanged | different_period | different_line_item | prose_judged
  old_value REAL, new_value REAL, judge_model TEXT, judge_rationale TEXT, cache_key TEXT);
CREATE TABLE actions(action_id TEXT PRIMARY KEY, artifact_id TEXT, kind TEXT, params_json TEXT, ledger_tx_id TEXT,
  executed_at TEXT, compensator_json TEXT,
  state TEXT);   -- executed | compensation_proposed | approved | compensated | rejected
CREATE TABLE approvals(approval_id TEXT PRIMARY KEY, action_id TEXT, proposer TEXT, approver TEXT,
  decision TEXT, reason TEXT, ts TEXT, CHECK (proposer <> approver));  -- segregation of duties in the schema
CREATE TABLE ledger_entries(tx_id TEXT, line INT, account TEXT, amount_cents INTEGER, period TEXT,
  orig_period TEXT, memo TEXT, action_id TEXT, approval_id TEXT, correction_id TEXT, ts TEXT);
CREATE TABLE llm_cache(cache_key TEXT PRIMARY KEY, request_json TEXT, response_json TEXT, model TEXT, ts TEXT);
```

Two invariants go in code and in tests: every `ledger_entries.tx_id` sums to zero, and no row is ever updated except to close `tx_to`.

### The Memento service, and the time-pinning profile on top of it

RFC 7089 defines four resources: the Original Resource (the current version), a Memento (an immutable prior state), a TimeGate (negotiates by datetime using the `Accept-Datetime` request header) and a TimeMap (lists every memento with its datetime, in `application/link-format`). A `Memento-Datetime` response header is a promise that the captured state won't change ([RFC 7089](https://www.rfc-editor.org/rfc/rfc7089.html)). It's small enough to hand-roll on FastAPI in an afternoon, about 150 lines, using the RFC's Pattern 2.1 (a separate TimeGate that 302-redirects to the memento):

| Endpoint | Behavior |
|---|---|
| `GET /r/{doc_id}` | Current version, with `Link` headers to the timegate and timemap |
| `GET /tg/{doc_id}` plus `Accept-Datetime` | 302 to `/m/{doc_id}/{yyyymmddHHMMSS}`, `Vary: accept-datetime`, Link to original and timemap. 400 on a malformed datetime |
| `GET /m/{doc_id}/{ts}` | Immutable body with `Memento-Datetime`, plus Link original/timegate/timemap and first/last/prev/next memento |
| `GET /tm/{doc_id}` | The TimeMap in `application/link-format` |

The key semantic point: `Memento-Datetime` is archival time, meaning when the system captured the version, not the fiscal period the number describes. So Memento covers the transaction-time axis (what was knowable), and valid time lives inside the claim data. Memento is "as of system time", and the claim graph handles "for which period".

Here's the part to get exactly right, because a judge who knows HTTP will check. Plain RFC 7089 is the wrong behavior for leak prevention. If you ask a TimeGate for a datetime before the first memento, it MUST return the first memento. If you ask for one after the latest, it returns the latest. And a missing `Accept-Datetime` SHOULD return the latest ([RFC 7089](https://www.rfc-editor.org/rfc/rfc7089.html)). Every one of those silently hands an agent a document from its future. So RECALL defines its own time-pinning profile over Memento with four deviations:

1. The pin is set server-side and bound to the agent run (an MCP session or a signed pin token). The client's `Accept-Datetime` is never the authority. The tool layer injects `Accept-Datetime = pinned_at`, and the server rejects anything later.
2. If the first memento postdates the pin, meaning the document didn't exist yet, return 404 instead of the RFC's first memento.
3. A direct fetch of any memento whose `Memento-Datetime` is after the pin is refused.
4. A missing `Accept-Datetime` in a pinned session resolves to `pinned_at`, never to "latest".

The refusal itself: `403 Forbidden` when a version exists but postdates the pin, `404 Not Found` when nothing existed as of the pin (which is truthful in the pinned world). The body is RFC 9457 problem details (`application/problem+json`) with `type: https://recall.local/problems/temporal-pin-violation` and the fields `pinned_at`, `requested_datetime` and `first_memento_datetime`, plus a custom `Recall-Pinned-At` header ([RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html)).

What about 425 Too Early? Don't send it on the wire. RFC 8470 defines 425 narrowly: "the server is unwilling to risk processing a request that might be replayed", for TLS early data. Clients that sent early data MUST retry after a 425, and user agents SHOULD retry automatically ([RFC 8470](https://www.rfc-editor.org/rfc/rfc8470.html)). A future-dated request isn't a replay problem, and retrying can never succeed until the wall clock passes the document's date. An HTTP stack that implements RFC 8470 could even loop. Keep "425 Too Early" as a slide joke with the explanation underneath: "We wanted 425. RFC 8470 reserves it for 0-RTT replay with mandatory retry, so we use 403 with problem+json." That line earns more credibility than the joke costs.

Don't run pywb in the demo. It's a mature WARC web-archive replay system with Memento support enabled by default ([pywb Memento docs](https://pywb.readthedocs.io/en/latest/manual/memento.html)), which makes it good prior art to cite ("the protocol is mature"), but the data here is synthetic finance documents and a hand-rolled service is faster and fully under control.

### Provenance capture: make the model unable to skip it

Capture is the part a skeptical judge will poke hardest ("how do you know what the agent actually used?"). Rank the methods by reliability and build only the top three.

1. Tool and MCP interception. The agent's only data tools are served by RECALL's own MCP server (`get_document`, `search_claims`, `get_claim`). Every response returns the memento URI, the source version ID, the `Memento-Datetime` and claim IDs, and writes a `reads` row. That's 100% capture by construction, because there's no other path to data. It over-approximates, though: it records everything the agent saw, not what it used.
2. Typed numeric tools. The agent can't write a number. It calls `emit_number(name, formula, inputs: [claim_id or artifact_id])`, and RECALL evaluates the formula with a safe expression evaluator and stores the value. A requested claim ID must already appear in this run's `reads`, or the call is rejected, so the model can't free-type an ID it was never served. Numeric edges are then exact, and the LLM never does arithmetic.
3. Claude's Citations API for prose. Pass each claim as one block of a "custom content" document, so a `content_block_location` citation maps one-to-one to a claim ID. Citations are "guaranteed to contain valid pointers to the provided documents", but that doesn't guarantee the claims are right. And citations can't be combined with structured outputs, since enabling both returns a 400 ([Claude Citations docs](https://platform.claude.com/docs/en/build-with-claude/citations)). So prose generation is its own call, separate from structured tool calls.
4. Post-hoc attribution, like ContextCite, which fits a sparse linear surrogate over 32 or more context ablations and needs token logprobs ([ContextCite](https://arxiv.org/html/2409.00729v2)). That rules out most closed APIs and live use. Mention it as an offline audit, don't build it.

Then cross-check. Flag any prose sentence with zero citations, and any claim that was read but never cited. Under a correction, a read-but-unused edge becomes "suspect, low priority" instead of invalidated. That's a concrete precision win over invalidating everything that touched a document.

Borrow one idea from the GuardWrite paper: at write time, attach a machine-checkable validity predicate to each edge, such as "claim C still equals 412.0 within 0.5%" ([NeurIPS 2026 workshop poster](https://neurips.cc/virtual/2026/170668)). Re-checking predicates on a correction is cheap and deterministic.

### The propagation algorithm

When correction K replaces source S's version v_old with v_new:

1. Claim diff. Parse v_new into claim versions and match on the stable key (entity, line item, period, unit). Each claim comes out changed, unchanged, added or removed.
2. Seeds. The seeds are justification edges whose supporter is an old version of a changed or removed claim. Edges to unchanged claims are marked unaffected (claim unchanged). Edges into other periods or line items never become seeds, because they point at different claim IDs. That's where "different period" and "different line item" precision comes from: it's structural, not a judgment call.
3. Topological walk. Run Kahn's algorithm over the descendants of the seeds:
   - Number or forecast cell: re-evaluate the formula with current supporter values. If the change is at or below the line item's materiality, the verdict is unaffected, with reason `early_cutoff` (exactly equal) or `below_materiality`, and children are not dirtied. If the artifact states a conclusion (covenant max, bonus tier, growth sign) and the conclusion doesn't flip, the verdict is unaffected with `conclusion_unchanged`. Otherwise it's invalidated, a proposed new version is created, and its children are enqueued.
   - Sentence: a deterministic precheck first. If the sentence literally contains the old number, propose a substitution. Then the LLM judge rules invalidated, unaffected or needs_review, with a rationale, as structured JSON.
   - Action: if any supporter is invalidated, set the state to `compensation_proposed` and build the compensator from the fixed menu. Never auto-execute. If the recomputed parameters fall within materiality, propose nothing, because early cutoff applies to actions too.
   - If the new content for a supporter is unavailable (a source retracted with no replacement), the verdict is unprovable, a category borrowed from EA-Graph ([arXiv 2608.04278](https://arxiv.org/abs/2608.04278)).
4. Write every finding in one transaction keyed by the correction ID. That set is the blast radius the UI renders.

Cost is linear in the affected subgraph, not the whole graph, so on a demo graph of 100 to 300 nodes the deterministic part runs in milliseconds. Forbid cycles by construction: artifacts point at supporter versions, and a forecast that feeds a later forecast points at the earlier version, so the graph stays a DAG.

Add a pre-execution fence, borrowed from PlanFence: before any action executes, check that every transitive supporter is still the current version, and block or replan if not ([PlanFence, arXiv 2609.03340](https://arxiv.org/abs/2609.03340)). The fence handles the proactive case (E14's duplicate never gets paid), and propagation handles the retroactive one (E12's bonus already went out).

### The LLM judge has a small, fenced job

The judge only sees prose edges: a flux sentence, a board-deck caption, a memo line. It never overrides a deterministic numeric verdict. It returns structured JSON (verdict, rationale, proposed rewrite), and anything low-confidence goes to needs_review rather than being forced into a yes or no. Run it at temperature 0 through the cache, use a different prompt (ideally a different model) from the one that wrote the prose to avoid self-preference, and report its agreement with the hand labels on prose edges only, with the small sample size stated. The proposed rewrite is GuardWrite's "conclusion rewriting" idea applied to a board deck: "Route-setting costs fell 18% QoQ" becomes "Route-setting costs fell 2% QoQ (corrected July 8; see E02)".

Judges will try to type their own correction, so the correction input is a structured form (pick a claim or source, enter a new value, answer "when did this fact first exist?"), not free text. If you add a free-text box, it parses into that same form and shows the parse for confirmation before anything propagates. If the parse is ambiguous, it asks.

### The ledger: inside the same SQLite file

Use the `ledger_entries` table above: append-only, amounts in integer cents, a sum-to-zero check per transaction, and every posting carrying its action, approval and correction IDs. It's about an hour of work with zero risk, and everything stays in one store the UI can query. If you want a credible ledger UI for free, generate Beancount text from the postings and open it in Fava (versions not checked). Formance is the most fintech-real option, with multi-posting transactions and the Numscript DSL, but its standalone Docker Compose starts five services: Postgres, a gateway, a server, a worker and a console ([Formance README](https://raw.githubusercontent.com/formancehq/ledger/main/README.md)). That's a stretch goal at most. Don't use stripe-mock for anything stateful: it "is stateless", ignores POST data and returns hardcoded responses ([stripe-mock](https://github.com/stripe/stripe-mock)). Mention TigerBeetle's immutable transfers on a slide as the philosophy ("compensate, don't edit"). It adds nothing to the demo.

### Determinism and caching: replay and the cache are the same mechanism

Every LLM call goes through one gateway keyed by `sha256(model, system, messages, tools, params, pinned_at, corpus_snapshot_id)` and stored in `llm_cache`. The gateway has three modes. Record runs live and writes the cache. Replay is cache only and fails loudly on a miss. Fallback uses a local model through Ollama on a miss or with no network (model lineup not checked; pull the weights before the event). That gives a clean story: "replaying exactly as the system saw it" is literally a cache hit with time-pinned tools. The "What Could the Agent See at 19:05?" paper does the same thing for evaluation, precomputing past states into a difference cache so replay is "a fast, reproducible lookup" with no model in the loop ([arXiv 2608.01042](https://arxiv.org/abs/2608.01042)).

The rest of the determinism list: seed every random choice, pin the demo clock to July 8 in config, freeze the scenario dataset, use a fixed graph layout (dagre or elk, never force-directed), and generate the proof-slide numbers from a script whose output file is the slide's source, so the video, the slide and the live run always agree.

Stack: Python 3.11, FastAPI (Memento service, RECALL API and MCP server via the official Python MCP SDK), SQLite, the Anthropic SDK behind the cache gateway, React plus Vite with React Flow for the graph. Pin versions you've used before. None were checked for October 2026.

## Proof: a frozen answer key, three baselines and zero leaks

The brief asks for "proof it works: what's real vs simulated, and how you know". The answer is a planted-answer-key benchmark, the same method recent agent papers use. EA-Graph evaluates on generated repositories with known ground truth and classifies prior claims as unaffected, affected or unprovable across seven test worlds ([arXiv 2608.04278](https://arxiv.org/abs/2608.04278)). PlanFence ran 30 live five-agent workflows with a planted post-planning revision. A freshness-only executor acted on the stale plan every time, PlanFence completed all 30 correctly, and supplying inherited input versions raised detected handoff conflicts from 0 of 30 to 30 of 30 ([arXiv 2609.03340](https://arxiv.org/abs/2609.03340)). Copying that style makes the number credible even though it's small and synthetic.

### Freeze the key before tuning the engine

The awkward truth about a hackathon benchmark is that the people writing the key are also writing the engine. Handle it head-on. Person 4 owns the answer key, writes the expected verdict for every (correction, artifact) pair, and commits it by around hour 10, before the propagation engine gets tuned. Put the commit hash and timestamp on the proof slide. Any later change to the key goes in a changelog with a reason. That's not perfect independence, but it's honest, and "we froze it at hour 10, here's the hash" answers the obvious question.

The world for the eval is Tidewall: the 23 items plus the norm, applied to the full artifact set (aim for roughly 60 to 150 artifacts: KPI tiles, flux sentences, forecast cells, schedules, the certificate, bonus and commission records, payment runs and journal entries). Every artifact gets a hand label per correction. Make sure the decoy categories are all present: a different-period correction, a different-line-item correction, an immaterial one, an offsetting one where revenue and cost both move so margin doesn't (early cutoff), a prose sentence that cites a metric qualitatively ("revenue grew") where the corrected value still grew, one that flips the sign of a growth claim, and a retraction with no replacement (unprovable).

### What gets measured

| Metric | Why it matters |
|---|---|
| Precision, recall and F1 of "invalidated" | The core claim |
| Specificity on decoys | Proves "doesn't cry wolf" |
| Over-invalidation ratio (flagged / truly affected) | The headline number versus the naive baseline |
| Per-reason confusion matrix | Shows which "not affected" reasons are reliable |
| Compensation correctness | Right compensations proposed, and nothing extra |
| Memento leak test | Future-dated fetch attempts refused versus leaked, by an adversarial agent told to use the latest information. Target: 0 leaks |
| Replay fidelity | Share of past decisions reproduced byte-identically when re-run pinned, with cached LLM responses. Target: 100% |
| Judge agreement | Raw agreement and Cohen's kappa against hand labels, prose edges only, with n stated |

### Baselines

B1 is source-level invalidation: everything that read the corrected document is stale. Expect high recall and poor precision, which is RECALL's headline win. B2 is no tracking at all. B3 is asking the agent "given this correction, what changed?". That's the one that matters scientifically, because the literature says agents are bad at it. B4 (optional) is degraph's downstream-impact query as an open-source comparator ([PyPI degraph](https://pypi.org/project/degraph/)). Run all four from the same script.

### The problem stat: use STALE, and keep the other one off the headline

The verified stat is STALE ("Can LLM Agents Know When Their Memories Are No Longer Valid?", arXiv 2605.06527). It covers 400 conflict scenarios and 1,200 queries. It finds "a pervasive gap between retrieving updated evidence and acting on it", with "even the best evaluated model achieving only 55.2% overall accuracy", and notes that "models often accept outdated assumptions embedded in a user's query" ([arXiv 2605.06527](https://arxiv.org/abs/2605.06527)). On stage: "In a 2026 benchmark, even the best model got only 55% of stale-memory cases right." Two other papers back it up qualitatively. One says existing agent runtimes "provide little support for notifying the model that a previously observed fact has become stale" ([arXiv 2610.05281](https://arxiv.org/abs/2610.05281)). Another says memory-augmented agents "can know that a user's stored state is outdated and still plan around the old value" ([arXiv 2608.01619](https://arxiv.org/abs/2608.01619v1)).

The "agents follow stale conclusions 91 to 100% of the time" figure, attributed to the NeurIPS 2026 workshop poster "Agents Retrieve but Do Not Re-Derive", is disputed between the research notes. One researcher couldn't find it in three targeted searches. Another cites the poster page. A quick check while writing this found the poster's abstract page describes the figure as applying when the stale entry states a premise (not a conclusion), on mid-scale models ([NeurIPS 2026 workshop poster](https://neurips.cc/virtual/2026/170668)). Nobody has opened the paper itself, though, so treat the number as unverified. Don't put it on the headline slide. Before using it anywhere, open the full paper and confirm the number, the condition it applies to and the models. A likely related paper, MemDerive (arXiv 2610.25373), should be checked at the same time. Its abstract page couldn't be loaded for this report (the fetch was rate-limited). If it checks out, it works as a Q&A answer ("agents retrieve but don't re-derive, which is why the dependency tracking has to live outside the model"), stated with the premise condition attached. The YC demo-day guide calls exaggeration "fatal" ([YC](https://www.ycombinator.com/blog/guide-to-demo-day-pitches/)), and a judge asking "which paper?" when you can't answer costs more than the stat gains.

### The proof slide

Generate it from the eval script's output file. Leave the numbers as placeholders until the run is real, and don't round them up.

> PROOF. 23 planted errors + 1 learned norm, answer key frozen at hour 10 (commit a1b2c3d)
> RECALL: precision X, recall Y, over-invalidation Z. Source-level baseline: precision X', over-invalidation Z'. Ask-the-agent: recall Y''
> Memento: 0 future reads leaked in N adversarial attempts. Replay: N of N decisions byte-identical
> Real: graph engine, propagation, Memento service, refusals, ledger, approvals, MPWR restatement (SEC XBRL), employment-data vintages (ALFRED). Simulated: Tidewall's books, bank, billing, people

### What's real and what's simulated

| Real | Simulated |
|---|---|
| The claim graph, propagation engine, early cutoff and materiality logic | Tidewall Climbing Co., its gyms, vendors, customers and people |
| The Memento service, TimeMaps, pin enforcement and refusals | The bank feed, ACH processor, billing system and AP inbox |
| Typed-tool provenance capture and the LLM judge (cached) | The 23 planted errors (designed from cited accounting rules) |
| The ledger, compensations and approval workflow with schema-enforced segregation of duties | Lender, credit agreement and covenant definition |
| Monolithic Power's restatement as two vintages from SEC XBRL companyfacts | |
| Employment-series vintages from ALFRED | |

The real-data scenario deserves its own button. SEC's XBRL companyfacts API needs no key and returns every concept for a company, and the nightly bulk `companyfacts.zip` can be downloaded once for offline use ([SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces); [SEC Accessing EDGAR Data](https://www.sec.gov/os/accessing-edgar-data)). It should hold the original FY2024 facts and the restated ones from the later filing, which makes "same claim, two vintages" real. Load it, and RECALL marks revenue-based artifacts valid and EPS-based ones superseded. Inspect one file before relying on the field names (believed to include accn, fy, fp, form, filed, frame, start, end and val, but not confirmed). FRED and ALFRED need a free API key, and setting the real-time window wide returns every vintage of a series ([FRED API docs](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)).

Prefer Monolithic Power over Quantum for the real-data beat.

## UI: lot codes, a recall notice and a wall you can't see past

### The metaphor: a product recall for numbers

Most judges aren't accountants, so the system needs a picture that lands in seconds. Food traceability maps almost one to one. Under the FDA's FSMA 204 rule, each lot gets a Traceability Lot Code, records link lots across Critical Tracking Events, and a "transformation" event records its input lot codes. Covered firms must produce records "within 24 hours of request" ([Reliamag: FSMA Rule 204](https://reliamag.com/topics/guides/fsma-rule-204-compliance)). In RECALL, a source claim version is a lot with a lot code. Each derivation (a sum, a forecast formula, an LLM-written sentence, a payment decision) is a transformation that consumes input lots and produces a new one. A correction is a recall notice on a lot. RECALL is the trace-forward that finds every product made from it.

The line for judges: "When a lettuce farm finds E. coli, the law says trace every salad it went into. When a billing system corrects a number, nobody traces every report, forecast and payment it went into. We do."

Two cautions. The 24 hours is FDA's deadline for producing records, not a measure of how long tracing takes, so don't say "food takes 24 hours, we take seconds" as if it were a benchmark. And skip the FSMA compliance-date saga, since enforcement moved to July 2028 ([Reliamag](https://reliamag.com/topics/guides/fsma-rule-204-compliance)). Use the lot-code concept only. Dominoes are the wrong picture, because they imply everything falls, which is the opposite of precision.

### One screen, three panes

The left pane is the "ledger": a spreadsheet-like table of report lines, forecast cells and executed actions. Each row carries a small monospace lot chip like `LOT 7F3A`. Clicking a chip traces backward with thin blue arrows that appear on demand, borrowed from spreadsheet trace-precedents.

The center pane is the claim graph in React Flow, laid out left to right with dagre or elk: sources on the left, actions on the right. Never use a force layout. It wobbles, reads as chaos on a projector, and isn't deterministic. Keep the hero scenario to about 25 visible nodes and collapse the rest into "+12 more cleared".

The bottom pane is a full-width time scrubber in the Wayback Machine or video-editor style. Tick marks show each source version (the TimeMap) and a vertical line shows "now". Everything right of the as-of cursor is hatched grey: the wall, labeled "Not knowable on April 10, 2026". When the agent or a judge tries to read past it, the request bounces off with a stamp: "REFUSED: this export was published July 8; decision time was April 10."

Side panels: the version history of the selected claim (v1 April 9, v2 July 8; clicking one moves the scrubber), with diffs shown as the old value struck through next to the new one. Then an approvals inbox showing proposer, approver, decision and reason. Then the 2x2 bitemporal view. And a norms panel listing proposed policies with their evidence and the deny-list.

### The ripple

The correction arrives as a literal card with a red header, "RECALL NOTICE", plus the lot code, "Reason: duplicated March deferred-revenue release, v1 to v2", the issuer and a timestamp. Dropping it on the source node starts the ripple: a timed breadth-first walk over descendants, about 120 to 200 ms per hop, so the audience can follow it. Each node resolves to one of three states. Red with an X means invalidated. Green with a check means checked and cleared, with the reason on hover ("different period", "conclusion unchanged: 2.966x"). Amber with a "!" means it needs a human or a compensating action. The green nodes matter as much as the red ones. A corner counter shows what source-level invalidation would have flagged ("Naive: 41. RECALL: 9 invalidated, 14 cleared, 3 need action"). After a fix is accepted, rows flip from a STALE badge to RECALCULATED with a new lot code, borrowing marimo's lazy mode, which marks cells "stale instead of running them" ([marimo reactivity](https://docs.marimo.io/guides/reactivity/)). Anyone who uses notebooks will recognize it immediately.

Compute the affected set first (it takes milliseconds), then animate a precomputed list of (node, status, delay). Don't use React Flow's built-in `animated` dashed edges. They rely on CSS stroke-dasharray, which gets CPU-heavy across many SVG elements. One team's fix was a custom edge that moves a few small ellipses with SVG `animateMotion`, rendered only on highlighted edges, which cut hover jank on a 100-plus-table diagram from about 5 dropped frames to 2 or 3 ([Liam ERD blog](https://liambx.com/blog/tuning-edge-animations-reactflow-optimal-performance)). Animate only the active path.

### Projector rules

Assume 1280x720 or 1920x1080 at low contrast. Use a light theme, 2 to 3 px edges, node labels of at least 18 to 20 px, and a browser zoom preset. Never rely on red versus green alone, since colorblind judges and washed-out projectors both exist. Every state gets an icon and a pattern too. Colors: recall-notice red (about #C62828) for invalidated, safety green for cleared, amber for needs action, and monospace for lot codes. Bundle every font and library locally. Nothing loads from a CDN at runtime.

## The three minutes, second by second, and the video

YC's demo-day advice fits here almost exactly. Say what you do in plain terms first ("Don't bury the lead"). People remember "at most 3 or 4 key points", so choose them and repeat them at the end. Keep slides to about 7 words in large fonts. Use one presenter, rehearse until it's boring, and avoid buzzwords ([YC](https://www.ycombinator.com/blog/guide-to-demo-day-pitches/)). YC also says demos "seldom work" on investor demo day. The way to make it work is to run everything offline and keep the core deterministic.

The three vertebrae: (1) every number carries a lot code; (2) a correction ripples forward precisely, with red and cleared shown side by side; (3) replay can't cheat with the future.

### The live pitch, 3:00

| Time | On screen | Said (roughly) | Brief criterion |
|---|---|---|---|
| 0:00 to 0:15 | Ledger pane, covenant certificate row highlighted. No slide | "On May 15, Tidewall's CFO told its lender leverage was 2.95 times. Today, July 8, the billing system admits it double-counted $118,000 of March revenue. That's under 4% of the year's profit. Is anything actually broken?" | The moment |
| 0:15 to 0:30 | One slide: "Corrections don't travel. Agents keep acting." Footer cites STALE | "Finance agents act on numbers that later change. In a 2026 benchmark, even the best model got only 55% of stale-memory cases right. RECALL gives every number a lot code. We trace any correction forward." | Something new |
| 0:30 to 1:20 | Drop the RECALL NOTICE card on billing export v1. Ripple runs | "Nine things are now wrong. The covenant certificate is 3.03x, a breach. Two board-deck tiles. The Fresno GM's bonus, overpaid by $1,280. The June tax payment. And fourteen things it touched and cleared, each with a reason: the cash forecast didn't move because no cash did, and San Jose's bonus didn't use those rows." Hover one green node | Catches what others missed, doesn't cry wolf |
| 1:20 to 1:45 | Approvals inbox. The agent's first JE is dated March 31. Controller rejects. Agent re-drafts in Q2 with an out-of-period tag, plus a lender notice for the CFO to sign | "It got the first draft wrong. Q1 is locked, and it can't approve its own entry: that's a constraint in the database. The controller said no, and it fixed it." | Recovers, limits, working with others |
| 1:45 to 2:15 | Drag the scrubber to April 10. Billing export v1 opens with the duplicated rows visible. Try to open the July 8 export: REFUSED stamp | "Was the agent negligent? Here's exactly what it saw on April 10. The duplicate was right there. This was knowable, so it's an error, and RECALL owns it: here's the dedupe control it proposes. And it can't peek at the future to look smart." Optional 5 s: the Bayline 1.08 accrual norm, "learned from ten months of invoices, waiting for the controller" | Defends a decision, history changes behavior |
| 2:15 to 2:35 | Proof slide | "23 planted errors, key frozen at hour 10. Precision X, recall Y, versus Z for flagging everything that touched the file. Zero future reads leaked. What's real and what's simulated is on the slide." | Proof |
| 2:35 to 2:50 | Seats slide | "RECALL does the senior close accountant's and the reporting analyst's job every time a source changes. The controller still signs." | Would you hire it |
| 2:50 to 3:00 | Tagline, then hand over the laptop | "Every number has a lot code. Corrections ripple forward precisely. Replay can't cheat. Pick any number and change it." | Invites the judge's scenario |

Rehearse the counts. Whatever the ripple actually shows on the day is what gets said. The "nine" and "fourteen" above are placeholders.

If the slot turns out shorter, cut the norms beat first, then the problem slide. Never cut the green nodes or the replay.

### The demo video, about 2:00 to 2:30

Generic hackathon advice agrees: start by "immediately demonstrating your project", skip the long intro, avoid "fuzzy voice-overs" ([Hackathon.com tips](https://tips.hackathon.com/article/creating-the-best-demo-video-for-a-hackathon-what-to-know)), and split production across teammates rather than leaving it to one person ([DEV: Jacklyn Biggin](https://dev.to/jacklyn/how-to-make-your-devpost-submissions-not-suck-37i0)). Check Devpost for any length limit before cutting.

| Time | Segment | Caption |
|---|---|---|
| 0:00 to 0:12 | The recall card hits the billing export and the ripple spreads. The covenant tile turns red: 2.95x becomes 3.03x | "July 8: one export is corrected. What else was wrong?" |
| 0:12 to 0:25 | Click a board-deck tile and trace it back through lot codes to the source span | "Every number knows where it came from" |
| 0:25 to 1:05 | Forward trace with counts, close-up of a green node and its reason, the bonus offset and corrected certificate proposals | "Invalidated vs checked and cleared" |
| 1:05 to 1:25 | Controller rejects the March 31 JE, the agent re-drafts | "The controller said no. It recovered" |
| 1:25 to 1:50 | Scrub to April 10, the duplicate visible, then the refused July document | "Exactly what it knew, nothing it couldn't" |
| 1:50 to 2:10 | Proof card and real-vs-simulated table | "How we know it works" |
| 2:10 to 2:20 | Seats line and tagline | |

Burn in captions for every line, because gallery judges often watch muted. Record at 1080p or higher with the browser zoomed to 125 to 150% so labels survive compression. Use a real microphone in a quiet room. Mark the core segment "unedited screen capture of the running system", which supports the brief's requirement that the demo be real. Record it from the same frozen build and dataset that produce the proof slide, so the numbers match.

## Hand the judge the red pen, with guardrails

The brief says judges may try their own scenario. That's the biggest functionality risk and the biggest opportunity. Give judges three doors, each constrained enough that nothing on the critical path can break.

### Door 1: "Pick any number and change it"

The judge clicks any source node or ledger cell. A small form appears with a numeric stepper, a dropdown of preset correction types (revised invoice, bank revision, FX fix, duplicate removal, contract amendment), and one question that matters more than the others: "When did this fact first exist?", with options like "before the Q1 close" or "after". That question is the estimate-versus-error test, and asking it is the "knowing when to ask" behavior the brief wants. Validate numeric ranges. The deterministic engine returns the affected set in under a second, and prose rationales stream in afterwards, labeled "drafting explanation".

Know the dramatic thresholds in advance. The covenant breaks once TTM EBITDA drops below $5.50M. Before E11 is applied and after E02 and E10, any extra EBITDA hit above about $64k flips the certificate. Here's a teaching moment worth rehearsing. A judge types "the March utilities invoice is actually $80k" (a $32k swing). If they answer "it arrived after close", RECALL calls it an estimate change, books it in April, and leaves Q1 alone. If they answer "it was in the inbox before close", it's an error: an out-of-period entry, a misstatement-log entry, and a recomputed covenant (about 2.98x, still compliant, so "touched, still valid"). Same number, two correct answers, and the system asks which world it's in instead of guessing.

### Door 2: "Why did you do this on that date?"

A dropdown lists the 5 to 10 executed actions (the May 15 certificate, the May 31 bonuses, the June 12 payment run, the June 15 tax payment). Choosing one moves the scrubber and renders exactly the decision's inputs as of then: lot codes, versions, values. If an LLM wrote the explanation, show the cached version by default, with "regenerate" as an option.

### Door 3: "Try to make it cheat"

A button labeled "Feed it tomorrow's news" plus a field to paste any document ID. The resolver checks the version's `Memento-Datetime` against the pin and shows the refusal with both timestamps. Include one canned sneaky case: a document whose text claims an early date but whose version was captured later. It gets refused, which shows the check uses the version timestamp, not what the content says about itself.

### Fallbacks, in order of how often you'll need them

| Failure | Fallback |
|---|---|
| A judge breaks Scenario A in an interesting way | One-key reset to the canonical snapshot (the same data the proof slide used), plus a "Scenario B" button |
| A judge's edit makes a mess | An undo stack, so the edit can be reverted live |
| LLM slow or offline | Deterministic results show first. Cached prose for every canned scenario. Local model or template text for new edits |
| Proposed fix looks weird | Compensations come only from the fixed menu (reverse, adjust amount, offset, hold, notify, flag for human), never free generation |
| Laptop hangs | A 60 to 90 second screen recording on the desktop and a USB stick, and a second laptop with the same build |
| Projector trouble | Two HDMI and USB-C adapters, a zoom preset, and the reset hotkey written on a sticky note |

Venue Wi-Fi is the reason all of this runs on localhost. The demo must pass with the network unplugged. Rehearse in airplane mode at least twice, once on battery with the projector mirrored.

## Competition: everyone traces backward or invalidates one fact

The honest verdict is that RECALL is adjacent, not taken. Every piece has a neighbor, and no neighbor does the whole loop: claim-level versions, forward propagation with value-aware cutoff across reports, forecasts and executed actions, compensation through approvals, and as-of replay, in finance. Don't claim nobody has thought of dependency invalidation. Doyle did in 1979. Claim the cross-system, finance, action-level version.

### Zep and Graphiti: bitemporal facts, not bitemporal consequences

Graphiti is the closest technical neighbor. It's genuinely bitemporal: edges carry `t_valid/t_invalid` for when a fact held and `t'created/t'expired` for when the system recorded or invalidated it. When an LLM detects a contradiction, Graphiti invalidates the old edge by setting its `t_invalid` instead of deleting it, and it "consistently prioritizes new information" ([Zep paper, arXiv 2501.13956](https://arxiv.org/html/2501.13956)). Its docs say temporal validity "is tracked at the edge level, not the node level" and describe point-in-time queries, but nothing about cascading to derived facts or values ([Graphiti docs](https://mintlify.wiki/getzep/graphiti/concepts/temporal-model)). So it's close on storage and far on semantics. It has no dependency graph from facts to numbers, report lines and payments, no cascade, no compensation layer, and a newest-wins rule that's wrong for finance, where a correction can itself be the bad one (E15). The line: "Graphiti gives you bitemporal facts. RECALL gives you bitemporal consequences." Saying RECALL could store on Graphiti is good for credibility.

### XTrace: the nearest prior art on propagation

XTrace implements AGM belief revision (expansion, revision, contraction), with provenance on each item and retracted beliefs "preserved for lineage". It says "When a high-entrenchment belief changes, the system flags what depended on it: downstream beliefs and artifacts" ([XTrace research](https://xtrace.ai/research/belief-revision-system)). Its own roadmap lists "dependency flagging across beliefs and artifacts" as upcoming, so it's unclear whether that's live. It describes no as-of query, and its examples are go-to-market, design and writing, not finance. Pricing is demo-gated and the claims are marketing only ([xtrace.ai/dev](https://xtrace.ai/dev)). The differentiators: numeric recomputation instead of LLM flagging wherever a formula exists, as-of replay, and compensating actions.

### Rillet: the finance-native neighbor, and evidence the market is moving

Rillet is an AI-native ERP valued at $1B after a $100M Series C in August 2026, about $208.5M raised in total ([Sacra](https://sacra.com/c/rillet/)). A July 2026 release added an audit trail that snapshots the exact ledger data an AI answer used when it ran, logs every AI action and auto-posts nothing without approval. When contracts are amended or usage files arrive, revenue schedules get recomputed with a traceable record of what changed ([Sacra](https://sacra.com/c/rillet/)). That snapshot is the closest finance analogue to Memento, and recompute-on-amendment is a narrow, single-module version of forward propagation. Cite it as validation that the problem is real and timely. The answer to "Rillet already does this" is that its recompute lives inside one module and one ledger. RECALL works across systems and artifacts (board decks, covenant certificates, payments, bonuses, agent decisions) and adds the knowable-then question.

Numeric markets agentic flux, an Agent Builder and "full visibility into every action", with no mention of change tracing or restatement impact ([numeric.io](https://www.numeric.io)). Campfire, DualEntry, FloQast, BlackLine, Basis, Digits and the FP&A tools (Anaplan, Pigment) weren't individually checked. Model-based FP&A tools almost certainly have formula graphs inside their own models, which is the spreadsheet critique again.

### degraph: the open-source comparator

degraph (PyPI 1.0.7, May 2026, MIT, no API keys or external calls) is a "Decision-Evidence Graph: traceable, challengeable, temporal decision provenance for AI agents". It records decisions with evidence, alternatives and "reconsider-if" triggers (time, metric drift, dependency change), traces upstream provenance, computes downstream impact, and exposes 9 MCP tools ([PyPI degraph](https://pypi.org/project/degraph/)). It's the one neighbor you can actually run as a baseline. The difference is finance semantics: degraph flags decisions to reconsider, while RECALL recomputes values, applies materiality and period rules, and proposes the accounting compensation. Use it as baseline B4 if time allows, and name it yourself before a judge does.

### Data lineage tools: right direction, wrong objects

Monte Carlo's field-level lineage tracks column dependencies "from upstream storage to dashboards and reports in the BI layer" for root-cause and impact analysis ([Monte Carlo](https://www.montecarlodata.com/announcing-monte-carlos-end-to-end-field-level-lineage-to-help-teams-achieve-data-trust/)). Atlan sells column-level lineage and impact analysis ([Atlan docs](https://docs.atlan.com/product/capabilities/lineage/concepts/what-is-column-level-lineage.md)). They answer "which dashboard reads this column". They don't answer "which wire did the agent send because of the old value, and what do we do now", and they have no notion of what was knowable when. One lineage vendor says capturing lineage for runtime, AI-generated queries "remains unsolved" ([Promethium](https://promethium.ai/guides/why-data-lineage-tools-miss-ai-generated-queries/)). Langfuse offers versioned dataset experiments, which are user-initiated reruns, not source-change-triggered invalidation ([Langfuse changelog](https://langfuse.com/changelog/2026-02-11-versioned-dataset-experiments)). LangSmith and Arize weren't checked.

### The 2026 papers: each covers one slice

| Work | What it does | What RECALL adds |
|---|---|---|
| EA-Graph ([arXiv 2608.04278](https://arxiv.org/abs/2608.04278)) | Anchors a coding agent's verification claims to content hashes. Verdicts: unaffected, affected, unprovable | Finance artifacts and actions, numeric cutoff, compensation |
| PlanFence ([arXiv 2609.03340](https://arxiv.org/abs/2609.03340)) | Rechecks a plan's inputs before a protected action. 143 to 237 ms stall per action | The retroactive case: actions that already happened |
| GuardWrite ([NeurIPS 2026 workshop poster](https://neurips.cc/virtual/2026/170668)) | Write-time validity predicates and conclusion rewriting in shared agent memory | Applied to board decks and certificates, across systems |
| "What Could the Agent See at 19:05?" ([arXiv 2608.01042](https://arxiv.org/abs/2608.01042)) | Rebuilds past enterprise state for replaying agents in evaluation | An enforcing gate at run time, not just an eval harness |
| STALE ([arXiv 2605.06527](https://arxiv.org/abs/2605.06527)) | Benchmark showing agents fail to act on updated evidence | The problem statement |

A June 2026 survey defines "selective invalidation" of affected claims, actions and derived memories, and names no system that does retraction propagation ([arXiv 2606.04990](https://arxiv.org/pdf/2606.04990)).

### What other track teams will build

Expect AP and invoice-coding agents, reconciliation bots, close or flux copilots, collections agents, fraud detectors and "chat with your ledger" apps. The risk for RECALL is sounding like one more audit trail. Lead with forward propagation and replay, never with logging.

### Positioning lines

| Against | Line |
|---|---|
| Graphiti | "Bitemporal facts versus bitemporal consequences." |
| XTrace | "Flagging dependents is step one. We recompute them, prove which are fine, and draft the reversing entry." |
| Rillet | "Recompute inside one module versus every report, forecast and payment that used the number." |
| Lineage tools | "Lineage tells you which dashboard read a column. We tell you which wire went out because of it." |
| Excel trace dependents | "Spreadsheets trace cells. We trace money that already moved, and what was knowable when." |
| The papers | "They stop a stale plan before it acts. We fix what already acted." |

## Hard questions and the answers

Assign each question an owner on the team and rehearse the answer out loud. Short answers win. Show something on screen whenever you can.

"Isn't this just Excel's trace dependents?" It's half right, and you should say so. Trace dependents shows structural arrows inside a workbook, right now. It doesn't cross systems (ERP, bank feed, contract text, agent action log). It doesn't know which version of a source a value used, or what was knowable at decision time. And it can't tell you a payment already went out and needs a compensating entry approved by someone else. Capturing dependencies at write time is the design, the way a build system works. It's practical now because the writers are machines, and recording their own inputs costs them nothing.

"If the agents declare their dependencies, isn't the graph trivial?" The agent doesn't declare anything. Every read goes through RECALL's tools and gets logged, numbers are computed by RECALL from claim IDs the agent was actually served, and prose cites claim blocks. The hard part isn't the graph. It's deciding what a correction doesn't break: different period, conclusion unchanged, below materiality, estimate versus error. Show a green node.

"How do you know your 'unaffected' verdicts are right?" Most of them aren't judgments. Different period and different line item are structural, because they're different claim IDs. Early cutoff is arithmetic: we recomputed and the value or the conclusion didn't move. Only prose goes to the LLM, it's labeled, low-confidence cases go to a person, and we report its agreement with hand labels separately. Then point at the proof slide.

"Zep/Graphiti already does bitemporal." Yes, and we'd happily store on it. Graphiti invalidates individual facts and prefers the newest information. It doesn't track which numbers, reports and actions were derived from a fact, and it doesn't cascade. We're the consequence layer.

Your trail answers "where did this number come from?" We answer the converse, "where did this source go?", plus "what did the agent know at 2pm on April 10?" Every edge we use is the same entry-level provenance you already record.

"This exists in papers." Name them first: EA-Graph, PlanFence, GuardWrite, the 19:05 replay paper, STALE. They stay inside one agent's memory, one codebase, or an eval harness. We cross source data, documents, forecasts and money that moved, in a company's books, with replay that enforces at run time.

"Isn't Memento just a web-archive protocol?" Yes, and that's the point. It's a mature standard for asking for a resource as of a time. Plain RFC 7089 actually returns the nearest version, even a later one, so the refusal is our own time-pinning profile on top: the pin is set server-side per run, nothing after it is served, and a missing datetime means the pin, not "latest". We list the four deviations in the README.

"Why not 425 Too Early?" We wanted to. RFC 8470 reserves 425 for TLS early-data replay and requires clients to retry, which would loop here. So it's 403 or 404 with an RFC 9457 problem body. The 425 is on a slide as a joke.

"What's real and what's simulated?" Point at the table. The engine, Memento service, refusals, ledger and approvals are real and running. The company is synthetic. One scenario uses Monolithic Power's actual restatement from SEC XBRL data, and the forecast uses real ALFRED vintages.

"Is the E11 treatment right? 3.7% is immaterial." Under the 5% rule of thumb, yes, which is exactly why a naive rule misses it. SAB 99 lists covenant compliance as a qualitative factor that makes a small misstatement material, and this one flips the covenant from 2.95x to 3.03x. It's also over our quarterly performance materiality. We escalate and the CFO signs the corrected certificate. We don't decide materiality for the controller. We hand over the calculation.

"Why isn't E07 a restatement of Q1?" Because the change order didn't exist on March 31. A modification that isn't a separate contract and isn't distinct gets a cumulative catch-up in the period it happens. Replay March 31 and you can see the estimate was right as of then.

"What happens when a correction changes meaning, not a number?" That's the hard case, and we're honest that it's open. One 2026 paper notes its own checks cover "provenance and chronology, not semantic supersession" ([arXiv 2608.01619](https://arxiv.org/abs/2608.01619v1)). We route those to the LLM judge with a needs_review default, and a person decides.

"Does it scale?" Propagation is a bounded walk from the changed claims, so cost scales with the blast radius, not the graph. Whatever isn't reachable is unaffected by construction. Writes are append-only. Quote the real node count and milliseconds from the demo run.

"Why would a company trust it?" It never auto-reverses anything. It proposes from a fixed menu and a different human approves, enforced in the schema. Every verdict cites exact claim versions. Mementos are immutable, so an auditor can reproduce any past view.

"Who buys this?" Platforms that let agents own outcomes, like the one sponsoring this track. The more autonomy, the more actions pile up on top of each bad source.

"What if the agent was wrong in the first place, not the source?" That's E11 and E22. Replay shows the duplicate was knowable, so RECALL calls it an error, owns the miss and proposes a control. It doesn't only defend itself.

## Other prizes, and the naming problem

### Which other prizes to enter

| Prize | Value (per Devpost) | Fit | Notes |
|---|---|---|---|
| Microsoft "Built for the Real World" | $3,800 plus a Surface laptop per member, a presentation at a Microsoft FDE team tech talk, 1:1 mentorship with senior FDEs | Strong | Forward-deployed engineers value "plugs into an existing ERP and agent stack". Watch the naming issue below |
| Microsoft Customer Impact Award | No cash. FDE talk and mentorship | Medium | Same story |
| Most Technically Advanced | NuPhy Air60 HE keyboard per member | Strong | Bitemporal store, TMS-style propagation, a Memento service, an eval harness |
| CRS Best Financial AI Agent | $500 | Direct fit, small | Low effort to enter |
| Convex Best Use | $1,308 plus hardware | Only if Convex is the reactive store | Live invalidations on reactive queries are a natural fit, but it's a stack change. Decide on day one or skip |
| Fetch.ai, Coinbase x402, Factory Droid SDK | Various | Weak | Each needs a bolted-on feature that dilutes the pitch. Skip |

Whether one project can win several of these isn't settled. The Devpost rules page couldn't be read during research, and one past winner's page lists only "1st Overall", which neither confirms nor rules out stacking ([Devpost: FaceTimeOS](https://devpost.com/software/facetime-macos-ai-agent)). Don't ask organizers or sponsors. Read the Devpost rules page and the hacker guide yourself before submitting, and opt into whatever the rules allow. Tailor each prize's write-up to that prize's criteria, and for sponsor prizes say exactly which sponsor tech you used and why ([DEV: Jacklyn Biggin](https://dev.to/jacklyn/how-to-make-your-devpost-submissions-not-suck-37i0)).

### The name: keep the recall metaphor, change the word

"RECALL" collides with two real things. Windows Recall is the Windows 11 feature that periodically screenshots the desktop so users can search it. It was announced in May 2024, delayed after researchers showed its local database was unencrypted, and re-shipped later with encryption and opt-in. Signal, Brave and AdGuard then added protections that block it from capturing their windows ([Wikipedia: Windows Recall](https://en.wikipedia.org/wiki/Windows_Recall)). To a Microsoft judge, "Recall" means a surveillance-memory feature with a security backlash, which is the opposite of what this project stands for. Recall.ai is a YC-backed meeting-bot API company with a reported $10M Series A ([Voicebot.ai](https://voicebot.ai/2024/05/16/generative-ai-meeting-bot-platform-recall-ai-raises-10m/)), so the name isn't ownable in the startup world either. "Hindsight", the obvious alternative for the replay feature, is already Vectorize's open-source agent-memory system ([Vectorize](https://vectorize.io/blog/introducing-hindsight-agent-memory-that-works-like-human-memory)).

My recommendation: call the product Recall Notice. It keeps the product-recall metaphor that makes the demo work, it reads as an event (a notice is issued) rather than a memory feature, and it's distinct from both Windows Recall and Recall.ai. Keep Memento as the name of the replay feature, since it honors RFC 7089 and technical judges will enjoy it. Use "lot code" everywhere in the UI. Never say "Recall for agents". Use Recall Notice on the Devpost page that Microsoft judges read. LotCode is the backup if Recall Notice turns out to be taken. In this document "RECALL" stays as the working name.

## A 36-hour plan for four people

Everything below starts at the opening of hacking. This document, the answer key on paper and the schema sketch are ideation. Writing any of it into code, data files or a repo waits until hacking starts. That includes the Tidewall generator and its data. Public datasets downloaded in advance are fine, because they aren't project work.

### Who owns what

| Person | Owns | Hours 0 to 12 | Hours 12 to 30 |
|---|---|---|---|
| P1: Memento and plumbing | Memento service (TimeGate, TimeMap, mementos), the time-pinning profile and refusals, the MCP data tools with `reads` logging, the LLM cache gateway (record/replay/fallback), the local-model fallback | Service, profile and MCP tools working against fixtures | Moves to the UI: graph canvas, ripple animation, time scrubber and the "future wall" |
| P2: Graph and engine | Schema, claim diff, propagation with early cutoff, materiality and conclusion checks, pre-action fence, ledger with sum-to-zero, compensations, approvals with the schema-level SoD check, eval harness and baselines | Schema frozen by hour 4, propagation on hand-made claims by hour 12 | Compensations, approvals, the E22 flow, eval script, B1 to B3 baselines |
| P3: Agents and judgment | The close/reporting agent using only typed tools, `emit_number`, the citations call for prose, the LLM judge, the replay runner, the correction form parser, the norm miner, loaders for the downloaded MPWR and ALFRED files | Agent loop producing artifacts with captured edges | Judge on prose edges, replay, norms, real-data scenario |
| P4: World and story | The Tidewall generator and dataset (January to July books, all systems, all 23 planted items), the frozen answer key, the ledger and approvals panes, slides, video, pitch. Also checks that every entry balances and the ASC 606 math is right | Critical path: generator plus answer key, frozen and committed by hour 10 | UI panes, proof slide wiring, script, video, rehearsals |

Pick one presenter by hour 24, ideally whoever explains the accounting most clearly. That person stops writing code at hour 30.

### Milestones

| Hour | Milestone |
|---|---|
| 0 to 1 | Agree the schema, the stable claim key and the fixture format on paper, using this document. Create the repo |
| 4 | Schema frozen. Fixture format frozen. P2 and P3 work against hand-made fixtures until P4's data lands |
| 10 | Tidewall dataset loaded. Answer key frozen and committed. Record the hash |
| 12 | End-to-end numeric propagation from a CLI on Tidewall data for E01, E02, E10 and E11, with correct verdicts and reasons |
| 16 | Agent runs recorded through pinned Memento tools. Cache populated. The April 10 refusal works |
| 20 | Compensations and approvals working. E22's reject-and-redraft flow works. LLM judge on prose edges, cached |
| 24 | UI wired: ripple, green nodes with reasons, scrubber, approvals inbox. First full dry run. First Wi-Fi-off test |
| 28 | Eval script produces the proof numbers. Proof slide generated from its output. MPWR and ALFRED scenarios working |
| 30 | Feature freeze. Only bug fixes after this |
| 30 to 34 | Record the video from the frozen build. Five timed rehearsals. Drill ten judge-style corrections, including the $80k utilities case both ways |
| 34 to 36 | Buffer. Submit on Devpost well before the deadline (check the exact time in the hacker guide) |

Stagger sleep so someone who knows each component is always awake. Nobody should touch the frozen answer key after hour 10 without writing a changelog line.

### Cut list, in order

Cut from the top when you're behind. Formance or Fava first. Then Convex, if it was ever considered. Then the recursive norm beat (re-deriving a norm when its history is corrected). Then the ALFRED scenario (E19), since E07 covers the "defends a decision" beat. Then the other learned norms beyond Bayline and Pacific Lumen. Then the Citations API path: fall back to prose generated with claim-block IDs and a cross-check. Then degraph as B4.

Never cut these: the E11 ripple with green nodes and reasons, E22's controller rejection, the April 10 replay and refusal, the proof script, the one-key reset, and replay-mode caching that lets the whole demo run offline. Try hard to keep the MPWR real-data scenario too, because it's what makes "real" on the proof slide more than one word.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The synthetic dataset is late, and everything waits on it | High | P4's only job for 10 hours. P2 and P3 build on hand-made fixtures in the frozen format. Generate the minimum (Q1 to July, the 23 items) before adding texture |
| Accounting mistakes in front of judges who rebuilt Microsoft's revenue systems | Medium | Fix the five answer-key issues above before hacking. Every entry balances in code. Never edit a posted entry. P4 double-checks ASC 606 math. Label unverified rules as company policy |
| Provenance capture is flaky | Medium | Agents touch data only through typed tools. RECALL computes every number. Uncited prose is flagged |
| The LLM judge gets prose wrong | Medium | The judge sees prose edges only and never overrides numeric verdicts. A needs_review bucket, rationales shown, everything cached, agreement reported separately |
| A judge's own scenario breaks something | Medium | Structured correction form, validated ranges, the "when did this exist?" question, undo, reset, Scenario B |
| Venue Wi-Fi or API latency | High | Fully offline. Replay-mode cache, local-model fallback, phone hotspot as a last resort, backup video |
| Over-flagging makes it look like "rerun everything" | Medium | Show green nodes on stage, the naive-baseline counter, and the over-invalidation ratio on the proof slide |
| Infra yak-shaving (XTDB, Formance, pywb, Convex) | Medium | SQLite and a hand-rolled Memento service. The rest are slide-only production swaps |
| Bitemporal theory loses the room | Medium | One 2x2, one sentence ("knowable-then versus true-then"), and the recall-notice metaphor |
| Sounds like another audit-trail project | Medium | Lead with forward propagation and replay. Never open on logging |
| An HTTP or Memento purist objects | Low | Present the refusal as RECALL's own time-pinning profile. List the four deviations. Explain why not 425 |
| A stat gets challenged | Medium | Headline STALE only. Keep the 91 to 100% figure off slides unless the paper is read |
| Name confusion with Windows Recall | Medium for the Microsoft prize | Recall Notice on Devpost. Always pair with the recall-notice visual |
| Using a possible host customer's restatement | Low | Use MPWR on stage, Quantum only as a written precedent |
| Projector washes out red and green | Medium | Icons and patterns on every state, light theme, thick strokes, large labels |
| Team burnout in the last six hours | High | Feature freeze at hour 30. Staggered sleep. The presenter stops coding early |

## Pre-event checklist (no project code before hacking starts)

The rule is simple. Before hacking starts you can think, read, set up machines, sign up for accounts and download public data and images. You can't write project code, build the generator or create the dataset. And you can't ask sponsors or organizers for help. Everything below stays inside those lines.

| Task | Why | Effort |
|---|---|---|
| Read the Devpost rules page and the hacker guide in full: prize stacking, sponsor opt-in limits, submission deadline, video requirements | Decides which prizes are real upside, and the exact deadline. Read it, don't ask | 20 min |
| Open the full "Agents Retrieve but Do Not Re-Derive" paper (not just the poster page) and confirm the 91 to 100% figure, its premise condition and its models. Check MemDerive (arXiv 2610.25373) too | Decides whether it can appear even in Q&A. STALE stays the headline either way | 20 min |
| Re-read the STALE abstract and note the exact wording | It goes on the problem slide | 5 min |
| Read the abstracts of EA-Graph, PlanFence, the 19:05 paper and the GuardWrite poster, plus degraph's PyPI page and XTrace's belief-revision post | The prior-art answer in Q&A | 30 min |
| Read RFC 7089's TimeGate rules and RFC 8470 section 5.2 again | Misquoting the standard you build on is fatal with technical judges | 15 min |
| Fix the five answer-key issues on paper (E04 date, E11 materiality wording, headroom figure, gym allocation, unverified rules labeled as policy) | Ideation, so allowed, and it saves an hour on day one | 30 min |
| Search "Tidewall Climbing", "Bayline Power", "Kletterwerk", "Summit Mats Supply", "Pacific Lumen Labs", "Northgate Biotech", "Redwood Commercial Credit" and "UC Sierra" | Avoids accidentally impersonating a real business | 15 min |
| Search Devpost and trademarks for "Recall Notice" and "LotCode" | Settles the name | 10 min |
| Download SEC `companyfacts.zip` (or MPWR's companyfacts JSON, CIK 0001280452) with a browser or a one-off curl. Set a User-Agent with contact info and stay under 10 requests per second | The real-data scenario, offline. Inspect one file's field names | 15 min |
| Register a free FRED API key and download a few employment-series vintages (all real-time periods) as files | E19, offline | 20 min |
| Download the MPWR 8-K and the Quantum 8-K pages for offline reference | Q&A backup | 5 min |
| Install Python 3.11, Node, a SQLite browser, and the Ollama runtime. Pull a small model's weights. Pre-pull any Docker images you might use | Venue Wi-Fi will be bad. Setup isn't project code | 45 min |
| Create and test LLM API keys and check rate limits. Bring a phone hotspot | The record-mode cache gets filled at the event | 15 min |
| Download fonts and front-end libraries you plan to vendor, at pinned versions you've used before | No CDN at runtime | 15 min |
| Assign roles P1 to P4 and the presenter. Walk through this document's schema and propagation steps together on paper | Saves the first three hours | 45 min |
| Pack two HDMI/USB-C adapters, chargers, a USB stick for the backup video, and a second laptop | Stage risk | 10 min |

## Conclusion

The most useful thing that came out of designing this in detail is that the accounting rules and the computer science line up exactly. The estimate-versus-error test that decides how a correction gets booked is, literally, a query on the transaction-time axis: was the fact in the system when the number was made? That means Memento isn't just a replay gimmick bolted on for the "defends a decision" beat. It's the evidence the controller needs to classify the correction at all, and it's equally willing to show the agent missed something (E11) as to clear it (E07). In the same way, SAB 99's qualitative factors turn out to be the "conclusion unchanged" early cutoff in disguise. A correction matters when it flips something a downstream artifact asserts, like a covenant line or a bonus tier, not when it crosses a fixed percentage. Pitch it that way and the project stops looking like infrastructure with a finance skin. It becomes the way a careful senior accountant already thinks, made mechanical and fast.

The strategic point is that RECALL's differentiation lives in the green nodes, not the red ones. Flagging what a correction touched is easy, and every neighbor from lineage tools to XTrace does a version of it. Proving what it didn't break, with a reason a controller would accept, is what nobody publicly ships. That's what the proof slide's over-invalidation ratio measures. False alarms are what kill autonomy at scale. Spend the build budget there, and on making the judge's own scenario survive, rather than on extra integrations.
