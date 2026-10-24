# Design review

Reviewed against the DESIGN.md quality checklist. Screenshots: `docs/screenshots/round-N/`, nine states at 1280x720 and 1920x1080, plus 25%-width copies of the four Stage shots for the legibility test.

## Round 1 (first build of the ledger look)

### Stage mode

| Shot | What works | What fails the checklist | Fix for round 2 |
|---|---|---|---|
| 1 Title card | Newsreader headline with the real number (2.95x from the certificate), subtitle, nothing else on screen. | Nothing. | Keep. |
| 2 Layered reveal, half built | Layer labels in small caps, sources then the Close Accountant, thin lines show who built on whom. | The live line under the agent name ("Done for the quarter") is mono and wraps to two lines in a narrow rail. The memo card truncates at 46 characters mid-word ("def…"). | Live line in Plex Sans; prose cards allow about 70 characters before truncating. |
| 3 Mid-ripple, ping bubble | The calc line under the source states the crossing in one line; one lane in focus, the rest dimmed; the bubble is a human sentence. | (a) The envelope and its postmark land on the identity card and cover the seat text. (b) The bubble header wraps ("Trackback → Close / Accountant") because the postmark shares its line. (c) "Your march deferred-revenue memo" lost its capital. (d) For Covenant and Comp the bubble cites covenant headroom ($100,000 → $-54,500) instead of the leverage figure that crossed 3.00x, and negative money prints as `$-54,500`. (e) The "+N cleared" chip sits under the bubble. (f) Lanes are in the Deep order (Sources, Close Accountant, Reporting Analyst, Covenant and Comp), so the line from TTM EBITDA to leverage crosses the Reporting Analyst lane. (g) At 1280 the bubble text is 20 px, about 5 px at 25% width: not readable. | (a) The envelope lands just left of the bubble. (b) Postmark on its own line. (c) Lower-case only a leading common noun; months, quarters and acronyms keep their capitals. (d) Prefer the field that crossed a threshold; negative money as `-$54,500`. (e) Cleared count moves into the lane's live line. (f) Stage lanes in flow order: Sources, Close Accountant, Covenant and Comp, Reporting Analyst. (g) Bubble text 24 px minimum, 1.9vw, and agent names 24 px minimum. |
| 4 Payoff | One giant number from the real run (10 of 174), one line (3 of 3 agents · 4 actions waiting · 0 stale), the tagline. | Faint cards remain visible behind the number, which competes with it. | Dim the stage to 97% paper behind the payoff. |

### Deep mode

| Shot | What works | What fails the checklist | Fix for round 2 |
|---|---|---|---|
| 5 Idle Tidewall graph | Dotted paper canvas, lane rails aligned, ledger cards with lot chips, Graph \| Ledger toggle, footer hints, empty state ("Nothing's been recalled. Yet."). | 25 cards at about 0.6 zoom render labels under 13 px at 1280. Edges cross back and forth. The "A recall notice arrived" button sits on the Sources rail. Sources lane shows contract titles nobody needs at rest. | Compact cards (one-line title, value and reason on one row, fixed height), at most 3 cards per agent lane and 16 in the hero view, columns by dependency depth so edges run left to right, the button moves to the counter strip. |
| 6 Ripple done, Who built this | The drawer shows the receipt chain back to the source with lot codes and versions; Built on / Built upon toggle in the sidebar; the results list summary line reads like Rodeo's. | Cards with prose overflow their lane and overlap the next one. Edges loop backwards because columns were assigned per lane, not by depth. "Compensations pending 13" counts every open item in the inbox, not this correction's. | Fixed card height with a two-line clamp for prose; depth columns; count only this correction's compensations. |
| 7 Approvals during E22 | Memo stack, red rule on locked or rejected memos, prefilled reasons, black approve button. | The first memo is an unrelated June accrual; the E22 rejection and re-draft are further down. | Sort the inbox: this correction's memos first, rejected ones on top. |
| 8 Memento at April 10 | Hatched "not knowable" region, cursor in ink, the refusal stamp rotated -6 degrees in mono. | The stamp is wider than the strip and spills over the footer hints. | Seat the stamp above the strip, inside the canvas. |
| 9 Proof | Every tile from latest.json, mono numerals, Newsreader title. | Nothing blocking. | Keep. |

## Round 2 (round 1 fixes applied)

| Shot | Checked against the list | Still wrong | Fix for round 3 |
|---|---|---|---|
| 1 Title | Holds. | — | — |
| 2 Reveal | Live line in Plex Sans, longer prose cards. | At 1280 the second layer label overlaps the first card. | Nudge the cards 10 px down during the reveal. |
| 3 Mid-ripple | Bubble asks about leverage and the 3.00x covenant (the crossed field), capitals kept, lanes in flow order, no stray chip, envelope beside the bubble. | At 25% width the bubble is still small at 1280; the agent name wraps onto two lines in a 20vw rail. | Bubble 28 px minimum (2.45vw), start it after the second card column so it is wider; rail 22.6vw. |
| 4 Payoff | Stage dimmed to 97% behind the number. | — | — |
| 5 Idle | Compact cards (one line, lot chip, value), depth columns, 13 cards, button in the counter strip. | The lane rail's live line and "+N more" link wrap; one empty lane (Humans) takes a full lane's height. | Empty lanes collapse to a 44 px strip; rail text truncates with an ellipsis. |
| 6 Ripple + Who built this | Edges run left to right, the drawer chain reads back to the source. | Prose and number cards share a row height now, good. The Who built this drawer covers the right third of the canvas at 1280 (accepted: it overlays, no layout shift). | — |
| 7 Approvals E22 | This correction's memos first, the rejected March draft on top with the Controller's reason in red. | — | — |
| 8 Memento | Hatched region labelled "Not knowable on April 10, 2026". | The stamp sits on the footer hints. | Seat the stamp inside the strip, scaled to 0.86. |
| 9 Proof | Holds. | — | — |

Checks that are not screenshots: `backend/scripts/kiosk_check.py` (attract loop after 60 s idle, any key hands over, three presets, the 40-cent fee shows 0 of 3 agents, D keeps state, Space alone runs title to payoff with numbers matching `/pings`).

## Round 3

| Shot | Still wrong | Fix for round 4 |
|---|---|---|
| 3 Mid-ripple | Bubble readable at 25% width now (the 1920 thumbnail shows "Your lender certificate rests on net leverage…" legibly). | — |
| 5 Idle, 6 Ripple, 8 Memento at 1920 | The canvas sometimes renders empty: React Flow had not measured the new cards, so it kept them `visibility: hidden`. Diagnosed with `elementsFromPoint` and the computed style chain; the click flake on cards had the same cause. | Give every canvas node an explicit width and height, fit the view from the layout's own geometry instead of measured nodes, play the ripple once per drop rather than on every data refresh. |
| All Deep shots | `type_floor_check.py` measured 9.9 px (the lane monogram after zoom) and 12.5 to 12.9 px in the lane rail at 1280. | Monogram 16 px minimum, canvas text 16 px so it stays at 13 px or more after the 0.86 zoom. |

## Round 4 (final)

Last fixes before the final shots: every Deep lane is the same height again (empty lanes had been collapsed to 44 px, which broke "lane heights equal"), and the refusal stamp sits in the empty band above the strip so the "Not knowable on April 10, 2026" label stays readable. `backend/scripts/quality_check.py` passes at both sizes: no horizontal scroll, no raw undefined/NaN/null, at most 7 Stage cards and 14 Deep cards, equal lanes with aligned rails, the drawer opens without moving the canvas, text tokens at 4.90:1 or better, and the Stage sequence runs to the payoff with reduced motion on.

All nine states at both sizes render with content and zero console errors. `type_floor_check.py`: smallest rendered text 13.0 px in every state at both sizes. A card click opens its drawer 14 of 14 times across both sizes (it failed about 1 in 8 before the explicit-dimensions fix).

| Shot | Description |
|---|---|
| 1-stage-title | Newsreader headline "May 15: Tidewall's CFO told its lender leverage was 2.95x." with "Three AI agents built on that number." and the keyboard caption. |
| 2-stage-reveal-half | Layer 0 sources and Layer 1 Close Accountant built, small-caps layer labels, the thin line from the billing export to the deferred-revenue memo and TTM EBITDA. |
| 3-stage-mid-ripple | The calc line "Leverage recomputed: 2.95x → 3.03x, crosses 3.00x"; Covenant and Comp in focus with "Re-checking 4 items"; the bubble "Your lender certificate rests on net leverage, which changed from 2.95x to 3.03x. It now crosses your 3.00x covenant. Still valid?"; the cash forecast card skipped. |
| 4-stage-payoff | "10 of 174 pieces of work needed an agent to look", "3 of 3 agents needed to act · 4 actions waiting for a human · 0 things left stale", and the tagline. |
| 5-deep-idle | Six swimlanes on the dotted paper canvas, 13 ledger cards with lot chips, the empty state "Nothing's been recalled. Yet.", Graph \| Ledger toggle, footer counts and key hints. |
| 6-deep-ripple-who-built | "3 of 3 agents pinged" with inspected, LLM-call and compensation counts; hatched red, blue reworked and dashed amber cards; the sidebar's sorted results; the Who built this receipts from the certificate back to the credit agreement. |
| 7-deep-approvals-e22 | The memo stack: the rejected March-dated correcting entry with its locked period and the Controller's reason, then the waiting bonus offset. |
| 8-deep-memento-april-10 | The scrubber at April 10 with the hatched "Not knowable" region and the stamp "REFUSED · published July 8 · decision time April 10". |
| 9-proof | Six tiles from latest.json: ping precision and recall, false still_valid, over-invalidation vs B1, LLM calls vs rerun-all, Memento leaks, replay fidelity. |

## DESIGN.md quality checklist, final build

- [x] Nothing looks like a default component library: every control is styled from the tokens (no shadcn or MUI).
- [x] Every number uses tabular mono numerals, right-aligned in tables (ledger tables, the inbox, claim history).
- [x] Every state has icon plus pattern plus color: red X and diagonal hatch; green check; amber "!" and dashed border; blue circular arrow; superseded faded with the value struck through; skipped dotted with a minus.
- [x] Clean at 1280x720 and 1920x1080, no horizontal scroll, no overlapping labels (`quality_check.py`; the round 4 shots).
- [x] At most 25 visible nodes in the hero view: 13 at rest and 14 after E11 in Deep mode, 7 in Stage mode; the rest collapse into "+N more checked".
- [x] Text contrast at least WCAG AA (lowest token pair 4.90:1); nothing under 13 px (`type_floor_check.py`: 13.0 px minimum).
- [x] Consistent 8 px spacing; lane heights equal; left rails aligned (`quality_check.py`).
- [x] Empty, loading and error states designed: "Nothing's been recalled. Yet.", "Loading the ledger…", "No eval output yet: run make eval"; no raw undefined, NaN or null on any screen.
- [x] No layout shift when the drawer opens (it overlays; canvas rectangle and viewport unchanged) or while the ripple runs (the view is fitted from the layout once per correction).
- [x] The three hero moments are deliberate: the recall notice card with its red band, lot code and mono timestamp, dropping onto the source; the envelope with its postmark gliding to the lane while the status line reads "Re-checking"; the -6 degree mono refusal stamp.
- [x] Reduced motion works: the whole Stage sequence runs with animations off.
- [x] Stage mode: one thing moves at a time; at most about 10 nodes (7); bubbles and agent names readable at 25% width (round 4 thumbnails); the whole sequence runs from keypresses with no mouse (`kiosk_check.py`).
- [x] Stage mode payoff numbers come from the run (10 items and 3 agents on the page, 10 items to 3 agents in `/pings`).
- [x] `D` switches between Stage and Deep mode without losing state.
- [x] Deep mode has the dotted grid canvas, the Graph | Ledger toggle, Built on / Built upon, the ⌘K palette and the footer status bar with keyboard hints.
- [x] The layered reveal builds the graph lane by lane with small-caps layer labels.
- [x] Kiosk: the attract loop starts after 60 s idle, stops on any input, and the three presets work, the 40-cent fee showing zero pings.
