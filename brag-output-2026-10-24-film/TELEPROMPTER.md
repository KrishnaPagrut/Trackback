# Teleprompter: the demo film

Total 2:41. The time on each heading is when that scene starts on screen. Say it like you're explaining it to a friend across the table; the subtitles on screen are a shorter version of the same thing, so don't try to match them word for word. If you finish a scene early, just pause until the next one comes up.

## 0:00 · Title

This is Trackback. Back in 2002, TrackBack was a little protocol for blogs: if someone wrote a post that built on yours, your page got a ping. We're bringing that idea back, but for the numbers inside a company.

## 0:08 · Meet Tidewall

So, meet Tidewall. They run six climbing gyms, do about forty million a year, and they've made one promise to their bank: keep leverage under three times EBITDA. Their finance team is small: two AI agents, an analyst named Maya, and Dana, the controller.

## 0:21 · The source

On April ninth, the billing system publishes its March export. Every member, every dollar released into revenue. That's the document everything else is about to be built on.

## 0:25 · Layer one

The next day, the Close Accountant closes the quarter on top of that export: revenue by gym, EBITDA, trailing EBITDA of five point six million. And every single piece of that work records exactly which rows of the export it read.

## 0:36 · Layers two and three

Then the Covenant agent builds on *those* numbers: leverage comes out at two point nine five, the certificate goes off to the bank, bonuses get paid, the tax estimate goes out. And Maya builds the board deck on top of all of it, using the same tools, so her reads are logged just like the agents'. That whole thing, every number pointing at what it was built from, is the context graph.

## 0:49 · July 8: Trackback is switched on

Now it's July eighth, and Tidewall switches on Trackback. The first thing it does is compare today's billing export with the version everyone actually read back in April. And it finds a hundred and eighteen thousand dollars that got counted twice. Which raises the real question: what else is wrong because of that?

## 1:00 · The reconciliation

Here's what runs. Trackback diffs the two versions of the export, then follows the read receipts to every piece of work that used those rows, and only those. It recomputes each number from its own formula, and checks every change against Dana's materiality memo. For sentences, if the claim still holds it just refreshes the figure; if the claim might not hold anymore, it sends the sentence back to whoever wrote it. In the end, forty-four pieces of work got a look. Everything else was cleared, and each one has a reason attached.

## 1:21 · One message per agent

Every agent that's affected gets exactly one message, and it only mentions what that agent actually used. Maya gets the same message as a notice. The one to the covenant agent reads: "Your certificate rests on net leverage, which is now three point oh three, over your covenant. Still valid?" It can't un-send a certificate, obviously, so it drafts a corrected one and a note to the bank, for the CFO to sign.

## 1:36 · Jade, the reviewer

This is the part we're proudest of. The agent's own write-up called this error immaterial, because it falls under the five percent rule of thumb. Jade, our reviewer, re-ran every one of its calls against the engines: it's over the performance threshold, the covenant is breached, and bonuses have already been paid. So Jade overruled it. And Jade never writes a number herself. She only checks them.

## 1:50 · The right person says no

Every fix gets routed to the person who's actually allowed to sign it: the certificate to the CFO, the bonuses to HR, the journal entries to the controller. And Dana turns the first entry down, because it was dated into a quarter that's already locked. So the agent re-drafts it in June, tagged back to March. And if the agent ever tries to approve its own work, the database just refuses the row. That rule lives in the schema, not in a prompt.

## 2:06 · It learns

Both of those mistakes, Jade's overrule and Dana's no, become proposed lessons. But a lesson doesn't go live just because someone suggested it. First it gets re-run against every case we've ever seen. One broad version fails that test, because three old cases would have flipped. The rest pass, Dana approves them, and the playbook moves to version two. On cases it had never seen before, it went from eighty percent right to a hundred.

## 2:21 · Time travel

And if anyone asks, "what did the agent actually know back on April tenth?", here it is: the export as it looked that day, duplicate rows and all. Try to pull the July version from that date and it refuses, and shows you both timestamps.

## 2:33 · Go look

All of this is live. The link opens in Deep mode on this same company, with a tour that walks you through it. Go drop the correction yourself. Trackback traces any correction forward.
