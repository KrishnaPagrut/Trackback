# PITCH.md: the three minutes, and the hard questions

Counts below are from the frozen build with the real model (Claude Sonnet 5.5 agents, Claude Opus 5.5 judge; `data/eval/latest.json`, `make eval`) and the live E11 run through the API. Say what the screen shows on the day; these are the numbers it showed at the freeze.

Vertebrae: (1) every number carries a lot code; (2) a correction ripples forward precisely, red and cleared side by side; (3) replay can't cheat with the future.

## The live pitch, 3:00

Run it in Stage mode (the app opens there). Every beat is one press of `Space`; `Backspace` goes back; `R` resets. The numbers on screen are read from the run, so they match the proof page.

| Time | On screen (key) | Say |
|---|---|---|
| 0:00–0:15 | Title card: "May 15: Tidewall's CFO told its lender leverage was 2.95x." | "Two AI agents and an FP&A analyst, Maya, run Tidewall's close. On May 15 the CFO told the lender leverage was 2.95 times. Three agents built on that number." |
| 0:15–0:30 | `Space`: the layered reveal. Sources, then the Close Accountant's work, then Covenant and Comp, then the Reporting Analyst, with thin lines for who built on whom. | "The Close Accountant's revenue fed the Covenant agent's certificate, and the Reporting Analyst's deck rests on both. Every line is a receipt." |
| 0:30–0:40 | `Space`: the recall notice. `Space`: drop it. | "July 8. The billing system admits it counted $118,000 of March revenue twice." |
| 0:40–1:00 | `Space`: the calc line "Leverage recomputed: 2.95x → 3.03x, crosses 3.00x". | "Trackback recomputes every number itself. No agent is asked about arithmetic. The certificate is now a breach." |
| 1:00–1:40 | `Space` three times: one ping bubble per agent, in its lane. | Read the Covenant and Comp bubble aloud: "Your lender certificate rests on net leverage, which changed from 2.95x to 3.03x. It now crosses your 3.00x covenant. Still valid?" Point at the cash forecast card: "Skipped. No cash moved, so nobody asks." |
| 1:40–2:10 | `Space` three times: each agent replies. The certificate card says "Waiting for the CFO". | "The Close Accountant reworks its memo. Covenant and Comp can't un-send a certificate, so a corrected one and a lender notice wait for the CFO. The Reporting Analyst rewrites three sentences and keeps one: revenue still grew." |
| 2:10–2:25 | `Space`: Jade's card, stamped OVERRULED. | "The agent's own write-up called this immaterial: $118,000 is under the $160,000 rule of thumb. Jade, the reviewer, read the whole graph: over performance materiality, the covenant flips to 3.03x, bonuses already paid change. Overruled." |
| 2:25–2:35 | `Space`: the lesson card. | "That mistake is now a lesson. It was re-run against every past case, nothing that passed before fails, the Controller approved it, and the playbook is v2. The broad misreading the gate rejected is on the card too." |
| 2:35–2:45 | `Space`: the payoff. | "Ten pieces of work out of 174 needed an agent to look. Three of three agents acted, four actions wait for a human, nothing left stale. Jade overruled two of four calls; two lessons learned." |
| 2:45–2:55 | `T`: April 10 and the refusal stamp. | "Was the agent negligent? Here is what it saw on April 10: the duplicate rows were right there. And it can't read July 8 to look smart." |
| 2:55–3:00 | `D` for a few seconds of Deep mode, then the tagline. | "And here's the full instrument. Trackback traces any correction forward." |

If the slot is shorter: cut the Deep mode coda first, then the April 10 beat, then the lesson card. Never cut Jade's overrule. Never cut the bubbles, the skipped cash forecast, or the payoff. If judging is at a table, open `/?kiosk=on`: after 60 seconds it loops on its own with captions, and a judge who presses a key gets three presets to try. The 40-cent bank fee is the precision demo: zero pings, everything cleared, five seconds.

The Lyft story (Real world tab, or a 20-second opener on a stage): "February 13, 2024: Lyft's release said 500 basis points. The model it came from said 50. Shares jumped 67% after hours. With Trackback the release is blocked before it goes out: the sentence says 500, the number it cites is 50."

## Real counts at the freeze (E11)

- Naive (source-level): 55 artifacts read the March export.
- Trackback: the numbers on the proof page and in the Stage payoff come from `make eval` and the run; at the freeze 10 of 174 pieces of work needed an agent, all three agents were pinged once, 4 executed actions got compensations.
- Leverage 2.946x → 3.030x against 3.00x.
- Fresno bonus $2,000 → $720 (overpaid $1,280); Oakland $2,000 → $960 (overpaid $1,040); offset against the next bonus, HR plus Controller.
- Q2 estimated tax $164,535 → $139,755; reduce the Q3 installment by $24,780 (company policy; tax advisor notified).
- Compensations: corrected certificate and lender notice (CFO), bonus offset (HR + Controller), tax installment (Controller), deck v2 with corrected banner (Controller).
- Jade: the agent's materiality call overruled (immaterial → material), its posting call overruled (March is locked → June with an out-of-period tag); L-posting recalled from memory (27% like E10). After the lesson beat: L-materiality and L-posting active, L-locked-means-estimate rejected by the gate, playbook v2.
- Jade on playbook v1: 13 of 13 planted agent mistakes caught, 0 false overrules in 63 correct claims; held-out learning: playbook v1 80.6% → v2 100.0% on 36 claims the agent never learned from, 4 lessons approved, 1 rejected by the regression gate (`data/eval/latest.json`, `learning` block).

## The $80k utilities judge drill, both ways

Red pen → search "utilities" → pick `utilities G3 2026-03` (the $48,000 accrual, now $51,900 after E01) → new value 80000.

- Answer "after": estimate change. Preview shows Q1 artifacts cleared with "estimate change: correct as of what was knowable"; nothing else moves. Book the true-up in April. Q1 alone.
- Answer "before": error. Q1 utilities, Sacramento EBITDA, EBITDA, pretax and TTM recalculate (−$28,100 from $51,900); leverage moves to about 2.98x; the certificate is touched and cleared with "conclusion unchanged, calculation attached"; an out-of-period entry and a misstatement-log line follow.

Same number, two correct answers. The system asks which world it's in instead of guessing. Headroom after E02 and E10 is $63.5k of EBITDA, so a hit above that flips the certificate (try 125000 with "before").

## Positioning lines

- "Every agent framework can rewind its own run. Trackback is what happens when someone else's output changes after you've already acted on it."
- "Dagster knows when a table is stale. It can't un-send a lender certificate."
- "PlanFence checks before you act. EffectMatch checks while you commit. Trackback handles the input changing after the effect."
- "Provenance isn't enough. Agents check it about one time in five. Trackback pings them."
- "TrackBack died of spam because pings were never verified. Ours only travel along hash-verified receipts of what each agent actually read."

Claims to avoid: not first at selective multi-agent re-activation (BoardroomAI), at recording input versions (PlanFence), at agent provenance graphs (MAP-Graph), or at bitemporal memory (Graphiti). Claim the combination: pings to the affected downstream agents, a value-aware materiality cutoff, compensation of already-executed actions with approvals, and per-agent as-of replay, on a real close workflow plus real SEC data. Rollback Repair says it cannot undo an irreversible external side effect; PlanFence notes passing validation doesn't stop an input changing before the effect. Cite both.

## Hard questions

- **Does it learn?** From Jade's overrules and the Controller's rejections, never from grading itself. Each lesson is a named check that is gated against every past case before the Controller approves it, prospectively. Measured on held-out cases: v1 80.6% → v2 100% on 36 claims it never learned from; one broad lesson rejected by the gate.
- **Isn't Jade just the engine wearing a hat?** Jade uses the same engines the pipeline trusts (Memento, the materiality memo, the period locks, the approval matrix) and is scored against the frozen answer keys like everything else: 13 of 13 planted mistakes caught, 0 false overrules in 63 correct claims. The point is that the agent's write-up is a judgment and the reviewer is arithmetic; the LLM never produces a number on either side.

- **Isn't this Dagster for agents?** Dagster assumes recomputing is cheap, deterministic and side-effect free, uses equality on data versions as its cutoff, and relies on lineage declared up front. Trackback records what each run actually read, uses a materiality judgment on real values, asks agents to re-check judgment and prose, and proposes compensations for actions that already happened.
- **LangGraph has time travel.** It replays one thread from a checkpoint by re-executing nodes. Memento returns what was knowable at a time across agents and sources, with a TimeMap and refusals, and doesn't re-execute anything to answer.
- **BoardroomAI already re-activates affected agents.** Yes, after a human intervention, in synthetic deliberation, with no executed side effects or compensation and no as-of replay. Trackback triggers on source corrections and agent self-revisions and handles money that already moved.
- **What stops ping storms?** Only the hub can ping, only along hash-verified receipts, only for material changes to fields the agent actually read, at most once per agent per wave, at most two waves, with hop and cycle limits.
- **Can agents loop?** No. Versions are immutable so the graph is a DAG, agents can't ping each other, and upstream challenges go to a human.

- **Isn't this just Excel's trace dependents?** Half right. Trace dependents is structural arrows inside one workbook, right now. It doesn't cross systems, doesn't know which version a value used or what was knowable at decision time, and can't tell you a payment went out and needs a compensating entry approved by someone else. Capturing dependencies at write time is practical now because the writers are machines.
- **If the agents declare their dependencies, isn't the graph trivial?** They don't declare anything. Every read goes through the Memento tools and is logged, numbers are computed by Trackback from claim ids the agent was actually served, prose cites claim blocks. The hard part is deciding what a correction doesn't break. Show a green node.
- **How do you know "unaffected" is right?** Different period and different line item are structural (different claim ids). Early cutoff is arithmetic. Only prose goes to the LLM (Claude Opus 5.5, a different model from the writer), labeled, low confidence routes to a person, and agreement with the hand labels is reported separately: 96% on n = 25 prose edges, Cohen's kappa 0.90. The one disagreement is the judge sending a cash sentence to a person under a $189 return.
- **Zep/Graphiti already does bitemporal.** Yes, and we'd store on it. Graphiti invalidates single facts and prefers the newest. It doesn't track what was derived and doesn't cascade. Bitemporal facts versus bitemporal consequences.
- **How is this different from an audit trail?** Your trail answers "where did this number come from?" We answer "where did this source go?" and "what did the agent know at 2 pm on April 10?"
- **This exists in papers.** EA-Graph, PlanFence, GuardWrite, the 19:05 replay paper, STALE, MemDerive. They stay inside one agent's memory, one codebase, or an eval harness. We cross source data, documents, forecasts and money that moved, with replay enforced at run time.
- **Isn't Memento just a web-archive protocol?** Yes, that's the point: a mature standard for "this resource as of a time". Plain RFC 7089 returns the nearest version, even a later one, so the refusal is our own time-pinning profile: the pin is server-side per run, nothing after it is served, a missing datetime means the pin. Four deviations, in the README.
- **Why not 425 Too Early?** We wanted to. RFC 8470 reserves 425 for TLS early-data replay and requires clients to retry, which would loop. So 403/404 with an RFC 9457 problem body. 425 is a slide joke.
- **What's real and what's simulated?** Proof page table. Engine, Memento service, refusals, ledger and approvals are real and running. The company is synthetic; the 23 planted corrections are designed from cited accounting rules. The Lyft tab: the release, the correction and the tape are public record; the finance-team documents and the outside-world dependents are reconstructions from those numbers, labeled on every line.
- **Is the E11 treatment right? 3.7% is immaterial.** Under the 5% rule of thumb, yes, which is exactly why a naive rule misses it. It's above our $60k performance materiality, so it must be booked and evaluated, and SAB 99 names covenant compliance as a qualitative factor. It flips 2.97x to 3.03x. We don't decide materiality for the controller; we hand over the calculation.
- **Why isn't E07 a restatement of Q1?** The change order didn't exist on March 31. ASC 606 cumulative catch-up in April. Replay March 31 and the estimate was right as of then.
- **What if the agent was wrong, not the source?** That's E11 and E22. Replay shows the duplicate was knowable on April 10, so Trackback calls it an error, owns the miss and proposes a dedupe control.
- **Does it scale?** Propagation walks from the changed claims; cost is the blast radius, not the graph. E11 touches 81 of 169 artifacts in about 100 ms through the API. Writes are append-only.
- **Why would a company trust it?** It never auto-reverses anything. Compensations come from a fixed menu and a different human approves, enforced in the schema. Every verdict cites exact claim versions. Mementos are immutable.
- **Is the model really doing the work?** Yes: every run in the frozen build was recorded with Claude Sonnet 5.5 driving the tools (reads, formulas, citations, proposals) from a work order; the demo replays those recorded responses offline. The model never does arithmetic: every number comes from a formula Trackback evaluates over claim ids the model was actually served. Show a run's turn count in the Decision door if asked.

## Video shot list (2:00 to 2:30; record Stage mode at 1920x1080, then 10 seconds of Deep mode before the proof page)

| Time | Segment (keys) | Caption |
|---|---|---|
| 0:00–0:10 | Title card | "Three AI agents built on one number" |
| 0:10–0:25 | `Space`: the layered reveal | "Each agent builds on the one before it" |
| 0:25–0:40 | `Space`, `Space`: the recall notice drops; the calc line crosses 3.00x | "July 8: the source admits it was wrong" |
| 0:40–1:25 | `Space` ×6: three ping bubbles, three replies; the cash forecast skipped | "Only the agents that used it get asked" |
| 1:25–1:40 | `Space`: the payoff number | "10 of 174 needed a look" |
| 1:40–1:55 | `T`: April 10 and the refusal stamp | "Exactly what it knew, nothing it couldn't" |
| 1:55–2:05 | `D`: Deep mode, click the certificate, Who built this | "And here's the full instrument" |
| 2:05–2:20 | `P`: the proof page | "How we know it works" |

Mark the core segment "unedited screen capture of the running system". Record from the frozen build and canonical snapshot (`make demo`) so the numbers match the proof page.
