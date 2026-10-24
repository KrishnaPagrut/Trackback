# /brag plan: Trackback, hackathon cut

Mode: brag-slim (Opus 5.5). Format: landscape 1920×1080, 30 fps, 23 s. Tone: user direction "show it as a hackathon project". Closest preset is `default` (punchy, clean), dressed as a hackathon submission: a submission-ticket opener and a judges'-table closer.

## Answers

- **What is it?** TrackBack for AI agents: when a number your work was built on changes, Trackback works out exactly what broke and pings only the agents who used it.
- **Who is it for?** Finance teams running AI agents on the close (record-to-report); more broadly anyone chaining agents that act on each other's outputs.
- **What sets it apart?** It recomputes numbers in code, clears what didn't move (with a reason), sends one ping per affected agent, and drafts compensations for actions that already happened. It also refuses to let an agent "read the future" on replay.
- **Most impressive claim (from the run, not invented):** a $118,000 double count moves leverage 2.95x → 3.03x across a 3.00x covenant; 10 of 174 pieces of work needed an agent, 3 of 3 agents acted, 4 actions wait for a human, 0 left stale. Answer key: ping precision 1.000, recall 1.000.
- **Visual hook:** a red "recall notice" slamming onto a calm paper ledger.
- **Real UI to show:** Stage mode (real screenshots from the running app in replay mode): lanes, recall notice, recompute line, ping bubble, agent reply, payoff, the April 10 refusal stamp.
- **Tone:** confident hackathon demo: quick, clear, a little proud.
- **Share caption:** see share-copy.txt.

## Identity

Paper #F7F4EE, ink #1C1B19, recall red #C62828, ping blue #1F5FBF, cleared green #2E7D32. Newsreader (serif headlines), IBM Plex Sans (body), IBM Plex Mono (numbers, chips). All from the project's own bundled fonts.

## Data hygiene

Tidewall is fictional; no real people, keys or hostnames appear. Screens come from the replay-mode demo.

## Storyboard (beat grid: 120 BPM, 0.5 s)

| # | Time | Scene | On screen | Motion | SFX |
|---|---|---|---|---|---|
| 1 | 0.0–3.0 | Hook | Hackathon slate stamps in ("DEMO"). Big serif: "Three AI agents built on one number." | Slate stamps down, line types in word by word, holds 1.6 s | soft stamp thud on 0.0 |
| 2 | 3.0–6.0 | The problem | Real Stage screen with the red RECALL NOTICE dropping in; caption "July 8: the source admits it was wrong. $118,000, counted twice." | Screen pushes in toward the notice; notice drops with overshoot | low thud on drop (3.5) |
| 3 | 6.0–9.0 | Reveal | Wordmark "Trackback", subline "TrackBack for agents. When work you built on changes, you get pinged." | Wordmark slides up, red underline draws | riser into 6.0 |
| 4 | 9.0–12.5 | Highlight 1 | Real screen, zoom onto "Leverage recomputed: 2.95x → 3.03x, crosses 3.00x". Caption "It recomputes every number itself." | Slow zoom; highlight sweep across "crosses 3.00x" | tick at 9.5 |
| 5 | 12.5–16.0 | Highlight 2 | Real ping bubble "Trackback → Covenant and Comp … Still valid?" Caption "One ping per agent. Only about what it used." | Push into bubble, envelope chip pops | in-key ping at 12.75 |
| 6 | 16.0–19.0 | Highlight 3 | Real payoff "10 of 174" with the three counts | Number scales in, counts stagger | soft chord hit |
| 7 | 19.0–23.0 | Outro / submission | Submission card: Trackback, tagline "Trackback traces any correction forward.", chips: precision 1.000 · recall 1.000 / runs offline | Card rises, chips stagger, stamp "SUBMITTED" | stamp thud at 20.5, music resolves |

Durations: 3 + 3 + 3 + 3.5 + 3.5 + 3 + 4 = 23 s.

## Music cue guidance

Original synthesized track, 120 BPM, A minor → C major lift at the reveal (6.0 s). Kick on every beat from 3.0 s, hats from 6.0 s, cuts on bar lines (every 2 s) or half bars. Effects tuned to A/E so they sit in key.
