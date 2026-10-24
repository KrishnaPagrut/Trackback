# STATUS.md

## Current phase
Freeze with the real model. Everything in the definition of done is built, recorded with Claude Sonnet 5.5 (agents) and Claude Opus 5.5 (judge), snapshotted, and replays offline.

## Works (and the command that proves it)
- `make test`: 10 tests (Memento profile, refusals, append-only, sum-to-zero, schema SoD).
- `TRACKBACK_LLM_MODE=record make world`: 20 agent runs with the real model (every required artifact produced; 2 to 18 tool turns each), 17 history corrections, approvals and executions, E14 fence block, norms N1 (proposed 1.08) and N2 (approved), MPWR two vintages from the SEC JSON, replay cache primed for the live flows. 169 artifacts, 688 edges, 537 findings, 160 cached LLM responses, 0 unbalanced entries. Citations API works with these models (CITATIONS_OK).
- `TRACKBACK_LLM_MODE=record make eval` → `data/eval/latest.json`: 21 corrections; invalidated precision 1.000 / recall 1.000 (116 tp, 0 fp, 0 fn); 222/223 verdicts, 223/223 reasons; decoy specificity 107/107; over-invalidation 1.00 vs B1 6.01; B3 ask-the-agent (real model) precision 0.54 / recall 0.91; 0 leaks in 279 adversarial fetches; replay fidelity 153/153; judge agreement 0.96 (Cohen's κ 0.90, n = 25). The one verdict difference: the Opus judge sent `cash_s_may` to needs_review under E04 ($189 R10 return); the key says unaffected. That is the "knowing when to ask" path, left as measured.
- `make demo` (replay mode, offline) + `make check`: PASS. Headless UI walkthrough: 0 console errors. Screenshots in `data/eval/screens/`.
- Live E11 through the UI (`N`) or `POST /api/live/e11`: naive 55; Trackback 33 invalidated + 4 need action + 44 cleared; leverage 2.966x → 3.030x; compensations: corrected certificate (CFO), bonus offset $2,320 (HR + Controller), tax installment $24,780 (Controller), deck v2 (Controller); E22 recovery recorded (locked-period draft, schema-rejected self-approval, Controller rejection, June re-draft). Scenario B (E20), undo and reset work.
- Docs: README, PITCH.md (real counts, $80k drill, hard Q&A, shot list), DEVPOST.md, TIMELINE.md, DECISIONS.md, answer key CHANGELOG.

## Known limits
- Graph labels in the E11 hero view are small at 720p until you zoom (React Flow controls). Consider further grouping if the projector is weak.
- Not built (stretch, cut list): Muse Spark adapter, recursive norm beat, ALFRED/E19, degraph B4.
- A judge's brand-new red-pen edit in replay mode gets the deterministic heuristic judge for prose (labeled `fallback:` in the finding) since there is no cached Opus response for it; numbers are exact regardless.

## Needs Krishna
1. Rehearse from PITCH.md with `make demo` and Wi-Fi off (`make check` first). Press `?` for hotkeys.
2. Keep `.env` on the laptop; nothing in the demo needs the network.
3. Optional: ALFRED vintages in `data/public/alfred/`; Meta key for Muse.

## Next three tasks (if time remains)
1. Recursive norm beat (correct one Bayline winter invoice → norm back to needs_review).
2. Tighter hero layout for a 720p projector.
3. degraph as baseline B4.
