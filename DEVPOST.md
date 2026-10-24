# Trackback

**Headline:** Trackback is TrackBack for agents. When work you built on changes, you get pinged, and you fix your own piece.

**Tagline:** Trackback traces any correction forward.

**Seats:** Trackback does the senior close accountant's and the reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign.

## What it does

Three AI agents (a Close Accountant, a Reporting Analyst, and a Covenant & Comp analyst) do real record-to-report work for Tidewall Climbing Co., a fictional chain of six California climbing gyms with a term loan, a 3.00x leverage covenant, ACH dues, corporate wellness contracts, a wall-build division and GM bonuses. Every source they read (bank statements, billing exports, contracts, FX tables, the materiality memo) is stored as versioned claims with two clocks: when the fact applies and when the system learned it. Every number, sentence, forecast cell and executed action records exactly which claim versions it rested on, down to a lot code.

Agents read each other's outputs only through the hub, which writes a consumption receipt with the fields read. When a source is corrected, or an agent revises its own earlier output, Trackback walks the dependency graph forward. It recomputes numbers in plain code, stops where values or conclusions don't move enough to matter, asks an LLM only about prose, and then sends one trackback ping per affected agent per wave, along hash-verified receipts only. Each pinged agent re-checks its own piece and answers still_valid (with a reason), reworked, or needs_human. Actions that already moved money get a compensating action from a fixed menu, routed to a human approver who is not the preparer. Memento replays any past decision exactly as the system saw it and refuses, with an HTTP 403 and both timestamps, to serve anything published after the decision time.

The moment: on July 8 the billing system admits a February migration double-counted $118,000 of March revenue. A naive "under 5% of pretax" rule shrugs. Trackback follows it into the Q1 lender certificate (2.97x becomes 3.03x against a 3.00x covenant), two board-deck tiles, the Fresno and Oakland GM bonuses and the Q2 tax estimate, and shows 44 things it checked and cleared, each with a reason. Its first correcting entry is dated into locked Q1 and tries to self-approve; the database's CHECK constraint says no, the controller rejects the date, and the agent re-drafts in June with an out-of-period tag. Replay April 10 and the duplicate rows are visibly in the export the agent read, so Trackback owns the miss and proposes a dedupe control.

## How we built it

Python 3.11, FastAPI, SQLite (append-only, bitemporal: the only UPDATE allowed closes a transaction-time interval), a hand-rolled RFC 7089 Memento service with a time-pinning profile (four documented deviations, RFC 9457 problem bodies, no 425 on the wire), a safe formula evaluator so the model never does arithmetic, the Anthropic Messages API behind a record/replay cache (agents on Claude Sonnet 5.5, the judge on Claude Opus 5.5 to avoid self-preference; the Citations API path for prose with a claim-marker fallback), a truth-maintenance-style propagation engine with build-system early cutoff, a fixed compensation menu, a PlanFence-style pre-execution fence, learned norms mined from the correction log with a hard deny-list, and a Vite + React + React Flow UI served from the same process, typeset like a ledger crossed with a recall notice (Newsreader, IBM Plex, bundled). Stage mode is the presentation view: four lanes, ten cards, one ping bubble at a time, a payoff number read from the run, and a kiosk loop that plays itself at the table and hands over to a judge on any key. Deep mode is the full instrument. The whole demo runs offline in replay mode, and `make check` proves it with networking refused in-process.

## The real-world story: Lyft, February 13, 2024

Lyft's Q4 2023 earnings release said Adjusted EBITDA margin would expand by "approximately 500 basis points" in 2024. The number in the CFO's prepared remarks, and in the model, was 50. The stock rose as much as 67% after hours before the correction on the call, and closed up 35% the next day on the quarter itself. The `Real world` tab rebuilds that afternoon from inside Lyft's finance team: an FP&A agent's model says 50, a Reporting/IR agent's draft cites that number and says 500, the CFO approves, and Trackback's pre-execution fence blocks the release before it leaves the building, with the fix rendered in place. Then it replays what actually happened outside the company: the real release, a newsroom and a sell-side desk that built on it, the correction at 5 pm, two pings, three cleared sentences, two compensations. Only the release, the correction and the tape are real; the internal documents and the outside dependents are reconstructions from those public numbers, labeled as such on screen.

## Real vs simulated

Real: the claim graph, propagation engine, early cutoff and materiality logic; the Memento service, TimeMaps, pin enforcement and refusals; typed-tool provenance capture and the LLM judge (cached); the ledger (sums to zero, integer cents), compensations and approvals with schema-enforced segregation of duties; Lyft's February 13, 2024 release as filed (500 basis points), the CFO's correction on the call (50), and the tape.

Simulated: Tidewall, its gyms, vendors, customers and people; the bank feed, ACH processor, billing system and AP inbox; the 23 planted errors, each designed from a cited accounting rule (ASC 250, ASC 606, SAB 99, NACHA return codes); the lender and credit agreement. Unverified rules are labeled "company policy" in the data. Agent runs: the frozen build replays 193 recorded Claude responses (Sonnet 5.5 agents, Opus 5.5 judge, Citations API prose) where their cache keys match; the rest, including the agents' rework replies to pings, is a labeled deterministic stand-in until a full record-mode rebuild. The proof page counts which is which. For Lyft, the finance-team documents and the outside dependents are reconstructions from the public numbers.

## Proof

Two answer keys, both hand-written before the engine was tuned, hashes on the proof page, later edits in a changelog. Per artifact (git tag `answer-key-frozen`): 21 corrections, precision 1.000 and recall 1.000 on invalidated artifacts, 222 of 222 verdicts and reasons, 104 of 104 decoys cleared, over-invalidation 1.00 versus 5.59 for flagging everything that touched the file, 0 future reads leaked in 288 adversarial attempts, replay 162 of 162 artifacts byte-identical. Multi-agent (tag `answer-key-v2-frozen`), 23 events including an agent's self-revision, two coalesced corrections and an upstream challenge: ping precision 1.000 and recall 1.000, the exact set of agents pinged in 23 of 23, 0 of 27 must-change nodes wrongly waved through, 0 of 14 unnecessary rework, 65 of 65 must-stay nodes preserved, 12 of 12 compensations with the right amounts, 125 of 125 tie-outs, every event settled in one wave, 1 LLM call in waves versus 318 to rerun every agent. Every number is read from `data/eval/latest.json`, which `make eval` writes.

## The story behind the names

TrackBack (2002) was the Movable Type protocol that let a site notify another site when it referenced it. Trackback does that for numbers inside a company, forward. Memento is RFC 7089, the HTTP time-travel standard; plain Memento returns the nearest version even if it's later, so Trackback adds a time-pinning profile: the pin is server-side per run, nothing after it is served, a missing datetime means the pin, and a document that didn't exist yet is a 404. We wanted to answer with 425 Too Early; RFC 8470 reserves it for TLS replay with mandatory retry, so it stays on a slide.

## Challenges

Deciding what a correction does not break is the whole product: different period and different line item are structural, early cutoff is arithmetic, conclusions (covenant, bonus tier, sign of a trend) can absorb a change that a dollar threshold cannot, and ratios need no dollar threshold at all. Estimate versus error (ASC 250) turned out to be a query on the transaction-time axis, which is what Memento answers. Keeping replays byte-identical meant keeping every state-dependent field out of what the model sees.

## What's next

A full record-mode run of the rework pings with the real model (the agents' history runs and the Citations API are recorded; the ping replies are the scripted stand-in until the API balance is topped up, and the proof page says which rows are which); A2A and MCP adapters so any agent framework can receive a trackback; a second domain pack (research citations) to show the core has no finance in it; the recursive norm beat (correct one Bayline invoice and the 1.08 factor goes back to review); XTDB as the production store.

## Finance capabilities

Pick a company and a corner: Tidewall's record-to-report seat. Sources disagree (contract vs master, bank vs ledger, a spoofed vendor email that is refused). Time: a March fact changes June's accrual policy. Working with others: an approvals inbox where the controller says no and the agent recovers. Limits: `CHECK (proposer <> approver)` in the schema, period locks, the CFO alone signs lender documents. Explainable and accountable: every verdict cites exact claim versions, every decision replays. Judges can type their own correction: the form asks "when did this fact first exist?" and the deterministic impact set returns in milliseconds.

## For Most Technically Advanced

A bitemporal append-only store, a Memento service with an enforcing profile, a truth-maintenance walk with value-aware cutoff, typed-tool provenance capture that makes the dependency graph complete by construction, replay-as-cache determinism, and an eval harness with three baselines and a frozen key.

## For Microsoft "Built for the Real World"

It plugs into an existing ERP and agent stack without replacing either: sources are documents, agents only touch data through three read tools, and every output carries provenance a forward-deployed engineer can audit. The real-data scenario is a public company's actual restatement parsed from SEC XBRL.

## For CRS Best Financial AI Agent

Three agents with named seats, limited access, a clean record and a habit of asking when timing or materiality is ambiguous, judged against a planted answer key.
