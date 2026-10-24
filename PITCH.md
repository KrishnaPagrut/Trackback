# PITCH.md: three minutes, then the keyboard

Every number below is read from the run (`data/eval/latest.json` and the Stage beats); if the screen shows a different number on the day, say the screen's.

Seat line (say it verbatim): **"Trackback does the close accountant's error review: when sources disagree, it finds what broke, sizes it, drafts the fix and the memo, and never posts anything without the controller."**

## The three minutes (Stage mode; `Space` for each beat)

| Time | Screen (beat) | Say |
|---|---|---|
| 0:00 | **Title**: "Tidewall told its bank leverage was 2.95x." | "48 climbing gyms, $186 million of revenue, a $105 million loan, and $533,333 of room under its limit." |
| 0:15 | **Reconcile**: four counters run; one row turns red | "Four reconciliations: 271 bank lines match, deposits in transit and a bundled wire clear with reasons. Most differences are noise. This one isn't: the billing migration double-counted $750,000." |
| 0:40 | **Evidence**: the billing line, both GL imports, Priya's cell, the deck line, the certificate | "Billing released batch 7 once. The import job timed out, retried, and posted it twice. Nobody linked Priya's spreadsheet or the board deck to the books; Trackback found where every number came from, and that the deck's $32.6 million was typed from a draft." |
| 1:00 | **Ripple**: lanes fill, red and green | "These are now wrong: 40 figures and actions, including the certificate already sent to the bank. These 23 it checked and cleared, each with a reason. Three agents built on this number; each got one ping. The Reporting Analyst rewrote its covenant sentence and kept two others, with reasons. The cash forecast was skipped: no cash moved." |
| 1:25 | **Jade**: the agent says immaterial; OVERRULED | "Under 5% of profit, so the agent's first draft says immaterial. Its reviewer doesn't: rollover $662,000 passes, iron curtain $1.1 million fails, SAB 108 needs both; leverage goes to 3.02, a breach; three bonuses were overpaid. And lender documents go to the CFO, not the controller." |
| 1:50 | **Approvals**, then **Dana says no** (live) | "It drafts; it never posts. Dana rejects the first entry: Q1 is locked. The agent re-drafts in June with an out-of-period tag. The July 15 bonus run is on hold. And it can't approve its own work: the database refuses." |
| 2:10 | **Replay**: April 9, 6 PM; the refusal stamp | "It owns the miss: on April 9 the billing export already showed the batch once and the GL showed it twice. And it can't peek: ask for July's export while pinned to the close and it's refused, with both timestamps." |
| 2:25 | **Scorecard** | "36 planted cases, step by step. A 5% rule gets materiality right 19 times in 32; with its reviewer, 32 of 32. Jade caught all 43 planted agent mistakes with no false overrules. Lessons it learned took held-out cases from 5 of 18 to 18 of 18." |
| 2:45 | **Memo** and the seat line | "It writes the memo your auditor will ask for." Then the seat line. |

Then hand over the keyboard: **"Change any number, or paste your own correction."** (`C`, or the button.) Good first tries: "March legal is $90k higher; the invoice was in the inbox before the close" (material after Jade: it changes the certificate); "Batch B03 February was imported twice" (every region's bonus moves).

**If there's time, or as an opener on a big stage (20 seconds, `W`):** "February 13, 2024: Lyft's release said 500 basis points. The model it came from said 50, and so did the CFO on the call. Shares jumped as much as 67% after hours. Trackback reads the real filing: 24 of 25 figures tie to their sources; one doesn't, and its nearest source is 50 at another power of ten. With Trackback inside, the release is blocked before it goes out. Outside, only the newsroom and the sell-side desk that built on the 500 get pinged."

Cut order if short: Lyft, the scorecard beat, the replay beat. Never cut: the ripple, Jade's overrule, Dana's rejection.

## Appendix B: the hard questions

- **"Is this just an LLM?"** No. A matching engine finds the error, the graph finds what it touched, code decides whether it matters, and the LLM writes the words and gets checked. The 5% rule and the agent without Jade are on the scorecard.
- **"Isn't a context graph common?"** Yes, and we use one as plumbing. The new parts: recovering links for hand-typed numbers nobody linked (55 of 55 here, including a stale one), the accounting judgment (SAB 108 both ways, qualitative tests through the graph, aggregation with the log), and a reviewer that is itself scored.
- **"Workiva and DataSnipper do this."** Workiva propagates links people set up by hand; DataSnipper helps auditors match numbers to documents. We find the links nobody drew and tell you whether the break matters.
- **"Why isn't X3 a restatement?"** The Cragline invoice arrived May 20, after the April 10 close; the $410,000 accrual was the best estimate then. Replay shows it. It's a change in estimate, already booked in May. The agent's first draft wanted to restate; Jade overruled it.
- **"4.7% is immaterial."** Under a naive 5% rule, yes. Rollover passes at $662,000; iron curtain fails at $1,118,000; SAB 108 requires both. And it flips the covenant, which SAB 99 names as a qualitative factor.
- **"How do you know the cleared items are right?"** Most are structural (another region, other accounts, a policy term); the rest are arithmetic (recomputed and the value or conclusion didn't move). 63 of 63 reasons match the key, which the generator wrote with its own arithmetic.
- **"Does it learn?"** From Jade's overrules and Dana's rejection, as lessons she approves, gated by a full regression run, measured on held-out cases. The gate refused one: "treat every closed-period invoice as an estimate" would have broken X2.
- **"What stops it doing damage?"** Read-only on sources, drafts only, `CHECK (proposer <> approver)` in the schema, holds on risky actions, every claim cites evidence, and Replay refuses anything published after a decision.
- **"Why pings? Can't agents just check provenance?"** They rarely do. The hub pings only along receipts it recorded at read time, only for material changes, once per agent per wave. Agents can't ping each other; challenges go to a human.
- **"Is the Lyft part real?"** The filing (500 basis points), the CFO's correction (50), the correcting release and the tape are real. The finance team's documents, the agents and the outside dependents are reconstructions from the public numbers, labeled on every line.
- **"Does it work without the internet?"** Yes: `python tasks.py check` runs every beat with outside connections refused. Recorded model responses replay from the cache.
