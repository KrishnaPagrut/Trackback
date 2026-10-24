# Trackback

**Trackback does the close accountant's error review: when sources disagree, it finds what broke, sizes it, drafts the fix and the memo, and never posts anything without the controller.**

*Hyphenate traces any number back. Trackback traces any correction forward.* The name comes from TrackBack, the 2002 blogging protocol that let a page notify everything that referenced it.

Built for the Hyphenate track at Cal Hacks 13.0. Two worlds run on the same engines:

- **Tidewall Climbing Co.** (synthetic): 48 gyms in six regions, about $185M of revenue, a $105M term loan, and leverage reported at 2.95x against a 3.00x covenant. The March import of one billing batch ran twice: $750,000 of revenue counted twice. Under 5% of pretax income, so a simple rule shrugs; it breaks the loan covenant (3.02x), overpays three regional bonuses and the Q2 tax, and sits in a certificate already sent to the bank.
- **Lyft, February 13, 2024** (real): the Q4 release furnished on an 8-K said "approximately 500 basis points" of margin expansion; the model behind it, and the CFO on the call, said 50. The tracer reads the real filing, finds the one figure with no source, and Trackback shows what would have happened with it inside (the release is blocked) and what did happen outside (only the work built on the 500 is pinged).

## What it does, step by step

1. **Detect.** Four reconciliations at the pinned time: billing to GL, bank to cash book (lags learned from history, Hungarian matching), cash application (aliases, acronyms, subset-sum for bundled wires, learned short-pay habits) and AP review. Matched items, cleared differences with a reason, and exceptions.
2. **Trust.** Each exception names its system of record and why (the billing line export over the GL's summary import).
3. **Trace.** The lineage tracer links every number people typed into spreadsheets, decks and certificates back to the books, with nobody having drawn the link: workbook formulas evaluated by its own whitelisted evaluator, display precision ($32.6M is 32.6M ± 50k), label scoring with hints, stale detection (the deck's $32.6M was typed from the April 9 draft), derived cells, small-sum reconstruction. The ripple then walks the graph: reach, recompute, early cutoff, conclusions, compensations for actions that already moved money.
4. **Evaluate.** The agent writes an Error Evaluation, seven questions as structured claims with evidence: what happened, which source to trust, error or estimate or new fact, how big (SAB 108 rollover and iron curtain), does it matter, what it touched, the fix.
5. **Review.** Jade, a second reviewer, checks every claim: numbers recomputed from the engines, evidence looked up, classification asked of Replay, materiality run with the full framework (both methods, SAB 99 qualitative tests computed through the graph, aggregation with the misstatement log), posting and authority checked; only wording goes to an LLM.
6. **Ask.** Corrections and compensations go to the right people (entries to Dana, lender documents to Sam, offsets to Lena, vendor credits to Marco; Priya's items to her delegate while she is out). The proposer can never approve (`CHECK (proposer <> approver)` in the schema). Risky actions are held. Busy approvers get reminders and escalation on a simulated clock. Dana rejects the March-dated entry ("Q1 is locked"); the agent re-drafts in June with an out-of-period tag.
7. **Report.** An error memo per material exception, in the format a controller hands an auditor, every line citing its evidence.
8. **Learn.** Mistakes caught by Jade or by people become proposed lessons; a lesson needs Dana's approval and must pass a regression gate (the whole scorecard rerun) before it changes the playbook.

And iteration 2's multi-agent graph runs inside it: three agents (Close Accountant, Covenant and Comp, Reporting Analyst) built on each other's work before July 8, each piece recording what it read in a hash-stamped consumption receipt. When the review finds the error, the hub sends **one trackback ping per agent per wave**; each agent answers `still_valid` (with a reason), `reworked` (new version) or `needs_human`. People get an inbox notice for the lines they typed by hand.

## Where AI is and isn't used

Math decides what matches and what it's worth; AI handles judgment and language, and everything it says gets checked.

| Component | How |
|---|---|
| Reconciliation matching | Code: normalization, candidate scoring, Hungarian assignment (scipy), subset-sum, learned lag windows and short-pay habits |
| Lineage tracer | Code: file parsing, formula evaluation, value matching at displayed precision, label scoring, version matching, small-sum reconstruction |
| Ripple | Code: structural reach, recompute, early cutoff, conclusion checks |
| Materiality | Code: thresholds, SAB 108 both methods, qualitative tests via the graph, aggregation |
| Agent | A versioned playbook decides; Claude (Sonnet 5.5) writes the root cause, the explanations and the memo prose |
| Jade | Code checks every numeric, evidence, policy and authority claim; Claude (Opus 5.5) critiques only the wording |
| Pinged agents | Executed actions are always `needs_human`; figures are re-rendered from Trackback's calc nodes; Claude answers for prose |

Everything works with no API key (deterministic templates, labeled). With `ANTHROPIC_API_KEY` set and `TRACKBACK_LLM_MODE=record`, Claude writes the words; every response is cached, so the demo replays offline byte for byte.

## Run it (Windows or macOS)

```bash
python tasks.py setup      # venv (Python 3.11) + backend deps + frontend deps; copies .env.example to .env
python tasks.py world      # generate Tidewall and Lyft, run the agents' history, run the review, write the canonical snapshot (~10 s)
python tasks.py test       # pytest: calibration, recons, tracer, ripple, materiality, Jade, workflow, pings, scorecard, Lyft (76 tests)
python tasks.py eval       # the scorecard over 36 cases -> data/eval/latest.json (replay mode)
python tasks.py check      # airplane-mode check: replay forced, outside connections refused in-process, every Stage beat
python tasks.py demo       # restore the snapshot and serve http://localhost:8000 (replay, offline); the built UI is committed in web/
python tasks.py reset      # restore the canonical snapshot (the R key does the same)
TRACKBACK_LLM_MODE=record python tasks.py world   # re-record the model's words (pays only for new prompts)
```

`make <target>` runs the same targets on macOS. The frontend source is in `frontend/` (`python tasks.py web` rebuilds `web/`).

### Two views

- **Stage mode** (the default): the three-minute story, one beat per `Space`: the title card, four reconciliations with one row turning red, the evidence side by side (the billing line, both GL imports, Priya's workbook cell, the deck line, the certificate line), the ripple across lanes (Trackback, people, three agents, executed actions; red with old and new values, green with reasons, envelopes for pings), Jade's overrule, the approvals, Dana saying no (live), Replay on April 9 with the refusal stamp, the scorecard, the memo and the seat line. `W` switches to the Lyft track. `Backspace` goes back, `R` resets, `C` opens "Change any number". Left idle for a minute it plays itself with captions; any key hands it back.
- **Deep mode** (`D`): Reconcile, Trace (the files rendered with every linked cell highlighted, and "who built this, on top of whom"), Graph (lanes plus a zoomable graph and every node's verdict), Evaluate (the seven questions with Jade's verdict on each claim), Pings, Approvals (act as each person, fast-forward the clock, try a self-approval), Memo, Time travel, Scorecard, Lessons, Access.

Judge doors: **Change any number** (describe a correction in words; it runs live: ripple, sizes, materiality, the agent, Jade, who it would ping), **Why on that date?** (any executed action replayed with its inputs as of its pin), **Try to make it peek** (ask for a later version under an earlier pin: refused with both timestamps).

## Replay: the time-pinning profile over RFC 7089

Every source keeps every version with the time it was captured (the Memento protocol's Memento-Datetime). Plain RFC 7089 is the wrong behaviour for decisions: a TimeGate asked for a time before the first version returns the first version, and an unpinned request returns the latest, so an agent can be handed a document from its future. Trackback keeps the protocol's resources (`/r`, `/tg` with 302, `/m` with `Memento-Datetime`, `/tm` in `application/link-format`) and deviates on purpose:

1. The pin is set server-side and bound to the run; the client's `Accept-Datetime` is never the authority.
2. If the first version postdates the pin, the answer is 404, not the first version.
3. A direct fetch of a version captured after the pin is refused (403).
4. A missing `Accept-Datetime` in a pinned session resolves to the pin, never to "latest".

Refusals are RFC 9457 `application/problem+json` (`type: https://trackback.local/problems/temporal-pin-violation`, with `pinned_at`, `requested`, `first_available`). **Why not 425 Too Early?** RFC 8470 reserves 425 for TLS early-data replay and tells clients to retry; a future-dated request can never succeed by retrying. So 425 lives on a slide and the wire carries 403/404.

Replay answers the estimate-versus-error question (was the fact in any system when the original number was made?) and the "own the miss" beat: on April 9 at 6:00 PM, the billing export already showed batch B07 once and the GL import log already showed it twice.

## The trackback ping protocol v1 (iteration 2)

Lineage: TrackBack (Six Apart, 2002; spec 1.2, 2004), Pingback 1.0, Webmention (W3C, 2017). TrackBack died of spam because pings were never verified; here the hub is the only thing that can ping, and a ping only travels along a consumption receipt the hub recorded at read time, with a matching content hash.

- CloudEvents 1.0 envelope (`dev.trackback.ping.v1`), HMAC-SHA256 over the canonical JSON; one ping per agent per wave bundling its affected nodes with the causal chain and each changed field (old, new, delta, threshold crossed) plus the inputs that did not move.
- Endpoints: `GET /.well-known/trackback`, `POST /agents/{id}/trackback` (202 + Location; idempotent), `GET /pings/{id}`, `POST /pings/{id}/response`, `POST /challenges`, `GET /events` (SSE).
- Refusals: `malformed`, `self_ping`, `unknown_target`, `stale_target`, `not_a_dependent`, `hash_mismatch`, `hop_limit`, `cycle`, `unauthenticated`. Caps: one ping per agent per wave, `MAX_WAVES = 2`, `MAX_HOPS = 6`, an LLM-call budget per event, an oscillation guard. Agents never ping each other; a downstream agent that disputes upstream work files an upstream challenge, which goes to a human.
- Scenarios: S1, an agent revises its own work (only the Reporting Analyst is pinged; Covenant and Comp is not, `different_period`); S2, the two bank fact updates arrive together and coalesce into one wave (the $312.40 fee alone would ping nobody); S3, the Reporting Analyst challenges the Close Accountant's allocation (to Dana; no wave starts).

## Proof

`python tasks.py eval` writes `data/eval/latest.json`; the Scorecard tab and the Stage scorecard read only that file. At the freeze:

| | |
|---|---|
| Exceptions found | 6 of 6; 0 false alarms on noise variants |
| Lineage links | 55 of 55 (49 linked or policy, 6 derived); the deck's $32.6M flagged stale |
| X1 ripple | 40 invalidated, 23 still valid with reasons (63 of 63 reasons right), 5 compensations; 30 of 191 metrics recomputed in 0.12 s |
| Materiality accuracy | 5% rule 19/32, agent alone 19/32, agent with Jade 32/32 |
| Jade | 43 of 43 planted agent mistakes caught, 0 false overrules on 82 correct claims |
| Learning | four lessons pass the gate; the over-general one fails it (breaks X2); held-out cases 5/18 (v1) to 18/18 (v2) |
| Pings (X1) | all three agents, precision and recall 1.0; 0 false still_valid; 0 unnecessary rework |
| Replay | 0 leaks in 73 adversarial fetches |
| Lyft | 24 of 25 figures in the real filing tie; the one that doesn't is 500 bps; 5 of 5 variants detected |

The answer key (`data/world/answer_key.json`) is written by the generator from its own reference arithmetic (`world/refcalc.py`), never from the engines it grades.

## Real vs simulated

| Real | Simulated |
|---|---|
| The reconciliation, lineage, ripple and materiality engines; Jade's code checks; the scoring | Tidewall Climbing Co., its books, people and files (labeled synthetic everywhere) |
| File parsing (xlsx formulas, pptx, pdf, the SEC exhibit) | The planted cases and the 30 variants |
| The ping protocol, the approvals schema with segregation of duties, Replay's pinning and refusals | Lyft's close pack and guidance model, its agents, and the outside newsroom and sell-side desk (reconstructions built from the public numbers, labeled) |
| Lyft's Exhibit 99.1 as filed (500 bps), the CFO's correction (50), Business Wire's CORRECTING and REPLACING release, the tape | The agents' history before July 8 (recorded runs of Claude where cached; scripted otherwise, labeled) |

## Layout

```
backend/trackback/
  config.py  cli.py  review.py  hub.py  jade.py  workflow.py  memo.py  lessons.py  api_v3.py  check.py
  world/     generator.py refcalc.py human_files.py files.py answer_key.py build.py history.py lyft.py
  engine/    books.py replay.py recon.py lineage.py graph.py materiality.py
  agent/     playbook.py agent.py llm.py rework.py
  eval/      cases.py scorecard.py
  core/      the iteration-2 core: db, pings, receipts, Memento endpoints, LLM gateway, approvals, waves (v2)
frontend/src/v3/   Stage, Deep, Lanes        web/   the built UI (committed)
data/world/        the generated files, the human files, the answer key, Lyft's files
```

`SPEC.md` is the v3 build spec; `SPEC_ITERATION_2.md` the multi-agent amendment; `STATUS.md` the current state; `DECISIONS.md` every call made while building.
