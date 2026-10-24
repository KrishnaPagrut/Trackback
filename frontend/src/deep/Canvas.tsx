import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ReactFlow, Background, BackgroundVariant, Controls, MiniMap, Handle, Position, useReactFlow, type Node, type Edge } from '@xyflow/react'
import { api, fmt, type GraphEdge } from '../api'
import { LANES, laneOf, stateOf, reduceEdges, nodeTitle, reasonText, explain, STATE_WORD, type State } from '../model'
import { Lot, StatusIcon, Monogram, Envelope, HoverCard } from '../ui/primitives'
import { TITLES } from '../labels'

/* Deep mode canvas: horizontal swimlanes, ledger cards, the ripple 150 ms per hop, envelopes to each pinged lane. */
const RAIL = 212, COLW = 222, LANE_H = 84, X0 = RAIL + 8, CARD_H = 76, COLS = 4
const GYM = /_G(\d)(?=_|$)/

type Props = { company: string; correction: string | null; data: { nodes: any[]; edges: GraphEdge[] } | null; pings: any[]; selected: string | null; onSelect: (id: string | null) => void
  trace: Set<string> | null; rippleKey: number; sound: boolean; onLaneMore: (lane: string) => void; onRippleDone?: () => void }

function CardNode({ data }: { data: any }) {
  const n = data.n; const st: State = data.state
  const moved = st !== 'idle' && n.old_value != null && n.new_value != null && n.old_value !== n.new_value
  const t = n.members ? `${nodeTitle({ id: n.members[0].replace(/_G\d(?=_|$)/, '') })}, ${n.members.length} gyms` : nodeTitle(n, 60)
  const val = n.kind === 'sentence' || n.type === 'source' || n.value == null ? '' : fmt(n.value, n.line_item)
  const word = st === 'idle' ? (n.type === 'source' ? (n.system || 'source').replace(/_/g, ' ') : '') : st === 'skipped' ? 'skipped, no change' : `${STATE_WORD[st].toLowerCase()}${n.reason && st !== 'reworked' ? ' · ' + reasonText(n.reason) : ''}`
  const h = (id: string, pos: Position, type: 'source' | 'target') => <Handle id={id} type={type} position={pos} style={{ opacity: 0, width: 4, height: 4 }} />
  return <div className={`dcard nopan nodrag ${st === 'idle' ? '' : st} ${data.selected ? 'selected' : ''} ${data.dim ? 'dim' : ''} ${data.lit ? 'lit' : ''}`}
    role="button" tabIndex={0} onPointerUp={e => { e.stopPropagation(); data.onPick?.() }} onKeyDown={e => { if (e.key === 'Enter') data.onPick?.() }}
    onMouseEnter={e => data.onHover?.(n, st, e.clientX, e.clientY)} onMouseMove={e => data.onHover?.(n, st, e.clientX, e.clientY)} onMouseLeave={() => data.onHover?.(null)}>
    {h('l', Position.Left, 'target')}{h('t', Position.Top, 'target')}{h('tb', Position.Bottom, 'target')}{h('r', Position.Right, 'source')}{h('b', Position.Bottom, 'source')}{h('bt', Position.Top, 'source')}
    <div className="r1"><Lot code={n.lot || (n.members ? `${n.members.length}×` : null)} /><StatusIcon state={st} size={17} /></div>
    <div className={`tt ${n.kind === 'sentence' ? 'prose' : ''}`}>{n.kind === 'sentence' ? `“${t}”` : t}</div>
    <div className="r3">{moved ? <><span className="o">{fmt(n.old_value, n.line_item)}</span><span className="v">{fmt(n.new_value, n.line_item)}</span></> : val && <span className="v">{val}</span>}{word && <span className="w">{word}</span>}</div>
  </div>
}
function LaneNode({ data }: { data: any }) {
  const l = data.lane
  return <div style={{ width: data.width, height: data.h, borderTop: '1px solid var(--rule)', position: 'relative', background: data.i % 2 ? 'rgba(255,255,255,0.4)' : 'transparent' }}>
    <div className="lane-rail" style={{ position: 'absolute', left: 10, top: 6, width: data.h < LANE_H ? data.width - 20 : RAIL - 18, display: 'flex', gap: 10, overflow: 'hidden', height: data.h - 10, alignItems: data.h < LANE_H ? 'center' : undefined }}>
      <Monogram text={l.mono} size={data.h < LANE_H ? 28 : 36} />
      <div style={{ minWidth: 0, display: data.h < LANE_H ? 'flex' : undefined, gap: 12, alignItems: 'baseline' }}>
        <div className="nm">{l.name}</div><div className="st">{l.seat}</div>
        {data.live && <div className="lv" style={{ color: data.live.startsWith('Re-checking') ? 'var(--ping)' : data.live.startsWith('Waiting') ? 'var(--caution-ink)' : 'var(--ink)' }}>{data.live}</div>}
        {data.more > 0 && <button className="more" onClick={() => data.onMore(l.id)}>+{data.more} more {data.moreWord}</button>}
      </div>
    </div>
  </div>
}
function EnvNode({ data }: { data: any }) { return <Envelope postmark={data.postmark} /> }
function SpacerNode({ data }: { data: any }) { return <div style={{ width: data.w, height: data.h }} /> }
const nodeTypes = { card: CardNode, lane: LaneNode, env: EnvNode, spacer: SpacerNode }

/* Fit from the layout's own geometry (we know every lane's size), so the view never depends on React Flow having measured a card yet. */
function AutoFit({ w, h, sig }: { w: number; h: number; sig: string }) {
  const rf = useReactFlow()
  useEffect(() => {
    const el = document.querySelector('.deep-canvas') as HTMLElement | null; if (!el) return
    const fit = () => {
      const r = el.getBoundingClientRect(); if (!r.width || !r.height) return
      const z = Math.min(1.3, (r.width / w) * 0.98, (r.height / h) * 0.98)
      rf.setViewport({ x: (r.width - w * z) / 2, y: (r.height - h * z) / 2, zoom: z })
    }
    fit()
    const ro = new ResizeObserver(fit); ro.observe(el)
    return () => ro.disconnect()
  }, [w, h, sig, rf])
  return null
}

function beep() {
  try {
    const Ctx = (window as any).AudioContext || (window as any).webkitAudioContext; const ctx = new Ctx()
    const o = ctx.createOscillator(); const g = ctx.createGain(); o.type = 'sine'; o.frequency.value = 880
    g.gain.setValueAtTime(0.0001, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.08, ctx.currentTime + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25)
    o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.3)
  } catch { /* no audio: silent */ }
}

export function heroSelect(company: string, correction: string | null, nodes: any[], edges: GraphEdge[], pingedNodes: Set<string>) {
  const lanes = LANES[company]
  // fold per-gym siblings into one card
  let ns: any[] = nodes.filter(n => n.type === 'artifact' || (n.type === 'source' && (correction ? n.corrected : true)))
  const groups: Record<string, any> = {}; const folded = new Set<string>()
  const key = (n: any) => `${laneOf(n)}|${n.id.replace(GYM, '_G×')}`
  const cnt: Record<string, number> = {}; ns.forEach(n => { if (GYM.test(n.id)) cnt[key(n)] = (cnt[key(n)] || 0) + 1 })
  ns.forEach(n => {
    if (!GYM.test(n.id) || (cnt[key(n)] || 0) < 3) return
    folded.add(n.id)
    const g = (groups[key(n)] ||= { ...n, id: `grp:${key(n)}`, members: [], nInv: 0, verdict: null, reason: null, old_value: null, new_value: null, lot: null })
    g.members.push(n.id); if (n.verdict === 'invalidated') g.nInv++
    if (n.verdict && (!g.verdict || n.verdict === 'invalidated')) { g.verdict = n.verdict; g.reason = n.reason; g.hop = Math.min(g.hop ?? 99, n.hop ?? 99) }
  })
  ns = [...ns.filter(n => !folded.has(n.id)), ...Object.values(groups)]
  const memberOf: Record<string, string> = {}; Object.values(groups).forEach((g: any) => g.members.forEach((m: string) => { memberOf[m] = g.id }))
  // which to show: what changed for this correction, or at rest the deliverables a person would ask about
  const desc: Record<string, number> = {}
  const outE: Record<string, string[]> = {}; edges.forEach(e => { (outE[e.source] ||= []).push(e.target) })
  const reach = (id: string) => { if (desc[id] != null) return desc[id]; const seen = new Set<string>(); const st = [id]; while (st.length) { const x = st.pop()!; (outE[x] || []).forEach(y => { if (!seen.has(y)) { seen.add(y); st.push(y) } }) } desc[id] = seen.size; return seen.size }
  const score = (n: any): number => {
    if (n.comp) return correction && n.run_id === `correction:${correction}` ? 0 : 99
    if (correction) {
      if (n.type === 'source') return n.corrected ? 0 : 99
      if (!n.verdict) return 99
      const s = stateOf(n, pingedNodes)
      return s === 'caution' ? 0 : s === 'reworked' ? 1 : s === 'invalidated' ? (n.kind === 'sentence' ? 1 : n.members ? 3 : 2) : s === 'cleared' ? (pingedNodes.has(n.id) ? 2 : 5) : n.id.startsWith('cf_2026_weekly') ? 4 : 9
    }
    if (n.type === 'source') return /billing_export_2026_03|lyft_q4_2023_release/.test(n.id) ? 0 : 99
    const known = n.id in TITLES || (n.members && n.members[0].replace(GYM, '') in TITLES)
    return (known ? 0 : 3) + (n.kind === 'action' ? 0 : n.kind === 'sentence' ? 1 : 2) - Math.min(2, reach(n.members ? n.members[0] : n.id) / 40)
  }
  const caps: Record<string, number> = { sources: 1, trackback: 3, humans: 3 }
  const byLane: Record<string, any[]> = {}; const hidden: Record<string, number> = {}
  lanes.forEach(l => { byLane[l.id] = []; hidden[l.id] = 0 })
  const sorted = [...ns].sort((a, b) => score(a) - score(b) || (a.hop ?? 0) - (b.hop ?? 0))
  let total = 0
  sorted.forEach(n => {
    const l = laneOf(n); if (!byLane[l]) return
    const sc = score(n)
    if (sc < 9 && byLane[l].length < (caps[l] ?? 3) && total < 16) { byLane[l].push(n); total++ } else if (sc < 99 && (correction ? n.verdict : n.type === 'artifact' && !n.comp)) hidden[l]++
  })
  return { byLane, hidden, memberOf }
}

export default function Canvas({ company, correction, data, pings, selected, onSelect, trace, rippleKey, sound, onLaneMore, onRippleDone }: Props) {
  const [hop, setHop] = useState(99)
  const [env, setEnv] = useState<{ lane: string; at: 'tb' | 'lane'; postmark: string } | null>(null)
  const [arrived, setArrived] = useState<Set<string>>(new Set())
  const [hover, setHover] = useState<{ n: any; st: State; x: number; y: number } | null>(null)
  const [comps, setComps] = useState<Record<string, any>>({})
  useEffect(() => { if (!correction) { setComps({}); return } api.approvals().then(d => { const m: Record<string, any> = {}; d.actions.forEach((a: any) => { if (a.params?.compensates && a.run_id === `correction:${correction}`) m[a.params.compensates.replace(/^ACT-/, '')] = a }); setComps(m) }).catch(() => null) }, [correction, pings.length])
  const onHover = useCallback((n: any, st?: State, cx?: number, cy?: number) => {
    if (!n) { setHover(null); return }
    const el = document.querySelector('.deep-wrap') as HTMLElement | null; const r = el?.getBoundingClientRect()
    setHover({ n, st: st!, x: (cx || 0) - (r?.left || 0), y: (cy || 0) - (r?.top || 0) })
  }, [])
  const lanes = LANES[company]
  const pingedNodes = useMemo(() => new Set<string>(pings.flatMap((p: any) => (p.items || []).map((i: any) => i.artifact_id))), [pings])
  const pingedLanes = useMemo(() => pings.map((p: any) => p.target_agent_id), [pings])
  const timers = useRef<number[]>([])

  // the ripple: 150 ms per hop, then one envelope per pinged lane
  const played = useRef<string>('')
  useEffect(() => {
    // play the ripple once per (correction, drop); a data refresh for the same correction never replays it
    const key = `${correction}:${rippleKey}`
    if (data && correction && played.current === key) return
    timers.current.forEach(clearTimeout); timers.current = []
    if (!data || !correction) { setHop(99); setEnv(null); setArrived(new Set(pingedLanes)); return }
    if (!pings.length && (data as any).correction?.correction_id === correction && correction === 'E11') return   // wait for the pings so the envelopes have somewhere to go
    played.current = key
    const maxHop = Math.max(0, ...data.nodes.filter(n => n.verdict).map(n => n.hop ?? 0))
    setHop(-1); setArrived(new Set()); setEnv(null)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) { setHop(99); setArrived(new Set(pingedLanes)); onRippleDone?.(); return }
    for (let h = 0; h <= maxHop; h++) timers.current.push(window.setTimeout(() => setHop(h), 150 * (h + 1)))
    let t = 150 * (maxHop + 2)
    pings.forEach((p: any) => {
      const tm = new Date(p.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles' })
      const ini = lanes.find(l => l.id === p.target_agent_id)?.mono || '?'
      timers.current.push(window.setTimeout(() => { setEnv({ lane: p.target_agent_id, at: 'tb', postmark: `${ini} · ${tm}` }); if (sound) beep() }, t))
      timers.current.push(window.setTimeout(() => setEnv(e => e && { ...e, at: 'lane' }), t + 60))
      timers.current.push(window.setTimeout(() => setArrived(s => new Set([...s, p.target_agent_id])), t + 700))
      t += 900
    })
    timers.current.push(window.setTimeout(() => { setEnv(null); setHop(99); onRippleDone?.() }, t + 200))
    return () => timers.current.forEach(clearTimeout)
  }, [data, correction, rippleKey, pings.length])  // eslint-disable-line react-hooks/exhaustive-deps

  const { nodes, edges, size } = useMemo(() => {
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[], size: { w: 1, h: 1 } }
    const { byLane, hidden, memberOf } = heroSelect(company, correction, data.nodes, data.edges, pingedNodes)
    // depth over the full graph so columns follow the direction of work
    const depth: Record<string, number> = {}; const into: Record<string, string[]> = {}
    data.edges.forEach(e => { (into[e.target] ||= []).push(e.source) })
    const d = (id: string, seen = new Set<string>()): number => { if (depth[id] != null) return depth[id]; if (seen.has(id)) return 0; seen.add(id); const v = Math.max(-1, ...(into[id] || []).map(s => d(s, seen))) + 1; depth[id] = v; return v }
    const visIds = Object.values(byLane).flat().map((n: any) => n.members ? n.members[0] : n.id)
    const depths = [...new Set(visIds.map(id => d(id)))].sort((a, b) => a - b)
    const binOf = (id: string) => depths.length <= 1 ? 0 : Math.round((depths.indexOf(d(id)) / (depths.length - 1)) * (COLS - 1))
    const width = X0 + COLS * COLW + 8
    const rf: Node[] = []; const colOf: Record<string, number> = {}; const laneIdx: Record<string, number> = {}
    const laneH = lanes.map(() => LANE_H); const laneY = laneH.map((_, i) => i * LANE_H)   // equal lane heights (DESIGN.md)
    lanes.forEach((l, i) => {
      const pinged = pings.find((p: any) => p.target_agent_id === l.id)
      const live = !correction ? (l.id === 'trackback' ? 'Watching for corrections' : undefined)
        : pinged ? (arrived.has(l.id) ? (pinged.state === 'needs_human' ? 'Waiting for a human' : pinged.state === 'reworked' ? 'Reworked' : pinged.state === 'still_valid' ? 'Still valid' : 'Answered') : env?.lane === l.id ? `Re-checking ${pinged.n_items} item${pinged.n_items === 1 ? '' : 's'}` : 'Pinged')
        : l.id === 'trackback' ? 'Recomputed numbers' : l.id === 'sources' ? 'Corrected: v2' : l.id === 'humans' ? undefined : 'Not pinged'
      rf.push({ id: `lane:${l.id}`, type: 'lane', position: { x: 0, y: laneY[i] }, width, height: laneH[i], draggable: false, selectable: false, zIndex: -1,
        data: { lane: l, i, width, h: laneH[i], live, more: hidden[l.id] || 0, moreWord: correction ? 'checked' : '', onMore: onLaneMore } })
      const used = new Set<number>()
      const items = [...(byLane[l.id] || [])].sort((a, b) => d(a.members ? a.members[0] : a.id) - d(b.members ? b.members[0] : b.id))
      items.forEach(n => {
        let c = binOf(n.members ? n.members[0] : n.id)
        const order = [c, c + 1, c - 1, c + 2, c - 2, c + 3, c - 3].filter(x => x >= 0 && x < COLS)
        c = order.find(x => !used.has(x)) ?? c; used.add(c); colOf[n.id] = c; laneIdx[n.id] = i
        const st: State = correction ? (n.verdict && (n.hop ?? 0) <= hop ? stateOf(n, pingedNodes) : n.comp && hop >= 99 ? 'caution' : 'idle') : 'idle'
        const dim = !!trace && !trace.has(n.id) && n.id !== selected && !(n.members && n.members.some((m: string) => trace.has(m)))
        rf.push({ id: n.id, type: 'card', position: { x: X0 + c * COLW, y: laneY[i] + (LANE_H - CARD_H) / 2 }, width: 208, height: CARD_H, draggable: false,
          data: { n, state: st, selected: selected === n.id || (n.members && n.members.includes(selected)), dim, lit: correction && n.verdict && (n.hop ?? 0) === hop, onPick: () => onSelect(n.members ? n.members[0] : n.id), onHover } })
      })
    })
    // an empty band under the last lane: the minimap and the zoom controls live there, so they never cover a card
    rf.push({ id: 'spacer', type: 'spacer', position: { x: 0, y: laneY[laneY.length - 1] + laneH[laneH.length - 1] }, width, height: 100, draggable: false, selectable: false, zIndex: -2, data: { w: width, h: 100 } })
    const visible = new Set(rf.filter(n => n.type === 'card').map(n => n.id))
    // edges between visible cards (through hidden ones); grouped members map to their group
    const mapped = data.edges.map(e => ({ ...e, source: memberOf[e.source] || e.source, target: memberOf[e.target] || e.target }))
    const red = reduceEdges(mapped, visible)
    const touched = (id: string) => { const n: any = rf.find(x => x.id === id)?.data; return n && ['invalidated', 'caution', 'reworked'].includes(n.state) }
    const es: Edge[] = red.filter(e => e.source !== e.target).map(e => {
      const fwd = colOf[e.target] > colOf[e.source]; const down = laneIdx[e.target] > laneIdx[e.source]
      return { id: `${e.source}>${e.target}`, source: e.source, target: e.target, type: 'default',
        sourceHandle: fwd ? 'r' : down ? 'b' : 'bt', targetHandle: fwd ? 'l' : down ? 't' : 'tb',
        className: trace && trace.has(e.source) && (trace.has(e.target) || e.target === selected) ? 'trace' : correction && touched(e.target) && (touched(e.source) || e.source.startsWith('billing') || e.source.startsWith('lyft_q4')) ? 'active' : '' }
    })
    if (env) {
      const li = lanes.findIndex(l => l.id === env.lane); const ti = lanes.findIndex(l => l.id === 'trackback')
      rf.push({ id: 'env', type: 'env', width: 150, height: 30, position: env.at === 'tb' ? { x: RAIL - 60, y: laneY[ti] + laneH[ti] - 34 } : { x: RAIL - 60, y: laneY[li] + laneH[li] - 34 }, draggable: false, selectable: false, zIndex: 20, className: 'env-node', data: { postmark: env.postmark } })
    }
    return { nodes: rf, edges: es, size: { w: width, h: laneY[laneY.length - 1] + laneH[laneH.length - 1] + 100 } }
  }, [data, company, correction, pings, pingedNodes, hop, env, arrived, selected, trace, lanes, onLaneMore, onHover])

  if (!data) return <div className="muted" style={{ padding: 24 }}>Loading the ledger…</div>
  const box = (document.querySelector('.deep-wrap') as HTMLElement | null)?.getBoundingClientRect()
  return (
    <div className="deep-wrap" style={{ position: 'absolute', inset: 0 }}>
    <ReactFlow className="deep-canvas" key={`${company}:${correction || 'none'}`} nodes={nodes} edges={edges} nodeTypes={nodeTypes} minZoom={0.3} maxZoom={1.8}
      nodesConnectable={false} onPaneClick={() => onSelect(null)} proOptions={{ hideAttribution: true }}>
      <AutoFit w={size.w} h={size.h} sig={`${company}:${correction || 'none'}`} />
      <Background variant={BackgroundVariant.Dots} gap={20} size={1.4} color="rgba(28,27,25,0.18)" />
      <MiniMap position="bottom-right" pannable zoomable nodeColor={(n: any) => n.type === 'lane' || n.type === 'spacer' ? 'transparent' : n.data?.state === 'invalidated' ? '#C62828' : n.data?.state === 'caution' ? '#B26A00' : n.data?.state === 'reworked' ? '#1F5FBF' : n.data?.state === 'cleared' ? '#2E7D32' : '#6B675F'} maskColor="rgba(247,244,238,0.6)" style={{ width: 150, height: 76, margin: 12 }} />
      <Controls position="bottom-right" showInteractive={false} orientation="horizontal" style={{ marginRight: 176, marginBottom: 12 }} />
    </ReactFlow>
    {hover && <HoverCard e={explain(hover.n.members ? { ...hover.n, id: hover.n.members[0] } : hover.n, hover.st, comps[hover.n.id])} x={hover.x} y={hover.y} box={{ w: box?.width || 1200, h: box?.height || 600 }} />}
    </div>
  )
}
