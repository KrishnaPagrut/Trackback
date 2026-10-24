# TRACKBACK ITERATION 2: the multi-agent handoff graph and trackback pings

You already have the first Trackback build prompt (Part 1 build spec plus Part 2 design appendix). This document is iteration 2. It is an amendment on top of that prompt, not a replacement. Precedence from now on: this document wins over Part 1, and Part 1 wins over Part 2. Everything in Part 1 that this document doesn't change still stands, including the event rules, the "never stop to ask" working style, the Tidewall world, the accounting rules, Memento, the offline demo and the definition of done.

How to apply it depending on where you are:
- If you haven't reached milestone M4 (engine) yet, fold these changes into the plan now and build them in from the start.
- If you're past M4, finish the milestone you're on, commit and tag it, then work through Section 14's added milestones as a refactor. Don't throw away working code. Extend the schema with new tables and columns. Never rewrite tables in place.

---

## 0. Housekeeping first (do this before anything else)

1. Save the first prompt to the repo root as `SPEC.md` if it isn't there already, and save this document as `SPEC_ITERATION_2.md`. Long runs compress old conversation history, and the spec must survive that.
2. Create or update `CLAUDE.md` at the repo root with exactly this content (adjust paths if needed):

```
# Trackback: standing instructions
- Before starting any milestone, re-read SPEC_ITERATION_2.md, then the Part 1 section of SPEC.md, then STATUS.md.
- Precedence: SPEC_ITERATION_2.md > SPEC.md Part 1 > SPEC.md Part 2 (design appendix).
- The spec is final and approved. Do not brainstorm, do not ask clarifying questions, do not wait for plan approval. Decide, log the decision in DECISIONS.md, and keep going.
- If a skill or plugin (for example a brainstorming or plan-approval skill) wants to ask the user questions or wait for approval, skip that step. Test-driven development, systematic debugging and verification-before-completion skills are welcome.
- Commit at least every 45 minutes. Update STATUS.md at every milestone.
- Demo clock is pinned to 2026-07-08T09:00:00-07:00. Final demo must run offline in replay mode.
- Never commit .env. Never call external services from the app except the Anthropic API in record mode.
```

3. Add an iteration-2 section to `STATUS.md` listing the new milestones (Section 14) and mark which ones are done.

---

## 1. What changes, in one paragraph

Iteration 1 made the fake company and its planted errors look like the product. They aren't. The product is a dependency graph across agents. Three agents build on each other's work. Every artifact records which agent and which run produced it, and exactly which upstream agent outputs and source versions it consumed. When a source is corrected, or when an agent revises its own earlier output, Trackback works out the blast radius, recomputes the numbers itself, and sends a trackback ping to each downstream agent whose work is actually affected. Each pinged agent re-checks its own piece and answers "still valid, here's why", "reworked, here's the new version", or "needs a human". Executed actions get compensations approved by a human who isn't the preparer. Memento replays what each agent knew when it acted. Tidewall is the stage the agents perform on, and the corrections timeline is the script. The answer key is how we prove the graph and the pings got it right.

New headline for the README, Devpost and pitch: "Trackback is TrackBack for agents. When work you built on changes, you get pinged, and you fix your own piece."

Keep the tagline: "Trackback traces any correction forward."

---

## 2. Vocabulary changes (apply everywhere: UI, docs, code comments, PITCH.md, DEVPOST.md)

- "Planted errors" becomes "the corrections timeline". Each item E01 to E23 is a correction event that arrives at a point in time. The answer key stays and is described as "the expected outcome of every correction event".
- "Blast radius" stays, but the main visual is now the ripple crossing agent lanes.
- A "ping" is a trackback ping from the Trackback hub to an agent. Agents never ping each other directly. The hub is the only thing that can create pings (that's the anti-spam rule).
- A "wave" is one pass of propagation for one correction event.

---

## 3. The core and the finance domain pack (new architectural rule)

Split the code into a domain-agnostic core and a finance domain pack. The core must not import anything from the domain pack. The domain pack plugs into the core through one interface.

Core (`trackback/core/`): versions, artifacts, edges and consumption receipts, the wave scheduler, ping protocol and outbox, Memento, the LLM gateway, approvals mechanics, Memento replay, the event stream.

Finance pack (`trackback/domains/finance/`): materiality rules, period locks, estimate-vs-error classification, "not affected" reasons, the compensation catalog, approver roles, tie-out checks, the norms miner.

Interface (`trackback/core/domain.py`), implemented by the finance pack:

```python
class DomainPack(Protocol):
    name: str
    def is_material(self, node, old_value, new_value, conclusions) -> tuple[bool, str]: ...
    def classify_correction(self, correction, knowable_at, original_artifact_time) -> str: ...  # estimate | error | fact_update
    def unaffected_reason(self, node, change) -> str | None: ...   # different_period, different_line_item, below_materiality, conclusion_unchanged, ...
    def compensation_for(self, action) -> dict: ...               # from a fixed catalog
    def approver_for(self, action_or_compensation) -> str: ...    # role name
    def can_post(self, entry) -> tuple[bool, str]: ...            # period lock check
    def tie_out_checks(self, artifact_versions) -> list[dict]: ...
```

Add a two-line `trackback/domains/README.md` saying the core is domain-agnostic and the finance pack is one implementation. In Q&A, Krishna will open this file to show the generality is real.

---

## 4. Data model additions

Keep the iteration 1 schema. Add these (append-only, same conventions):

- On `artifacts`: `agent_id` (close_accountant, reporting_analyst, covenant_comp, or `trackback` for calc nodes the engine computes), `node_kind` (`source`, `calc`, `judgment`, `prose`, `action`), `origin` (`source_correction`, `agent_revision`, `rework`, `initial`), `supersedes_version`, `content_hash`, `reason`, `approved_by`.
- `consumption_receipts(receipt_id, consumer_artifact_id, consumer_version, consumed_artifact_id, consumed_version, consumed_sha256, fields_read_json, run_id, agent_id, ts)`. Written automatically whenever an agent reads another agent's artifact through the hub. This is the "verified link" TrackBack never had: pings only travel along receipts whose hashes match.
- `waves(wave_id, correction_id, wave_no, started_at, finished_at, status)`.
- `pings(ping_id, idempotency_key UNIQUE, correction_id, wave_id, root_ping_id, hop, causal_chain_json, target_agent_id, payload_json, state, refusal_code, created_at, delivered_at, responded_at)`.
- `ping_responses(ping_id, state, reason, evidence_json, new_versions_json, material_change, responded_at)`.
- `upstream_challenges(challenge_id, from_agent_id, target_artifact_id, reason, state, created_at)`: the only way a downstream agent can ask an upstream agent to change something. It creates a new wave only if a human approves it.
- `outbox(event_id, kind, payload_json, created_at, sent_at)`: everything the UI event stream sends comes from here.

Node kinds and who handles them:
- `source`: documents and claims from the systems.
- `calc`: pure Python functions (trial balance lines, EBITDA, TTM, leverage ratio, headroom, bonus pools, tax estimate). Trackback recomputes these itself. Agents never compute numbers.
- `judgment`: an agent's classification or decision (accrual estimate, estimate-vs-error call, revenue treatment).
- `prose`: sentences and paragraphs (flux commentary, board deck captions, the certificate's narrative line).
- `action`: something that happened in the world (journal entry posted, certificate sent, bonus paid, tax paid, payment run).

---

## 5. Agent-to-agent handoffs (required edges)

Agents read each other's outputs only through a new hub tool, `get_artifact(artifact_id)`, which returns the current version visible at the run's pin and writes a consumption receipt with the fields read. Agents still read sources through the Memento tools from Part 1. Required handoffs, so the graph genuinely crosses agents:

| Producer | Artifact | Consumer | Uses it for |
|---|---|---|---|
| Close Accountant | Q1 revenue, deferred revenue schedule, accruals, Q1 P&L by gym | Covenant and Comp | TTM Adjusted EBITDA, leverage, gym bonuses, Q2 tax estimate |
| Close Accountant | Q1 P&L lines and flux inputs | Reporting Analyst | Board deck tiles, flux commentary, budget vs actuals |
| Covenant and Comp | Leverage ratio and covenant status | Reporting Analyst | Board deck covenant tile and the sentence "we remain within our 3.00x covenant" |
| Close Accountant | June close accruals | Reporting Analyst | 13-week cash forecast, BvA |
| Reporting Analyst | Demand forecast (E19) | Covenant and Comp | Forward covenant projection note (optional, cut if late) |

### 5.1 Goals, not scripts

Agents get goals, not scripted work orders. Each historical run (April 10 close, April 24 deck, May 15 certificate, May 31 bonuses, June 12 payment run, June 15 tax, July 8 June close) is launched with a goal and a short list of required deliverables, and the agent decides everything else it produces: which accruals to book, which commentary to write, which tiles to show, which checks to run. Trackback tracks whatever it actually built.

| Agent | Example goal | Required deliverables (must exist, because they are the seat's actual job) |
|---|---|---|
| Close Accountant | "Close Q1 2026 for Tidewall following the close calendar and company policies." | Q1 P&L by gym, deferred revenue schedule, accrual entries, misstatement log |
| Reporting Analyst | "Prepare the Q1 board deck from the latest close." | Revenue tile, EBITDA tile, covenant tile, at least one sentence on covenant status, flux commentary for any line over the flux threshold |
| Covenant and Comp | "Prepare the Q1 lender compliance package and Q1 incentive payouts." | Compliance certificate (action, CFO approval), one bonus record per gym G1 to G6 (actions), commission records, Q2 estimated tax payment (action) |

Rules that keep goals compatible with the rest of the spec:
- Every number an agent produces goes through `emit_number` with a `metric` name from a controlled vocabulary (chart of accounts lines plus a fixed KPI list such as `revenue_total`, `revenue_membership`, `ebitda_gym`, `ttm_adj_ebitda`, `net_leverage`, `bonus_gym`, `tax_estimate_q2`, `cash_balance`, `cash_forecast_week`). Free-form names are allowed only as a label on top of a vocabulary metric. This is what lets the answer key match whatever artifacts the agents chose to produce.
- Every sentence goes through `emit_sentence` and must cite the claims and metrics it relies on.
- Goals and deliverables are recorded on the run, so Memento replay shows what the agent was asked to do as well as what it read.
- Runs are recorded once and replayed from the cache, so goal-driven output is still deterministic on stage.

The E11 ripple must visibly cross all three agent lanes:
1. Billing export v2 (source correction) → the Close Accountant's deferred revenue judgment is pinged and reworked (and it drafts the correcting JE, which triggers E22).
2. Trackback recomputes Q1 revenue, gym EBITDA, TTM EBITDA and leverage (calc nodes, engine lane).
3. Covenant and Comp is pinged: certificate (action, compensation: corrected certificate plus lender notice for the CFO), G1 and G4 bonuses (actions, compensation: offset next payout), G3, G5 and G6 bonuses (answers still_valid: below target before and after), Q2 tax (action, compensation: reduce next installment).
4. Reporting Analyst is pinged: revenue and EBITDA tiles (reworked), the covenant sentence (reworked: no longer true), and the 13-week cash forecast (not pinged at all, because no cash moved: shown with a "skipped, no material change" badge).
5. San Jose (G2) never gets pinged, because it never consumed the duplicated claims.

---

## 6. The trackback ping protocol v1

The design borrows from three real specs, and the README should say so: TrackBack (Six Apart shipped it in Movable Type in August 2002; spec version 1.2 is dated August 1, 2004), Pingback 1.0, and Webmention (W3C Recommendation, January 12, 2017). TrackBack died of spam because pings were never verified. Trackback fixes that: the hub only pings along consumption receipts whose hashes match.

### 6.1 Message

CloudEvents 1.0 structured JSON envelope, with PROV-O names for the provenance fields:

```json
{
  "specversion": "1.0",
  "type": "dev.trackback.ping.v1",
  "source": "trackback://hub/corrections/E11",
  "id": "ping_<ulid>",
  "subject": "trackback://artifact/<target_artifact_id>@<version>",
  "time": "<transaction time of the wave, from the pinned clock>",
  "datacontenttype": "application/json",
  "data": {
    "ping_id": "ping_<ulid>",
    "idempotency_key": "sha256(agent|correction|wave|sorted suspect version ids)",
    "correction_id": "E11",
    "wave": 1,
    "root_ping_id": "ping_<ulid>",
    "hop": 2,
    "max_hops": 6,
    "causal_chain": [
      {"node": "billing_export_march", "from": "v1", "to": "v2", "summary": "duplicated deferred-revenue release removed"},
      {"node": "calc:ttm_adj_ebitda", "old": 5563500, "new": 5445500},
      {"node": "calc:net_leverage", "old": 2.966, "new": 3.030, "crossed": "covenant_max 3.00"}
    ],
    "your_nodes": [
      {
        "artifact_id": "cert_q1_2026", "node_kind": "action", "prior_version": 1,
        "prior_output_excerpt": "...", "fields_read": ["net_leverage", "ttm_adj_ebitda"],
        "changed_fields": [{"field": "net_leverage", "old": 2.966, "new": 3.030, "delta": 0.064, "crossed_threshold": true}],
        "consumed": {"artifact_id": "calc:net_leverage", "version": 2, "sha256": "..."}
      }
    ],
    "allowed_responses": ["still_valid", "reworked", "needs_human"],
    "constraints": "Only change content that depends on changed fields. Never compute numbers; numbers come from Trackback.",
    "status_url": "/pings/ping_<ulid>",
    "signature": "hmac-sha256=<hex>"
  }
}
```

`change_kind` for a source or artifact change is one of `revised`, `retracted` (the Webmention 410 analogue: the input is withdrawn, so anything resting on it must be replaced or marked unprovable) or `added_input`. Sign with HMAC-SHA256 over the canonical JSON of `data`, using a per-install secret from `.env`.

### 6.2 Endpoints (FastAPI, same process as everything else)

| Method | Path | Purpose |
|---|---|---|
| GET | `/.well-known/trackback` | Lists agents, their ping endpoints and supported ping versions (TrackBack autodiscovery in spirit, like an A2A Agent Card) |
| POST | `/artifacts/{id}/versions` | Publish a new version (agent revision or rework). Hub diffs, finds receipts, runs the wave, enqueues pings, all in one transaction |
| POST | `/artifacts/{id}/retract` | Retraction, pings with `change_kind=retracted` |
| POST | `/corrections` | Root a cascade from a source correction (the judge's red pen and the corrections timeline both use this) |
| POST | `/agents/{agent_id}/trackback` | Deliver a ping. Returns 202 plus `Location: /pings/{id}`. A duplicate idempotency key returns 202 with the existing Location |
| GET | `/pings/{id}` | Ping status |
| POST | `/pings/{id}/response` | The agent's verdict |
| GET | `/corrections/{id}/graph` | Affected DAG with per-node state, per wave, for the UI |
| GET | `/events` | Server-sent events stream for the live UI, fed from the outbox |

Synchronous refusals on delivery (400 class, recorded as `refused` with a code): malformed, source equals target, unknown target, target version already superseded (`stale_target`), no matching receipt (`not_a_dependent`), consumed hash mismatch, hop over max (`hop_limit`), target already in the causal chain (`cycle`), bad signature (`unauthenticated`).

### 6.3 Response states

| State | Meaning | What the hub does next |
|---|---|---|
| `acknowledged` | Received, working | Nothing |
| `still_valid` | Re-checked; the dependent content holds. A reason is required (for example "G5 was below target before and after; bonus stays $0") | Append a re-verified receipt against the new input version. Children are not pinged (backdating) |
| `reworked` | New version produced | If the content hash or stated conclusions changed materially, continue the wave to this artifact's dependents with hop + 1 |
| `needs_human` | Ambiguous, conflicting, or any escalation rule fired | Show in the approvals inbox; the cascade pauses below this node |
| `refused` | Not a dependent, stale, cycle, hop limit, unauthenticated | Logged; no cascade |
| `superseded` (system) | Coalesced into a newer ping | Nothing |
| `failed` (system) | Delivery or agent error after retries | Becomes `needs_human` |

Map these states to iteration 1's verdicts in the impact findings: `still_valid` = unaffected (with the reason), `reworked` = invalidated then superseded, `needs_human` = needs_review, retraction with no replacement = unprovable.

### 6.4 Protocol adapters (stretch, cut first)

Write these only after Section 15's never-cut list is done:
- MCP: expose artifacts and each agent's inbox as resources, and send `notifications/resources/updated` when a ping is enqueued. The research found the current MCP spec is dated 2026-07-28, that it replaced `resources/subscribe` with a `subscriptions/listen` stream, and that the Python `mcp` SDK (2.3.0, October 2026) supports `ctx.notify_resource_updated(uri)`. Verify all of that against the installed package before relying on it. The SQLite outbox stays the durable record, because MCP notifications carry only a URI and aren't replayed.
- A2A 1.0: a JSON-RPC `/a2a` endpoint where a ping is a `SendMessage` carrying a Trackback extension URI, with `context_id` = correction id and `reference_task_ids` pointing at the task that produced the old input. Map response states to TaskState (COMPLETED, INPUT_REQUIRED, REJECTED, CANCELED, FAILED). Verify field names against the installed SDK.

If neither adapter gets built, the README and pitch can still say the protocol is shaped to map onto both, and show the mapping table. Don't claim an adapter exists unless it runs.

---

## 7. The wave algorithm

One correction event (or one agent revision) produces one wave. Deterministic first, LLMs only where judgment is needed.

1. Write the new version. Seed the worklist with the changed node. Increment the revision counter.
2. Process the worklist with a min-heap keyed by a precomputed `topo_index`, so each node is evaluated at most once per wave, after all of its changed parents.
3. For a `calc` node: recompute in Python. Ask the domain pack `is_material(...)`. Material means the change is at least `max(abs_threshold, rel_threshold × |old|)` or it crosses a stated conclusion (covenant max, bonus target or tier, sign of a growth rate). If not material, keep the old version as current (backdate), record the reason, and don't enqueue children. If material, write a new version and enqueue children.
4. For a `judgment`, `prose` or `action` node: don't call an LLM inside the wave. Check field-level relevance first: if none of the materially changed fields are in the node's `fields_read`, mark it `still_valid` with reason `fields_not_read`, with no ping. Otherwise mark it `suspect` and add it to its owning agent's pending bundle. Its children wait.
5. After the deterministic pass, dispatch pings agent by agent, in order of each agent's lowest `topo_index` suspect node. Each agent gets exactly one ping per wave containing all its suspect nodes.
6. On a response: `still_valid` clears suspect and does not enqueue children. `reworked` writes new versions; if the change is material, enqueue children and continue the same wave (which may produce a second ping to a different agent, never a second ping to the same agent in the same wave; if a later node for an already-pinged agent becomes suspect, open wave 2 for it). `needs_human` blocks the subtree.
7. Coalescing: corrections arriving within a 3-second debounce window, or fired together with the "Apply corrections" button, merge into one wave.

Termination and safety rules (put these on the README and a slide):
- Versions are immutable and every receipt points at a specific version, so the graph is a DAG by construction.
- `MAX_WAVES = 2` per root correction. A third would-be wave becomes `needs_human`.
- `MAX_HOPS = 6`, and a ping to a target already in its causal chain is refused as a cycle.
- One ping per agent per wave. The idempotency key prevents duplicate rework on retries.
- An agent is never pinged about a node it just wrote in the same wave (no self-pings).
- Oscillation guard: if a rework produces a content hash equal to an earlier version of the same node within the same root correction (A to B to A), stop and escalate as `oscillation`.
- `MAX_LLM_CALLS_PER_EVENT = 12`. Exceeding it escalates to a human. Log every call with tokens so cost can be compared against rerunning everything.
- Agents can't create pings. A downstream agent that believes an upstream output is wrong files an `upstream_challenge`, which goes to a human (and, if approved, starts a new wave through the owning agent's revision).

---

## 8. Agent self-revisions (new correction origin)

Any agent can revise its own earlier output through `POST /artifacts/{id}/versions` with `origin = agent_revision`, a reason, and (if the artifact is a judgment that feeds the ledger) an approver. Propagation is identical to a source correction. The differences: the seed node is the agent's artifact, revisions of executed actions always produce a compensation proposal, and the revising agent isn't pinged about its own node.

Add these corrections-timeline items to `TIMELINE.md` and the answer key (before the key is frozen, or as a logged changelog entry if it's already frozen):

- X1, agent self-revision, July 2: after the controller approves the Bayline Power accrual norm (factor 1.08 for November to March), the Close Accountant revises its own June utilities accrual method note and the Q2 accrual estimate. Expected: the Reporting Analyst is pinged for the BvA utilities line and the 13-week cash forecast (reworked, small), and the Covenant and Comp agent is not pinged, because the Q1 certificate didn't consume any Q2 accrual (reason `different_period`, no ping). This shows a self-revision with selective pings.
- X2, coalesced corrections, June 2: E17 (the 40-cent bank fee) and E18 (the retroactive unemployment insurance rate) arrive within the debounce window and merge into one wave. Expected: zero pings for E17 (below trivial), one ping to the Reporting Analyst for the payroll tax BvA line from E18, and no ping to Covenant and Comp.
- X3, upstream challenge: during the E11 wave, the Reporting Analyst questions the Close Accountant's gym allocation of the duplicate. It files an `upstream_challenge`, which lands in the human inbox and does not start a wave on its own. This demonstrates the wave cap and the no-agent-pings rule.

---

## 9. What a pinged agent does

When an agent receives a ping, it gets a dedicated rework run pinned at the wave's transaction time. Its prompt contains: its seat description, the ping's `causal_chain` and `your_nodes` (prior outputs, prior rationale, fields read, changed fields with old and new values and threshold crossings), the allowed responses, and these rules:
- Never compute numbers. Prose uses numeric slots like `{ttm_adj_ebitda}` that Trackback fills from calc nodes. A reworked sentence only changes wording whose truth depends on the changed values (for example "we remain within our 3.00x covenant" becomes "we exceeded our 3.00x covenant; a corrected certificate and waiver request are in progress").
- For each node, answer `still_valid` (with a reason that cites the specific changed field) or `reworked` (with the new content and which diff items it addressed), or `needs_human`.
- Re-derive from the new inputs using the tools. Don't paraphrase the old output.

Trackback then runs the domain pack's tie-out checks on every reworked output before accepting it (for example the Reporting Analyst's revenue tile must equal the Close Accountant's ledger calc version it consumed, and the Covenant agent's leverage must use the current EBITDA version). A failed tie-out turns the response into `needs_human`.

Deterministic escalation to `needs_human` happens when the agent says so, when the node is an executed action (a compensation is always proposed and routed to the right human), when a covenant or compensation threshold was crossed, when a tie-out fails, when a cap is hit, or on oscillation.

All rework runs go through the LLM cache like every other call, so the demo replays them offline.

---

## 10. Compensations for executed actions

Keep iteration 1's fixed compensation menu and approver roles, now provided by the finance domain pack. Add an EffectMatch-style check: every action stores `effect_spec` (what was approved, for example the JE lines) and `observed_effect` (what the ledger actually recorded), and downstream nodes don't consume an action until the two match. Compensation states go `proposed → approved → executed` (or `rejected`), with `approved_by` required and the proposer-not-approver CHECK from iteration 1. Forward recovery is the default in finance: post a correcting entry rather than pretending the original never happened. Show "reverse and repost" as one compensation in the UI.

---

## 11. Memento across agents

Memento now answers "what did each agent know when it acted?". For any action or artifact, the replay view shows the agent's run, its pin time, every source memento it read and every upstream agent artifact version it consumed (with hashes), and the refusals it hit. For the E11 defense beat, replay the Covenant agent's May 15 certificate run: it consumed the Close Accountant's April 10 revenue version, which consumed billing export v1, where the duplicate is visible.

Add the "who built this, on top of whom" view for any document: select an artifact, and the UI draws its full upstream chain across lanes back to raw sources, labeled with agent, run, version and pin time. This is the view Krishna asked for. It should also be reachable from the lot-code chip.

---

## 12. UI changes

- The graph becomes swimlanes: Sources, Close Accountant, Trackback (calc), Reporting Analyst, Covenant and Comp, and a Humans lane for approvals. Use React Flow group nodes as fixed-height horizontal lanes (child nodes with a parent id and extent constrained to the parent; verify the exact prop names against the installed `@xyflow/react` version). Place nodes by `topo_index` on the x-axis.
- Node states: active (grey), suspect (amber), reworked (blue), still valid (green check with the reason on hover), needs human (red), superseded (faded), and a "skipped: no material change" badge on descendants that were never pinged. Every state also gets an icon and a pattern, per the projector rules.
- Pings animate as a small envelope traveling from the Trackback lane to the agent's lane, then the agent's response animates back. Precompute the sequence and animate it at about 150 ms per hop.
- A ping log panel shows each ping, its payload summary and its response, plus a Mermaid sequence diagram generated from the ping table for the current correction (one block per wave, with escalations shown as alternative branches). Vendor Mermaid locally.
- A counter strip computed from real data: "Nodes inspected 7 of 42 (17%) | Agents pinged 2 of 3 | LLM calls 3 vs 9 for rerun-all | Compensations 3 pending approval".
- Presenter hotkeys from Part 1 stay. Add `L` (toggle lanes versus the old layered view), `S` (show the ping sequence diagram), `B` ("who built this" for the selected artifact).

---

## 13. Evaluation changes

Keep iteration 1's metrics and add the multi-agent ones. All of them must be computed from SQLite logs and the answer key, never typed by hand.

### 13.1 The answer key is written as rules about what things rest on, not as artifact names

Because agents choose what to produce (Section 5.1), the key can't say "tile #3 must turn red". Rewrite `answer_key.yaml` as rules that resolve against whatever artifacts actually exist after the runs:

```yaml
- correction: E11
  ground_truth_affected:            # from the generator's own knowledge of which source rows feed which true quantities
    claims: [billing_export_march.annual_prepaid_release.G1, .G3, .G4, .G5, .G6]
    metrics_changed: [revenue_membership.Q1, revenue_total.Q1, ebitda_gym.G1.Q1, ebitda_gym.G3.Q1, ebitda_gym.G4.Q1,
                      ebitda_gym.G5.Q1, ebitda_gym.G6.Q1, ttm_adj_ebitda.Q1, net_leverage.Q1, tax_estimate_q2]
    conclusions_flipped: [covenant_status.Q1: compliant->breach, bonus_gym.G1: overpaid, bonus_gym.G4: overpaid]
  must_invalidate: "any artifact stating a metric in metrics_changed whose stated conclusion flips, or any sentence asserting a flipped conclusion"
  must_stay: "any artifact that rests only on metrics not in metrics_changed (for example cash_balance, cash_forecast_week, anything for G2); bonus_gym for G3, G5, G6 (conclusion unchanged)"
  must_ping: [close_accountant, covenant_comp, reporting_analyst]
  must_not_ping_nodes: "cash forecast cells, G2 artifacts"
  required_compensations:
    - {deliverable: compliance_certificate.Q1, compensation: corrected_certificate_and_lender_notice, approver: CFO}
    - {deliverable: bonus_gym.G1, compensation: offset_next_payout, approver: HR+Controller}
    - {deliverable: bonus_gym.G4, compensation: offset_next_payout, approver: HR+Controller}
    - {deliverable: tax_estimate_q2, compensation: reduce_next_installment, approver: Controller}
```

Important: the ground truth must come from the data generator's own model of the world (which source rows feed which true quantities), never from Trackback's recorded edges. Otherwise the test is circular. The scorer resolves each rule against the actual artifacts by their metric tags, periods and stated conclusions, then computes the metrics below. Required deliverables (Section 5.1) are also checked by name. Freeze the rules at M3 as before.

- False still_valid rate (headline safety metric): share of pinged nodes in the key's `must_change` set that an agent wrongly cleared as `still_valid`. This is the failure that matters most, an agent clearing its own stale work. Run every LLM-dependent condition at least 3 times in record mode (different cache namespaces) and report the spread, not just the best run.
- Ping precision, recall and F1 against the answer key's `must_ping` set (by agent and node).
- Unnecessary rework rate: reworked nodes whose final hash equals the pre-event hash, or that were in `must_stay`.
- Inspection fraction: nodes evaluated (calc recomputes plus agent checks) over total nodes. Cite BoardroomAI's mean of 14.59% only as framing, noting the graphs differ.
- Preservation: share of `must_stay` nodes with an unchanged hash.
- Rework correctness: share of `must_change` nodes whose final value matches the key (numbers exact; prose and judgment scored by deterministic conclusion labels such as `covenant_status = breach`, not by an LLM).
- Cross-agent consistency: all tie-out checks pass after the event.
- Cost: LLM calls and tokens per event, and savings versus rerun-all.
- Convergence: waves and seconds until nothing is suspect or everything is escalated.
- Compensation precision and recall.
- Replay fidelity: Memento's reconstructed state hash at a revision equals the snapshot hash taken live at that revision.

Baselines, all run from the same script: B0 no tracking (only the source changes; counts stale artifacts left behind), B1 rerun all three agents from scratch (in record mode once, then cached), B2 ping every descendant of the source with no cutoff and no field-level relevance. Ablations if time allows: no materiality gate, no field-level read-sets, no LLM judge.

Scenario categories the eval must cover: immaterial correction (zero pings expected), material with no threshold crossing (numbers recompute, prose still valid), threshold crossing (E11), a correction whose effects cancel downstream (early cutoff), agent self-revision (X1), coalesced corrections (X2), upstream challenge (X3), and the MPWR real-world restatement.

---

## 14. Added milestones

Insert these into Part 1's sequence. If you're already past the point where one belongs, do it next.

| Milestone | Goes after | Deliverable | Acceptance check |
|---|---|---|---|
| I2-0 housekeeping | Immediately | `SPEC.md`, `SPEC_ITERATION_2.md`, `CLAUDE.md`, STATUS section | Files exist and are committed |
| I2-1 domain pack split | M4 | Core and finance pack separated behind `DomainPack` | `grep` shows no import of `domains` inside `core`; existing tests pass |
| I2-2 handoff receipts | M5 | `get_artifact` tool, consumption receipts, agent and node-kind columns, the required handoffs in Section 5 | After `make world`, every Reporting Analyst and Covenant artifact has at least one receipt pointing at another agent's artifact version |
| I2-3 ping protocol | M5 | Ping message, endpoints, refusals, HMAC, outbox, SSE | Tests for each refusal code, duplicate idempotency key, signature check |
| I2-4 waves | I2-3 | Wave scheduler, coalescing, caps, oscillation guard, self-revision path, upstream challenges | E11 from the canonical snapshot pings exactly the agents and nodes in the key; X1, X2, X3 behave as specified |
| I2-5 rework runs | I2-4 | Agent rework prompts, tie-out checks, escalation rules, all cached | E11 rework replays offline byte-identically |
| I2-6 lanes UI | M7 | Swimlanes, ping animation, ping log, Mermaid sequence, counter strip, "who built this" | Full E11 walkthrough at 1280x720 with lanes |
| I2-7 eval | M8 | New metrics and baselines B0 to B2 | Proof page shows ping precision and recall and the LLM-call savings from real runs |
| I2-8 adapters (stretch) | Freeze-critical done | MCP and A2A adapters | Only if time; never block the freeze |
| I2-9 second domain pack (stretch) | Freeze-critical done | A tiny `domains/research/` pack and a two-agent pipeline (Section 18) | The same core, unchanged, runs the research scenario; `grep` still shows no domain imports in core |

---

## 15. Cut list and never-cut list (replaces Part 1's)

Cut in this order: A2A adapter; MCP adapter; Muse adapter; the second domain pack demo (Section 18); the forward covenant projection handoff; degraph baseline; recursive norm beat; ALFRED (E19); ablations; Mermaid sequence panel (keep the ping log list); norms beyond Bayline and Pacific Lumen; the Citations API path (use the marker fallback).

Never cut: the E11 ripple crossing all three agent lanes, with at least one `still_valid` response with a reason, at least one `reworked` response, and at least one compensation; the skipped-no-change badge on the cash forecast; the "who built this" view; E22's rejection and re-draft; the April 10 and May 15 Memento replays and the future refusal; X1 (agent self-revision); the MPWR Real world tab; the eval script driving the proof page; the one-key reset; offline replay mode.

---

## 16. Pitch, Devpost and Q&A changes

Update `PITCH.md`, `DEVPOST.md` and the README.

Problem stats, in this order:
1. MemDerive (arXiv 2610.25373): memory systems "rarely propagate implicit changes, which no new record states"; on derived state every tested memory system fell behind BM25; three principles (gather inputs along the derivation, store rules with their versions, maintain derived states through recorded dependencies), and Trackback implements all three.
2. "When Stale Constraints Go Unchecked" (arXiv 2608.25553): agents inspected provenance only about 1 time in 5 and acted on stale constraints 74 to 77% of the time. That's why Trackback pushes a ping instead of hoping agents check. Verify these exact numbers against the paper before they go on a slide; if you can't, say "most of the time" instead.
3. Backup: STALE (arXiv 2605.06527), best model 55.2%.
Never use the "91 to 100%" figure.

Pitch structure change: open on the E11 moment as before, but describe it as agents: "Three agents run Tidewall's close. The Close Accountant's numbers fed the Covenant agent's lender certificate and the Reporting Analyst's board deck. Today the billing system admits it was wrong. Watch who gets pinged."

Generality closer (last 10 seconds): "The core doesn't know what a covenant is. Finance is a plug-in, because finance is where a wrong number costs the most. Any agent that builds on another agent's work needs a trackback." If the second domain pack (Section 18) works, show it here for about 15 seconds: press `D`, a paper is retracted, and the research summary and recommendation light up in their own lanes, with the same engine and a different plug-in.

Finance is the hero; generality is the closer, not the opener.

Positioning lines:
- "Every agent framework can rewind its own run. Trackback is what happens when someone else's output changes after you've already acted on it."
- "Dagster knows when a table is stale. It can't un-send a lender certificate."
- "PlanFence checks before you act. EffectMatch checks while you commit. Trackback handles the input changing after the effect."
- "Provenance isn't enough. Agents check it about one time in five. Trackback pings them."
- "TrackBack died of spam because pings were never verified. Ours only travel along hash-verified receipts of what each agent actually read."

Claims to avoid: don't claim to be first at selective multi-agent re-activation (BoardroomAI, arXiv 2608.13046, does it for human interventions), at recording input versions (PlanFence, arXiv 2609.03340), at agent provenance graphs (MAP-Graph, arXiv 2608.10509), or at bitemporal memory (Zep's Graphiti). Claim the combination: pings to the affected downstream agents, a value-aware materiality cutoff, compensation of already-executed actions with approvals, and per-agent as-of replay, running on a real close workflow plus real SEC data. Two papers explicitly leave executed side effects open: Rollback Repair (arXiv 2608.10502) says it cannot undo an irreversible external side effect, and PlanFence notes that passing validation doesn't stop an input from changing before the external effect. Cite both.

New Q&A answers to add:
- "Isn't this Dagster for agents?" Dagster assumes recomputing is cheap, deterministic and side-effect free, uses equality on data versions as its cutoff, and relies on lineage declared up front. Trackback records what each run actually read, uses a materiality judgment on real values, asks agents to re-check judgment and prose, and proposes compensations for actions that already happened.
- "LangGraph has time travel." It replays one thread from a checkpoint by re-executing nodes. Memento returns what was knowable at a time across agents and sources, with a TimeMap and refusals, and doesn't re-execute anything to answer.
- "BoardroomAI already re-activates affected agents." Yes, after a human intervention, in synthetic deliberation, with no executed side effects or compensation and no as-of replay. Trackback triggers on source corrections and agent self-revisions and handles money that already moved.
- "What stops ping storms?" Only the hub can ping, only along hash-verified receipts, only for material changes to fields the agent actually read, at most once per agent per wave, at most two waves, with hop and cycle limits.
- "Can agents loop?" No. Versions are immutable so the graph is a DAG, agents can't ping each other, and upstream challenges go to a human.

---

## 17. Definition of done (additions)

- Dropping the E11 recall notice shows pings crossing all three agent lanes, each agent's response with a reason, compensations in the approvals inbox, and the cash forecast skipped with a "no material change" badge.
- "Who built this" on the board deck's covenant sentence shows the chain: Reporting Analyst ← Covenant and Comp ← Trackback calc ← Close Accountant ← billing export v1.
- X1 shows an agent revising its own work and only the Reporting Analyst being pinged.
- The proof page shows ping precision and recall, unnecessary rework, inspection fraction and LLM-call savings versus rerun-all, all from real runs.
- `grep` confirms the core never imports the finance pack.

---

## 18. Stretch: a second domain pack to prove the core is general

Build this only after the never-cut list in Section 15 is done and the freeze checks pass. Timebox it to 3 hours. If it isn't working by then, drop it and log why.

- `domains/research/`: a minimal pack. Materiality: a finding matters if its direction or significance changes, or a cited effect size moves by more than 20%. Compensation menu: `issue_correction_note`, `withdraw_recommendation`, `notify_readers`. Approver: "editor".
- Sources: four short synthetic study summaries (clearly labeled synthetic), each with a few claims (effect direction, effect size, sample size).
- Two agents with goals: a Literature agent ("summarize what the evidence says about X") and a Brief agent ("write a one-paragraph recommendation from the latest summary", with one executed action: `publish_brief`).
- Scenario: one study is retracted (`change_kind = retracted`). Expected: the summary sentence that relied on it is pinged and reworked; a sentence supported by two independent studies stays valid with the reason "independent support remains"; the brief is pinged, and if its recommendation flips, `publish_brief` gets a compensation proposal (`issue_correction_note`) for the editor.
- Add it to the answer key as scenario R1 and to the proof page as a separate small table.
- UI: a domain switcher (Tidewall / Real world: MPWR / Research), and hotkey `D` jumps to the research scenario.

The point is to show the same core code, untouched, running a different domain through a different plug-in. Don't polish it beyond that.

Start with Section 0 now, then continue with the milestones without waiting for input.
