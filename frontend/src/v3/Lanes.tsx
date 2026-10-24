/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { Check, Mail } from 'lucide-react'
import { fig, money, reason, who, type Any, type World } from './api'
import { Icon } from './Stage'

const KEY_METRICS: Record<World, [string, string][]> = {
  tidewall: [['ttm_adj_ebitda@2026Q1', 'TTM Adj. EBITDA'], ['leverage@2026Q1', 'Net leverage'], ['covenant_status@2026Q1', 'Covenant status'], ['covenant_headroom@2026Q1', 'Headroom']],
  lyft: [['release.margin_expansion_bps', 'Release: margin expansion'], ['street.implied_fy24_margin', 'Implied FY24 margin'], ['street.implied_fy24_adj_ebitda', 'Implied FY24 Adj. EBITDA']],
}
const FILE_SHORT: Record<string, string> = { 'Covenant_Q1-26_PN.xlsx': 'Workbook', 'Board_Deck_Q1-26.pptx': 'Board deck', 'Compliance_Certificate_Q1-26_signed.pdf': 'Certificate' }
const OWNER_NOTE: Record<string, string> = { priya: "Priya's covenant workbook", sam: "the CFO office's slide 2" }
type N = { id: string; t: string; old?: string; now?: string; s: string; w: string; prose?: string; hop: number }

const st = (v: string) => (v === 'reworked' ? 'reworked' : v === 'still_valid' ? 'cleared' : v === 'needs_human' ? 'caution' : 'invalidated')

export function buildLanes(rp: Any, world: World) {
  const lanes: { k: string; n: string; s: string; nodes: N[]; ping?: Any; extra?: string }[] = []
  const metrics = KEY_METRICS[world].map(([k, label]) => [k, label, rp.metrics[k]]).filter(x => x[2]) as [string, string, Any][]
  const changed = Object.values(rp.metrics as Record<string, Any>).filter((m: Any) => m.changed).length
  lanes.push({ k: 'Trackback', n: 'Trackback', s: 'recomputes the numbers', nodes: metrics.map(([k, label, m]) => ({ id: k, t: label, old: fig(m.old, m.unit, k), now: fig(m.new, m.unit, k), s: 'invalidated', hop: 1,
    w: m.conclusion_old !== m.conclusion_new ? (k.startsWith('leverage') || k.startsWith('covenant_status') ? 'crosses the 3.00x covenant' : 'changes sign') : 'recomputed' })),
    extra: changed > metrics.length ? `+${changed - metrics.length} more recomputed` : '' })
  const items = Object.entries(rp.items as Record<string, Any>)
  const people: Record<string, [string, Any][]> = {}
  for (const [i, v] of items) if (v.verdict === 'invalidated' && ['priya', 'sam'].includes(v.owner)) (people[v.owner] ||= []).push([i, v])
  const notices = (rp.wave?.notices || []) as Any[]
  if (Object.keys(people).length) {
    const nodes: N[] = Object.entries(people).map(([o, list]) => {
      const sample = list.find(([i]) => i === 'WB.Covenant.B7' || i === 'DECK.s2.l2') || list[0]
      const n = notices.find(x => x.owner === o)
      return { id: o, t: `${FILE_SHORT[sample[1].file] || sample[1].file}: ${list.length} ${sample[1].file.endsWith('xlsx') ? 'cells' : 'lines'}`, old: typeof sample[1].old === 'number' ? fig(sample[1].old) : String(sample[1].old ?? ''),
        now: typeof sample[1].new === 'number' ? fig(sample[1].new) : String(sample[1].new ?? ''), s: 'invalidated', hop: 2,
        w: n ? `notice → ${who(n.to)}${n.routed_because ? ' (Priya is out)' : ''}` : `notice → ${who(o)}` }
    })
    lanes.push({ k: 'People', n: 'People', s: Object.keys(people).map(o => OWNER_NOTE[o] || who(o)).join(', '), nodes })
  }
  const pings: Record<string, Any> = {}
  for (const p of (rp.wave?.pings || []) as Any[]) pings[p.agent] = p
  const agentOrder = Object.keys(pings).length ? Object.keys(pings) : []
  const skipped = (rp.wave?.skipped || Object.entries(rp.agent_nodes || {}).filter(([, v]: Any) => v.skipped).map(([k, v]: Any) => ({ node_id: k, ...v }))) as Any[]
  for (const s of skipped) { const o = s.owner || (rp.agent_nodes?.[s.node_id]?.owner); if (o && !agentOrder.includes(o)) agentOrder.push(o) }
  for (const a of agentOrder) {
    const its = ((pings[a]?.items || []) as Any[]).filter(i => !(rp.actions || {})[i.artifact_id])
    const groups: Record<string, Any[]> = {}
    const nodes: N[] = []
    for (const it of its) {
      const g = it.artifact_id.startsWith('CERT.') ? 'cert' : it.artifact_id.startsWith('DECK.s4') ? 's4' : null
      if (g) (groups[g] ||= []).push(it)
      else nodes.push({ id: it.artifact_id, t: label(it.artifact_id), s: st(it.verdict), hop: 3, w: it.verdict === 'still_valid' ? `still valid: ${(it.reason || '').split(/[;.]/)[0].slice(0, 70)}` : it.verdict.replace('_', ' '),
        prose: it.verdict === 'reworked' ? String(it.new_version?.content || '').slice(0, 110) : '' })
    }
    if (groups.cert) nodes.unshift({ id: 'cert', t: `Certificate: ${groups.cert.length} lines`, s: 'caution', hop: 3, w: 'delivered May 15: needs the CFO' })
    if (groups.s4) nodes.unshift({ id: 's4', t: `Slide 4: ${groups.s4.length} regions`, s: 'reworked', hop: 3, w: 're-rendered from Trackback' })
    for (const s of skipped.filter(x => (x.owner || rp.agent_nodes?.[x.node_id]?.owner) === a)) nodes.push({ id: s.node_id, t: label(s.node_id), s: 'skipped', hop: 4, w: 'skipped: no material change' })
    lanes.push({ k: a, n: who(a), s: pings[a] ? 'agent · pinged once' : 'agent · not pinged', nodes, ping: pings[a] })
  }
  const acts = Object.entries(rp.actions as Record<string, Any>)
  const actNodes: N[] = acts.filter(([, v]) => v.verdict === 'invalidated').map(([k, v]) => ({ id: k, t: shortAct(v.label), s: 'invalidated', hop: 5,
    w: v.compensation?.amount && v.kind !== 'publish_story' ? `${money(v.compensation.amount)} ${v.compensation.direction} → ${who(v.compensation.approver)}` : `${v.compensation?.title?.split('(')[0] || ''} → ${who(v.compensation?.approver)}` }))
  const actOk = acts.filter(([, v]) => v.verdict === 'still_valid')
  lanes.push({ k: 'Actions', n: 'Executed actions', s: 'money already moved', nodes: actNodes, extra: actOk.length ? `${actOk.length} still valid (${[...new Set(actOk.map(([, v]) => reason(v.reason)))].join('; ')})` : '' })
  const cleared = items.filter(([, v]) => v.verdict === 'still_valid')
  return { lanes, cleared }
}

function label(id: string): string {
  const m: Record<string, string> = { 'CA.q1_close_memo': 'Q1 close memo', 'DECK.s3.l1': 'Slide 3: covenant sentence', 'RA.commentary.membership_growth': '“Membership revenue grew”', 'RA.commentary.regions_profitable': '“All six regions were profitable”',
    'RA.cash_forecast.opening': '13-week cash forecast', 'CA.q1_accruals': 'Q1 close accruals', 'LY.news.headline': 'Headline', 'LY.news.story_q4': 'Story: Q4 bookings', 'LY.street.note': 'Flash note', 'LY.street.q4_beat': 'Note: Q4 beat' }
  return m[id] || id
}
function shortAct(l: string): string {
  return l.replace('Q1 GM bonus paid, ', 'Bonus ').replace('Q1 compliance certificate sent to Redwood', 'Certificate sent').replace('Q2 estimated tax paid', 'Q2 tax paid').replace(/\s*\(.*\)\s*$/, '')
}

export function RippleLanes({ rp, world, animate = true }: { rp: Any; world: World; animate?: boolean }) {
  const [hop, setHop] = useState(animate ? 0 : 9)
  useEffect(() => { if (!animate) return; const t = setInterval(() => setHop(h => (h < 8 ? h + 1 : h)), 380); return () => clearInterval(t) }, [animate])
  const { lanes, cleared } = buildLanes(rp, world)
  const byReason: Record<string, number> = {}
  for (const [, v] of cleared) byReason[reason(v.reason)] = (byReason[reason(v.reason)] || 0) + 1
  return (
    <div className="rlanes">
      {lanes.map(L => (
        <div key={L.k} className="rlane">
          <div className="rname"><div className="n">{L.n}</div>
            {L.ping && hop >= 3 ? <div><span className="envchip"><Mail size={15} /> {L.ping.state.replace('_', ' ')}</span></div> : <div className="s">{L.s}</div>}</div>
          <div className="rnodes">
            {L.nodes.filter(n => n.hop <= hop).map(n => (
              <div key={n.id} className={`rnode ${n.s}`}>
                <span className="ic"><Icon s={n.s} size={18} /></span>
                <div className="t">{n.t}</div>
                {n.old && n.now && <div className="v"><span className="strike-old">{n.old}</span>{n.now}</div>}
                {n.prose && <div className="w pr">“{n.prose}”</div>}
                <div className="w">{n.w}</div>
              </div>
            ))}
            {L.extra && hop >= 6 && <span className="rmore" style={{ color: L.k === 'Actions' ? 'var(--cleared)' : 'var(--ink-muted)' }}>{L.k === 'Actions' && <Check size={16} />} {L.extra}</span>}
            {L.k === 'People' && hop >= 6 && cleared.length > 0 && <span className="rmore"><Check size={16} /> {cleared.length} lines still valid: {Object.entries(byReason).slice(0, 3).map(([k, v]) => `${v} ${k}`).join(', ')}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
