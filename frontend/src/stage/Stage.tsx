import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api, fmt, dayLabel } from '../api'
import { title } from '../labels'
import { LANES, stateOf, pingStory, reduceEdges, STATE_WORD, type State } from '../model'
import { StatusIcon, RecallNotice, RefusalStamp, Envelope } from '../ui/primitives'

/* Stage mode: four lanes, about ten cards, one thing moves at a time, every step on a keypress.
   Space advances, Backspace goes back, R resets, T shows the Memento frame, K turns the kiosk loop off and on. */
const STAGE_LANES = ['sources', 'close_accountant', 'covenant_comp', 'reporting_analyst']   // flow order: each lane builds on the one above
const HERO: Record<string, string[]> = {
  sources: ['billing_export_2026_03'],
  close_accountant: ['memo_q1_deferred_revenue', 'ttm_adj_ebitda_2026_q1'],
  reporting_analyst: ['deck_s_covenant', 'cf_2026_weekly_dues'],
  covenant_comp: ['leverage_2026_q1', 'cert_send_q1_2026'],
}
const LAYER: Record<string, string> = { sources: 'Layer 0 · sources', close_accountant: 'Layer 1 · Close Accountant', covenant_comp: 'Layer 2 · Covenant and Comp', reporting_analyst: 'Layer 3 · Reporting Analyst' }
const LAYER_ORDER = ['sources', 'close_accountant', 'covenant_comp', 'reporting_analyst']

type Preset = { key: string; label: string; notice: { id: string; lot: string; headline: string; reason: string; issuer: string; ts: string }; apply: () => Promise<string> }

async function findClaim(q: string, pred: (c: any) => boolean, fallback: string): Promise<string> {
  try { const r = await api.claims(q); const c = r.claims.find(pred); return c ? c.claim_id : fallback } catch { return fallback }
}
const PRESETS: Preset[] = [
  { key: 'e11', label: 'The billing duplicate', notice: { id: 'E11', lot: '7F3A', headline: 'March billing export: annual-plan revenue was released twice', reason: '$118,000 counted twice across five gyms', issuer: 'Membership billing vendor', ts: 'Jul 8, 2026 · 9:05 AM' },
    apply: async () => { await api.liveE11(); return 'E11' } },
  { key: 'fee', label: 'A 40-cent bank fee', notice: { id: 'FEE', lot: '2B19', headline: 'The June 2 bank fee was $25.80, not $25.40', reason: 'A 40-cent correction from the bank feed', issuer: 'Redwood Bank', ts: 'Jul 8, 2026 · 9:20 AM' },
    apply: async () => { const id = await findClaim('bank_fee', c => c.line_item === 'bank_fee', 'c_e013d68db085'); const r = await api.postCorrection({ claim_id: id, new_value: 25.8, correction_type: 'bank_revision', knowable: 'after', note: 'kiosk: 40-cent bank fee' }); return r.correction_id } },
  { key: 'util', label: 'A utilities invoice', notice: { id: 'UTIL', lot: '5C02', headline: "Fresno's March utilities invoice is $40,000, not $28,000", reason: 'Revised invoice; it was in the inbox before the close', issuer: 'Valley Power', ts: 'Jul 8, 2026 · 9:30 AM' },
    apply: async () => { const id = await findClaim('utilities', c => c.source_id === 'utilities_invoices_2026_q1' && c.entity === 'G4' && (c.period_start || '').startsWith('2026-03'), 'c_1e06a73f530f'); const r = await api.postCorrection({ claim_id: id, new_value: 40000, correction_type: 'revised_invoice', knowable: 'before', note: 'kiosk: utilities invoice' }); return r.correction_id } },
]

type Data = { graph: any; pings: any[]; comps: Record<string, any>; counts: any; total: number; stale: number; compsWaiting: number; calc: { label: string; old: number; new: number; line: string; crosses?: number } | null }

export default function Stage({ world, onReset, kioskEnabled, idleSeconds, initialStep, onCorrection, active = true, correction }: { world: any; onReset: () => Promise<void>; kioskEnabled: boolean; idleSeconds: number; initialStep?: number; onCorrection?: (c: string) => void; active?: boolean; correction?: string | null }) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 1280, h: 664 })
  const [step, setStep] = useState(initialStep ?? 0)
  const [layers, setLayers] = useState(0)            // layered reveal progress (0..4)
  const [corr, setCorr] = useState<string | null>(null)
  const [preset, setPreset] = useState<Preset>(PRESETS[0])
  const [data, setData] = useState<Data | null>(null)
  const [busy, setBusy] = useState(false)
  const [memento, setMemento] = useState<any>(null)
  const startVisitor = new URLSearchParams(window.location.search).get('visitor') === '1'
  const [kiosk, setKiosk] = useState<'off' | 'attract' | 'visitor'>(startVisitor ? 'visitor' : 'off')
  const [offer, setOffer] = useState(startVisitor)
  const [paste, setPaste] = useState<string | null>(null)
  const [pasteMsg, setPasteMsg] = useState<string | null>(null)
  const [fly, setFly] = useState<{ x: number; y: number; to: string } | null>(null)
  const idle = useRef<number | undefined>(undefined)
  const auto = useRef<number | undefined>(undefined)
  const [jumpEnd, setJumpEnd] = useState(false)

  useLayoutEffect(() => {
    const el = ref.current; if (!el) return
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight })); ro.observe(el); setSize({ w: el.clientWidth, h: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  // ------------------------------------------------ data for a correction
  const load = useCallback(async (c: string) => {
    const [g, p, ap, arts] = await Promise.all([api.graph('tidewall', c), api.pings(c), api.approvals(), api.artifacts('tidewall')])
    const comps: Record<string, any> = {}; let waiting = 0
    ap.actions.forEach((a: any) => { if (a.params?.compensates && a.run_id === `correction:${c}`) { comps[a.params.compensates.replace(/^ACT-/, '')] = a; if (a.state === 'proposed') waiting++ } })
    const inv = g.nodes.filter((n: any) => n.verdict === 'invalidated' && (n.kind === 'number') && n.old_value != null && n.new_value != null)
    let calc: Data['calc'] = null
    const lev: any = g.nodes.find((n: any) => n.id === 'leverage_2026_q1' && n.verdict === 'invalidated')
    if (lev) calc = { label: 'Leverage recomputed', old: lev.old_value, new: lev.new_value, line: 'leverage', crosses: lev.new_value > 3 && lev.old_value <= 3 ? 3 : undefined }
    else if (inv.length) { const m: any = [...inv].sort((a: any, b: any) => Math.abs(b.new_value - b.old_value) / (Math.abs(b.old_value) || 1) - Math.abs(a.new_value - a.old_value) / (Math.abs(a.old_value) || 1))[0]; calc = { label: `${title(m)} recomputed`, old: m.old_value, new: m.new_value, line: m.line_item } }
    const findingIds = new Set(g.nodes.filter((n: any) => n.verdict === 'invalidated').map((n: any) => n.id))
    const stale = arts.artifacts.filter((a: any) => findingIds.has(a.artifact_id) && String(a.badge).startsWith('STALE')).length
    setData({ graph: g, pings: p.pings, comps, counts: g.counts, total: g.nodes.filter((n: any) => n.type === 'artifact').length, stale, compsWaiting: waiting, calc })
  }, [])

  useEffect(() => {
    if (!active || !correction || correction === corr || !correction.match(/^(E11|J\d+)$/)) return
    setCorr(correction); load(correction).then(() => setJumpEnd(true))
  }, [active, correction])  // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------ the sequence
  const pingAgents: string[] = useMemo(() => (data?.pings || []).map((p: any) => p.target_agent_id).filter((a: string) => STAGE_LANES.includes(a)).sort((a: string, b: string) => LAYER_ORDER.indexOf(a) - LAYER_ORDER.indexOf(b)), [data])
  const steps: string[] = useMemo(() => {
    const head = ['title', 'reveal', 'recall']
    if (!corr || !data) return head
    return [...head, 'calc', ...pingAgents.map(a => `ping:${a}`), ...pingAgents.map(a => `reply:${a}`), 'payoff']
  }, [corr, data, pingAgents])
  useEffect(() => { if (jumpEnd && steps.length > 4) { setStep(steps.length - 2); setLayers(4); setJumpEnd(false) } }, [jumpEnd, steps.length])
  const cur = steps[Math.min(step, steps.length - 1)]
  const idx = (s: string) => steps.indexOf(s)
  const after = (s: string) => idx(s) >= 0 && step >= idx(s)

  // layered reveal, about 9 seconds
  useEffect(() => {
    if (cur !== 'reveal') { if (step > 1) setLayers(4); else setLayers(0); return }
    setLayers(0); const t = [0, 1800, 4200, 6600].map((ms, i) => window.setTimeout(() => setLayers(i + 1), ms + 300))
    return () => t.forEach(clearTimeout)
  }, [cur])  // eslint-disable-line react-hooks/exhaustive-deps

  const drop = useCallback(async () => {
    if (busy) return
    setBusy(true)
    try { const c = await preset.apply(); setCorr(c); await load(c); setStep(3); onCorrection?.(c) } catch (e) { setPasteMsg(String(e)) } finally { setBusy(false) }
  }, [busy, preset, load])

  const next = useCallback(() => {
    if (cur === 'reveal' && layers < 4) { setLayers(4); return }
    if (cur === 'recall' && !corr) { drop(); return }
    setStep(s => Math.min(steps.length - 1, s + 1))
  }, [cur, layers, corr, drop, steps.length])
  const back = useCallback(() => setStep(s => Math.max(0, s - 1)), [])
  const reset = useCallback(async () => {
    window.clearTimeout(auto.current); setMemento(null); setCorr(null); setData(null); setStep(0); setLayers(0); setPreset(PRESETS[0])
    await onReset()
  }, [onReset])

  // the envelope flies from the calc line to the agent's identity card on each ping step
  useEffect(() => {
    if (!cur.startsWith('ping:')) { setFly(null); return }
    const a = cur.slice(5); const g = geom(size); setFly({ x: g.calcX, y: g.laneTop(0) + g.laneH * 0.5, to: a })
    const t = window.setTimeout(() => setFly({ x: g.bubbleX - 42, y: g.laneTop(STAGE_LANES.indexOf(a)) + 14, to: a }), 40)
    return () => window.clearTimeout(t)
  }, [cur, size])

  // ------------------------------------------------ keyboard
  const showMemento = useCallback(async () => {
    if (memento) { setMemento(null); return }
    const m = await api.memento('billing_export_2026_03', '2026-04-10T17:00:00-07:00')
    const tm = await api.timemap('billing_export_2026_03'); const later = tm.versions.filter((v: any) => v.tx_from > '2026-07-01')
    const ch = later.length ? await api.cheat('billing_export_2026_03', '2026-04-10T17:00:00-07:00', later[later.length - 1].version_id) : null
    setMemento({ m, ch })
  }, [memento])
  useEffect(() => {
    if (!active) return
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return
      if (e.key.toLowerCase() === 'd' || e.metaKey || e.ctrlKey) return
      if (kiosk === 'attract') { e.preventDefault(); return }   // the window listener below hands control to the visitor
      if (e.key === ' ' || e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next() }
      else if (e.key === 'Backspace' || e.key === 'ArrowLeft') { e.preventDefault(); back() }
      else if (e.key.toLowerCase() === 'r' && !e.metaKey) reset()
      else if (e.key.toLowerCase() === 't') showMemento()
      else if (e.key === 'Escape') { setMemento(null); setOffer(false); setPaste(null) }
    }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  })

  // ------------------------------------------------ kiosk: attract loop after idle, visitor mode on any input
  const stopAttract = () => { window.clearTimeout(auto.current); setKiosk('visitor'); setOffer(true); setMemento(null) }
  useEffect(() => {
    if (!kioskEnabled || !active) { if (kiosk === 'attract' && !active) { window.clearTimeout(auto.current); setKiosk('off') } window.clearTimeout(idle.current); return }
    const arm = () => {
      window.clearTimeout(idle.current)
      idle.current = window.setTimeout(() => { if (kiosk !== 'attract') startAttract() }, (kiosk === 'visitor' ? Math.max(idleSeconds, 90) : idleSeconds) * 1000)
    }
    const onInput = (e: Event) => { if (kiosk === 'attract' && e.type !== 'mousemove') { stopAttract() } arm() }
    arm()
    const evs = ['keydown', 'mousedown', 'touchstart', 'wheel', 'mousemove']
    evs.forEach(ev => window.addEventListener(ev, onInput, { passive: true }))
    return () => { window.clearTimeout(idle.current); evs.forEach(ev => window.removeEventListener(ev, onInput)) }
  })
  const startAttract = async () => {
    setKiosk('attract'); setOffer(false); setPaste(null); await reset(); setKiosk('attract')
  }
  // autoplay while attracting: a readable pace, then loop
  useEffect(() => {
    if (kiosk !== 'attract') return
    const dwell: Record<string, number> = { title: 4500, reveal: 10500, recall: 3500, calc: 3500, payoff: 8000 }
    const ms = cur.startsWith('ping:') ? 4500 : cur.startsWith('reply:') ? 5000 : dwell[cur] ?? 4000
    auto.current = window.setTimeout(async () => {
      if (cur === 'payoff') { await reset(); setKiosk('attract'); return }
      next()
    }, ms)
    return () => window.clearTimeout(auto.current)
  }, [kiosk, cur, steps.length])  // eslint-disable-line react-hooks/exhaustive-deps

  const choosePreset = async (p: Preset) => {
    setPaste(null); setPasteMsg(null); setKiosk('visitor'); setOffer(false); setBusy(true)
    try { await onReset(); setCorr(null); setData(null); setPreset(p); setStep(2); setLayers(4) } finally { setBusy(false) }
  }
  const pasteOwn = async () => {
    if (!paste) return
    setPasteMsg(null)
    try {
      const pr = await api.parse(paste)
      if (!pr.claim_id || pr.parsed?.new_value == null) { setPasteMsg('Could not match that to one number. Try: "the March utilities invoice at Fresno is $40,000 and was in the inbox before close".'); return }
      await onReset()
      const own: Preset = { key: 'own', label: 'Your correction', notice: { id: 'YOURS', lot: 'VISITOR', headline: paste.length > 90 ? paste.slice(0, 88) + '…' : paste, reason: `${title({ id: pr.candidates?.[0]?.line_item || 'a number' })}: now ${fmt(pr.parsed.new_value)}`, issuer: 'You', ts: 'just now' },
        apply: async () => { const r = await api.postCorrection({ claim_id: pr.claim_id, new_value: pr.parsed.new_value, correction_type: 'revised_invoice', knowable: pr.parsed.knowable || 'after', note: `visitor: ${paste}` }); return r.correction_id } }
      setPaste(null); setPreset(own); setCorr(null); setData(null); setStep(2); setLayers(4)
    } catch (e) { setPasteMsg(String(e).replace(/^Error: /, '')) }
  }

  // ------------------------------------------------ geometry
  const g = geom(size)
  const worldGraph = world?.graph
  const graph = data?.graph || worldGraph
  const pinged = useMemo(() => new Set<string>((data?.pings || []).flatMap((p: any) => (p.items || []).map((i: any) => i.artifact_id))), [data])
  const node = (id: string) => graph?.nodes.find((n: any) => n.id === id)
  const heroIds = useMemo(() => {
    const out: Record<string, string[]> = {}
    STAGE_LANES.forEach(l => {
      if (!corr || preset.key === 'e11' || !data) { out[l] = HERO[l].filter(id => node(id)); return }
      if (l === 'sources') { const src = data.graph.nodes.filter((n: any) => n.type === 'source' && n.corrected).map((n: any) => n.id); out[l] = src.length ? src.slice(0, 1) : HERO[l]; return }
      const touched = data.graph.nodes.filter((n: any) => n.type === 'artifact' && n.agent_id === l && n.verdict && n.verdict !== 'unaffected' && !n.comp)
      const rank = (n: any) => n.kind === 'action' ? 0 : n.kind === 'sentence' ? 1 : 2
      const pick = touched.sort((a: any, b: any) => rank(a) - rank(b)).slice(0, 2).map((n: any) => n.id)
      out[l] = pick.length ? pick : HERO[l].filter(id => node(id))
    })
    return out
  }, [corr, data, preset, graph])  // eslint-disable-line react-hooks/exhaustive-deps
  const allHero = Object.values(heroIds).flat()
  const lines = useMemo(() => graph ? reduceEdges(graph.edges, new Set(allHero)) : [], [graph, allHero.join(',')])  // eslint-disable-line react-hooks/exhaustive-deps
  const pos = (id: string) => { const l = STAGE_LANES.findIndex(x => heroIds[x]?.includes(id)); const k = heroIds[STAGE_LANES[l]]?.indexOf(id) ?? 0; return { x: g.colX(k), y: g.laneTop(l) + g.laneH / 2, lane: STAGE_LANES[l] } }
  const laneVisible = (l: string) => cur === 'title' ? false : cur === 'reveal' ? LAYER_ORDER.indexOf(l) < layers : true
  const nodeState = (id: string): State => {
    const n = node(id); if (!n || !corr || !data) return 'idle'
    const lane = pos(id).lane
    const final = stateOf(n, pinged)
    if (!after('calc')) return 'idle'
    if (n.type === 'source') return n.corrected ? 'invalidated' : 'idle'
    const pingedHere = pinged.has(id)
    if (pingedHere) { if (after(`reply:${lane}`)) return final; if (after(`ping:${lane}`)) return 'pending'; return 'idle' }
    return final   // numbers recomputed by Trackback, and skipped work, resolve at the calc step
  }
  const focusLane = cur.startsWith('ping:') || cur.startsWith('reply:') ? cur.split(':')[1] : null
  const story = (a: string) => { const p = data?.pings.find((x: any) => x.target_agent_id === a); return p ? pingStory(p, data!.comps) : null }
  const cleared = (l: string) => data ? data.graph.nodes.filter((x: any) => x.type === 'artifact' && x.agent_id === l && x.verdict === 'unaffected').length : 0
  const live = (l: string): string => {
    if (l === 'sources') return ''
    if (!corr || !after('calc')) return cur === 'title' ? '' : 'Finished its work'
    if (!pingAgents.includes(l)) return `Not pinged · ${cleared(l)} checked, all fine`
    if (after(`reply:${l}`)) { const s = story(l); return `${s?.replyTone === 'caution' ? 'Waiting for a human' : s?.replyTone === 'reworked' ? 'Reworked' : 'Still valid'} · ${cleared(l)} cleared` }
    if (after(`ping:${l}`)) { const s = story(l); return `Re-checking ${s?.items ?? ''} item${s?.items === 1 ? '' : 's'}` }
    return 'Watching'
  }
  const caption = (() => {
    if (kiosk === 'attract') return { left: 'Three AI agents built on one number. Watch what happens when it is corrected.', right: 'Press any key to try it' }
    const hint = 'Space next · Backspace back · T time travel · R reset · D deep mode'
    const m: Record<string, string> = { title: 'Press Space to begin.', reveal: 'Each agent builds on what the one before it made.', recall: 'The source admits it was wrong.', calc: 'Trackback recomputes every number itself. No agent is asked about arithmetic.', payoff: '' }
    if (cur.startsWith('ping:')) return { left: `Trackback pings the ${LANES.tidewall.find(x => x.id === cur.slice(5))?.name}, once, about only what it used.`, right: hint }
    if (cur.startsWith('reply:')) return { left: `The ${LANES.tidewall.find(x => x.id === cur.slice(6))?.name} answers in its own words.`, right: hint }
    return { left: m[cur] ?? '', right: hint }
  })()
  const cert = node('cert_send_q1_2026')

  return (
    <div ref={ref} className="stage" aria-label="Stage mode">
      {/* title card */}
      {cur === 'title' && <div className="title-card">
        <h1>May 15: Tidewall's CFO told its lender leverage was {cert ? fmt(cert.old_value ?? cert.value, 'leverage') : '2.95x'}.</h1>
        <p>Three AI agents built on that number.</p>
      </div>}

      {/* lanes */}
      {cur !== 'title' && STAGE_LANES.map((l, i) => {
        const lane = LANES.tidewall.find(x => x.id === l)!
        const vis = laneVisible(l)
        const dim = (!!focusLane && focusLane !== l && l !== 'sources') || cur === 'payoff'
        return <div key={l} className={`lane ${dim ? 'dim' : ''}`} style={{ top: g.laneTop(i), height: g.laneH, opacity: vis ? undefined : 0.08 }}>
          <div className="id-card" style={{ opacity: vis ? 1 : 0, transition: 'opacity 300ms ease-out' }}>
            <div className="av">{lane.mono}</div>
            <div style={{ minWidth: 0 }}><div className="nm">{lane.name}</div><div className="st">{l === 'sources' ? 'What the agents read' : lane.seat}</div>{live(l) && <div className="lv" style={{ color: live(l).startsWith('Re-checking') ? 'var(--ping)' : live(l).startsWith('Waiting') ? 'var(--caution-ink)' : 'var(--ink)' }}>{live(l)}</div>}</div>
          </div>
          {cur === 'reveal' && vis && <div className="layer-label smallcaps" style={{ left: g.trackX, top: 6 }}>{LAYER[l]}</div>}
        </div>
      })}

      {/* who built on whom */}
      {cur !== 'title' && <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }}>
        {lines.map(e => { const a = pos(e.source), b = pos(e.target); if (!laneVisible(a.lane) || !laneVisible(b.lane)) return null
          const x1 = a.x + g.nodeW, y1 = a.y, x2 = b.x, y2 = b.y, mx = (x1 + x2) / 2
          const hot = corr && after('calc') && ['invalidated', 'caution', 'reworked', 'pending'].includes(nodeState(e.target))
          const d = x2 > x1 + 20 ? `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}` : `M ${a.x + g.nodeW / 2} ${y1 + (y2 > y1 ? 34 : -34)} C ${a.x + g.nodeW / 2} ${(y1 + y2) / 2}, ${b.x + g.nodeW / 2} ${(y1 + y2) / 2}, ${b.x + g.nodeW / 2} ${y2 + (y2 > y1 ? -34 : 34)}`
          return <path key={`${e.source}>${e.target}`} d={d} fill="none" stroke={hot ? 'var(--ink)' : 'var(--ink-muted)'} strokeOpacity={hot ? 0.9 : 0.35} strokeWidth={hot ? 2.5 : 1.5} />
        })}
      </svg>}

      {/* cards */}
      {cur !== 'title' && STAGE_LANES.flatMap((l, li) => heroIds[l].map((id, k) => {
        const n = node(id); if (!n) return null
        const st = nodeState(id)
        const moved = st !== 'idle' && st !== 'pending' && n.old_value != null && n.new_value != null && n.old_value !== n.new_value
        const comp = data?.comps[id]
        const vis = laneVisible(l)
        const dim = (!!focusLane && focusLane !== l && l !== 'sources') && !(cur.startsWith('ping:') && false)
        return <div key={id} className={`snode ${st === 'idle' || st === 'pending' ? '' : st} ${vis ? '' : 'hidden'}`} style={{ left: g.colX(k), top: g.laneTop(li) + g.laneH / 2 + (cur === 'reveal' ? 10 : 0), transform: 'translateY(-50%)', width: g.nodeW, zIndex: 2, opacity: dim ? 0.35 : undefined, transitionDelay: cur === 'reveal' ? `${k * 250}ms` : undefined }}>
          <span className="ic"><StatusIcon state={st} size={Math.round(g.icon)} /></span>
          <div className={`tt ${n.kind === 'sentence' ? 'prose' : ''}`}>{n.type === 'source' && n.id === 'billing_export_2026_03' ? 'Billing export, March' : n.kind === 'sentence' ? `“${title(n, 72)}”` : title(n, 40)}</div>
          {n.type === 'source' ? <div className="vv" style={{ fontSize: 'clamp(16px, 1.15vw, 24px)' }}>{st === 'invalidated' ? <span style={{ color: 'var(--recall)' }}>{n.id === 'billing_export_2026_03' ? 'v2: corrected' : 'Source corrected'}</span> : n.id === 'billing_export_2026_03' ? 'v1 · captured Apr 9' : `${n.versions ?? 1} stored version${n.versions === 1 ? '' : 's'}`}</div>
            : n.kind !== 'sentence' && <div className="vv">{moved ? <><span className="old">{fmt(n.old_value, n.line_item)}</span>{fmt(n.new_value, n.line_item)}</> : fmt(n.old_value ?? n.value, n.line_item)}</div>}
          {st !== 'idle' && n.type !== 'source' && <div style={{ fontSize: 'clamp(18px, 1.15vw, 22px)', marginTop: 2, color: st === 'invalidated' ? 'var(--recall)' : st === 'cleared' ? 'var(--cleared)' : st === 'caution' ? 'var(--caution-ink)' : st === 'reworked' || st === 'pending' ? 'var(--ping)' : 'var(--ink-muted)' }}>
            {st === 'caution' && comp ? `Waiting for ${comp.approver_role === 'cfo' ? 'the CFO' : comp.approver_role.replace('+', ' and ').replace('controller', 'the Controller').replace('hr', 'HR')}` : st === 'skipped' ? 'Skipped · no material change' : STATE_WORD[st]}
          </div>}
        </div>
      }))}

      {/* the calc line under the source */}
      {data?.calc && after('calc') && cur !== 'payoff' && <div className="calcline drop-in" style={{ left: g.calcX, top: g.laneTop(0) + g.laneH / 2, transform: 'translateY(-50%)' }}>
        <span className="muted">{data.calc.label}:</span> {fmt(data.calc.old, data.calc.line)} → <b>{fmt(data.calc.new, data.calc.line)}</b>{data.calc.crosses ? <span style={{ color: 'var(--recall)' }}>, crosses {data.calc.crosses.toFixed(2)}x</span> : ''}
      </div>}
      {corr && data && after('calc') && pingAgents.length === 0 && cur !== 'payoff' && <div className="calcline drop-in" style={{ left: g.calcX, top: g.laneTop(0) + g.laneH / 2 + (data.calc ? 44 : 0), transform: 'translateY(-50%)', borderColor: 'var(--cleared)' }}>
        <span style={{ color: 'var(--cleared)' }}>Nothing material changed. No agent needs to look.</span></div>}

      {/* the recall notice */}
      {cur === 'recall' && <div style={{ position: 'absolute', left: g.colX(0) + g.nodeW + 24, top: g.laneTop(0) + 8, zIndex: 9 }}>
        <RecallNotice {...preset.notice} onDrop={drop} busy={busy} />
      </div>}

      {/* envelope */}
      {fly && <div className="fly" style={{ left: fly.x, top: fly.y }}><Envelope /></div>}

      {/* bubbles: the ping and the reply, in the receiving lane */}
      {focusLane && (() => {
        const s = story(focusLane); if (!s) return null
        const li = STAGE_LANES.indexOf(focusLane)
        const isReply = cur.startsWith('reply:')
        const anchor = li < 2 ? { top: g.laneTop(li) + 8 } : { bottom: g.H - (g.laneTop(li) + g.laneH) + 8 }
        const name = LANES.tidewall.find(x => x.id === focusLane)?.name
        return <div style={{ position: 'absolute', left: g.bubbleX, ...anchor, width: g.bubbleW, zIndex: 7, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="bubble" style={{ position: 'relative', width: '100%', opacity: isReply ? 0.6 : 1, fontSize: isReply ? '0.78em' : undefined }}>
            <div className="who"><span>Trackback → {name}</span></div>
            {!isReply && <div style={{ margin: '2px 0 6px' }}><span className="postmark">{s.postmark}</span></div>}
            {s.ask}
          </div>
          {isReply && <div className="bubble reply" style={{ position: 'relative', width: '100%' }}>
            <div className="who"><span>{name} replies</span></div>
            <div style={{ color: s.replyTone === 'caution' ? 'var(--caution-ink)' : s.replyTone === 'reworked' ? 'var(--ping)' : 'var(--cleared)' }}>{s.reply}</div>
            {s.extra.slice(0, 2).map((x, k) => <div key={k} style={{ fontSize: '0.86em', marginTop: 4, color: x.startsWith('Still') ? 'var(--cleared)' : x.startsWith('Reworked') ? 'var(--ping)' : 'var(--caution-ink)' }}>{x}</div>)}
          </div>}
        </div>
      })()}

      {/* the payoff */}
      {cur === 'payoff' && data && <div className="payoff">
        <div className="big num" style={{ fontFamily: 'var(--serif)' }}>{data.pings.reduce((a: number, p: any) => a + (p.n_items || 0), 0)} of {data.total}</div>
        <div className="bigsub">pieces of work needed an agent to look. Trackback checked the rest itself.</div>
        <div className="line">{pingAgents.length} of 3 agents needed to act · {data.compsWaiting} action{data.compsWaiting === 1 ? '' : 's'} waiting for a human · {data.stale} things left stale</div>
        <div className="tag">Trackback traces any correction forward.</div>
      </div>}

      {/* Memento in one frame */}
      {memento && <div className="payoff" style={{ background: 'rgba(247,244,238,0.97)' }}>
        <div className="serif" style={{ fontSize: 'clamp(32px, 3vw, 56px)' }}>April 10, 2026: what the agent actually saw</div>
        <div className="card" style={{ marginTop: '3vh', padding: '1vw 1.4vw', textAlign: 'left', fontSize: 'clamp(18px, 1.2vw, 24px)', position: 'relative' }}>
          <div className="mono muted" style={{ fontSize: '0.8em' }}>billing export, March · v1 · captured {dayLabel(memento.m?.memento?.memento_datetime_http)}</div>
          {(memento.m?.memento?.text || '').split('\n').filter((r: string) => /ANN-2026-03/.test(r)).slice(0, 4).map((r: string, k: number) => <div key={k} className="mono" style={{ color: 'var(--recall)' }}>{r.split(',').slice(0, 4).join('  ')}</div>)}
          <div className="muted" style={{ marginTop: 6 }}>The duplicate rows were right there. That makes it an error, not new information.</div>
          {memento.ch?.refused && <div style={{ position: 'absolute', right: '-2vw', bottom: '-3vh' }}><RefusalStamp published={dayLabel(memento.ch.memento_datetime).replace(', 2026', '')} decision={dayLabel(memento.ch.pin).replace(', 2026', '')} /></div>}
        </div>
      </div>}

      {/* kiosk: visitor card */}
      {kiosk === 'visitor' && offer && paste === null && <div className="payoff" style={{ background: 'rgba(247,244,238,0.9)' }}>
        <div className="card" style={{ padding: '2.4vw 3vw', textAlign: 'left', boxShadow: 'var(--shadow)', maxWidth: 820 }}>
          <div className="serif" style={{ fontSize: 'clamp(32px, 2.8vw, 52px)', lineHeight: 1.1 }}>Try it: drop a recall notice</div>
          <div className="muted" style={{ fontSize: 'clamp(18px, 1.2vw, 24px)', margin: '1vh 0 2.4vh' }}>Pick a correction. Watch who gets asked, and who doesn't.</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {PRESETS.map(p => <button key={p.key} className="btn primary" style={{ height: 48, fontSize: 18, padding: '0 22px' }} onClick={() => choosePreset(p)} disabled={busy}>{p.label}</button>)}
            <button className="btn" style={{ height: 48, fontSize: 18, padding: '0 22px' }} onClick={() => { setOffer(false); setPaste('') }}>Paste your own</button>
          </div>
        </div>
      </div>}
      {paste !== null && <div className="payoff" style={{ background: 'rgba(247,244,238,0.92)' }}>
        <div className="card" style={{ padding: '2vw 2.4vw', textAlign: 'left', width: 'min(760px, 90vw)', boxShadow: 'var(--shadow)' }}>
          <div className="serif" style={{ fontSize: 32 }}>Paste your own correction</div>
          <textarea autoFocus className="field" rows={3} style={{ width: '100%', marginTop: 12, fontSize: 18 }} value={paste} onChange={e => setPaste(e.target.value)} placeholder="The March utilities invoice at Fresno is $40,000, and it was in the inbox before close." />
          {pasteMsg && <div style={{ color: 'var(--recall)', marginTop: 8, fontSize: 16 }}>{pasteMsg}</div>}
          <div style={{ display: 'flex', gap: 10, marginTop: 12 }}><button className="btn primary" style={{ height: 44, fontSize: 16 }} onClick={pasteOwn}>Make it a recall notice</button><button className="btn" style={{ height: 44, fontSize: 16 }} onClick={() => { setPaste(null); setOffer(true) }}>Back</button></div>
        </div>
      </div>}

      <div className="caption"><span>{caption.left}</span><span className="muted" style={{ whiteSpace: 'nowrap' }}>{kiosk === 'attract' ? caption.right : `${caption.right}`}</span></div>
    </div>
  )
}

function geom(size: { w: number; h: number }) {
  const W = size.w, H = size.h
  const cap = Math.max(48, Math.min(72, H * 0.06))
  const laneH = (H - cap) / 4
  const cardX = W * 0.02
  const trackX = W * 0.25
  const nodeW = Math.max(200, Math.min(300, W * 0.16))
  const gap = W * 0.018
  const colX = (k: number) => trackX + k * (nodeW + gap)
  const bubbleX2 = trackX + 2 * (nodeW + gap)
  const bubbleW = W - bubbleX2 - W * 0.02
  return { H, laneH, lanesH: H - cap, laneTop: (i: number) => i * laneH, cardX, trackX, nodeW, colX, bubbleX: bubbleX2, bubbleW, calcX: colX(1), icon: Math.max(18, Math.min(26, W * 0.014)) }
}
