# Trackback

**Trackback does the close accountant's error review: when sources disagree, it finds what broke, sizes it, drafts the fix and the memo, and never posts anything without the controller.**

*Hyphenate traces any number back. Trackback traces any correction forward.*

## Inspiration

A wrong number in a finance team doesn't stay in one place. It lands in a spreadsheet someone typed by hand, a board deck, a certificate already sent to the bank, a bonus already paid. When someone finally spots it, the hard part isn't fixing the ledger; it's knowing what else it broke, whether it matters, and who has to fix what. Today a person guesses. TrackBack, the 2002 blogging protocol, let a page notify everything that referenced it; we wanted that for corrections.

## What it does

Two worlds run on the same engines.

**Tidewall Climbing Co.** (synthetic): 48 gyms, $186M of revenue, a $105M loan, leverage reported at 2.95x against a 3.00x covenant. On July 8 Trackback:

1. **Reconciles** four ways (billing to GL, bank to book, cash application, AP) and clears the ordinary mess with reasons: deposits in transit, outstanding checks, a one-cent FX difference, a bundled wire found by subset-sum, a customer's habitual short-pay, a payer under another name, a colleague's half-finished reconciliation. Six real exceptions remain. One is big: the March import of a billing batch ran twice, $750,000 of revenue counted twice.
2. **Traces** every number people typed into a covenant workbook, a board deck and a signed compliance certificate back to the books, with nobody having drawn the links (55 of 55), and notices that the deck's $32.6M was typed from a draft.
3. **Ripples** the correction forward: 40 figures and actions are now wrong, including the certificate already sent to the bank, three overpaid bonuses and the Q2 tax; 23 were checked and still hold, each with a reason. Three AI agents that built on the number each get one ping and answer still valid, reworked or needs a human.
4. **Judges** it. The agent's first draft calls it immaterial (4.7% of pretax). Jade, its reviewer, overrules: SAB 108 rollover $662,000 passes but iron curtain $1,118,000 fails; leverage moves to 3.02x, a breach; management bonuses change.
5. **Asks** the right people. It drafts; it never posts. The controller rejects the March-dated entry ("Q1 is locked"); the agent re-drafts in June with an out-of-period tag. The next bonus run is on hold. The database refuses self-approval.
6. **Owns the miss**: Replay shows the duplicate was visible on April 9, before the close, and refuses to show anything published later.
7. **Writes the memo** an auditor will ask for, and **learns**: lessons from Jade's overrules and the controller's rejection, approved by the controller and gated by a full regression run.

**Lyft, February 13, 2024** (real): the release said "approximately 500 basis points" of margin expansion; the model said 50. Trackback reads the real filing (24 of 25 figures tie; the 25th is 500 against a source of 50, the same digits at another power of ten), blocks the release before publication when it runs inside, and pings only the newsroom and sell-side desk that built on the 500 when the correction lands.

## How we built it

Python (FastAPI, SQLite, numpy, scipy, openpyxl, python-pptx, pypdf), React and TypeScript. An append-only, bitemporal ledger and versioned sources; a metric library over ledger slices; Hungarian assignment and subset-sum for reconciliations; a lineage tracer with its own formula evaluator and display-precision matching; a ripple engine with early cutoff and conclusion checks; SAB 108/99 materiality computed through the graph; a versioned playbook; Jade's code checks; a ping hub (CloudEvents envelope, HMAC, hash-verified consumption receipts); Claude Sonnet 5.5 for the agent's words and Claude Opus 5.5 for Jade's critique, every response cached so the demo runs offline.

Math decides what matches and what it's worth; AI handles judgment and language, and everything it says gets checked.

## Proof

36 planted cases with an answer key the generator writes from its own arithmetic: exceptions found 6 of 6, no false alarms on noise; lineage 55/55; the $750k ripple 40/23/5 with 63 of 63 reasons right; materiality 19/32 for a 5% rule vs 32/32 with Jade; Jade catches 43 of 43 planted agent mistakes with no false overrules; held-out cases go from 5/18 to 18/18 after approved lessons; zero future reads leaked in 73 adversarial fetches; Lyft variants 5 of 5. `python tasks.py check` runs the whole demo with outside connections refused.

**Real vs simulated:** the engines, Jade, the scoring, the file parsing and Lyft's filing, correction and tape are real; Tidewall, its people and files, and Lyft's internal documents and outside dependents are simulated or reconstructed, and labeled.

## Challenges

Making "is it material?" honest: a 5% rule is wrong in both directions, so the qualitative tests are computed from the graph (does it flip the covenant, change someone's pay, sit in a delivered document) rather than guessed, and a clearly trivial amount never becomes material. Keeping the answer key independent of the engines. Making a ripple across people, agents and executed actions readable in three minutes.

## What's next

An SDK so any agent's tool calls write receipts; uploads of people's files with confirm-the-link flows; a hosted hub with webhooks; domains beyond finance (the ping hub and receipts are already domain-agnostic; the metric library and materiality rules are the finance plug-in).
