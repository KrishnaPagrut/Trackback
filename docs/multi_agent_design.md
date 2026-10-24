# Corrections ping only the agents they break

Trackback should grow into a ledger of receipts with a scheduler on top, not a group chat between agents. Every artifact version records which agent and which run made it, plus the exact upstream agent outputs and source versions it consumed, down to version ID, content hash and the fields it actually read. When a source gets corrected or an agent revises its own work, the engine (never the agents) recomputes every number itself, stops wherever the value didn't move enough to matter, and only then sends one ping per affected agent per wave, in dependency order. The ping is shaped like a Webmention (async 202 plus a status URL, idempotent re-sends, retraction as the 410 analogue), but it's verified against a hash-stamped consumption receipt, which makes the spam that killed the original TrackBack structurally impossible. Each agent answers still_valid, reworked or needs_human, and anything that already acted on the world (a sent covenant certificate, a paid bonus) gets a compensating action that someone other than the preparer approves. On novelty, be careful. BoardroomAI (August 2026) already does dependency-aware selective re-activation of specialist agents, and PlanFence already records exact input versions per artifact, so neither is yours to claim. What's still open is the combination: push pings to the agents who own the affected work, a materiality cutoff on real financial values instead of hashes or symbolic status, compensation of actions that already executed, as-of replay of what each agent knew, and running code on a finance close. MCP's 2026-07-28 spec gives you a native doorbell for this (`notifications/resources/updated`), but it carries no payload and never redelivers, so SQLite has to be the source of truth. The biggest honest risk isn't the plumbing, it's whether an LLM agent re-checking its own output says "still valid" when it shouldn't.

## Every artifact carries a receipt: agent, run, and the exact versions it read

The original single-agent design (working name RECALL) treated the system as one close-and-reporting agent over a claim graph. The multi-agent version splits that into three agents that hand work to each other, which matches how a real finance team divides it and gives the ping somewhere to go. The Close Accountant (CA) owns accruals, journal entries and the misstatement log. The Reporting Analyst (RA) owns flux commentary, board-deck tiles and the 13-week forecast. Covenant and Comp (CC) owns the lender compliance certificate and the bonus and commission payouts. The controller and CFO stay human. On Tidewall, the running example, that means a $118,000 duplicate in the March billing export flows from CA's revenue entries into RA's EBITDA tiles and from there into CC's leverage calculation, which moves from 2.95x to 3.03x against a 3.00x covenant. Three lanes, one correction, and a certificate that already went out. All of those numbers belong to the synthetic Tidewall company, not sourced facts.

Every node in the graph has one of five kinds, and the split decides who does what. Sources are ledger rows, bank files, billing exports and contracts. Calc nodes are pure functions (trial balance, TTM EBITDA, net leverage, covenant headroom, bonus pool), and Trackback recomputes them itself. Judgment nodes are LLM-made classifications like "this is an error, not an estimate change". Prose nodes are memos and deck captions. Action nodes are things that touched the world: a posted entry, a sent certificate, an approved payout. Agents only ever get pinged about judgment, prose and action nodes. Keeping the model out of arithmetic is what makes the numeric half reproducible and cheap, and it carries over unchanged from the single-agent RECALL design.

The receipt is the core data structure. An artifact version isn't just content. It's content plus who made it, in which run, with which model and prompt version, and exactly what it read. That last part has to be captured by the hub, not declared by the agent, which is why agents can only reach data through Trackback's own tools: every read writes an edge row at read time with the parent version and its hash. Dagster draws the same line between a code version ("the version of the code that computes an asset") and a data version ("the version of the data represented by the asset"), and hashes the two together to decide staleness ([Dagster asset versioning](https://dagster.io/docs/guides/build/assets/asset-versioning-and-caching)). For agents, the code version becomes model plus prompt version, and the data version becomes the set of consumed upstream versions.

```sql
CREATE TABLE agents(agent_id TEXT PRIMARY KEY, display_name TEXT, ping_endpoint TEXT,
  model TEXT, prompt_version TEXT);
CREATE TABLE runs(run_id TEXT PRIMARY KEY, agent_id TEXT, trigger TEXT,      -- initial | ping | challenge | human
  ping_id TEXT, pinned_at TEXT, model TEXT, prompt_version TEXT, started_at TEXT, finished_at TEXT);
CREATE TABLE nodes(node_id TEXT PRIMARY KEY,
  kind TEXT CHECK(kind IN ('source','calc','judgment','prose','action')),
  owner_agent TEXT, topo_index INT, materiality_policy_id TEXT);
CREATE TABLE versions(version_id TEXT PRIMARY KEY, node_id TEXT, rev INT, run_id TEXT,
  value_json TEXT, content_hash TEXT,
  status TEXT CHECK(status IN ('active','suspect','superseded','retracted','needs_human')),
  supersedes TEXT,                                -- previous version_id, PROV wasRevisionOf
  origin TEXT CHECK(origin IN ('initial','source_correction','agent_revision','upstream_challenge','human_override')),
  reason TEXT, approved_by TEXT, changed_at_rev INT, tx_from TEXT, tx_to TEXT);
CREATE TABLE edges(edge_id TEXT PRIMARY KEY,      -- the consumption receipt
  child_version TEXT, parent_version TEXT, parent_sha256 TEXT,
  kind TEXT CHECK(kind IN ('used','derived_from','quoted','assumed')),
  fields_read_json TEXT, recorded_at TEXT);
```

Two things about this schema matter more than they look. First, edges point from a specific child version to a specific parent version, and versions are immutable, so the graph over versions is a DAG by construction. Second, `changed_at_rev` is borrowed from Salsa, the incremental engine behind rust-analyzer. When a dependency re-executes and produces the same value, the dependent keeps its old revision, because "even though the inputs changed, the output didn't" ([Salsa algorithm docs](https://salsa-rs.github.io/salsa/reference/algorithm.html)). That one column is how early cutoff gets stored.

Change enters the graph from four origins, and they all produce the same thing: a new immutable version with a `supersedes` link, a reason and an approver. A source correction is a fact change and is auto-approved. An agent revision is CA deciding its own accrual was wrong. An upstream challenge is RA thinking CA's accrual is wrong, filed as a request against CA rather than an edit. A human override is the controller stepping in. Propagation downstream is identical for all four. What differs is the seed node and whether approval is needed before anything propagates.

Why push at all, when every agent could just check its inputs? Because agents don't. In one August 2026 study across 16 models, agents inspected the provenance path in about 1 of 5 episodes when a memory's source had been superseded, and made stale-consistent decisions in 74.7% to 77.3% of episodes ([arXiv 2608.25553](https://arxiv.org/abs/2608.25553)). MemDerive, posted three days ago, found that memory systems "rarely propagate implicit changes" and recommends maintaining derived state "through recorded dependencies" ([arXiv 2610.25373](https://arxiv.org/abs/2610.25373)). Provenance sitting in a table does nothing until something tells the downstream agent to look. That's the ping.

## BoardroomAI already reactivates specialists, so claim the five things nobody ships

The 2026 literature has split Trackback's idea into pieces and published most of them separately. That's good news for credibility (judges can see the problem is real) and bad news for any "first" claim. The fair summary is that each paper does one slice, none ships code, and none closes the loop on actions that already executed.

BoardroomAI is the one to take seriously. It keeps a typed decision graph with owners per node, and its propagation "finds affected subgraphs, keeps unaffected artifacts, and reactivates only relevant specialists." On 600 synthetic interventions, propagation matched exhaustive impact computation while inspecting 14.59% of nodes, and in a 12-case pilot selective repair recomputed 62.11% of nodes, kept every unaffected node intact, and produced a valid decision in 6 cases while abstaining in the other 6 ([arXiv 2608.13046](https://arxiv.org/abs/2608.13046)). Its cutoff recomputes a semantic signature (status, justification environments, active attacks, content) and stops where the signature holds, and it routes repair obligations to specialists with a budgeted set-cover router ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)). What it lacks: any handling of real-world side effects, a numeric materiality cutoff, a per-agent as-of snapshot, a notification protocol, and a repo. Its own words are "synthetic and prototype-level", and the domain is organizational decisions like a launch budget cut, not finance ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)).

PlanFence is the strongest precedent for receipts. It stores exact links from each plan to its input records, and before a protected action it asks each input's owner for the current version, allows one replan, and otherwise blocks. Detected handoff conflicts rose from 0 of 30 to 30 of 30, at a stall of 143 to 237 ms under emulated LTE ([arXiv 2609.03340](https://arxiv.org/abs/2609.03340)). But it's pull-only, it compares version IDs rather than values (so any version bump forces a replan even when content didn't change), and it says plainly that "passing validation does not prevent an input from changing before the external effect" ([PlanFence full text](https://arxiv.org/html/2609.03340v2)). Dependency-Guided Rollback Repair does selective replay for a single agent and says its rollback "cannot undo an irreversible external side effect" and needs "a domain-specific compensating action" ([Rollback Repair full text](https://arxiv.org/html/2608.10502v1)). EffectMatch blocks a commit when persistent effects don't match what was approved, but acts before the commit, not after ([arXiv 2609.31301](https://arxiv.org/abs/2609.31301)). Those two quotes are the cleanest citations you have for the open gap.

| Work | Multi-agent | Pushes to downstream agents | Selective re-execution | Value-aware cutoff | Compensates executed effects | As-of replay | Code |
|---|---|---|---|---|---|---|---|
| BoardroomAI ([2608.13046](https://arxiv.org/abs/2608.13046)) | Yes | Partly (central router) | Yes | Partly (symbolic signature) | No | Partly (versions, no per-agent snapshot) | No |
| PlanFence ([2609.03340](https://arxiv.org/abs/2609.03340)) | Yes | No (pull before action) | One replan | No (IDs, not values) | No | No | No |
| MAP-Graph ([2608.10509](https://arxiv.org/abs/2608.10509)) | Yes | No (read-time gate) | No | No | No | No | No |
| Rollback Repair ([2608.10502](https://arxiv.org/abs/2608.10502)) | No | No | Yes | No | No (out of scope) | No | No |
| MemoRepair ([2605.07242](https://arxiv.org/abs/2605.07242)) | No | No | Yes | No (cost min-cut) | No | No | No |
| Execution Lineage ([2605.06365](https://arxiv.org/abs/2605.06365)) | No | No | Yes | No (input hash) | No | No | No |
| EA-Graph ([2608.04278](https://arxiv.org/abs/2608.04278)) | No | No | No | Partly (content-anchored) | No | No | No |
| EffectMatch ([2609.31301](https://arxiv.org/abs/2609.31301)) | Unclear | No | No | No | No (blocks pre-commit) | No | No |

A caveat on that table: full texts were read for BoardroomAI, PlanFence, Rollback Repair and Execution Lineage. For MAP-Graph, EffectMatch and EA-Graph only abstracts were read, so "No" means the abstract doesn't mention it.

Products are further behind than papers. degraph has `impact(id)` for downstream cascades and flags decisions stale when triggers fire, but it makes no LLM calls and doesn't rerun anything ([degraph on PyPI](https://pypi.org/project/degraph/)). Graphiti is genuinely bi-temporal and invalidates an old edge by setting `invalid_at` rather than deleting it, with point-in-time queries, but its docs say nothing about propagating to derived facts or notifying agents ([Graphiti temporal model](https://mintlify.wiki/getzep/graphiti/concepts/temporal-model)). The agent frameworks don't track output-to-output dependencies at all. LangGraph's replay "re-executes nodes" after a chosen checkpoint, and `update_state` "creates a new checkpoint that branches", so downstream work reruns because it comes later, not because it depended on anything ([LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)). Google ADK's rewind leaves external systems as "your responsibility" ([ADK rewind docs](https://raw.githubusercontent.com/google/adk-docs/refs/heads/main/docs/sessions/session/rewind.md)), and Microsoft Agent Framework's checkpoints say nothing about selective re-execution ([MS Agent Framework checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)). CrewAI, the OpenAI Agents SDK, LangSmith and Arize weren't checked against primary docs, so say "we didn't find", not "nobody has".

### The two questions a technical judge will ask

"Isn't this just Dagster for agents?" Borrow from Dagster openly, then name four differences. Dagster's "Unsynced" status is non-transitive: if an upstream rematerialization yields the same data version, downstream stays in sync ([Dagster asset versioning](https://dagster.io/docs/guides/build/assets/asset-versioning-and-caching)), and its `eager()` policy rebuilds as soon as upstreams update while `on_cron()` waits for a tick ([Dagster Declarative Automation](https://dagster.io/docs/guides/automate/declarative-automation)). That's early cutoff and per-artifact rebuild policy, and Trackback should use both. But Dagster assumes recomputation is deterministic, cheap and free of side effects. Trackback's nodes are agents whose rework is non-deterministic and needs a reason, and some of their outputs already left the building. Dagster's cutoff is a hash equality test, while Trackback's is a materiality judgment (did leverage cross 3.00x?). Dagster's lineage is declared at definition time, while Trackback records what each run actually read. And Dagster answers "what was materialized when", while Memento answers "what did this agent know when it acted". dbt is an even weaker comparison, since `state:modified` detects only changes to code and config, not data ([dbt state comparison caveats](https://docs.getdbt.com/reference/node-selection/state-comparison-caveats)), and data corrections are Trackback's main trigger.

"LangGraph already has time travel." It has a per-thread, append-only checkpoint log addressed by `checkpoint_id`. It isn't addressed by datetime (no TimeGate or TimeMap), it can't answer what agent B knew about agent A's output at 3:14pm, it snapshots graph state rather than artifact versions, and its replay re-executes. Memento replay reads what was known, read-only.

### Say this, not that

| Say | Don't say |
|---|---|
| "Every agent framework can rewind its own run. Trackback is what happens when someone else's output changes after you've already acted on it." | "First system to selectively re-activate affected agents" (BoardroomAI) |
| "Dagster knows when a table is stale. It can't un-send a lender certificate." | "First to record exact input versions per artifact" (PlanFence, EA-Graph, Execution Lineage) |
| "PlanFence checks before you act. EffectMatch checks while you commit. We handle the input that changed after the effect." | "First provenance graph for agents" (PROV-AGENT, AgentTrails, the 2026 survey) |
| "Agents inspect provenance about 1 time in 5. So we ping them." | "First bi-temporal agent memory" (Graphiti) |
| "Materiality, not hashes: a $3 rounding fix doesn't reopen the deck, a reclass that crosses 3.00x reopens the certificate." | "Blast radius" as your coined term (DamageFlow/BlastGuard and a HackerNoon piece already use it) |
| "Same four TrackBack fields, now typed and verified." | "First dependency-invalidation ping for agents" (you only know MCP and A2A have no such extension) |

The safest frame is composition: Trackback is these published pieces closed into one loop on a real finance workflow, with code. The group behind MAP-Graph, Rollback Repair and the provenance survey posted all three between June and October 2026, and the survey lists "memory and multi-agent lineage" and "provenance-aware safety and recovery" as open directions ([arXiv 2606.04990](https://arxiv.org/abs/2606.04990)). A multi-agent rollback paper from them could land the week of the hackathon. Search arXiv the morning of judging.

## A trackback ping is a Webmention with a hash-verified receipt

The name is a gift, so use the actual history. TrackBack shipped in Movable Type in August 2002 ([Wikipedia: Trackback](https://en.wikipedia.org/wiki/Trackback)), and version 1.2 (2004) is almost comically small: a form-encoded POST where only `url` is required (`title`, `excerpt` and `blog_name` are optional), answered with `<response><error>0</error></response>` ([TrackBack 1.2](http://archive.cweiske.de/trackback/trackback-1.2.html)). There was no verification at all. Trackbacks "publish user-submitted URLs without prior authentication", one campaign studied in 2009 sent nearly 10 million spam pings in a year, and by the 2010s most platforms had turned them off ([Wikipedia: Trackback](https://en.wikipedia.org/wiki/Trackback)). Pingback 1.0 (2002) moved to XML-RPC `pingback.ping(sourceURI, targetURI)` and made verification a MAY, with fault codes like 0x0011 "source doesn't link to target" and 0x0030 "already registered" ([Pingback 1.0](https://www.hixie.ch/specs/pingback/pingback)). Webmention, a W3C Recommendation in 2017, finished the job: the receiver MUST fetch the source and find an exact match of the target, SHOULD do that asynchronously, returns 202 Accepted or 201 with a `Location` status URL, SHOULD process re-sends idempotently, and treats a source that returns 410 Gone as a deletion ([W3C Webmention](https://www.w3.org/TR/webmention/)). Vouch then added a third-party voucher and a "449 Retry With" response for unknown senders ([IndieWeb: Vouch](https://indieweb.org/Vouch)).

The lesson is that every generation of this protocol was a fight against unverified pings. Trackback's answer is to make verification exact instead of heuristic. Webmention checks "does the source page link to the target?" Trackback checks "did the hub record, at read time, that this target version consumed that source version with this hash?" The hub only emits pings along edges in its own ledger, so the ledger is the voucher.

| Spec feature | Trackback equivalent |
|---|---|
| TrackBack `url`, `title`, `excerpt`, `blog_name` | `change.uri`, `correction.reason`, `changes[]` (the claim diff), `agent_id` |
| TrackBack RDF autodiscovery | `GET /.well-known/trackback`, or the A2A Agent Card |
| Pingback 0x0011 "source doesn't link to target" | `refused: not_a_dependent` (no edge in the ledger) |
| Pingback 0x0030 "already registered" | Duplicate idempotency key returns the existing status URL, as a success |
| Webmention 202 + `Location` | `202 Accepted` + `Location: /pings/{ping_id}` |
| Webmention idempotent re-send on update | Every new source version re-pings; older pending pings for the same edge are superseded |
| Webmention 410 Gone means delete | `change_kind: "retracted"`; downstream must drop or replace the claim, or escalate |
| Vouch 449 | Only for external senders outside the ledger. Out of scope for the demo |

### The ping message

The most important design decision: a ping is addressed to an agent, not to a single artifact. The obvious design is one ping per (target artifact, source change), and that per-edge pinging is exactly what makes an agent rework twice when two of its inputs changed. So a ping bundles every suspect node that agent owns for this correction and wave, with all of each node's changed inputs. Wrap it in CloudEvents 1.0, whose required attributes are `specversion`, `id`, `source` and `type`, and whose `source + id` pair is unique per event, which gives you a ready-made dedup key ([CloudEvents spec](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)). Extension attribute names must be lowercase alphanumerics and should stay at 20 characters or fewer, hence `tbcorrection` and `tbwave`. The values below are illustrative Tidewall numbers.

```json
{
  "specversion": "1.0",
  "type": "dev.trackback.ping.v1",
  "source": "trackback://hub/corrections/corr_0042",
  "id": "ping_0107",
  "subject": "trackback://agent/covenant_comp",
  "time": "2026-07-08T15:02:11Z",
  "datacontenttype": "application/json",
  "tbcorrection": "corr_0042",
  "tbwave": 1,
  "data": {
    "ping_id": "ping_0107",
    "idempotency_key": "sha256(covenant_comp|corr_0042|wave1|cert_q1@v3,bonus_g1_q1@v2)",
    "correction": {
      "id": "corr_0042",
      "origin": "source_correction",
      "reason": "Billing export double-counted the March deferred revenue release ($118,000)",
      "approved_by": "system",
      "root": "trackback://source/billing_export_2026_03"
    },
    "causal_chain": [
      {"uri": "trackback://source/billing_export_2026_03", "old": "v1", "new": "v2", "by": null},
      {"uri": "trackback://artifact/je_rev_march", "old": "v3", "new": "v4", "by": "close_accountant", "ping_id": "ping_0105"},
      {"uri": "trackback://calc/ttm_ebitda", "old": "v7", "new": "v8", "by": "engine"},
      {"uri": "trackback://calc/net_leverage", "old": "v7", "new": "v8", "by": "engine"}
    ],
    "hop": 3,
    "max_hops": 6,
    "items": [
      {
        "target": {"uri": "trackback://artifact/cert_q1", "version": "v3", "kind": "action",
                   "run_id": "run_cc_0515", "executed_at": "2026-05-15T17:00:00Z"},
        "consumed": [{"uri": "trackback://calc/net_leverage", "version": "v7", "sha256": "ab12...",
                      "edge_id": "edge_552", "edge_kind": "used", "fields_read": ["ratio"]}],
        "changes": [{"uri": "trackback://calc/net_leverage", "field": "ratio", "change_kind": "revised",
                     "old": 2.95, "new": 3.03, "crossed": ["covenant_max_3.00"]}],
        "prior_output_ref": "trackback://artifact/cert_q1@v3"
      },
      {
        "target": {"uri": "trackback://artifact/bonus_g1_q1", "version": "v2", "kind": "action",
                   "run_id": "run_cc_0531", "executed_at": "2026-05-31T12:00:00Z"},
        "consumed": [{"uri": "trackback://calc/gym_ebitda_g1_q1", "version": "v4", "sha256": "cd34...",
                      "edge_id": "edge_590", "edge_kind": "used", "fields_read": ["ebitda_above_target"]}],
        "changes": [{"uri": "trackback://calc/gym_ebitda_g1_q1", "field": "ebitda_above_target",
                     "change_kind": "revised", "old": 535000, "new": 417000, "crossed": []}],
        "prior_output_ref": "trackback://artifact/bonus_g1_q1@v2"
      }
    ],
    "allowed_responses": ["still_valid", "reworked", "needs_human"],
    "constraints": "Only change content that depends on the listed changes. Numbers are supplied by Trackback.",
    "status_url": "/pings/ping_0107",
    "respond_by": "2026-07-08T15:07:11Z",
    "signature": "hmac-sha256=..."
  }
}
```

A few field choices are worth defending. `change_kind` is `revised`, `retracted` or `added_input`. `edge_kind` is `used`, `derived_from`, `quoted` or `assumed`, and each maps to a PROV-O term so you can say "provenance is W3C PROV-O" honestly: a consumption edge is `prov:used`, the output is `prov:wasGeneratedBy` the run and `prov:wasDerivedFrom` the input, a reworked version is `prov:wasRevisionOf` the old one, and a retraction is `prov:wasInvalidatedBy` the correction ([W3C PROV-O](https://www.w3.org/TR/prov-o/)). `fields_read` and `changes` are what keep rework cheap, because the agent re-checks only what depends on what moved. And `causal_chain` is there so the agent can't ignore another agent's input or have context withheld from it, two of MAST's failure modes ([MAST](https://arxiv.org/html/2503.13657v3)). The HMAC over canonical JSON is enough on localhost and mirrors A2A's HMAC/token option.

### Endpoints

| Method | Path | What it does | Lineage |
|---|---|---|---|
| GET | `/.well-known/trackback` | Lists agents, their ping endpoints, supported ping versions | TrackBack RDF autodiscovery; A2A Agent Card |
| POST | `/corrections` | Root a cascade (a human, a source monitor, or an approved agent revision) | |
| POST | `/artifacts/{id}/versions` | Publish a version. Hub diffs it, runs the deterministic wave, writes pings and outbox rows in one transaction | Webmention re-send on update |
| POST | `/artifacts/{id}/retract` | Retraction, pings with `change_kind: retracted` | Webmention 410 |
| POST | `/edges` | Record a consumption receipt. Called by the hub's own data tools, never by agents directly | "Source links to target", made explicit |
| POST | `/agents/{agent_id}/trackback` | Receive a ping. Returns `202 Accepted` + `Location: /pings/{ping_id}` | Webmention 202; Pingback 0x0030 |
| GET | `/pings/{ping_id}` | State, attempts, response | Webmention status URL; A2A GetTask |
| POST | `/pings/{ping_id}/response` | The agent's verdict | A2A push notification |
| POST | `/challenges` | An agent disputes an upstream output. Goes to the owner or a human, never becomes a ping | |
| GET | `/corrections/{id}/graph` | Affected subgraph with per-node state, for the UI | |
| GET | `/events` | SSE stream of ping and response events | A2A SSE |
| POST | `/a2a` (optional) | JSON-RPC adapter for `SendMessage` and `GetTask` | A2A 1.0 |
| `/mcp` (optional) | Streamable HTTP | Artifacts and inboxes as MCP resources | MCP 2026-07-28 |

In a local build the dispatcher calls each agent in-process through the same handler the HTTP route wraps. The route exists so the protocol is real and inspectable, not because localhost needs a network hop.

`POST /agents/{id}/trackback` refuses synchronously, in the 400 class, when the body is malformed, source equals target, the target is unknown, the target version is already superseded (`stale_target`), the edge isn't in the ledger (`not_a_dependent`), the consumed hash doesn't match, the hop count exceeds the limit (`hop_limit`), the target already appears in the causal chain (`cycle`), or the signature is bad (`unauthenticated`). Everything else is asynchronous, the way Webmention handles source verification.

### Response states and how they map

```json
{
  "ping_id": "ping_0107",
  "items": [
    {"target": "trackback://artifact/cert_q1@v3", "verdict": "needs_human",
     "reason": "Leverage crossed 3.00x. Certificate already sent. Proposing corrected certificate and lender notice.",
     "addressed_changes": ["net_leverage.ratio"], "compensation_id": "comp_0019"},
    {"target": "trackback://artifact/bonus_g1_q1@v2", "verdict": "reworked",
     "reason": "Excess EBITDA fell $118,000; bonus at 4% falls $4,720. Proposing offset against Q2 payout.",
     "addressed_changes": ["gym_ebitda_g1_q1.ebitda_above_target"],
     "new_version": {"uri": "trackback://artifact/bonus_g1_q1", "version": "v3", "sha256": "ef56..."},
     "material_change": true, "compensation_id": "comp_0020"}
  ],
  "responded_at": "2026-07-08T15:03:40Z"
}
```

| State | Who sets it | Meaning | Next step | A2A 1.0 TaskState | Web analogue |
|---|---|---|---|---|---|
| `acknowledged` | Hub | Received, queued or running | None | SUBMITTED, then WORKING | 202 Accepted |
| `still_valid` | Agent | Re-checked; holds. Reason required, citing the changes | Append a re-verified edge to the new parent version. No downstream pings | COMPLETED, no artifact | Webmention re-verify OK |
| `reworked` | Agent | New version produced | If `material_change`, the hub runs the next wave from it | COMPLETED, with Artifact | Re-send on update |
| `needs_human` | Agent or hub | Ambiguous, executed action, threshold crossed, failed tie-out, budget hit | Shown in the approvals queue. Everything below this node waits | INPUT_REQUIRED | Moderation queue |
| `refused` | Hub | Not a dependent, stale, cycle, hop limit, bad signature, rate limit | Logged, no cascade | REJECTED | 400; Pingback faults |
| `superseded` | Hub | Coalesced into a newer ping | None | CANCELED | |
| `failed` | Hub | Delivery or agent error after retries | Dead letter, escalates to `needs_human` | FAILED | 500 |

The TaskState column comes straight from A2A 1.0's proto (package `lf.a2a.v1`), whose enum is SUBMITTED, WORKING, COMPLETED, FAILED, CANCELED, INPUT_REQUIRED, REJECTED and AUTH_REQUIRED, with COMPLETED, FAILED, CANCELED and REJECTED terminal ([a2a.proto](https://raw.githubusercontent.com/a2aproject/A2A/main/specification/a2a.proto); [A2A spec](https://a2a-protocol.org/latest/specification/)).

### MCP is the doorbell, SQLite is the mailbox

MCP's 2026-07-28 revision replaced `resources/subscribe` with a single long-lived `subscriptions/listen` stream, removed protocol-level sessions, and removed SSE resumability and message redelivery ([MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)). A client listens with `resourceSubscriptions: [uris]` and receives `notifications/resources/updated` carrying only a URI, then calls `resources/read` ([MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)). That's a TrackBack ping in all but name, and you can say so on a slide. The catch is spelled out in the Python SDK v2 docs: events "are not replayed", so if nobody is connected the notification is simply lost, and clients should re-listen and refetch ([MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/v2/handlers/subscriptions/)). So the design has to be doorbell plus mailbox. The hub exposes `trackback://inbox/{agent_id}`, `trackback://ping/{ping_id}` and `trackback://artifact/{id}@{version}` as resources, calls `ctx.notify_resource_updated` on the inbox URI whenever a ping is enqueued, and every agent reads its full inbox on connect and on every notification. Provenance metadata rides in `_meta` under a custom extension identifier like `dev.trackback/provenance`, which follows MCP's reverse-domain extension convention ([MCP Extensions](https://modelcontextprotocol.io/extensions/overview)). Use a domain the team actually controls. None of the official extensions covers provenance or dependencies. Don't touch Sampling, which this revision deprecated; agents call the Anthropic API directly. The latest Python SDK is `mcp` 2.3.0 from October 2 ([PyPI mcp](https://pypi.org/project/mcp/)). Whether Claude Desktop or Claude Code implements `subscriptions/listen` yet wasn't checked, and it doesn't matter, because Trackback's agents are your own Python loops.

### A2A is the costume for "these are real agents"

On A2A 1.0, the hub acts as a client and calls `SendMessage` on the downstream agent. The message parts carry a text reason and the ping JSON as a data part, `extensions` lists a Trackback ping URI, `reference_task_ids` points at the task that produced the stale input, and `context_id` is the correction ID so a whole cascade shares one context. A2A's push config (`TaskPushNotificationConfig` with a URL and token) carries the verdict back, and the Agent Card advertises `pushNotifications`, `streaming` and the extension ([a2a.proto](https://raw.githubusercontent.com/a2aproject/A2A/main/specification/a2a.proto); [A2A streaming and async](https://a2a-protocol.org/latest/topics/streaming-and-async/)). The A2A docs recommend JWTs checked against a JWKS, plus `jti` replay protection, and warn servers not to POST blindly to client-supplied URLs ([A2A streaming and async](https://a2a-protocol.org/latest/topics/streaming-and-async/)). On localhost, a shared token plus an HMAC body signature is fine and is one of the listed schemes. My recommendation: build the native protocol, use camelCase JSON field names that match the proto's JSON mapping, and add one `/a2a` route that handles `SendMessage` and `GetTask`. Don't take a dependency on the full A2A SDK. The exact Agent Card path and the webhook token header name weren't verified, so check them before quoting them on stage.

### Delivery semantics

Use a transactional outbox: write the new version, the pings and the outbox rows in one SQLite transaction, and let a separate relay dispatch them. The pattern guarantees a message is sent "if and only if the database transaction commits", and because the relay can send twice, "a message consumer must be idempotent" ([microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)). That gives at-least-once delivery with exactly-once effect.

```sql
CREATE TABLE corrections(correction_id TEXT PRIMARY KEY, origin TEXT, root_node TEXT,
  old_version TEXT, new_version TEXT, reason TEXT, created_by TEXT, approved_by TEXT,
  rev INT, wave_count INT DEFAULT 0, status TEXT, created_at TEXT);
CREATE TABLE pings(ping_id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, correction_id TEXT,
  wave INT, hop INT, target_agent TEXT, payload_json TEXT,
  state TEXT CHECK(state IN ('pending','acknowledged','still_valid','reworked','needs_human',
                             'refused','superseded','failed')),
  attempts INT DEFAULT 0, next_attempt_at TEXT, superseded_by TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, ping_id TEXT, dispatched_at TEXT);
CREATE TABLE responses(ping_id TEXT, target_version TEXT, verdict TEXT, reason TEXT,
  addressed_json TEXT, new_version TEXT, material_change INT, responded_at TEXT);
CREATE TABLE dead_letter(ping_id TEXT, last_error TEXT, moved_at TEXT);
CREATE TABLE llm_calls(call_id TEXT PRIMARY KEY, ping_id TEXT, run_id TEXT, model TEXT,
  input_tokens INT, output_tokens INT, cache_key TEXT, ts TEXT);
```

The rules, in plain terms. Run SQLite in WAL mode with one writer process. The dispatcher takes outbox rows in `seq` order, but only for pings that are ready in the topological sense (next section). It marks a row dispatched before invoking the agent, and the agent dedups on the idempotency key, so a crash in between causes at most one duplicate that returns the cached answer. Pings to the same agent go FIFO. Across agents the only promise is topological order. Agent errors and timeouts retry with exponential backoff (1, 2, 4, 8, 16 seconds), and after five attempts the ping moves to the dead-letter table and its nodes go to `needs_human`. None of the specs prescribe those numbers. They're starting points to tune.

## One wave, one ping per agent, and a reason it always stops

The scheduling rule that makes everything else work: do all the arithmetic first, then talk to agents in dependency order, and never talk to the same agent twice about the same correction in the same wave. This is what BoardroomAI's worklist does in spirit (seed with changed nodes, recompute dependents, enqueue only those whose signature changed, which yields the least fixed point) ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)), and it's what "Build Systems à la Carte" calls a minimal build: every task runs at most once, and only if it transitively depends on a changed input ([Mokhov, Mitchell, Peyton Jones](https://www.microsoft.com/en-us/research/uploads/prod/2018/03/build-systems-a-la-carte.pdf)). Neither paper bundles pings per agent. That part is an engineering choice, and it's the one that prevents ping storms.

### The wave algorithm

```python
def run_wave(correction, seeds):
    rev = bump_revision()
    correction.wave_count += 1
    heap = MinHeap(key=lambda node: node.topo_index)
    for node in seeds:
        heap.push(node)
    bundles = defaultdict(list)   # agent_id -> suspect items

    while heap:
        node = heap.pop()
        if node.kind == "source":
            push_children(heap, node)
        elif node.kind == "calc":
            new_value = recompute(node)
            verdict = materiality(node, node.current_value, new_value)
            if verdict.material:
                write_version(node, new_value, changed_at_rev=rev)
                push_children(heap, node)
            else:
                record_cutoff(node, verdict.reason)    # keep old changed_at_rev (backdating)
        else:  # judgment, prose, action
            if touched_fields(node) & changed_fields_upstream(node):
                mark_suspect(node)
                bundles[node.owner_agent].append(build_item(node))
            else:
                record_cutoff(node, "fields_not_read")
            # children wait for the agent's answer

    for agent_id in agents_in_topo_order(bundles):
        enqueue_ping(correction, agent_id, bundles[agent_id], wave=correction.wave_count)
```

When an agent answers `still_valid`, its nodes keep their old `changed_at_rev` and their children are never enqueued. When it answers `reworked` with a material change, the hub writes the new version, seeds a continuation of the same wave from it, and the next agent down gets its bundle only after that. So CA always answers before RA, and RA before CC, and each agent sees all of its changed inputs at once. On a known, static three-agent pipeline a Make-style topological scheduler is enough. You don't need Excel-style restarting or dynamic dependency discovery.

### Coalescing, debounce and supersession

Corrections that arrive close together should become one revision. For the demo, the cleanest version is an explicit "Apply corrections" button that merges staged corrections into one set of seeds. For background arrivals, a 2-second debounce before starting any agent does the same job. If a newer version of a source arrives while an older ping is still pending and not started, merge the new change into the pending ping and mark the older ping `superseded`. If the agent is already mid-run, let it finish, then re-check materiality against the newest version and ping again only if it still matters. None of the cited agent papers specify debounce or coalescing, so treat the windows as tunable.

### Why it always stops

You'll get asked "what stops two agents pinging each other forever?" The answer fits on a slide. Edges point from an immutable parent version to an immutable child version, so the version graph is a DAG. Within a wave, the heap processes nodes in increasing `topo_index`, and an agent can only write versions of nodes it owns, all of which sit after their parents. So nothing is re-enqueued after it's processed, and a wave does at most one evaluation per node and one ping per agent. The only way to send influence upstream is an explicit upstream challenge, which starts a new wave, and waves per root correction are capped at two. After that, any further challenge goes to a human. Finite waves times finite work per wave means termination. This is a construction from DAG and minimality properties, not a cited proof for LLM agents, so present it as an argument.

Two more guards close the gaps. An oscillation check stores a content hash per version, and if a rework produces a hash equal to any earlier version of the same node within the same root correction (A to B back to A), it stops and escalates as `oscillation`. And genuine numeric cycles, like a bonus pool that depends on net income while net income depends on the bonus accrual, get solved inside the calc layer with a closed form or a few fixed-point iterations until the change is under $1. Never let an agent sit inside a cycle. BoardroomAI does the analogous thing by collapsing cycles into strongly connected components and escalating when they don't converge ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)).

These guards map to real failure data. MAST's taxonomy of 1,642 multi-agent traces found step repetition in 15.7%, being unaware of stopping conditions in 12.4%, and incorrect verification in 9.1% ([MAST](https://arxiv.org/html/2503.13657v3)). One ping per agent per wave plus the idempotency key addresses the first. The wave cap and an explicit `still_valid` answer address the second. Deterministic tie-outs on every reworked output address the third.

### Anti-spam is five rules, and materiality is the one that matters

Pings are generated only by the engine; agents can't insert them. Every ping must reference a recorded edge whose parent is the old version, with a matching hash. Every ping passes a materiality gate. Pings are coalesced per agent per wave. And every root correction has a budget: one ping per agent per wave, two waves, and a cap on LLM calls (say 10), beyond which everything left goes to `needs_human`.

The materiality gate should be finance-native, and Tidewall's synthetic controller memo already supplies the numbers: $8,000 clearly trivial, $60,000 quarterly performance materiality, a flux threshold of more than 10% and more than $25,000, and qualitative overrides for covenant, bonus tier and sign changes. Store that memo as a versioned node so changing it is itself a correction. The test for a calc node is:

```
material = abs(new - old) >= max(abs_threshold, rel_threshold * abs(old))
           or crosses_any(old, new, node.thresholds)     # covenant max, bonus tier, sign
```

Threshold crossings are always material regardless of size, because those are precisely the cases where a small number flips a conclusion. Tie-out nodes use a $1 threshold, since they're checking exactness. Every non-ping gets a logged reason so the UI can say "not pinged: change $312, below $8,000 trivial threshold".

The second cheap precision win is field-level read sets. If RA's flux paragraph read `revenue_q1` and `ebitda_q1` but not `capex`, a capex correction never reaches it, without an LLM ever looking. That's the `fields_read` column on the edge.

### Agents revising their own work, and challenging someone else's

An agent self-revision is the same primitive as a source correction: a new version with `supersedes`, `origin: agent_revision`, a reason and an approver. Three things differ. The seed is the agent's own judgment, prose or action node rather than a source. If the revision touches an executed action or crosses a threshold, a human approves before anything propagates. And the revising agent is excluded from being pinged in that wave about the node it just wrote, which kills self-ping loops. BoardroomAI's intervention compiler handles human edits the same way, turning them into typed operations like Replace (a new version plus a supersedes edge) and Retract ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)).

An upstream challenge is different and must stay different. If RA thinks CA's accrual is wrong, RA does not get to edit it, and it does not send a ping. It files `POST /challenges` against CA's node with a reason. CA (or the controller) decides. If CA revises, that's an agent revision that starts a new wave. This one rule is what keeps information flowing only downstream within a wave, and it doubles as segregation of duties.

### What an agent actually does with a ping

The agent gets a structured bundle: the root correction and its reason, the causal chain, and for each of its suspect nodes the prior output, its prior rationale, the fields it read, and the old and new value of each changed field with deltas and any thresholds crossed. It must return one verdict per item. `still_valid` needs a justification that cites which changes it considered. `reworked` is a patch to its own prior output, not a rewrite from scratch, plus which changes drove it. `needs_human` carries the question for the human.

Patch, don't regenerate. Execution Lineage found that on an unrelated-branch update, DAG replay left the final memo identical while loop baselines regenerated it and pulled in unrelated context, and that final-answer quality and maintained-state quality are different things ([arXiv 2605.06365](https://arxiv.org/abs/2605.06365)). For prose, make the agent's original output a template with numeric slots (`{ttm_ebitda}`) that Trackback fills. A reworked paragraph then re-renders with new numbers automatically, and the LLM only touches wording whose truth depends on them, like "comfortably within the covenant" becoming "above the 3.00x covenant". That makes `still_valid` the common answer and keeps the model's job narrow.

Borrow one idea from Rollback Repair: keep candidates with "independent trusted support" rather than invalidating everything reachable ([arXiv 2608.10502](https://arxiv.org/abs/2608.10502)). If CC's conclusion rests on two independent inputs and only one moved, CC can answer `still_valid` and say why.

The hub never takes an agent's word blindly. Escalation to `needs_human` is deterministic when any of these hold: the agent asks for it; a threshold was crossed on a covenant or comp node; a reworked output fails a tie-out (RA's revenue must equal CA's ledger calc, CC's leverage must use RA's current EBITDA version); the wave cap or LLM budget is hit; or oscillation is detected. Executed actions get one more rule: a reworked action never self-heals. It produces a compensation proposal, and everything downstream of the action stays suspect until that compensation is approved, executed and verified. In the example ping above, the certificate goes to `needs_human` because leverage crossed 3.00x, while the bonus is `reworked` with an offset proposal waiting for approval.

Every ping response is idempotent by key. If a ping with the same key already has a response, the hub returns it without calling the model again. Every superseded version stays forever with `status = superseded`, which is exactly what Memento needs to answer "what did CC believe on May 15?"

### Compensations: sagas, not undo

Each executed action is a saga step that registers its compensation when it executes. Garcia-Molina and Salem's 1987 sagas pair every transaction with a compensation that semantically undoes it, restoring "an acceptable approximation" of the prior state rather than the exact one ([Temporal's summary of Sagas](https://dev.to/temporalio/paper-summary-sagas-4bb6)). Finance almost always prefers forward recovery (post a correcting entry that references the original) over pretending the original never happened, which is the "compensate, don't undo" rule.

| Action | Compensation | Approver (not the preparer) |
|---|---|---|
| `post_journal_entry` (CA) | Current-period correcting entry referencing the original, or reverse and repost in an open period | Controller |
| `send_covenant_certificate` (CC) | Corrected certificate, lender notice, waiver request drafted | CFO signs |
| `approve_bonus_payout` (CC) | Offset against next payout, or recovery request per plan terms | HR plus controller |
| `publish_board_deck` (RA) | Version 2 with a "corrected" banner and diff, original recipients notified | Controller |

Approval status runs `proposed`, `approved`, `executed` or `rejected`, and the approvals table carries a `CHECK (proposer <> approver)` constraint so segregation of duties lives in the schema. Then borrow EffectMatch's check: every action row stores what was approved and what the simulated ERP actually recorded, and nothing downstream consumes the action until the two match ([arXiv 2609.31301](https://arxiv.org/abs/2609.31301)). EffectMatch does that check before a commit. Applying it to compensations, after the fact, is your synthesis. Also keep a PlanFence-style pre-action fence, so an action that hasn't executed yet gets blocked if any supporter went stale ([arXiv 2609.03340](https://arxiv.org/abs/2609.03340)). The fence covers the proactive case and the ping covers the retroactive one.

## Score it against rerun-all, ping-everything and silence

The proof has to show two things at once: Trackback pings the agents that need it, and it leaves alone the ones that don't. Recall without precision is "rerun everything", and judges will see through it. So build a seeded scenario suite with a hand-written answer key, freeze the key before tuning the engine (commit it around hour 10 and put the commit hash on the proof slide), and run every condition from one script.

The suite should have 20 to 40 correction events over the Tidewall world, and each event's key lists the nodes that must change, the nodes that must stay, the agents that must be pinged, the actions that need compensation, and the final correct values and conclusion labels. Cover seven shapes on purpose: an immaterial correction (gold: zero pings); a material one that doesn't cross a threshold (numbers recompute, prose stays valid); a threshold crossing (covenant flips, bonus tier changes, CC pinged, compensation proposed); a correction that cancels out downstream, like revenue and cost moving together (tests early cutoff); a CA self-revision; two near-simultaneous corrections (tests coalescing); and a deliberately induced upstream challenge (tests the wave cap).

| Metric | Definition | Why it matters |
|---|---|---|
| Ping precision, recall, F1 | Pinged items vs gold must-rework set | The core claim |
| Unnecessary rework rate | Reworked items whose content hash didn't change or that were gold must-stay, over all reworked | Catches agents that churn |
| False still_valid rate | Gold must-change items the agent marked still_valid | The safety number. An agent clearing its own stale work is the worst failure |
| Preservation | Gold must-stay nodes whose hash is unchanged after the event | Execution Lineage's "zero churn" analogue |
| Rework correctness | Gold must-change nodes whose final value or conclusion label matches the key | Numbers exact; prose scored by a deterministic label like `covenant_status = breach`, not by an LLM |
| Cross-agent consistency | All tie-outs pass after the event | Proves the lanes agree |
| Inspection fraction | Nodes evaluated over total nodes | BoardroomAI-style framing |
| Cost | LLM calls and tokens per event; savings vs rerun-all | The efficiency claim, measured not quoted |
| Convergence | Waves and wall-clock seconds until nothing is suspect | Shows it stops |
| Compensation precision and recall | Invalidated actions that got a proposal; no proposals for valid actions | The novel part |
| Replay fidelity | Memento-reconstructed state hash equals the live snapshot at that revision | Should be 100% by construction; cheap to show |

The baselines are the obvious alternatives a judge would propose. B0 is no tracking: only the source changes, which measures how much stale state survives, echoing Rollback Repair's point that deleting only the source leaves propagated effects active ([arXiv 2608.10502](https://arxiv.org/abs/2608.10502)). B1 reruns all three agents from scratch, the cost ceiling and the churn generator. B2 pings every descendant with no cutoff and no materiality, which is BoardroomAI's "descendant reachability" baseline ([BoardroomAI full text](https://arxiv.org/html/2608.13046v1)). Then ablate Trackback itself: no materiality gate, no field-level read sets, and no agent judgment (every suspect prose node is sent to rework by rule). If time allows, add an "ask the agent what changed" baseline and degraph's `impact()` as an open-source comparator.

Two honesty rules. First, agent verdicts are non-deterministic, so run each LLM condition at least three times (record mode, not cached replay) and report the spread, not the best run. The cached replay mode is for the live demo, not for the eval. Second, don't put Trackback's inspection fraction next to BoardroomAI's 14.59% as if they were comparable. Different graphs, different sizes. Cite it as the framing you borrowed.

External benchmarks are mostly framing for now. MemDerive has exactly the right structure, with gold derivation DAGs produced in Datalog over 10 scenarios, 4,692 events and 1,503 queries, and it found every memory system tested fell behind plain BM25 on derived state ([arXiv 2610.25373](https://arxiv.org/abs/2610.25373)). But it's memory QA rather than multi-agent rework, and no data release was confirmed, so cite it as motivation. MAST's annotated traces and LLM annotator are public ([arXiv 2503.13657](https://arxiv.org/abs/2503.13657)), so you could label Trackback's own traces for failure modes as a stretch goal.

## Swimlanes make the ripple readable from the back of the room

The multi-agent version needs one new picture: the ripple crossing from one agent's lane into another's, and visibly not crossing into some. Use horizontal swimlanes, one per participant: Sources, Engine (every calc node lives here, which shows at a glance that agents never do arithmetic), Close Accountant, Reporting Analyst, and Covenant and Comp, with a narrow approvals rail on the right for the controller and CFO. Lay nodes out left to right by `topo_index`, so time and dependency both read left to right. React Flow handles this with group nodes as lanes: set `parentId` on each child, add `extent: 'parent'` so it can't be dragged out, and list parents before children in the nodes array ([React Flow sub flows](https://reactflow.dev/learn/layouting/sub-flows)). The docs don't mention swimlanes by name, but that's the mechanism. Syncfusion has first-class swimlanes if you'd rather not build them, but it's commercial ([Syncfusion lane docs](https://help.syncfusion.com/diagram-sdk/react/lane)).

Node states need an icon and a pattern as well as a color, because projectors wash out red versus green. Grey for active, amber with "!" for suspect, blue for reworked, green with a check for still valid (with the agent's reason on hover), red for needs human, faded for superseded, and a small grey "not pinged" badge with the reason ("$312, below $8,000 trivial") on descendants the cutoff skipped. Those grey badges are the whole argument against TrackBack-style ping storms, so make them legible.

The ping itself should be a visible object. When the engine finishes its deterministic pass, an envelope chip labeled with the ping ID travels from the Engine lane into the CA lane, the lane header shows "reviewing 2 items", and the verdict lands on each node. Then the next envelope goes to RA. A step-through control at the top (deterministic pass, then CA, RA, CC) lets you pause between hops while you talk. Precompute the whole sequence and animate a list of (node, state, delay) at roughly 150 ms per hop. Animate only edges on the active path. React Flow's built-in dashed `animated` edges get CPU-heavy, and one team cut hover jank on a 100-plus-node diagram by using a custom edge with SVG `animateMotion` on highlighted edges only ([Liam ERD blog](https://liambx.com/blog/tuning-edge-animations-reactflow-optimal-performance)).

Next to the graph, a side panel renders the ping log for the selected correction as a Mermaid sequence diagram, generated straight from the `pings` and `responses` tables. Mermaid supports `rect` background blocks, `alt` branches, `autonumber` and participant `box` grouping ([Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram.html)), which is all you need:

```
sequenceDiagram
  autonumber
  participant E as Engine
  participant CA as Close Accountant
  participant RA as Reporting Analyst
  participant CC as Covenant and Comp
  participant H as CFO
  rect rgb(240,240,240)
    Note over E: Wave 1, deterministic pass: 14 calc nodes, 9 cut off
    E->>CA: ping_0105 (je_rev_march)
    CA-->>E: reworked v4
    E->>RA: ping_0106 (2 tiles, 1 flux sentence)
    RA-->>E: tiles reworked, sentence still_valid
    E->>CC: ping_0107 (cert_q1, bonus_g1_q1)
  end
  alt leverage crossed 3.00x
    CC-->>E: cert needs_human, comp_0019 proposed
    E->>H: approve corrected certificate
  end
```

Under the graph, a counter strip turns the eval metrics into live numbers: "nodes inspected 11 of 64 | agents pinged 3 of 3 | items reworked 4, cleared 3, skipped 9 | LLM calls 4 vs 12 for rerun-all | compensations 2 pending". Those numbers are illustrative until the build produces real ones. The Memento time scrubber sits at the bottom, now with one tick row per agent lane, so dragging it to May 15 shows exactly what CC's lane looked like when it sent the certificate.

## The honest risks

Most of the risk here isn't in the protocol, which is boring on purpose. It's in the parts where an LLM makes a call, and in trying to build all of it in 36 hours.

| Risk | How likely | What to do about it |
|---|---|---|
| An agent marks its own stale work `still_valid`. The owner of an output re-checking it is the natural design, and also the one most prone to self-preference. MAST puts incorrect verification at 9.1% of traces ([MAST](https://arxiv.org/html/2503.13657v3)) | High | Threshold crossings and executed actions go to a human no matter what the agent says. Tie-outs run on every output. Sample `still_valid` answers through a separate verifier prompt, ideally a different model. Report the false still_valid rate on the proof slide even if it's ugly |
| Novelty gets challenged because BoardroomAI exists, or a new paper lands that week | Medium | Name BoardroomAI and PlanFence yourself, use the composition framing, and search arXiv the morning of judging |
| "Three prompts in a pipeline isn't multi-agent" | Medium | Concede the pipeline. Point out that the agents have different tools and permissions (only CA posts entries, only CC sends certificates), which is segregation of duties, and that the protocol works across processes via the A2A adapter |
| The design has never been prototyped. Verdict quality depends on prompting and how well claims are extracted | High | Get one correction flowing through all three lanes end to end before adding anything else |
| Field-level read sets are wrong. Over-capture costs precision; under-capture silently misses a dependent, which is the dangerous direction | Medium | Agents read only through typed tools. When field-level capture is uncertain, record the whole artifact as read |
| MCP notifications get lost (no replay), and host support for `subscriptions/listen` is unknown | Medium | SQLite is the source of truth, agents read their inbox on connect, and MCP is optional |
| A2A details quoted wrong (Agent Card path, webhook header name and release date weren't verified) | Low | Don't put unverified field names on slides |
| Sequential waves are slow live, since each agent call takes seconds | Medium | Use cached replay for the stage demo, and use the step-through control so the pauses look deliberate |
| Materiality thresholds get disputed by a finance judge | Medium | They're a versioned policy node the controller owns. Show it, and show that changing it propagates |
| Scope: protocol, two adapters, UI, eval and compensations in 36 hours | High | Cut the A2A adapter first, then the MCP doorbell, then upstream challenges, then the Mermaid panel |
| The name evokes spam to anyone who remembers blog trackbacks | Low | Lean in: "TrackBack died of spam. This one can't be spammed, because every ping comes from a receipt." Check Devpost for a same-named project |

What should never get cut: the deterministic wave with materiality cutoff, one ping per agent per wave, the three verdicts, at least one compensation with a different-person approval, the swimlane ripple with "not pinged" badges, and the eval script with the rerun-all and ping-all-descendants baselines.

## Conclusion

The thing the protocol history teaches is that notification protocols live or die on verification, and every web generation had to bolt it on after the fact. Agent systems get it nearly free, because when the hub mediates every read, the dependency record exists before anyone needs to ping along it. That flips the old problem around. TrackBack had to ask whether a ping was legitimate. Trackback can only ever send legitimate ones, so the hard question moves to whether a ping is worth sending, which is a materiality question, which is where finance already has decades of rules. The other design choice that turned out to matter more than expected is addressing pings to agents rather than artifacts. That small change converts a notification protocol into a scheduler with an at-most-once-per-wave guarantee, and it's what lets you answer "what stops this from looping?" in one slide.

The implication for the pitch is that the impressive part is not the ripple, which BoardroomAI and every lineage tool can draw. It's the green and grey nodes, each with a reason, and the false still_valid rate sitting honestly next to them. A finance team running agents at high straight-through rates doesn't fear missed corrections as much as two things: false alarms that pull humans back into every close, and silent self-approval by an agent that should have reopened its own work. Trackback is worth building if it can show numbers on both, and the eval plan above is designed to produce exactly those two numbers.
