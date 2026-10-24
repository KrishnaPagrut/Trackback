# Trackback

**Trackback is TrackBack for agents. When work you built on changes, you get pinged, and you fix your own piece.**

Tagline: *Trackback traces any correction forward.*

The product is a dependency graph across agents. Three agents build on each other's work. Every artifact records which agent and which run produced it, and exactly which upstream agent outputs and source versions it consumed (a hash-stamped consumption receipt). When a source is corrected, or an agent revises its own earlier output, Trackback works out the blast radius, recomputes the numbers itself, and sends one trackback ping per affected agent per wave. Each pinged agent re-checks its own piece and answers still_valid (with a reason), reworked (new version) or needs_human. Executed actions get compensations approved by a human who is not the preparer. Memento replays what each agent knew when it acted. Tidewall is the stage the agents perform on; the corrections timeline is the script; the answer key is how we prove the graph and the pings got it right.

Three AI agents do real record-to-report work for Tidewall Climbing Co., a fictional chain of six California climbing gyms. Every source they read is stored as versioned claims with two clocks (when the fact applies, and when the system learned it). Every number, report sentence, forecast cell and executed action they produce records exactly which claim versions it relied on. When a source is corrected, Trackback walks the dependency graph forward, recomputes numbers in plain code, stops where values or conclusions don't move enough to matter, asks an LLM only about prose, and returns a verdict for every touched artifact: invalidated, unaffected (with a reason), needs review, or unprovable. Actions that already moved money get a compensating action from a fixed menu, routed to a human approver who is not the preparer. Memento replays any past decision exactly as the system saw it, and refuses to serve anything published after the decision time.

Seats: *Trackback does the senior close accountant's and the reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign.*

The name revives TrackBack, the 2002 Movable Type protocol that let a site notify another site when it referenced it; the replay feature is called Memento after RFC 7089.

## Run it

```bash
make setup                       # venv + deps + frontend deps, copies .env.example to .env
make world                       # generate Tidewall, run the agents through history, write the canonical snapshot
make eval                        # both answer keys, baselines, leak test, replay fidelity -> data/eval/latest.json
make check                       # offline demo check: replay forced, networking off, every beat
make demo                        # build the frontend, restore the snapshot, serve http://localhost:8000 in replay mode (works offline)
make reset                       # restore the canonical snapshot (the R hotkey does the same)
make test                        # pytest
```

`make world` builds with a writer: `TRACKBACK_LLM_MODE=record` calls Claude through the Anthropic API and fills the cache; anything else builds with `scripted`, a deterministic in-process provider that drives the same tools and reuses every recorded response whose cache key matches. `replay` is cache-only and fails loudly on a miss; `make eval`, `make check` and `make demo` always use it. `make check` is the airplane-mode check: replay forced, outside networking refused in-process, every demo beat run against a copy of the snapshot.

### Two views

- **Stage mode** (the default, `/`): the presentation view. Four lanes (sources and the three agents), about ten cards, one thing moving at a time. `Space` advances through the title card, the layered reveal of who built on whom, the recall notice, the ripple with each ping as a plain-language bubble in the receiving lane, each agent's reply, and the payoff number read from the run. `Backspace` goes back, `R` resets, `T` shows April 10 and the refusal stamp. Left idle for 60 seconds it plays itself on a loop with captions; any key hands it to the visitor with three preset corrections (the billing duplicate, a 40-cent bank fee that pings nobody, a utilities invoice) and "Paste your own".
- **Deep mode** (`D`, or `/?mode=deep`): the full instrument. Six swimlanes of ledger cards on a dotted canvas, the results list with a filter and Built on / Built upon, a 420 px drawer (Who built this, Claim history, Approvals, Ping log, Norms), the film-strip scrubber, `⌘K` search, Graph | Ledger, the proof page, and the footer with live counts and key hints. `D` again returns to Stage mode where you left it.
- `/styleguide` shows the tokens, the type scale, the ledger card in every state, the lane rail and the three hero moments. Add `?kiosk=off` to any URL to disable the attract loop.

Secrets live in `.env` (git-ignored): `ANTHROPIC_API_KEY`, optional `META_API_KEY`, optional `FRED_API_KEY`.

Recorded model responses survive rebuilds: `make history` exports the cache to `data/llm_cache/cache.jsonl` (real-model rows only), and `make generate` seeds every fresh world from it. So `TRACKBACK_LLM_MODE=record make world` re-uses each recorded turn whose cache key still matches (same prompt, tools, pin and corpus) and only pays for new turns; `scripted` builds also pick those rows up, which is why a scripted world can carry some real Claude Sonnet prose. The proof page reports how many cache rows came from the real model versus the scripted stand-in. The pre-iteration-2 record-mode world is kept at `data/snapshots/canonical_i1_record.sqlite` for reference.

## Deploy it

`docker build -t trackback . && docker run -p 8000:8000 trackback` gives the whole demo (API, Memento, UI, the world, replay mode, no key) on one port. `deploy/DEPLOY.md` has the Fly.io one-liner, the Render setup and the caveats (one shared world per instance; press `R` to reset).

## The trackback ping protocol v1

Lineage: TrackBack (Six Apart, Movable Type, August 2002; spec 1.2 dated August 1, 2004), Pingback 1.0, and Webmention (W3C Recommendation, January 12, 2017). TrackBack died of spam because pings were never verified. Trackback fixes that structurally: the hub is the only thing that can create pings, and a ping only travels along a consumption receipt the hub itself recorded at read time, with a matching content hash.

- Message: CloudEvents 1.0 envelope (`type: dev.trackback.ping.v1`), PROV-O names for the provenance fields, HMAC-SHA256 over the canonical JSON of `data`. One ping per agent per wave bundles every suspect node that agent owns, with the causal chain and each node's changed fields (old, new, delta, threshold crossed).
- Endpoints: `GET /.well-known/trackback` (discovery), `POST /artifacts/{id}/versions` and `/retract` (agent revisions, retractions), `POST /corrections`, `POST /agents/{id}/trackback` (202 + `Location: /pings/{id}`; duplicate idempotency key returns the existing Location), `GET /pings/{id}`, `POST /pings/{id}/response`, `POST /challenges`, `GET /corrections/{id}/graph`, `GET /events` (SSE from the outbox).
- Synchronous refusals (400 class): `malformed`, `self_ping`, `unknown_target`, `stale_target`, `not_a_dependent`, `hash_mismatch`, `hop_limit`, `cycle`, `unauthenticated`.
- Response states: `acknowledged`, `still_valid`, `reworked`, `needs_human`, `refused`, `superseded`, `failed`.
- Why it always stops: versions are immutable and receipts point at specific versions, so the graph is a DAG; one ping per agent per wave; `MAX_WAVES = 2` per root correction; `MAX_HOPS = 6`; a target already in its causal chain is refused as a cycle; no self-pings; an oscillation guard on content hashes (A to B to A escalates); `MAX_LLM_CALLS_PER_EVENT = 12`. Agents cannot create pings; a downstream agent that disputes an upstream output files an upstream challenge, which goes to a human.
- The protocol is shaped to map onto MCP (`notifications/resources/updated` as the doorbell, SQLite as the mailbox) and A2A 1.0 (`SendMessage` with a Trackback extension; response states to TaskState). Neither adapter is built in this version; the mapping is in `docs/multi_agent_design.md`.

The core (`backend/trackback/core/`) is domain-agnostic; the finance rules live in `backend/trackback/domains/finance/` behind `core/domain.py`'s `DomainPack` (see `backend/trackback/domains/README.md`).

## Architecture (text)

```
                     agents (Close Accountant · Reporting Analyst · Covenant & Comp)
                       │  tool-use loop, max 25 turns, pinned_at per run
                       ▼
   tools.py  ── get_document / search_claims / get_claim ──►  Memento service (/r /tg /m /tm)
             ── emit_number (safe formula evaluator) ─────►  artifacts + justification edges
             ── emit_sentence (Citations API / markers) ──►  sentence + citation edges
             ── propose_journal_entry / propose_action ───►  approvals inbox (CHECK proposer <> approver)
                       │
   SQLite, append-only, bitemporal: sources, source_versions (mementos), claims, claim_versions,
   artifacts, justifications, reads (every read, refusals too), corrections, claim_diffs,
   impact_findings, actions, approvals, ledger_entries (sum to zero), llm_cache, norms
                       │
   core/propagate + core/waves: diff ─► seeds ─► deterministic walk (calc nodes recomputed; early cutoff; materiality and
            conclusions from the domain pack) ─► suspect judgment/prose/action nodes bundled per owning agent ─► one ping per
            agent per wave (core/pings) ─► rework runs answer still_valid / reworked / needs_human (agents/rework) ─►
            compensations for executed actions ─► fence (pre-execution) ─► findings in one transaction
                       │
   FastAPI (api.py) + Vite/React/React Flow UI served from one process on :8000
```

## The time-pinning profile over RFC 7089

Plain Memento is the wrong behaviour for leak prevention: a TimeGate asked for a datetime before the first memento MUST return the first memento, one asked after the latest returns the latest, and a missing `Accept-Datetime` SHOULD return the latest. Every one of those silently hands an agent a document from its future. Trackback keeps the RFC's four resources (original, TimeGate with 302, memento with `Memento-Datetime`, TimeMap in `application/link-format`) and adds four deviations:

1. The pin is set server-side and bound to the agent run (`X-Trackback-Run`). The client's `Accept-Datetime` is never the authority; anything later than the pin is refused.
2. If the first memento postdates the pin (the document did not exist yet), the answer is 404, not the RFC's first memento.
3. A direct fetch of any memento whose `Memento-Datetime` is after the pin is refused (403).
4. A missing `Accept-Datetime` in a pinned session resolves to `pinned_at`, never to "latest".

Refusals are `403` (a version exists but postdates the pin) or `404` (nothing existed as of the pin) with an RFC 9457 `application/problem+json` body (`type: https://trackback.local/problems/temporal-pin-violation`, fields `pinned_at`, `requested_datetime`, `first_memento_datetime`) and a `Trackback-Pinned-At` header. Pinned TimeMaps list only versions up to the pin.

**Why not 425 Too Early?** We wanted it. RFC 8470 reserves 425 for TLS 0-RTT replay and requires clients to retry; a future-dated request can never succeed by retrying, and an RFC 8470 stack could loop. So 425 lives on a slide, and the wire carries 403/404 with problem+json.

## Real vs simulated

| Real | Simulated |
|---|---|
| The claim graph, propagation engine, early cutoff and materiality logic | Tidewall Climbing Co., its gyms, vendors, customers and people |
| The Memento service, TimeMaps, pin enforcement and refusals | The bank feed, ACH processor, billing system and AP inbox |
| Typed-tool provenance capture and the LLM judge (cached) | The 23 planted errors (designed from cited accounting rules) |
| The ledger, compensations and approval workflow with schema-enforced segregation of duties | Lender, credit agreement and covenant definition |
| Lyft's February 13, 2024 release (Exhibit 99.1 as filed, 500 basis points), the CFO's correction on the call (50), and the tape; the finance-team documents and the outside-world dependents are reconstructions built from those public numbers and labeled as such | Agent runs: 193 recorded Claude responses (Sonnet agents, Opus judge, Citations API) are replayed where the request matches; the rest, including every rework ping, is the scripted stand-in until the API balance allows a record-mode rebuild (STATUS.md; the proof page counts the rows) |

Unverified rules are labeled "company policy" in the data: the NACHA limit on re-presenting R01 debits, the IRS rule for applying an estimated-tax overpayment, and the "10% and $25k" flux threshold.

## Real world: Lyft, February 13, 2024

The `Real world: Lyft` tab (hotkey `W`) tells one public story from inside a finance team. Lyft's Q4 2023 release guided to "approximately 500 basis points" of Adjusted EBITDA margin expansion; the CFO corrected it to 50 on the 4:30 pm ET call; the stock had risen as much as 67% after hours in between. In the reconstruction, the FP&A agent's model says 50, the Reporting/IR agent's draft sentence cites that number and says 500, the CFO approves, and the pre-execution fence blocks publication: a sentence that cites a figure must show it, and the same digits at another magnitude is a mismatch (`core/fence.py`, `figure_mismatch`; not Lyft-specific, runs on every action). The right-hand side replays what actually happened: the real release goes out, a newsroom and a sell-side desk build on it (reconstructed), the correction lands at 5 pm, and Trackback pings the two outside agents, clears the Q4-beat sentences that never cited the guide, and proposes compensations for the story and the filled order. What is real and what is reconstructed is labeled on every line; the as-filed exhibit is in `data/public/lyft/`.

## Requirements mapping

| Brief | Where |
|---|---|
| Sources that disagree | Contract net-45 vs customer master net-30 (E16); spoofed IBAN email refused (E15); bank vs ledger (E05) |
| Time: March changes June | E02 timesheets existed at close: error, out-of-period entry; Bayline norm learned from ten winter months |
| Working with others | Approvals inbox; the Controller rejects the March-dated draft (E22); the agent re-drafts |
| Limits | `CHECK (proposer <> approver)` in the schema; only the CFO signs lender documents; period locks |
| Explainable and accountable | Every artifact carries lot codes to exact claim versions; Memento replays any decision; the proof page |
| The moment | E11: $118k duplicate, 2.95x becomes 3.03x; cleared nodes with reasons; owned miss (knowable on April 10) |

## Layout

See `backend/trackback/` (engine, agents, memento, api), `backend/scripts/` (generate, build_history, eval, snapshot, apply_correction), `frontend/`, `data/` (public, generated, answer_key, snapshots, eval). `STATUS.md` is the current state; `DECISIONS.md` lists every call made while unattended; `TIMELINE.md` is the world's calendar.
