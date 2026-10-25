# Trackback: the three-minute film

One story, told from inside Tidewall's finance team, that shows every part of the system once: the context graph, the reconciliation (diff → reach → recompute → materiality → prose → pings → compensations), Jade and the ripple she checks, routing to the right person and the person saying no, and the learning loop that comes out of that no. Voice-over is about 430 words; read it brisk, not fast. Every number spoken is on screen at that moment.

Record the app at 1920x1080 from `http://localhost:8000` (Stage mode) or the live link with `?mode=stage&tour=0`. Press `R` before the take. Hide the mouse cursor except for the three clicks called out below. Captions on throughout: judges watch muted.

## Cold open: the skit (0:00–0:22), black and white, film grain

Two of you. A sits at a laptop showing something that looks like a 2002 blog (any plain page with blue links). B walks in. Lower third: **2002**.

> **A** (typing, not looking up): Two thousand two. Movable Type ships TrackBack. You write a post, I build on it, your page gets pinged. You always know who built on you.
> **B** (squinting at the camera): Why are we in black and white?
> **A**: It's 2002.
> **B**: 2002 is the twenty-first century.
> **A** (beat): …Fair.

**Color snaps in on "Fair."** Music starts.

> **B**: So why don't our agents have this?

Hard cut to the title card in the app (Stage mode, step one): *"May 15: Tidewall's CFO told its lender leverage was 2.95x."*

## The film (0:22–3:00)

| Time | On screen (keys) | Voice-over |
|---|---|---|
| 0:22–0:40 | Stage title card. `Space`: the layered reveal, Sources → Close Accountant → Covenant and Comp → Reporting Analyst, lines drawing between them. | Tidewall runs climbing gyms. Three AI agents close its books. On May 15 the CFO signed a certificate for the bank: leverage 2.95 times, under a 3.00 limit. The Close Accountant's revenue fed the covenant agent's certificate; the Reporting Analyst's board deck rests on both. Every line here is a receipt: what each agent read, which version, hash-stamped the moment it read it. That is the context graph. Recorded, not declared. |
| 0:40–0:52 | `Space`: the TRACKBACK NOTICE card. `Space`: drop it. The calc line appears: *Leverage recomputed: 2.95x → 3.03x, crosses 3.00x*. | July 8. The billing system admits it counted $118,000 of March revenue twice. One notice. Watch where it lands. |
| 0:52–1:22 | `D`: Deep mode. The ripple runs lane by lane; the strip reads *looked at 44 of 174 pieces of work · LLM calls 0*. **Click** the *Lender certificate, sent* card: its path lights up in blue, everything else fades; the left panel lists *Built on*. `Esc`, then `D` back to Stage. | Now the reconciliation. Diff the claims. Walk only what consumed them. Recompute every number in code: no model does arithmetic here. Check materiality against the controller's own memo: a forty-cent bank fee stops dead; a conclusion flip never does. Sentences get their figures re-rendered in place; only a sentence whose *claim* might flip goes back to its owner. Forty-four of 174 pieces of work looked at; the rest cleared, each with a reason. Click the certificate: it rests on leverage, on EBITDA, on the March release, on the export that lied. |
| 1:22–1:44 | `Space` to the Covenant and Comp ping. The bubble: *"Your lender certificate rests on net leverage, which changed from 2.95x to 3.03x. It now crosses your 3.00x covenant. Still valid?"* `Space` through to its reply: *Needs a human: a corrected certificate and lender notice are drafted for the CFO.* Point at the cash-forecast card: *Skipped · no material change*. (Cut the other two pings in the edit, or let them flash.) | One ping per agent, once, about only what it used. "Your certificate rests on net leverage, 2.95 to 3.03. It crosses your covenant. Still valid?" The agent answers in its own words: it cannot un-send a certificate, so a corrected one and a lender notice wait for the CFO. The thirteen-week cash forecast? Skipped. Nothing material moved there, so nobody was asked. |
| 1:44–2:12 | `Space`: Jade's card, stamped OVERRULED. Agent: *Immaterial: $118,000 is under the $160,000 annual threshold.* Jade: *Material: over the $60,000 performance threshold; leverage 2.95x → 3.03x crosses the covenant; bonuses already paid change.* Then `D`, `A`: the Approvals drawer, the first journal entry **rejected** by Dana Ortiz: *"Q1 is locked…"*, the re-draft below it posting to 2026-06 tagged 2026-03. **Click** *Try self-approve*: the red message from the database. `Esc`, `D`. | The agent's own write-up called this immaterial: under the five-percent rule of thumb. Jade, the reviewer, re-ran the call from the engines: over performance materiality, the covenant flips, bonuses already paid change. Overruled. And the agent's first correcting entry was dated into locked Q1. Dana, the controller, says no. The agent re-drafts in June with an out-of-period tag. Try to make it approve itself: the database refuses. That is a constraint in the schema, not a line in a prompt. |
| 2:12–2:34 | `Space`: the lesson card. *"Post corrections in the first open period…"*, proposed from six cases, **Regression gate: 71 of 72 past claims pass · 0 newly failing**, **Approved: Dana Ortiz · playbook v2**, and in red: *Rejected by the gate: "If the period is locked, treat the item as a change in estimate" — E10, E02, E09 would flip.* | Jade's overrule and Dana's no both become proposed lessons. Before a lesson turns on, every past case is re-run with it. The broad reading, "a locked period means an estimate", fails the gate: three old cases would flip. Dana approves the rest. Playbook v2, from now on, never backwards. On cases it never learned from: eighty percent to one hundred. |
| 2:34–2:47 | `T`: the April 10 frame. The duplicate rows in red; the stamp *REFUSED · published July 8 · decision time April 10*. `T` to close. | Was the agent negligent? Here is what it saw on April 10: the duplicate rows were right there. That makes it an error, not new information. And it cannot peek at July 8 to look smart. Refused, with both timestamps. |
| 2:47–3:00 | `Space`: the payoff. *10 of 174 · 3 of 3 agents needed to act · 4 actions waiting for a human · 0 things left stale · Jade overruled 2 of 4 calls · 2 lessons learned · playbook v2.* End card: the live URL and the seat line. | Ten pieces of work out of 174 needed an agent. Four actions wait for a person. Nothing left stale. Trackback does the senior close accountant's job every time a source changes: it finds what broke, proves what didn't, drafts the fix for the controller to sign, and learns from her no. Trackback traces any correction forward. |

## Why this order holds attention

- A question in the first ten seconds ("why don't our agents have this?") and a number with stakes in the next ten (2.95 against 3.00).
- One villain, introduced once ($118,000, twice). Everything after is consequence.
- The camera never explains a concept without a thing on screen changing: lines drawing, the ripple, a path lighting up, a stamp landing, a red rejection, a gate count.
- Two surprises placed where attention sags: Jade overruling the agent at 1:44, and the gate rejecting a plausible lesson at 2:12.
- The last 25 seconds answer the two questions a finance judge is already asking: was the agent negligent, and what did it cost the humans.

## Production notes

- Skit: shoot on a phone, 16:9, two takes. Black-and-white plus grain in the edit; the color snap is a hard cut on "Fair", not a fade. Keep it under 22 seconds; if it runs long, cut A's first line to "2002. TrackBack. You build on my page, my page gets pinged."
- App capture: 1920x1080, 60 fps. The layered reveal takes about nine seconds on its own; let it play. Everything else is one keypress per beat. Press `R` once before the take and do not touch the mouse except for the two clicks (certificate card; *Try self-approve*).
- Keys in order: `Space` (reveal) · `Space` (notice) · `Space` (drop) · `D` · click certificate · `Esc` · `D` · `Space`×2 (pings to Covenant and Comp) · `Space`×3 (replies) · `Space` (Jade) · `D` · `A` · click *Try self-approve* · `Esc` · `D` · `Space` (lesson) · `T` · `T` · `Space` (payoff). Do the lesson beat in Stage, before opening Lessons in Deep: Stage approves the pending lessons when it reaches that beat, and if Deep already did it the card will say there is nothing new to learn.
- Voice-over recorded separately, then the capture is cut to it. Captions from the voice-over text above.
- Music: low, instrumental, starts on the color snap, drops under the Jade card, out on the end card.
- End card: `trackback-gamma.vercel.app` · *Trackback does the senior close accountant's and the reporting analyst's job every time a source changes: it finds what broke, proves what didn't, and drafts the fix for the controller to sign.*

## If the slot is 90 seconds (table judging)

Skit cut. Start at the notice (0:40), keep the Deep ripple and the certificate click, one ping bubble, Jade's card, the lesson card, the payoff. Hand over the keyboard: "Change any number, or paste your own correction." The live link opens in Deep mode with the tour for anyone who scans the QR code.
