# NEW_SPEC: the hackathon submission

- Hacking starts: Friday, October 23, 2026, around 6:00 pm PT.
- Devpost deadline: Sunday, October 25, 2026, 9:00 am PT.
- The brief below comes from a paste of the track description, not a public page. Check it against the official Devpost listing before building.

---

## 1. What the track is asking for

### In one paragraph

Build an AI system that does part of a finance team's job by itself, inside a company you invent. Build that company too: the software it uses, the people the system answers to, and the mistakes hidden in its data. The AI does most of the work and makes the routine decisions. People approve what matters and can say no. The system should know when to ask a person, and every decision should trace back to the data, rule or person behind it.

### What to build

1. **A company.** Invent one. It can be anything, but the brief wants you to be "imaginative about the company and strict about how it works underneath."
2. **A few seats.** Pick one corner of the finance team (for example the month-end close, accounts payable or reporting) and name the jobs the system fills.
3. **The AI system** that does those jobs.
4. **The world around it:** the company's software, its people (approvers, a controller, colleagues), and realistic mistakes in its data.

### What makes it hard (the system should handle all five)

| Challenge | What it means in practice |
|---|---|
| Sources that disagree | The bank, the ledger and the contract each tell a slightly different story. The system picks which one to trust and says why. |
| Time | "What happened in March should change what the system does in June." Past events and corrections have to affect later decisions. |
| Working with others | Approvers are busy. Colleagues hand over half-finished work. The controller sometimes says no, and the system has to cope with that. |
| Limits | Whoever requests a payment can't approve it (segregation of duties). The AI can't approve its own work. |
| Explainable and accountable | Every decision traces back to the data, rule or person behind it, however long ago it was made. |

### Humans in the loop

The track does **not** ask for a fully autonomous system with no people in it. It asks for:

- an AI that does the bulk of the work and the routine decisions;
- people who approve what counts (payments, material entries, anything legal or lender-facing) and who can reject the AI's work;
- an AI that **knows when to ask**. That is a judging criterion. Asking about everything fails "approvers are busy", and asking about nothing fails "limits".

### How it's judged

| # | Question | What a strong answer looks like |
|---|---|---|
| 1 | Is it real enough? | Realistic data, a messy problem, and proof that it works |
| 2 | Would you hire it? For which seats? | Named seats, limited access, a clean record of every action, and good judgement about when to ask |
| 3 | Did we see something new? | A distinct capability beyond existing tools |
| 4 | The moment | One scene where the system catches what others missed, recovers from something going wrong, or defends a decision when questioned |

### What to submit

- **A demo video that opens with the moment.** No long intro.
- **A live demo that really runs.** Judges may try a scenario of their own, so the system can't be a canned recording.
- **One line on the seats it fills.**
- **Proof it works:** what's real, what's simulated, and how you know. The suggested method is planted errors checked against an answer key.

---

## 2. The project

### The problem

Finance work is a chain. One file feeds a schedule, the schedule feeds a report, and the report feeds a decision or a payment. Some links are made by AI agents and some by people with AI tools. When something early in the chain turns out to be wrong, nothing tells the rest of the chain. Later work quietly becomes wrong, and no one knows which pieces to fix. Today a person notices the error and guesses what else it touched.

### What the system does

It connects every document and number to what it was built from and what was built from it. It doesn't matter whether an agent made it or a person uploaded it. When something is corrected:

1. It follows the links forward and finds everything downstream.
2. It recalculates the numbers itself and stops where nothing changed enough to matter.
3. It tells the owner of each affected piece (an agent or a person) what changed and why.
4. Agents re-check their own work and answer "still valid, because...", "redone" or "needs a person".
5. Anything that already moved money gets a proposed fix, which goes to a person who didn't prepare it.
6. It can replay what was known at any past moment, so a past decision can be defended or owned.

### The goal

When a fact changes, give a short, provable answer: what broke, what didn't break and why, and what got fixed. Nobody should have to redo everything, and errors should never quietly spread.

### One line

"We trace any correction forward."

---

## 3. Documents from agents and from people are treated the same

Every document, number and action is a **node**. Each node has versions, and a **link** says "this version was built from that version." Who made the node is only a label on it.

The only difference is how the links get recorded.

| Method | How it works | Reliability | Use it for |
|---|---|---|---|
| **Capture at read** | Agents (and AI tools connected through MCP) read sources through the system, so every read writes a link automatically | Exact | Everything our own agents do |
| **Match after upload** | When a person uploads a file, the system scans it for numbers, names and quotes that match known sources and suggests links | A guess, so a person confirms it | Files people make in ChatGPT, Excel or similar tools |
| **Declare at upload** | The uploader picks what the file was built from | As good as the person | Fallback when matching finds nothing |

Requirements:
- A suggested link stays **unconfirmed** until a person accepts it. Unconfirmed links still raise a warning when a correction reaches them, but they're marked as uncertain.
- Every link records how it was made (captured, matched-and-confirmed, or declared). That's part of the "clean record".
- The demo shows at least one document a person uploaded sitting in the same graph as the agents' work, so judges see the idea isn't limited to agents.

---

## 4. Fitting it to the track

### The company

Required: invent one. Decide before hacking (see Section 10). It should:
- be boring enough that the accounting is believable, and specific enough to remember;
- have a lender agreement, payroll or bonuses, and taxes, so a correction can reach things outside the books;
- produce all five "hard" challenges naturally;
- have names checked against real businesses before anything is published.

Use a fictional chain of six California climbing gyms, or choose a new company.

### Seats

The system fills the jobs that see every correction and own the work that goes stale:

| Seat | Filled by | Owns |
|---|---|---|
| Senior accountant, close and reporting | AI (main) | Accruals, adjustments, the log of known errors |
| Reporting analyst | AI | Variance commentary, forecasts, the lender report draft |
| Controller | Person | Approves entries, judges what matters, can say no |
| CFO | Person | Signs anything that goes to the lender |

Seats line (draft): "It does the close accountant's and reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign."

### How each challenge is met

| Challenge | What the system must do | How we show it |
|---|---|---|
| Sources disagree | Compare bank, ledger and contract. Pick one, give the reason, and record it | A planted disagreement and the system's written reason |
| Time | Corrections to old periods flow into later work. Approvals and rejections change future routing (Section 5) | A March fix changing a June number. A threshold that moved because of past approvals |
| Working with others | Handle a rejection by revising and resubmitting. Accept half-finished work handed over by a colleague | The controller rejects the first fix and the agent revises it |
| Limits | The preparer can't approve. Agents can't approve their own work or overrule another agent | An attempted self-approval being refused |
| Explainable | Every node shows what it was built from, who made it, and every approval | Click any number to see its sources and history |

---

## 5. When to ask a person: score-based routing

### The score

Every decision the AI wants to make gets a risk score from 0 to 100. Start with a weighted sum and tune it later.

| Factor | Low risk | High risk | Starting weight |
|---|---|---|---|
| Amount | small next to the company's materiality threshold | large or near a limit | 30 |
| Confidence | sources agree and a clear rule applies | sources conflict or the rule is ambiguous | 25 |
| Precedent | seen many times, always approved | first time | 15 |
| Reversibility | a draft or internal note | money sent or a filing submitted | 20 |
| Who's affected | internal only | lender, tax authority, an employee's pay | 10 |

### What the score triggers

| Score | Action |
|---|---|
| 0–30 | AI acts alone and logs the reason |
| 30–60 | AI acts, and a person reviews a sample afterwards |
| 60–85 | AI prepares it and waits for approval |
| 85+ | AI hands it to a person with its findings and doesn't prepare a fix |

### Hard rules (they override the score)

These always go to a person, whatever the score:
- payments or entries above a set amount;
- anything the AI requested itself, because the requester can't approve;
- anything touching a lender agreement, a tax filing or someone's pay;
- reopening a closed period.

### Learning from history

- Record every approval and rejection along with the score at the time.
- If people approve one kind of item every time, lower its score. The AI is asking too often.
- If people keep rejecting a kind of item the AI handled alone, raise its score.
- Show each change as a proposed rule that a person approves. The system doesn't rewrite its own rules silently.

One more case to handle: if a past approval was based on a source that has since been corrected, flag the habit learned from it as suspect too.

### What the approver sees

Every escalation says why it reached them, in one line. For example: "Score 78: $12,400, bank and ledger disagree, first invoice from this vendor."

### Metrics to report

- the share of decisions handled without a person;
- the share of escalations approved unchanged (too high means it asks too much);
- the number of decisions handled alone that turned out wrong (should be close to zero);
- the number of escalations per approver per day.

---

## 6. The moment

The demo opens with this. The requirements:
- It's a correction whose size looks harmless, but downstream it crosses a line that matters (a lender limit, a bonus target, a tax payment).
- A simple rule like "ignore anything under 5%" would have missed it. Our system catches it because it recalculates downstream instead of judging only the size of the correction.
- It shows, in one view, what broke, what was checked and cleared (with reasons), and the fix waiting for a person.
- It's followed by a recovery: the controller rejects the first fix, and the agent revises it.
- It ends with a defence or an admission. Replaying what was known on the day of the original decision shows whether the AI should have caught it.

Example: a billing export double-counted $118k of March revenue. That's only 3.7% of yearly pretax income, but it pushes the lender's debt ratio from 2.95x to 3.03x, past a 3.00x limit.

---

## 7. Proof it works

- **Planted errors with an answer key.** Plant 15–25 known mistakes in the company's data and write down, before running anything, what the correct response to each is. That covers what should break, what shouldn't, and who should be asked.
- **Scoring against the key.** Report what the system got right, missed and flagged wrongly.
- **Baselines.** Compare with simple approaches: redo everything, ignore anything under 5%, or notify everyone downstream. Show where each one fails.
- **Real versus simulated.** One table listing what is real (the AI model, the engine, the approval rules) and what is simulated (the company, its data, its people).
- **A judge's own scenario.** A text box where a judge describes a correction in plain words. The system turns it into a correction and runs it live. This must work, because the brief says judges may try their own.
- **Offline.** The demo runs with the network off, using recorded model responses. Venue Wi-Fi is unreliable.

---

## 8. The UI

Judges decide within a few minutes, so the UI matters more than extra features.

Requirements:
- **Plain words.** No internal terms such as "claim", "wave", "receipt" or "artifact" on screen. Say "source", "built from", "affected" and "needs approval".
- **One main screen** that answers three questions in order: what changed, what it affected, and what needs a person.
- **One thing moving at a time** when a correction spreads.
- **Approvals as an inbox.** Each item gets its one-line reason and approve or reject buttons.
- **Click any number** to see what it was built from and its history.
- **Detail on demand.** Graphs, logs and metrics go behind a click, not on the first screen.
- **A test:** someone who hasn't seen the project explains what it does after 60 seconds of watching. If they can't, simplify.

---

## 9. Scope for 36 hours

### Must have
- The graph: nodes, versions and links, with forward tracing after a correction.
- Number recalculation done by code, not by the model, with a cutoff where nothing changes enough to matter.
- Two or three agents that build on each other and re-check their own work when notified.
- One uploaded document linked by matching after upload, with person confirmation.
- Score-based routing, the hard rules, and an approval inbox. The preparer can never approve.
- The moment, the controller's rejection with the agent's revision, and replay of what was known at a past time.
- A company generator with planted errors and an answer key, plus a scoring script.
- Offline replay mode.
- The plain UI described in Section 8.
- A judge-entered scenario.

### Should have
- Thresholds that learn from approval history, shown as proposed rules.
- Baseline comparisons in the proof.
- One scenario on real public data (for example an SEC restatement).

### Won't do during the hackathon
- Accounts, workspaces or hosting for outside users.
- Real accounting-system integrations (a simulated ledger is enough).
- A browser extension or plugins for outside AI tools.

---

## 10. Decisions to make before hacking starts

1. The company and its industry.
2. The seats (see Section 4's list).
3. The exact moment scenario and its numbers.
4. The planted error list and the answer key (ideation is allowed before the event, code isn't).
5. The starting score weights and hard-rule thresholds.
6. Which model, and how responses are recorded for the offline demo.
7. Who presents, and who records the video.

---

## 11. After the hackathon (if it becomes a platform)

Not in scope for the event. Kept here so the design doesn't block it.

- **Simplest route:** an open-source SDK people run themselves. They install it, wrap their agent's tool calls, and run the hub locally. No accounts needed.
- **Hosted product:** this needs API keys and separate workspaces, a real database (Postgres), a way to upload sources and their versions, pings delivered to agents by webhook, and a plain graph-plus-inbox UI.
- **Wider than finance:** the engine doesn't depend on finance. The accounting rules are a plug-in. Any team whose documents build on each other (legal, research, compliance) is a later market.

---

## 12. Design priorities

Keep:
- A core that knows nothing about the domain, with finance rules as a plug-in.
- Numbers recalculated by code, with the model used only for judging prose.
- Pinned replay of what was known at any time, refusing anything published later.
- Answer-key evaluation and an offline replay mode.
- A one-container deploy.

Change:
- The UI. It was too dense and full of internal terms (Section 8).
- Links for documents people upload. See Section 3.
- Escalation. It needs an explicit score and a one-line reason (Section 5) instead of rule branches the judges can't see.
- The pitch. Lead with the problem in plain words, not the mechanism.
