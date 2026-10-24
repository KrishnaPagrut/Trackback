/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, money, when, who, reason, type Any, type World } from './api'
import { TidewallStage, LyftStage, TIDEWALL_BEATS, LYFT_BEATS, CAPTIONS, Icon } from './Stage'
import { Deep, type Tab } from './Deep'
import './v3.css'

export default function App() {
  const qs = new URLSearchParams(window.location.search)
  const [world, setWorld] = useState<World>(qs.get('world') === 'lyft' ? 'lyft' : 'tidewall')
  const [mode, setMode] = useState<'stage' | 'deep'>(qs.get('mode') === 'deep' ? 'deep' : 'stage')
  const [step, setStep] = useState(0)
  const [tab, setTab] = useState<Tab>('Reconcile')
  const [data, setData] = useState<Record<World, Any>>({ tidewall: null, lyft: null })
  const [st, setSt] = useState<Any>(null)
  const [tick, setTick] = useState(0)
  const [door, setDoor] = useState<null | 'change' | 'why'>(null)
  const [kiosk, setKiosk] = useState(false)
  const kioskAllowed = qs.get('kiosk') !== 'off'
  const idleMs = Number(qs.get('idle') || 60) * 1000
  const last = useRef(Date.now())
  const beats = world === 'tidewall' ? TIDEWALL_BEATS : LYFT_BEATS

  const bump = useCallback(() => setTick(t => t + 1), [])
  useEffect(() => { api.state(world).then(setSt) }, [world, tick])
  useEffect(() => { api.stage(world).then(d => setData(x => ({ ...x, [world]: d }))) }, [world, tick])
  const reset = useCallback(async () => { await api.reset(); setStep(0); setDoor(null); setData({ tidewall: null, lyft: null }); bump() }, [bump])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      last.current = Date.now()
      if (kiosk) { setKiosk(false); return }
      const t = e.target as HTMLElement
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')) { if (e.key === 'Escape') setDoor(null); return }
      if (e.key === 'Escape') { setDoor(null); return }
      if (e.key === 'd' || e.key === 'D') { setMode(m => (m === 'stage' ? 'deep' : 'stage')); return }
      if (e.key === 'w' || e.key === 'W') { setWorld(w => (w === 'tidewall' ? 'lyft' : 'tidewall')); setStep(0); return }
      if (e.key === 'r' || e.key === 'R') { reset(); return }
      if (e.key === 'c' || e.key === 'C') { setDoor('change'); return }
      if (e.key === 't' || e.key === 'T') { if (mode === 'stage') setStep(beats.indexOf('Replay') >= 0 ? beats.indexOf('Replay') : step); else setTab('Time travel'); return }
      if (mode !== 'stage') return
      if (e.key === ' ' || e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); setStep(s => Math.min(beats.length - 1, s + 1)) }
      if (e.key === 'Backspace' || e.key === 'ArrowLeft') { e.preventDefault(); setStep(s => Math.max(0, s - 1)) }
    }
    const onMove = () => { last.current = Date.now(); if (kiosk) setKiosk(false) }
    window.addEventListener('keydown', onKey); window.addEventListener('pointerdown', onMove)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('pointerdown', onMove) }
  }, [mode, beats, step, kiosk, reset])

  // the attract loop: after a minute idle, Stage plays itself with captions; any input hands control back
  useEffect(() => {
    if (!kioskAllowed) return
    const t = setInterval(() => { if (!kiosk && mode === 'stage' && Date.now() - last.current > idleMs) { setKiosk(true); setStep(0) } }, 2000)
    return () => clearInterval(t)
  }, [kiosk, mode, idleMs, kioskAllowed])
  useEffect(() => {
    if (!kiosk) return
    const t = setInterval(() => setStep(s => { if (s + 1 >= beats.length) { setWorld(w => (w === 'tidewall' ? 'lyft' : 'tidewall')); return 0 } return s + 1 }), 7000)
    return () => clearInterval(t)
  }, [kiosk, beats.length])

  const d = data[world]
  return (
    <div className="shell">
      <div className="topbar">
        <div className="brand">Trackback<small>traces any correction forward</small></div>
        <div className="seg" role="tablist">
          <button className={world === 'tidewall' ? 'on' : ''} onClick={() => { setWorld('tidewall'); setStep(0) }}>Tidewall <span className="t14" style={{ opacity: 0.7 }}>synthetic</span></button>
          <button className={world === 'lyft' ? 'on' : ''} onClick={() => { setWorld('lyft'); setStep(0) }}>Real world: Lyft</button>
        </div>
        <div className="seg"><button className={mode === 'stage' ? 'on' : ''} onClick={() => setMode('stage')}>Stage</button><button className={mode === 'deep' ? 'on' : ''} onClick={() => setMode('deep')}>Deep</button></div>
        <div className="spacer" />
        {world === 'tidewall' && <button className="btn" onClick={() => setDoor('change')}>Change any number</button>}
        <button className="btn" onClick={() => setDoor('why')}>Why on that date?</button>
        <button className="btn" onClick={() => { setMode('deep'); setTab('Time travel') }}>Try to make it peek</button>
        <button className="btn ghost" onClick={reset} title="R">Reset</button>
      </div>
      <div style={{ position: 'relative', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {mode === 'stage' ? (
          <div className="stage" style={{ position: 'relative', flex: 1 }}>
            {kiosk && <div className="kiosk-banner">Playing on its own · press any key to take over</div>}
            {world === 'tidewall' ? <TidewallStage key={`t${step}`} data={d} step={step} onRefresh={() => api.state(world).then(setSt)} /> : <LyftStage key={`l${step}`} data={d} step={step} onRefresh={() => api.state(world).then(setSt)} />}
            <div className="caption">
              <span>{CAPTIONS[world][step]}</span>
              <span className="t14 muted" style={{ whiteSpace: 'nowrap' }}>{step + 1}/{beats.length} · {beats[step]} · <span className="kbd">Space</span> next <span className="kbd">⌫</span> back <span className="kbd">D</span> deep <span className="kbd">W</span> world <span className="kbd">C</span> change a number <span className="kbd">R</span> reset</span>
            </div>
          </div>
        ) : <Deep world={world} tab={tab} setTab={setTab} tick={tick} bump={bump} />}
        {door === 'change' && <ChangeDoor onClose={() => setDoor(null)} />}
        {door === 'why' && <WhyDoor world={world} onClose={() => setDoor(null)} />}
      </div>
      <div className="footer">
        <span><span className={`world-tag ${world === 'lyft' ? 'real' : ''}`}>{world === 'lyft' ? 'real · Lyft' : 'synthetic · Tidewall'}</span></span>
        <span>now <b>{when(st?.now)}</b></span>
        {world === 'tidewall' && <span>clock <b>{when(st?.clock)}</b></span>}
        <span><b>{st?.pending ?? '—'}</b> waiting for a person</span>
        {world === 'tidewall' && <span><b>{st?.holds ?? '—'}</b> on hold</span>}
        <span>LLM mode <b>{st?.mode}</b></span>
        <span>recorded responses: <b>{st?.cache_rows?.real ?? 0}</b> real, <b>{(st?.cache_rows?.scripted ?? 0) + (st?.cache_rows?.fallback ?? 0)}</b> stand-in</span>
        <span className="spacer" />
        <span><a href="/styleguide" style={{ color: 'inherit' }}>styleguide</a></span>
      </div>
    </div>
  )
}

const EXAMPLES = ['March legal is $90k higher; the invoice was in the inbox before the close', 'Batch B03 February was imported twice', 'Q1 utilities at HQ were $40k lower, and we only learned in May', 'A $20k bank fee in June was never booked']

function ChangeDoor({ onClose }: { onClose: () => void }) {
  const [text, setText] = useState(EXAMPLES[0])
  const [r, setR] = useState<Any>(null)
  const [busy, setBusy] = useState(false)
  const run = async () => { setBusy(true); setR(null); try { setR(await api.correction(text)) } finally { setBusy(false) } }
  const inv = r ? Object.entries(r.ripple.items as Record<string, Any>).filter(([, v]) => v.verdict === 'invalidated') : []
  return (
    <><div className="scrim" onClick={onClose} /><div className="modal">
      <h3 className="serif" style={{ fontSize: 26, margin: '0 0 6px' }}>Change any number</h3>
      <div className="t14 muted">Describe a correction in plain words, or pick one. Trackback turns it into balanced correcting lines, runs the ripple, sizes it both SAB 108 ways, lets the agent evaluate it and Jade review it, and shows who it would ping. Nothing is posted.</div>
      <div style={{ display: 'flex', gap: 8, margin: '10px 0', flexWrap: 'wrap' }}>{EXAMPLES.map(x => <button key={x} className="btn ghost" onClick={() => setText(x)}>{x}</button>)}</div>
      <div style={{ display: 'flex', gap: 8 }}><textarea className="field" rows={2} style={{ flex: 1 }} value={text} onChange={e => setText(e.target.value)} /><button className="btn primary" disabled={busy} onClick={run}>{busy ? 'Tracing forward…' : 'Run it'}</button></div>
      {r && r.ripple && <div style={{ marginTop: 14 }}>
        <div className="panel"><b>Parsed:</b> {r.correction.title} · {r.correction.correction.lines.length} lines · orig_period {r.correction.correction.orig_period}</div>
        <div className="grid-cards">
          <div className="panel recall"><b>{r.ripple.counts.invalidated}</b> now wrong · <b>{r.ripple.counts.still_valid}</b> still valid · <b>{r.ripple.counts.compensations}</b> compensations · naive {r.ripple.counts.naive}
            <div className="t14" style={{ marginTop: 6 }}>{inv.slice(0, 8).map(([i, v]) => <div key={i}>{i}: {typeof v.old === 'number' ? `${money(v.old)} → ${money(v.new)}` : `${v.old} → ${v.new}`} ({reason(v.reason)})</div>)}{inv.length > 8 && <div>… {inv.length - 8} more</div>}</div></div>
          <div className={`panel ${r.final.q5_matters.material ? 'recall' : 'cleared'}`}><b>{r.final.q5_matters.material ? 'Material' : 'Not material'}</b> after Jade
            <div className="t14">The agent said {r.evaluation.q5_matters.material ? 'material' : 'immaterial'} ({r.evaluation.q5_matters.why}).</div>
            <div className="t14">{(r.jade as Any[]).filter(j => j.verdict !== 'approve').map(j => <div key={j.claim_key}><Icon s={j.verdict === 'overrule' ? 'invalidated' : 'caution'} size={14} /> {j.verdict} {j.claim_key}: {j.why}</div>)}</div></div>
          <div className="panel ping"><b>Would ping</b>{Object.entries(r.would_ping).map(([a, ids]: Any) => <div key={a} className="t14">{who(a)}: {ids.length} pieces of work</div>)}
            <div className="t14">Notices: {Object.entries(r.would_notify).map(([p, n]) => `${who(p)} (${n} lines)`).join(', ') || 'none'}</div>
            <div className="t14 muted">Skipped: {r.skipped.join(', ') || 'none'}</div></div>
        </div>
        <div className="panel t14">Classification: <b>{r.final.q3_classification.value.replace('_', ' ')}</b> · treatment: {r.final.q7_fix.treatment?.replace(/_/g, ' ')} · posting {r.final.q7_fix.posting_period} · aggregate with the log: rollover {money(r.aggregate.rollover)}, iron curtain {money(r.aggregate.iron_curtain)}</div>
      </div>}
      {r && !r.ripple && <div className="panel recall">{r.detail || 'Could not parse that correction.'}</div>}
      <div style={{ marginTop: 10 }}><button className="btn" onClick={onClose}>Close</button></div>
    </div></>
  )
}

const ACTIONS: Record<World, [string, string][]> = {
  tidewall: [['ACT-cert-q1', 'Certificate sent to Redwood, May 15'], ['ACT-bonus-R1', 'Bonus paid, Bay Area, May 31'], ['ACT-tax-q2', 'Q2 estimated tax paid, Jun 15']],
  lyft: [['LY.street.order', 'Sell-side buy order, 4:25 PM ET'], ['LY.news.publish', 'Newsroom story published, 4:18 PM ET']],
}

function WhyDoor({ world, onClose }: { world: World; onClose: () => void }) {
  const [id, setId] = useState(ACTIONS[world][0][0])
  const [r, setR] = useState<Any>(null)
  useEffect(() => { setR(null); api.decision(id).then(setR) }, [id])
  return (
    <><div className="scrim" onClick={onClose} /><div className="modal">
      <h3 className="serif" style={{ fontSize: 26, margin: '0 0 6px' }}>Why did you do this on that date?</h3>
      <div className="t14 muted">The decision replayed exactly as of its pin: every input it rested on, at the version it read, and who approved it.</div>
      <div style={{ display: 'flex', gap: 8, margin: '10px 0', flexWrap: 'wrap' }}>{ACTIONS[world].map(([k, n]) => <button key={k} className={`btn ${k === id ? 'primary' : ''}`} onClick={() => setId(k)}>{n}</button>)}</div>
      {r && <div>
        <div className="panel"><b>{r.action.summary || r.action.action_id}</b> · executed {when(r.executed_at)} · state {r.action.state}
          <div className="t14">{(r.approvals as Any[]).map(a => `${who(a.approver)} ${a.decision} (${when(a.ts)}): ${a.reason}`).join(' · ')}</div></div>
        {(r.inputs as Any[]).map((c, i) => <div key={i} className="t14" style={{ paddingLeft: c.depth * 16, borderLeft: '2px solid var(--rule)', marginBottom: 6 }}>
          <b>{who(c.who)}</b> · {c.kind}{c.version ? ` v${c.version}` : ''}{c.lot ? ` · LOT ${c.lot}` : ''}{c.pinned_at ? ` · as of ${when(c.pinned_at)}` : ''}<br /><span className="muted">{String(c.label || '').slice(0, 140)}</span>{typeof c.value === 'number' ? <span className="num"> = {c.value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span> : null}</div>)}
      </div>}
      <div style={{ marginTop: 10 }}><button className="btn" onClick={onClose}>Close</button></div>
    </div></>
  )
}
