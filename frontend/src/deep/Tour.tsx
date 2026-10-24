import { useEffect, useState } from 'react'
import { X as Close } from 'lucide-react'
import { StatusIcon } from '../ui/primitives'
import type { State } from '../model'

/* A guided tour of Deep mode for a visitor on the live link: nine short steps, each pointing at one thing to click or press.
   A step with a `done` test advances itself when the visitor does the thing; every step has a button that does it for them. */
export type TourCtx = { selected: string | null; correction: string | null; drawer: string | null; travelOpen: boolean
  openNotice: () => void; openDrawer: (t: any) => void; openTravel: () => void; toStage: () => void; toScorecard: () => void }
type Step = { id: string; title: string; body: string; target?: string; action?: { label: string; run: (c: TourCtx) => void }; done?: (c: TourCtx) => boolean }

const STEPS: Step[] = [
  { id: 'welcome', title: 'Tidewall, a climbing-gym company, closed its quarter', body: 'Three AI agents did the work. Each row is one agent; each card is a piece of work it made: a number, a sentence in the board deck, a certificate that already went to the lender. A line means "rests on".' },
  { id: 'click', title: 'Click any card', body: 'You get who built it, on top of whom, and the receipts of what it read. Hover a card for its one-line story.', done: c => !!c.selected },
  { id: 'drop', title: 'A correction just arrived', body: 'The billing system admits it counted $118,000 of March revenue twice. Send the trackback and watch where it lands.', target: 'recall', action: { label: 'Open the notice', run: c => c.openNotice() }, done: c => !!c.correction },
  { id: 'ripple', title: 'Read the ripple', body: 'Red: wrong now, recomputed by Trackback. Green: still valid, with the reason. Amber: already went out, a fix waits for a person. Blue: reworked by its owner. The cash forecast was skipped: nothing material moved there.' },
  { id: 'jade', title: 'Jade, the reviewer', body: 'The agent wrote "immaterial" ($118,000 is under the $160,000 rule of thumb). Jade re-ran the call from the engines: the covenant flips to 3.03x. Overruled.', target: 'jade', action: { label: 'Open Jade (J)', run: c => c.openDrawer('review') }, done: c => c.drawer === 'review' },
  { id: 'lessons', title: 'It learns from that', body: 'The overrule is now a proposed lesson. Run the gate (every past case re-checked), approve as Dana, and the playbook becomes v2. The broad misreading fails the gate.', action: { label: 'Open Lessons (E)', run: c => c.openDrawer('lessons') }, done: c => c.drawer === 'lessons' },
  { id: 'approvals', title: 'A human said no', body: 'The first correcting entry was dated into locked Q1. The Controller rejected it; the agent re-drafted in June with an out-of-period tag. Try "self-approve": the database refuses.', action: { label: 'Open Approvals (A)', run: c => c.openDrawer('approvals') }, done: c => c.drawer === 'approvals' },
  { id: 'travel', title: 'Time travel', body: 'What could the agents see on April 10? The duplicate rows were already in the export. Then try to peek at the July 8 version: refused, with both timestamps.', target: 'travel', action: { label: 'Open Time travel (T)', run: c => c.openTravel() }, done: c => c.travelOpen },
  { id: 'end', title: 'That is Trackback', body: 'Scorecard: every number scored against a frozen answer key. Stage mode plays the 90-second story (D). R resets the world. ⌘K finds anything.', target: 'stage', action: { label: 'Open the Scorecard', run: c => c.toScorecard() } },
]
const LEGEND: [State, string][] = [['invalidated', 'wrong now'], ['cleared', 'still valid'], ['caution', 'needs a person'], ['reworked', 'reworked'], ['skipped', 'skipped']]

export function Tour({ ctx, onClose }: { ctx: TourCtx; onClose: () => void }) {
  const [i, setI] = useState(0)
  const step = STEPS[i]
  // the visitor did the thing: move on after a beat
  useEffect(() => {
    if (!step.done || !step.done(ctx)) return
    const t = window.setTimeout(() => setI(x => Math.min(STEPS.length - 1, x + 1)), 900)
    return () => window.clearTimeout(t)
  }, [ctx, step])  // eslint-disable-line react-hooks/exhaustive-deps
  // highlight the target
  useEffect(() => {
    document.querySelectorAll('.tour-hi').forEach(el => el.classList.remove('tour-hi'))
    if (step.target) document.querySelector(`[data-tour="${step.target}"]`)?.classList.add('tour-hi')
    return () => document.querySelectorAll('.tour-hi').forEach(el => el.classList.remove('tour-hi'))
  }, [step, ctx.correction, ctx.drawer])
  return <div className="tour" role="dialog" aria-label="Guided tour">
    <div className="hd"><span className="mono t14 muted">Tour · {i + 1} of {STEPS.length}</span><button className="btn ghost" style={{ height: 26, padding: '0 6px' }} onClick={onClose} aria-label="Close the tour"><Close size={16} strokeWidth={1.5} /></button></div>
    <div className="serif" style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.15, margin: '2px 0 6px' }}>{step.title}</div>
    <div className="t14" style={{ lineHeight: 1.4 }}>{step.body}</div>
    {step.id === 'welcome' && <div className="t14" style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>{LEGEND.map(([s, w]) => <span key={s} style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}><StatusIcon state={s} size={15} />{w}</span>)}</div>}
    <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
      {step.action && <button className="btn primary" onClick={() => step.action!.run(ctx)}>{step.action.label}</button>}
      <button className="btn" disabled={i === 0} onClick={() => setI(x => x - 1)}>Back</button>
      {i < STEPS.length - 1 ? <button className="btn" onClick={() => setI(x => x + 1)}>Next</button> : <button className="btn" onClick={onClose}>Done</button>}
      <span className="stepdots" style={{ marginLeft: 'auto' }}>{STEPS.map((s, k) => <i key={s.id} className={k === i ? 'on' : k < i ? 'done' : ''} />)}</span>
    </div>
  </div>
}
