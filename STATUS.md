# STATUS.md

## v3 (current): building to SPEC.md, keeping every iteration-2 feature, for Tidewall and Lyft

Freeze: Sunday 2026-10-25 04:00 PT. Submission: 09:00 PT.

| Checkpoint | State | Proof |
|---|---|---|
| CP0 housekeeping | done | SPEC.md is v3; CLAUDE.md; tasks.py; v2 tests pass on Windows (27) |
| CP1 world | done | `python tasks.py world` in 2.4 s; `python tasks.py test`: 11 v3 calibration tests (TTM $32.0M close / $32.6M draft, cash $10.6M, 2.95x → 3.0208x / 3.0681x, overpaid bonuses $8,400/$7,200/$4,800, tax $195,000, $662k / $1.118M, Appendix A 40/23/5) |
| CP2 detect | done | `tests/test_v3_cp2_detect.py`: exactly six exceptions (X1 $750,000 duplicate import, X2 $140,000 unaccrued, X3 $58,000 true-up, X4 $18,750 duplicate invoice, X5 $2,310 R01, X6 $312.40 fee); P1 known x6; 12 in transit, 3 outstanding checks, 1 FX rounding, subset-sum, known short-pay, SSU alias; Priya's handoff confirmed 1-6, finished 7-9 |
| CP3 trace | done | `tests/test_v3_cp3_trace.py`: 49/49 lineage truths + 6 derived cells; H1 stale; X1 ripple 40 invalidated / 23 still valid / 5 compensations in 0.2 s (30 of 191 metrics recomputed; naive 43); X2/X4/X6 match the key; Replay refuses the Jul 8 export at an Apr 10 pin (403) |
| CP4 judge | done | `tests/test_v3_cp4_judge.py`: aggregate $662,000 (passes) / $1,118,000 (fails); v1 calls X1 immaterial (4.69%), Jade overrules (covenant 3.0208x, compensation); Jade overrules X3 to a change in estimate; flags lender routing to the CFO; escalates the locked March posting to Dana |
| CP5 act (+ pings) | done | `tests/test_v3_cp5_act.py`: Dana rejects the March-dated entry, the agent re-drafts in June tagged to March, self-approval raises, Jul 15 bonus run held for R1/R2/R4 and released by Lena's approval, Summit Mats held, Sam signs the corrected certificate, reminders and escalation, memo renders; X1 wave pings all three agents (reworked / needs_human / still_valid with reasons), cash forecast skipped, Priya's notice routed to Marco; S1 pings only the Reporting Analyst; S2 coalesced; S3 to Dana with no wave |
| CP6 prove | done | `python tasks.py eval` writes data/eval/latest.json in ~11 s: 34 cases (6 Tidewall + 28 variants over 9 families); 6/6 exceptions, 0 noise false alarms; lineage 55/55; X1 40/23/5 vs 43 naive; materiality accuracy naive 5% rule 0.59, v1 0.59, v1+Jade 1.00; Jade catches 43/43 planted mistakes, 0 false overrules; Replay 0 leaks |
| CP7 learn | done | four lessons from Jade's overrules and Dana's rejection pass the regression gate and are approved by Dana; the over-general 'closed-period invoices are estimates' lesson fails the gate (breaks X2 and the invoices received before the close); held-out pass rate v1 0.28 -> v2 1.00 |
| Lyft parity | done | `tests/test_v3_lyft.py`: the tracer reads the real as-filed exhibit (25 figures, 24 tie to the reconstructed close pack and guidance model; 500 bps has no source and matches the model's 50 at another power of ten); release-to-sources exception; v1 calls it immaterial, Jade overrules (qualitative) and flags the routing (CFO + General Counsel); the fence blocks the inside release; the correction pings only the newsroom and the sell-side desk (headline and note reworked, order and story needs_human, Q4 sentences skipped); the General Counsel rejects the silent fix, the agent re-drafts a CORRECTING and REPLACING release, the CFO approves; memo; 5 variants detected correctly |
| CP8 UI | done | Stage mode runs the Section 2 sequence from the keyboard for Tidewall (10 beats) and Lyft (7 beats), numbers from the API, live beats for Dana's rejection, the General Counsel's rejection and the Replay refusal; Deep mode tabs Reconcile, Trace, Graph, Evaluate, Pings, Approvals, Memo, Time travel, Scorecard, Lessons, Access; judge doors (change any number, why on that date, try to make it peek); kiosk loop; screenshots in docs/screenshots/v3 at 1280x720 and 1920x1080 |
| CP9 polish | done | `python tasks.py check`: 25 of 25 checks offline (replay forced, outside connections refused in-process); record mode with real Claude (Sonnet 5.5 agent, Opus 5.5 Jade; 23 cached responses, 0 stand-ins in the canonical world); README, PITCH, DEVPOST, TIMELINE current; Dockerfile serves web/ with no Node stage |
| CP10 live learning + time travel | done | Deep > Lessons gates each proposed lesson live (four pass, 'closed-period invoices are estimates' fails), Dana approves, re-run under v2 needs no Jade corrections (`tests/test_v3_cp7_learn_live.py`); Deep > Time travel shows the timeline with the not-knowable-after wall, the version served at the pin, a 403 on the peek and the books as of the pin (`/api/asof`), for Tidewall and Lyft; 77 tests, check 25/25 |

Next three tasks: rehearse from PITCH.md; optional docker build where Docker exists; small UI polish from the screenshots.

---

# v2 status (frozen at commit 06bbbc9)

## Current phase
Built to SPEC.md Part 1, amended by SPEC_ITERATION_2.md, with the frontend following DESIGN.md. The canonical world is built in scripted mode with 193 recorded Claude responses reused where their cache keys match; a full record-mode rebuild is blocked on API credits (see "Needs Krishna"). The demo runs offline in replay mode from `data/snapshots/canonical.sqlite`.

## Definition of done

From SPEC.md Part 1 section 14, SPEC_ITERATION_2 section 17 and the goal brief. Each item names the command or file that proves it.

- [x] `make demo` on a fresh clone plus the canonical snapshot runs fully offline. Proof: `make check` forces replay, refuses every non-loopback connection in-process, and runs every beat against a copy of the snapshot (`backend/scripts/demo_offline_check.py`); fonts and libraries are bundled (no CDN in `frontend/dist`).
- [x] Dropping the E11 recall notice shows the breach (leverage 2.946x → 3.030x against 3.00x), cleared nodes with reasons, the compensations, and the E22 rejection and re-draft. Proof: `make check`.
- [x] The E11 ripple crosses all three agent lanes: the Close Accountant's March deferred-revenue memo is reworked; Covenant and Comp's certificate, bonuses and tax payment need a human with a compensation each; the Reporting Analyst's deck needs a human, three sentences are reworked and "Q1 revenue grew year over year" stays still_valid with a reason. Proof: `make check`.
- [x] The 13-week cash forecast is skipped with "Skipped, no material change" (16 cash forecast nodes checked, none pinged). Proof: `make check`; Stage mode step 4 shows the badge.
- [x] Scrubbing to April 10 shows billing export v1 with the duplicated rows; the July 8 export is refused with 403 and both timestamps. Proof: `make check`; Deep mode `T`; Stage mode `T`.
- [x] X1: the Close Accountant revises its own estimate and only the Reporting Analyst is pinged. Proof: `make check`.
- [x] "Who built this" on the deck's covenant sentence shows Reporting Analyst ← Covenant and Comp (leverage) ← Close Accountant (TTM EBITDA, EBITDA, membership revenue, recomputed by Trackback) ← billing export v1. Proof: the Deep mode drawer.
- [x] The Real world tab passes. Per Krishna's decision, Lyft's February 13, 2024 "500 basis points" release replaces Monolithic Power: the release is blocked before publishing (states 500, cites 50), the real correction pings the two outside agents, and fixes are proposed for the filled order and the published story. Proof: `make check`.
- [x] The proof page shows real eval numbers and both key hashes: ping precision and recall, false still_valid, unnecessary rework, inspection fraction, LLM calls versus rerun-all, over-invalidation versus B1, Memento leaks, replay fidelity. Proof: `make eval` writes `data/eval/latest.json`; every tile reads from it.
- [x] The core never imports or names the finance pack. Proof: `grep -r "domains" backend/trackback/core` prints nothing; the registry loads packs from `config.PACK_MODULES`.
- [x] `make test` exits 0 (27 tests).
- [x] Design: `/styleguide` exists; Stage mode is the default and runs title card → layered reveal → recall notice → ripple → replies → payoff from keypresses alone, with the payoff numbers read from the run; `D` toggles to Deep mode and back without losing state; the kiosk attract loop starts after 60 s idle and hands control to a visitor on any input; the 40-cent preset shows zero pings. Proof: `backend/scripts/kiosk_check.py` (all checks pass).
- [x] Screenshots of DESIGN.md's nine states at 1280x720 and 1920x1080 in `docs/screenshots/round-1` to `round-4`, with 25% copies of the Stage shots; written critique and fixes per round in `docs/design-review.md`. Proof: `backend/scripts/design_shots.py N`.
- [x] Nothing under 13 px anywhere, measured after the canvas zoom. Proof: `backend/scripts/type_floor_check.py` (smallest rendered text 13.0 px in every state at both sizes).
- [x] STATUS.md, README.md, PITCH.md and DEVPOST.md are current.

## Works (and the command that proves it)
- `make test`: 27 tests (Memento profile, ping refusals, HMAC, idempotency, discovery, append-only, sum-to-zero, schema segregation of duties, the extra-zero check, the cache seed, and snapshot restores with existing/concurrent readers).
- `make world`: generates Tidewall, runs every agent through the history in scripted mode (record mode with `TRACKBACK_LLM_MODE=record`), reuses the 193 recorded responses in `data/llm_cache/cache.jsonl`, builds the Lyft scenario, writes the snapshot. 188 artifacts and 305 receipts at rest.
- `make eval`: both scorers, merged into `data/eval/latest.json` with a computed `headline` block. Per-artifact key: 21 corrections, precision 1.000, recall 1.000, 222 of 222 verdicts and reasons, 104 of 104 decoys cleared, over-invalidation 1.00 versus 5.59 for flag-everything, 0 leaks in 288 adversarial fetches, replay 162 of 162. Multi-agent key: 23 events, ping precision and recall 1.000, exact agent set in 23 of 23, false still_valid 0 of 27, unnecessary rework 0 of 14, 65 of 65 preserved, 12 of 12 compensations with correct amounts, 125 of 125 tie-outs, max one wave, 1 LLM call in waves versus 318 for rerunning every agent, mean inspection fraction 7%.
- `make check`: the offline demo check described above.
- `make demo`: builds the frontend, restores the snapshot, serves http://localhost:8000 in replay mode. Stage mode at `/`, Deep mode with `D` or `/?mode=deep`, `/styleguide`, kiosk off with `/?kiosk=off`.
- Deployable: `Dockerfile`, `fly.toml`, `deploy/DEPLOY.md`. The image build itself is unverified on this machine (no Docker).

## Broken / pending
- Record mode: the iteration-2 rebuild with the real model stopped with "credit balance is too low". Rework replies in pings are the labeled scripted stand-in until it is rerun.
- Not built (stretch): A2A/MCP adapters, a second domain pack (the "Research" world shows disabled), the Mermaid sequence panel, the Muse adapter, the recursive norm beat, ALFRED/E19.
- Sound on pings is off by default and toggles with `M` in Deep mode.

## Verification after copying
- Fixed the Makefile so npm and Vite both use the available Node 22 runtime; selecting npm alone still launched the system Node 20 and failed the frontend build.
- Added development-server proxies for `/pings`, `/challenges`, and `/.well-known/trackback`. Verified each returns JSON through Vite.
- Corrected Stage source cards for utilities and other custom corrections: show the actual source name instead of always labeling it as the March billing export.
- Refreshed both evaluation reports from replay evaluations against database copies. Their answer-key hashes now match the current YAML files. Results: 222/222 verdicts and reasons, expected agents for 23/23 events, zero future-data leaks in 288 attempts, and 162/162 identical replayed artifacts.
- Fixed reset/undo replacing a live SQLite file while worker connections were open. Reset, undo, and CLI restore now use SQLite's backup API; regression tests cover existing readers and concurrent resets. HTTP verification passed 80 graph reads overlapping 10 resets and a database integrity check.
- Validation passed: 27 backend tests, TypeScript checking, production frontend build, `make check`, the kiosk/preset checks, browser quality checks at 1280×720 and 1920×1080, reduced-motion playback, a typed utilities correction, the time-travel refusal after E11, and the proof/Lyft/styleguide pages.
- The offline checker now keeps undo snapshots in its temporary directory. Browser verification also used a separate database, preserving the working demo state.
- A fresh scripted world rebuild with external networking disabled also passed both evaluation suites: 222/222 verdicts and reasons, 23/23 expected agent sets, and 162/162 identical replayed artifacts. The browser demo was rerun after the restore fix with no page errors or server errors.
- Remaining limits: React lint warnings and the frontend bundle-size warning remain. Live record-mode calls and deployment were not tested in this verification.

## Needs Krishna
1. Top up the API balance, then `TRACKBACK_LLM_MODE=record make world && make eval && make check`. Only new turns are paid for.
2. Rehearse from PITCH.md in Stage mode with Wi-Fi off; leave the laptop in kiosk mode at the table.
3. Optional: `make docker-build` once Docker is installed; `fly deploy` per `deploy/DEPLOY.md`.

## Iteration 2 checklist
- [x] I2-0 to I2-7: core/pack split, receipts, ping protocol, waves, rework runs, lanes UI, eval v2.
- [ ] I2-8 adapters, I2-9 second domain pack (stretch): not built.
