# STATUS.md

## Current phase
V3 reconciled onto the verified build (Oct 24): Jade the reviewer, the lessons memory with recall and a regression gate, hover explanations on every card, a Jade beat and a lesson beat in Stage mode, Jade and Lessons tabs in Deep mode, Jade and learning numbers on the proof page. Built to SPEC.md Part 1, amended by SPEC_ITERATION_2.md, with the frontend following DESIGN.md; the V3 spec's reviewer, lessons and judge doors are grafted onto this world rather than the 48-gym rewrite (DECISIONS.md, Oct 24). The canonical world is built in scripted mode with 193 recorded Claude responses reused where their cache keys match; a full record-mode rebuild is blocked on API credits (see "Needs Krishna"). The demo runs offline in replay mode from `data/snapshots/canonical.sqlite`.

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
- [x] `make test` exits 0 (31 tests).
- [x] V3: Jade reviews every correction and overrules the agent's "immaterial" call on E11 with the real numbers; the overrule and the Controller's rejection propose lessons; the regression gate passes the narrow lessons and rejects the broad one; only the Controller can approve (an agent gets 403); the playbook reaches v2. Proof: `make check` (nine Jade/lessons checks) and `backend/tests/test_v3_jade_lessons.py`.
- [x] V3: `make eval` writes the `learning` block (Jade catch rate and false-overrule rate; held-out v1 vs v2; lessons approved and rejected) and the proof page reads it. Proof: `backend/scripts/eval_learning.py`.
- [x] V3: hover on any card in Stage or Deep mode shows what happened to it in words (`explain()` in `frontend/src/model.ts`); Stage mode shows the Jade card and the lesson card between the replies and the payoff; step dots in the caption. Proof: `docs/screenshots/round-5`.
- [x] Design: `/styleguide` exists; Stage mode is the default and runs title card → layered reveal → recall notice → ripple → replies → payoff from keypresses alone, with the payoff numbers read from the run; `D` toggles to Deep mode and back without losing state; the kiosk attract loop (opt in with `?kiosk=on` or `K`, off by default after Krishna saw it reset the stage mid-demo) starts after 60 s idle and hands control to a visitor on any input; the 40-cent preset shows zero pings. Proof: `backend/scripts/kiosk_check.py` (all checks pass).
- [x] Screenshots of DESIGN.md's nine states at 1280x720 and 1920x1080 in `docs/screenshots/round-1` to `round-4`, with 25% copies of the Stage shots; written critique and fixes per round in `docs/design-review.md`. Proof: `backend/scripts/design_shots.py N`.
- [x] Nothing under 13 px anywhere, measured after the canvas zoom. Proof: `backend/scripts/type_floor_check.py` (smallest rendered text 13.0 px in every state at both sizes).
- [x] STATUS.md, README.md, PITCH.md and DEVPOST.md are current.

## Film
- `brag-output-2026-10-24-film/trackback-demo.mp4`: the demo portion (~2:27, 1080p, narrated, captioned); the black-and-white skit is cut in front by the team. Script: `docs/VIDEO_SCRIPT.md`; rebuild notes: `brag-output-2026-10-24-film/README.md`.

## Live
- https://trackback-gamma.vercel.app (Vercel, project `trackback`, production). Opens in Deep mode with the nine-step guided tour; `D` or `?mode=stage` for Stage mode. Verified end to end from a headless browser twice in a row (tour, the E11 drop, 3 of 3 agents pinged, Jade's overrule, Stage payoff 10 of 174 with 4 fixes waiting), see DECISIONS.md for the serverless consistency design.

## Works (and the command that proves it)
- `make test`: 31 tests (Jade's playbook and overrules, lessons, the gate and recall; Memento profile, ping refusals, HMAC, idempotency, discovery, append-only, sum-to-zero, schema segregation of duties, the extra-zero check, the cache seed, and snapshot restores with existing/concurrent readers).
- `make world`: generates Tidewall, runs every agent through the history in scripted mode (record mode with `TRACKBACK_LLM_MODE=record`), reuses the 193 recorded responses in `data/llm_cache/cache.jsonl`, builds the Lyft scenario, writes the snapshot. 188 artifacts and 305 receipts at rest.
- `make eval`: both scorers, merged into `data/eval/latest.json` with a computed `headline` block. Per-artifact key: 21 corrections, precision 1.000, recall 1.000, 222 of 222 verdicts and reasons, 104 of 104 decoys cleared, over-invalidation 1.00 versus 5.59 for flag-everything, 0 leaks in 288 adversarial fetches, replay 162 of 162. Multi-agent key: 23 events, ping precision and recall 1.000, exact agent set in 23 of 23, false still_valid 0 of 27, unnecessary rework 0 of 14, 65 of 65 preserved, 12 of 12 compensations with correct amounts, 125 of 125 tie-outs, max one wave, 1 LLM call in waves versus 318 for rerunning every agent, mean inspection fraction 7%.
- `make check`: the offline demo check described above, now including Jade's E11 overrule, the lessons' states, the gate's rejection of the broad lesson, playbook v2 and the 403 for an agent approving a lesson.
- `make eval` also writes the `learning` block: Jade on playbook v1: 13 of 13 planted agent mistakes caught, 0 false overrules in 63 correct claims; held-out learning: playbook v1 80.6% → v2 100.0% on 36 claims the agent never learned from, 4 lessons approved, 1 rejected by the regression gate.
- `make demo`: builds the frontend, restores the snapshot, serves http://localhost:8000 in replay mode. Stage mode at `/`, Deep mode with `D` or `/?mode=deep`, `/styleguide`, kiosk off with `/?kiosk=off`.
- Deployable: `Dockerfile`, `fly.toml`, `deploy/DEPLOY.md`. The image build itself is unverified on this machine (no Docker).

## Broken / pending
- Record mode: the iteration-2 rebuild with the real model stopped with "credit balance is too low". Rework replies in pings are the labeled scripted stand-in until it is rerun.
- Jade critiques judgment claims only in code; the LLM critique of prose (V3 spec section 8) is not wired, and no API credits exist to record it. Lessons are enforced as playbook checks; the "guidance text pulled into the LLM context" path is stored on each lesson but not sent anywhere.
- The V3 prototype engines (48-gym world, reconciliations, lineage tracer) are not in the tree: they describe a different company and would have discarded every verified number.
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
2. Rehearse from PITCH.md in Stage mode with Wi-Fi off; at the table open `/?kiosk=on` so it loops and hands over to judges.
3. Optional: `make docker-build` once Docker is installed; `fly deploy` per `deploy/DEPLOY.md`.

## Iteration 2 checklist
- [x] I2-0 to I2-7: core/pack split, receipts, ping protocol, waves, rework runs, lanes UI, eval v2.
- [ ] I2-8 adapters, I2-9 second domain pack (stretch): not built.
