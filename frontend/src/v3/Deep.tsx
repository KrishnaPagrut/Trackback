/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'
import { api, money, fig, lev, when, reason, who, type Any, type World } from './api'
import { Icon } from './Stage'

export const TABS = ['Reconcile', 'Trace', 'Graph', 'Evaluate', 'Pings', 'Approvals', 'Memo', 'Time travel', 'Scorecard', 'Lessons', 'Access'] as const
export type Tab = typeof TABS[number]

export function Deep({ world, tab, setTab, tick, bump }: { world: World; tab: Tab; setTab: (t: Tab) => void; tick: number; bump: () => void }) {
  const [exc, setExc] = useState<Any[]>([])
  const [sel, setSel] = useState<string | null>(null)
  useEffect(() => { api.exceptions(world).then(r => { setExc(r.exceptions); setSel(s => (s && r.exceptions.some((e: Any) => e.exception_id === s) ? s : r.exceptions[0]?.exception_id || null)) }) }, [world, tick])
  return (
    <div className="deep">
      <div className="side">
        <div className="tabs" style={{ flexWrap: 'wrap', padding: '6px 10px' }}>{TABS.map(t => <button key={t} className={`tab ${t === tab ? 'on' : ''}`} onClick={() => setTab(t)}>{t}</button>)}</div>
        <div className="smallcaps muted" style={{ padding: '12px 14px 4px' }}>exceptions</div>
        {exc.map(e => (
          <button key={e.exception_id} className={`row ${e.exception_id === sel ? 'on' : ''}`} onClick={() => setSel(e.exception_id)}>
            <Icon s={e.material ? 'invalidated' : e.classification === 'estimate_change' ? 'cleared' : 'caution'} size={18} />
            <div><div style={{ fontWeight: 600 }}>{e.exception_id} · {e.kind.replace(/_/g, ' ')}</div><div className="muted t14">{e.title}</div>
              <div className="t14">{money(e.amount, { cents: e.amount < 1000 })} · {e.classification?.replace('_', ' ')} · {e.material ? 'material' : 'not material'}</div></div>
          </button>
        ))}
      </div>
      <div className="main">
        {tab === 'Reconcile' && <Reconcile world={world} />}
        {tab === 'Trace' && <Trace world={world} />}
        {tab === 'Graph' && sel && <Graph world={world} id={sel} />}
        {tab === 'Evaluate' && sel && <Evaluate world={world} id={sel} />}
        {tab === 'Pings' && <Pings world={world} bump={bump} tick={tick} />}
        {tab === 'Approvals' && <Approvals world={world} bump={bump} tick={tick} />}
        {tab === 'Memo' && sel && <Memo world={world} id={sel} />}
        {tab === 'Time travel' && <TimeTravel world={world} />}
        {tab === 'Scorecard' && <Scorecard />}
        {tab === 'Lessons' && <Lessons />}
        {tab === 'Access' && <Access />}
      </div>
    </div>
  )
}

function Reconcile({ world }: { world: World }) {
  const [d, setD] = useState<Any>(null)
  const [f, setF] = useState<string>('exception')
  useEffect(() => { api.recons(world).then(setD) }, [world])
  if (!d) return null
  const items = (d.items as Any[]).filter(i => !f || i.outcome === f)
  return (
    <div>
      <h3>Reconciliations</h3>
      <div className="grid-cards">{(d.summary as Any[]).map(r => (
        <div key={r.recon} className="panel">
          <div style={{ fontWeight: 600 }}>{r.title}</div>
          <div className="t14" style={{ marginTop: 6 }}><b className="num">{r.counts.matched}</b> matched · <b className="num">{r.counts.cleared}</b> cleared · <b className={`num ${r.counts.exceptions ? 'red' : ''}`}>{r.counts.exceptions}</b> exceptions</div>
          <div className="t14 muted">{Object.entries(r.cleared_by_reason || {}).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(' · ')}</div>
          {r.learned_lags && <div className="t14" style={{ marginTop: 4 }}>Learned lags: {Object.entries(r.learned_lags).map(([k, v]: Any) => `${k} ${v.min === v.max ? v.min : `${v.min}-${v.max}`}d`).join(', ')}</div>}
          {r.learned_habits && Object.keys(r.learned_habits).length > 0 && <div className="t14">Learned habit: {Object.entries(r.learned_habits).map(([k, v]: Any) => `${k} short-pays ${v.short_pays} of 12 ($${v.min}–$${v.max})`).join(', ')}</div>}
          {r.handoff && <div className="panel caution t14" style={{ marginTop: 8, marginBottom: 0 }}><b>Priya's handoff:</b> “{r.handoff.note}” <br />{r.handoff.summary}</div>}
        </div>
      ))}</div>
      <div style={{ display: 'flex', gap: 8, margin: '10px 0' }}>{['exception', 'cleared', 'matched'].map(o => <button key={o} className={`btn ${f === o ? 'primary' : ''}`} onClick={() => setF(o)}>{o}</button>)}</div>
      <table className="ledger-table"><thead><tr><th>Recon</th><th>Outcome</th><th>Reason</th><th className="n">Amount</th><th>Detail</th></tr></thead>
        <tbody>{items.slice(0, 200).map((i, k) => (
          <tr key={k} className={i.outcome === 'exception' ? 'dup' : ''}><td>{i.recon}</td><td><Icon s={i.outcome === 'exception' ? 'invalidated' : 'cleared'} size={16} /> {i.outcome}</td><td>{(i.reason || '').replace(/_/g, ' ')}</td>
            <td className="n">{money(i.amount, { cents: Math.abs(i.amount || 0) < 1000 })}</td><td className="t14">{detailText(i)}</td></tr>
        ))}</tbody></table>
    </div>
  )
}

function detailText(i: Any): string {
  const d = i.detail || {}
  if (i.outcome === 'exception') return d.title || d.label || ''
  if (d.why) return d.why
  if (d.description) return `${d.description} (${d.date || ''})`
  if (d.customer) return `${d.customer}: ${(d.invoices || []).join(', ')}`
  if (d.batch) return `${d.period} ${d.batch}${d.note ? ': ' + d.note.slice(0, 80) : ''}`
  if (d.vendor) return `${d.vendor} ${d.invoice_no || ''}`
  return d.book_id ? `${d.book_id} ↔ ${d.bank_id}` : d.label || ''
}

const FILES: Record<World, [string, string][]> = {
  tidewall: [['covenant_workbook', "Priya's covenant workbook"], ['board_deck', 'Board deck'], ['compliance_certificate', 'Compliance certificate'], ['billing_rec_incomplete', "Priya's half-finished rec"]],
  lyft: [['lyft_release', 'Exhibit 99.1 as filed (real)']],
}

function Trace({ world }: { world: World }) {
  const [src, setSrc] = useState(FILES[world][0][0])
  const [f, setF] = useState<Any>(null)
  const [pick, setPick] = useState<Any>(null)
  const [chain, setChain] = useState<Any>(null)
  useEffect(() => { setSrc(FILES[world][0][0]) }, [world])
  useEffect(() => { setF(null); setPick(null); api.file(world, src).then(setF) }, [world, src])
  useEffect(() => { if (pick?.item_id) api.built(world, pick.item_id).then(setChain); else setChain(null) }, [pick, world])
  return (
    <div style={{ display: 'flex', gap: 18 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h3>Trace: links nobody drew</h3>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>{FILES[world].map(([s, n]) => <button key={s} className={`btn ${s === src ? 'primary' : ''}`} onClick={() => setSrc(s)}>{n}</button>)}</div>
        {f && <div className="t14 muted" style={{ marginBottom: 8 }}>{f.title} · captured {when(f.captured_at)} · {f.version_id}</div>}
        {f?.kind === 'xlsx' && f.sheets.map((s: Any) => (
          <div key={s.name} style={{ marginBottom: 18 }}><div style={{ fontWeight: 600, marginBottom: 4 }}>{s.name}</div>
            <table className="sheet"><tbody>{s.rows.map((r: Any[], i: number) => (
              <tr key={i}>{r.map((c, j) => c == null ? <td key={j} /> : (
                <td key={j} className={`${c.link ? ({ linked: 'linked', stale: 'stale', derived: 'derived', policy: 'pol', reconstructed: 'linked' } as Any)[c.link.status] || '' : 'label'} ${pick?.item_id === c.link?.item_id ? 'sel' : ''}`}
                  onClick={() => c.link && setPick(c.link)} title={c.formula || ''} style={{ cursor: c.link ? 'pointer' : 'default' }}>
                  {typeof c.value === 'number' ? (Math.abs(c.value) < 10 ? c.value.toFixed(c.value % 1 ? 4 : 2) : c.value.toLocaleString(undefined, { maximumFractionDigits: 2 })) : String(c.value)}
                  {c.formula && <span className="muted" style={{ fontSize: 12 }}> ƒ</span>}
                </td>))}</tr>
            ))}</tbody></table></div>
        ))}
        {f?.kind === 'pptx' && f.slides.map((s: Any) => (
          <div key={s.n} className="slide"><div className="st">Slide {s.n}: {s.title}</div>
            {s.lines.map((l: Any) => { const lk = l.links?.[0]; return (
              <div key={l.n} className={`ln ${lk ? lk.status : ''}`} onClick={() => lk && setPick(lk)}>{l.text}
                {(l.links || []).map((x: Any) => <span key={x.item_id} className={`chip ${x.status === 'stale' ? 'recall' : 'cleared'}`} style={{ marginLeft: 8 }} onClick={e => { e.stopPropagation(); setPick(x) }}>{x.status}</span>)}</div>) })}
          </div>
        ))}
        {f?.kind === 'pdf' && <div className="slide">{f.lines.map((l: Any, i: number) => <div key={i} className={`ln ${l.link ? l.link.status : ''}`} onClick={() => l.link && setPick(l.link)}>{l.text}</div>)}</div>}
        {f?.kind === 'htm' && <div className="slide">{f.items.map((it: Any) => <div key={it.item_id} className={`ln ${it.status === 'unlinked' ? 'stale' : 'linked'}`} onClick={() => setPick(it)}>
          <Icon s={it.status === 'unlinked' ? 'invalidated' : 'cleared'} size={16} /> <b className="num">{it.display}</b> <span className="muted">{(it.label || '').slice(-90)}</span></div>)}</div>}
      </div>
      <div style={{ width: 380, flex: 'none' }}>
        {pick ? (
          <div className={`panel ${pick.status === 'stale' || pick.status === 'unlinked' ? 'recall' : 'cleared'}`} style={{ position: 'sticky', top: 0 }}>
            <div className="smallcaps muted">{pick.locator || pick.item_id}</div>
            <div style={{ fontWeight: 600, fontSize: 18 }}>{pick.status}{pick.metric_id ? ` → ${pick.metric_id}` : ''}</div>
            {pick.confidence != null && <div className="t14">confidence {Math.round(pick.confidence * 100)}%</div>}
            <div className="t14" style={{ marginTop: 6 }}>{pick.explanation}</div>
            {chain && <><h4>Who built this, on top of whom</h4>{chain.chain.map((c: Any, i: number) => (
              <div key={i} className="t14" style={{ paddingLeft: c.depth * 14, borderLeft: '2px solid var(--rule)', marginBottom: 6 }}>
                <b>{who(c.who)}</b> · {c.kind}{c.version ? ` v${c.version}` : ''}{c.pinned_at ? ` · pinned ${when(c.pinned_at)}` : ''}<br /><span className="muted">{(c.label || '').toString().slice(0, 120)}</span>{c.value != null && typeof c.value === 'number' ? <span className="num"> = {fig(c.value)}</span> : null}<br /><span className="t14 blue">{c.how}</span></div>))}</>}
          </div>
        ) : <div className="panel t14 muted">Click a highlighted cell or line to see what it was built from. Green: linked to the books. Red: stale or no source. Grey italic: derived from other cells. Blue: a policy term.</div>}
      </div>
    </div>
  )
}

function Graph({ world, id }: { world: World; id: string }) {
  const [d, setD] = useState<Any>(null)
  useEffect(() => { setD(null); api.ripple(world, id).then(setD).catch(() => setD({ error: true })) }, [world, id])
  const { nodes, edges } = useMemo(() => {
    if (!d?.graph) return { nodes: [] as Node[], edges: [] as Edge[] }
    const lanes: string[] = d.graph.lanes
    const used = lanes.filter(l => d.graph.nodes.some((n: Any) => n.lane === l))
    const perLane: Record<string, number> = {}
    const ns: Node[] = d.graph.nodes.map((n: Any) => {
      const li = used.indexOf(n.lane); const k = (perLane[n.lane] = (perLane[n.lane] ?? -1) + 1)
      const st = n.verdict === 'invalidated' ? (n.ping === 'reworked' ? 'reworked' : n.ping === 'needs_human' ? 'caution' : 'invalidated') : n.verdict === 'suspect' ? (n.ping === 'still_valid' ? 'cleared' : n.ping === 'reworked' ? 'reworked' : 'caution') : n.skipped ? 'skipped' : 'cleared'
      return { id: n.id, position: { x: 230 + (n.kind === 'metric' ? 260 : n.kind === 'action' ? 520 : n.kind === 'correction' ? 0 : n.kind === 'ledger' ? 0 : 520) + (k % 4) * 230, y: li * 120 + Math.floor(k / 4) * 84 },
        data: { label: <div className={`dcard ${st}`} style={{ width: 216 }}><div className="r1"><span className="t14 muted">{n.kind}</span><Icon s={st} size={16} /></div><div className="tt">{n.label}</div>
          <div className="r3">{n.old != null && n.new != null && typeof n.old !== 'object' ? <><span className="o">{fig(n.old, n.unit, n.id.replace('M:', ''))}</span><span className="v">{fig(n.new, n.unit, n.id.replace('M:', ''))}</span></> : <span className="w">{reason(n.reason)}</span>}</div></div> },
        style: { background: 'transparent', border: 0, padding: 0, width: 216 } }
    })
    const laneNodes: Node[] = used.map((l, i) => ({ id: `lane:${l}`, position: { x: 0, y: i * 120 - 6 }, data: { label: <div style={{ fontWeight: 600, fontSize: 16, width: 200 }}>{l}</div> }, style: { background: 'transparent', border: 0, width: 210 }, selectable: false, draggable: false }))
    const es: Edge[] = d.graph.edges.map((e: Any, i: number) => ({ id: `e${i}`, source: e.source, target: e.target, className: 'recall' }))
    return { nodes: [...laneNodes, ...ns], edges: es }
  }, [d])
  if (!d) return <div className="muted">Loading the ripple…</div>
  if (d.error) return <div className="panel">No ripple for {id}: it has no correcting entry (for example, a change in estimate already booked).</div>
  return (
    <div style={{ height: 'calc(100vh - 170px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 8 }}><b className="red">{d.counts.invalidated}</b> invalidated · <b className="green">{d.counts.still_valid}</b> still valid · <b className="amber">{d.counts.compensations}</b> compensations · {d.counts.metrics_recomputed} of {d.counts.metrics_total} metrics recomputed in {d.seconds}s · naive {d.counts.naive}
        <span className="muted t14"> · cleared: {Object.entries(d.graph.cleared_by_reason).map(([k, v]) => `${v} ${reason(k)}`).join(', ')}</span></div>
      <div style={{ flex: 1, border: '1px solid var(--rule)', borderRadius: 6 }}><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.2} proOptions={{ hideAttribution: true }}><Background gap={18} size={1} /><Controls showInteractive={false} /></ReactFlow></div>
    </div>
  )
}

const QS: [string, string][] = [['q1_what', '1. What happened'], ['q2_trust', '2. Which source to trust'], ['q3_classification', '3. Error, estimate or new fact'], ['q4_size', '4. How big'], ['q5_matters', '5. Does it matter'], ['q6_touched', '6. What it touched'], ['q7_fix', '7. The fix']]

function Evaluate({ world, id }: { world: World; id: string }) {
  const [d, setD] = useState<Any>(null)
  useEffect(() => { setD(null); api.evaluation(world, id).then(setD).catch(() => setD(null)) }, [world, id])
  if (!d) return <div className="muted">No evaluation for {id}.</div>
  const jfor = (q: string) => (d.jade as Any[]).filter(j => j.claim_key.startsWith(q))
  const summary = (q: string, c: Any): string => {
    if (!c) return ''
    if (q === 'q1_what') return c.root_cause
    if (q === 'q2_trust') return `${c.trusted} over ${c.over}. ${c.why || ''}`
    if (q === 'q3_classification') return `${(c.value || '').replace('_', ' ')}: ${c.rule || ''}`
    if (q === 'q4_size') return `${money(c.amount, { cents: c.amount < 1000 })}; rollover ${money(c.rollover)}, iron curtain ${money(c.iron_curtain)}`
    if (q === 'q5_matters') return `${c.material ? 'Material' : 'Immaterial'}. ${c.why || ''}`
    if (q === 'q6_touched') return c.counts ? `${c.counts.invalidated} invalidated, ${c.counts.still_valid} still valid, ${c.counts.compensations} compensations; agent work: ${Object.entries(c.agent_work || {}).map(([k, v]) => `${k} ${v}`).join(', ')}` : ''
    if (q === 'q7_fix') return `${(c.treatment || '').replace(/_/g, ' ')}${c.posting_period ? `, posting ${c.posting_period}` : ''}${c.orig_period && c.orig_period !== c.posting_period ? ` tagged ${c.orig_period}` : ''}; approvers ${Object.entries(c.approvers || {}).map(([k, v]) => `${k.replace('_', ' ')}: ${who(v as string)}`).join(', ')}`
    return ''
  }
  return (
    <div>
      <h3>{id}: the Error Evaluation, claim by claim</h3>
      <div className="t14 muted" style={{ marginBottom: 8 }}>The agent writes each claim with its evidence (playbook {d.playbook}); Jade recomputes numbers from the engines, checks evidence and authority with code, and critiques only the wording.</div>
      <div className="claim t14 muted" style={{ fontWeight: 600 }}><div>Question</div><div>The agent (and after Jade, when it changed)</div><div>Jade</div></div>
      {QS.map(([q, label]) => {
        const js = jfor(q)
        const changed = JSON.stringify(d.agent[q]) !== JSON.stringify(d.final?.[q])
        return (
          <div key={q} className="claim">
            <div className="q">{label}</div>
            <div>{summary(q, d.agent[q])}{changed && <div className="red" style={{ marginTop: 4 }}>After Jade: {summary(q, d.final[q])}</div>}
              <div className="t14 muted">evidence: {[].concat(d.agent[q]?.evidence || []).join(', ')}</div></div>
            <div className="verdict">{js.length ? js.map(j => <div key={j.claim_key} style={{ marginBottom: 4 }}><Icon s={j.verdict === 'approve' ? 'cleared' : j.verdict === 'overrule' ? 'invalidated' : 'caution'} size={16} /> <b>{j.verdict}</b> {j.claim_key !== q ? <span className="muted">({j.claim_key.replace(q + '.', '')})</span> : null}<div className="t14">{j.why}</div></div>) : <span className="muted">not reviewed</span>}</div>
          </div>
        )
      })}
    </div>
  )
}

function Pings({ world, bump, tick }: { world: World; bump: () => void; tick: number }) {
  const [d, setD] = useState<Any>(null)
  const [s1, setS1] = useState<Any>(null)
  useEffect(() => { api.pings(world).then(setD) }, [world, tick])
  if (!d) return null
  return (
    <div>
      <h3>Trackback pings: one per owner per wave</h3>
      <div className="t14 muted" style={{ marginBottom: 10 }}>Only the hub can ping, only along consumption receipts it recorded at read time (hash-checked), only for material changes, at most once per agent per wave. People get a notice in their inbox, routed to a delegate when they are out.</div>
      {Object.entries(d.waves || {}).map(([k, w]: Any) => w.challenge ? (
        <div key={k} className="panel caution"><b>Upstream challenge</b> ({k}) to {who(w.challenge.to)}: no wave starts unless a human approves it.</div>
      ) : (
        <div key={k} className="panel">
          <div style={{ fontWeight: 600 }}>{k}{w.coalesced ? ` · coalesced (${w.coalesced.join(' + ')}; alone they would ping ${Object.entries(w.solo_pings).map(([a, b]) => `${a}: ${b}`).join(', ')})` : ''}</div>
          {(w.pings || []).map((p: Any) => (
            <div key={p.ping_id} style={{ marginTop: 8 }}><span className="envchip">{p.ping_id} → {who(p.agent)} · {p.state?.replace('_', ' ')}</span>
              {p.items.map((i: Any) => <div key={i.artifact_id} className="t14" style={{ marginLeft: 18, marginTop: 4 }}><Icon s={i.verdict === 'reworked' ? 'reworked' : i.verdict === 'still_valid' ? 'cleared' : 'caution'} size={14} /> <b>{i.artifact_id}</b> {i.verdict.replace('_', ' ')}: {i.reason}
                {i.new_version?.content && <div className="serif" style={{ fontStyle: 'italic' }}>“{i.new_version.content}”</div>}</div>)}
            </div>
          ))}
          {(w.notices || []).map((n: Any) => <div key={n.notice_id} className="t14" style={{ marginTop: 6 }}>Notice to {who(n.to)}{n.routed_because ? ` (${n.routed_because})` : ''}: {n.lines.length} lines in {n.files.join(', ')}</div>)}
          {(w.skipped || []).length > 0 && <div className="t14 muted" style={{ marginTop: 6 }}>Skipped, no material change: {w.skipped.map((s: Any) => s.node_id).join(', ')}</div>}
        </div>
      ))}
      {world === 'tidewall' && <div className="panel">
        <b>S1: an agent revises its own work.</b> The Close Accountant raises its June utilities accrual from $180,000 to $195,000.
        <div style={{ marginTop: 8 }}><button className="btn" onClick={async () => { setS1(await api.s1()); bump() }}>Revise it now</button></div>
        {s1 && <div className="t14" style={{ marginTop: 8 }}>Pinged: {s1.pings.map((p: Any) => `${who(p.agent)} (${p.items.map((i: Any) => `${i.artifact_id} ${i.verdict}`).join(', ')})`).join('; ') || 'nobody'}. Not pinged: {s1.not_pinged.map((n: Any) => `${who(n.agent)}: ${n.reason}`).join('; ')}.</div>}
      </div>}
    </div>
  )
}

const ACTORS: Record<World, string[]> = { tidewall: ['dana', 'sam', 'lena', 'marco'], lyft: ['general_counsel', 'cfo'] }

function Approvals({ world, bump, tick }: { world: World; bump: () => void; tick: number }) {
  const [d, setD] = useState<Any>(null)
  const [msg, setMsg] = useState<string>('')
  const load = () => api.approvals(world).then(setD)
  useEffect(() => { load() }, [world, tick]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!d) return null
  const act = async (p: string) => { const r = await api.act(world, p); setMsg(`${who(p)}: ${r.results.map((x: Any) => `${x.action_id} ${x.decision}${x.redraft ? ` (re-draft ${x.redraft})` : ''}`).join(', ') || 'nothing waiting'}`); bump(); load() }
  const selfApprove = async (id: string) => { const r = await api.decide(world, id, world === 'lyft' ? 'lyft_ir' : 'close_accountant', 'approved', 'approving my own work'); setMsg(r.refused ? `Refused: ${r.error}` : 'approved?'); bump(); load() }
  return (
    <div>
      <h3>Approvals</h3>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        {ACTORS[world].map(p => <button key={p} className="btn" onClick={() => act(p)}>Act as {who(p)}</button>)}
        {world === 'tidewall' && <><button className="btn ghost" onClick={async () => { const r = await api.advance(8); setMsg(`Clock ${when(r.clock)}: ${r.reminded.length} reminders, ${r.escalated.length} escalations`); bump(); load() }}>Fast-forward 8 hours</button>
          <span className="pill">clock {when(d.clock)}</span></>}
      </div>
      {msg && <div className="panel caution t14">{msg}</div>}
      <table className="ledger-table"><thead><tr><th>Item</th><th>To</th><th>State</th><th>Why it reached them</th><th /></tr></thead>
        <tbody>{(d.items as Any[]).map(a => (
          <tr key={a.action_id}><td><b>{a.action_id}</b><div className="t14">{a.summary}</div></td><td>{who(a.assignee)}{a.escalated_to ? ` → ${who(a.escalated_to)}` : ''}</td>
            <td><Icon s={a.state === 'rejected' ? 'invalidated' : a.state === 'executed' || a.state === 'acknowledged' ? 'cleared' : 'caution'} size={16} /> {a.state}</td>
            <td className="t14">{(a.approvals || []).map((x: Any) => `${who(x.approver)} ${x.decision}: ${x.reason}`).join(' · ') || a.params?.routed || a.kind?.replace(/_/g, ' ')}</td>
            <td>{a.state === 'proposed' && <button className="btn ghost" title="The proposer tries to approve its own work" onClick={() => selfApprove(a.action_id)}>Self-approve</button>}</td></tr>
        ))}</tbody></table>
      {d.holds?.length > 0 && <><h4>Holds</h4>{d.holds.map((h: Any) => <div key={h.hold_id} className="t14"><Icon s={h.state === 'held' ? 'caution' : 'cleared'} size={14} /> {h.target}: {h.state} ({h.reason})</div>)}</>}
    </div>
  )
}

function Memo({ world, id }: { world: World; id: string }) {
  const [m, setM] = useState<Any>(null)
  useEffect(() => { setM(null); api.memo(world, id).then(r => setM(r._status === 404 ? { none: true } : r)) }, [world, id])
  if (!m) return null
  if (m.none) return <div className="panel">No memo for {id}: memos are written for material exceptions only.</div>
  const download = () => { const b = new Blob([m.markdown], { type: 'text/markdown' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `memo_${id}.md`; a.click() }
  return <div><div style={{ display: 'flex', gap: 8, marginBottom: 8 }}><button className="btn" onClick={download}>Download Markdown</button><span className="pill">version {m.version}</span></div>
    <div className="panel memohtml" dangerouslySetInnerHTML={{ __html: m.html }} /></div>
}

const SOURCES: Record<World, string[]> = { tidewall: ['billing_release_lines', 'gl_import_log', 'ap_invoices', 'bank_statement_2026_06', 'covenant_workbook', 'compliance_certificate'], lyft: ['lyft_release', 'lyft_fpa_model', 'lyft_close_pack'] }

function TimeTravel({ world }: { world: World }) {
  const [src, setSrc] = useState(SOURCES[world][0])
  const [tm, setTm] = useState<Any>(null)
  const [pin, setPin] = useState(world === 'lyft' ? '2024-02-13T16:20' : '2026-04-09T18:00')
  const [gate, setGate] = useState<Any>(null)
  const [peek, setPeek] = useState<Any>(null)
  useEffect(() => { setSrc(SOURCES[world][0]); setPin(world === 'lyft' ? '2024-02-13T16:20' : '2026-04-09T18:00') }, [world])
  useEffect(() => { api.timemap(src).then(setTm); setPeek(null); setGate(null) }, [src])
  const tz = world === 'lyft' ? '-05:00' : '-07:00'
  const check = async () => setGate(await api.timegate(src, `${pin}:00${tz}`))
  return (
    <div>
      <h3>Time travel (Replay)</h3>
      <div className="t14 muted" style={{ marginBottom: 10 }}>Every source keeps every version with the time it was captured. A read pinned to a time never returns a version captured later: before the first version it refuses (404), and a later version is refused (403) with both timestamps. Not RFC 7089's "nearest memento"; never HTTP 425.</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
        {SOURCES[world].map(s => <button key={s} className={`btn ${s === src ? 'primary' : ''}`} onClick={() => setSrc(s)}>{s.replace(/_/g, ' ')}</button>)}
      </div>
      {tm && <div className="panel"><b>{tm.title}</b>{tm.versions.map((v: Any) => <div key={v.version_id} className="t14">{v.version_id} · captured {when(v.captured_at)} {v.note ? `· ${v.note}` : ''}</div>)}</div>}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input className="field" type="datetime-local" value={pin} onChange={e => setPin(e.target.value)} />
        <button className="btn primary" onClick={check}>Read as of this time</button>
        <button className="btn recall" onClick={async () => setPeek(await api.attempt(src, `${pin}:00${tz}`))}>Try to make it peek</button>
      </div>
      {gate && <div className={`panel ${gate.status >= 400 ? 'recall' : 'cleared'}`} style={{ marginTop: 10 }}>{gate.version ? <>Served <b>{gate.version.version_id}</b>, captured {when(gate.version.captured_at)}.</> : <><b>{gate.status} {gate.title}</b>: {gate.detail}</>}</div>}
      {peek && (peek.refused ? <div style={{ marginTop: 14 }}><span className="stamp stamp-in">REFUSED · {peek.status} · captured {when(peek.problem.requested)} · pinned {when(peek.problem.pinned_at)}</span></div> : <div className="panel cleared">Served: the latest version was already captured at that time.</div>)}
    </div>
  )
}

function Scorecard() {
  const [d, setD] = useState<Any>(null)
  useEffect(() => { api.scorecard().then(setD) }, [])
  if (!d || !d.configs) return <div className="panel">Run <span className="kbd">python tasks.py eval</span> to write data/eval/latest.json.</div>
  const cols = Object.keys(d.configs)
  return (
    <div>
      <h3>Scorecard</h3>
      <div className="t14 muted">Every number below is computed by <span className="kbd">python tasks.py eval</span> from runs against the answer key ({d.answer_key.sha256.slice(0, 12)}), {d.cases.n} cases ({Object.entries(d.cases.by_family).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(', ')}). Generated {d.generated_at}.</div>
      <table className="ledger-table" style={{ marginTop: 10 }}><thead><tr><th>Step</th>{cols.map(c => <th key={c} className="n">{c.replace(/_/g, ' ')}</th>)}</tr></thead>
        <tbody>{['detect', 'classify', 'size', 'materiality', 'materiality_small_covenant_breaking', 'fix', 'cases'].map(s => (
          <tr key={s}><td>{s.replace(/_/g, ' ')}</td>{cols.map(c => { const v = d.configs[c][s]; return <td key={c} className="n">{v ? (v.n ? `${v.correct ?? v.passed}/${v.n}` : '—') : '—'}</td> })}</tr>))}</tbody></table>
      <div className="grid-cards" style={{ marginTop: 14 }}>
        <div className="panel"><b>Jade</b><div className="t14">caught {d.jade.caught} of {d.jade.planted_mistakes} planted mistakes; {d.jade.false_overrules} false overrules on {d.jade.correct_claims} correct claims</div></div>
        <div className="panel"><b>Lineage</b><div className="t14">{d.lineage.correct}/{d.lineage.truths} links; stale detection {d.lineage.stale_detection}; min confidence {d.lineage.min_confidence}</div></div>
        <div className="panel"><b>Impact (X1)</b><div className="t14">{d.impact.X1?.invalidated} invalidated, {d.impact.X1?.still_valid} still valid, {d.impact.X1?.compensations} compensations; precision {d.impact.X1?.precision}, recall {d.impact.X1?.recall}; reasons {d.impact.X1?.reasons_correct}; naive {d.impact.X1?.naive_flagged}</div></div>
        <div className="panel"><b>Replay</b><div className="t14">{d.replay.leaked} leaks in {d.replay.adversarial_fetches} adversarial fetches</div></div>
        <div className="panel"><b>Pings (X1)</b><div className="t14">agents {d.iteration2.x1.agents_pinged.join(', ')}; precision {d.iteration2.x1.ping_precision}, recall {d.iteration2.x1.ping_recall}; false still_valid {d.iteration2.x1.false_still_valid}; unnecessary rework {d.iteration2.x1.unnecessary_rework}; inspection {Math.round(d.iteration2.x1.inspection_fraction * 100)}%</div></div>
        <div className="panel"><b>Lyft</b><div className="t14">detect {Math.round(d.lyft.detect_accuracy * 100)}% on {d.lyft.detect_cases.length} cases; {d.lyft.trace.tied}/{d.lyft.trace.figures} figures tie; v1 {d.lyft.v1.material ? 'material' : 'immaterial'} → v2 {d.lyft.v2.material ? 'material' : 'immaterial'}; fence blocked inside: {String(d.lyft.fence_blocked_inside)}</div></div>
      </div>
      <h4>Real vs simulated</h4>
      <div className="grid-cards"><div className="panel"><b>Real</b>{d.real_vs_simulated.real.map((x: string) => <div key={x} className="t14">· {x}</div>)}</div><div className="panel"><b>Simulated</b>{d.real_vs_simulated.simulated.map((x: string) => <div key={x} className="t14">· {x}</div>)}</div></div>
    </div>
  )
}

function Lessons() {
  const [d, setD] = useState<Any>(null)
  useEffect(() => { api.lessons().then(setD) }, [])
  if (!d) return null
  const L = d.learning
  return (
    <div>
      <h3>Lessons</h3>
      <div className="t14 muted">Mistake signals are never the agent grading itself: Jade's overrules and the Controller's rejection. Each lesson is a check in the playbook; it needs Dana's approval and must pass the regression gate (the whole scorecard rerun; any previously passing check that fails rejects it).</div>
      {L && <><div className="grid-cards" style={{ marginTop: 12 }}>{L.lessons.map((l: Any) => (
        <div key={l.lesson} className={`panel ${l.gate === 'pass' ? 'cleared' : 'recall'}`}><b>{l.lesson.replace(/_/g, ' ')}</b><div className="t14">gate: <b>{l.gate}</b>{l.fixed ? ` · fixed ${l.fixed} checks` : ''}</div>{l.broke?.length > 0 && <div className="t14 red">broke: {l.broke.join(', ')}</div>}</div>))}</div>
        <h4>Held-out cases, agent alone</h4>
        <div className="t14">v1 passes {L.heldout.v1.cases.passed}/{L.heldout.v1.cases.n}; v2 ({L.playbook}) passes {L.heldout.v2.cases.passed}/{L.heldout.v2.cases.n}.</div></>}
    </div>
  )
}

function Access() {
  const [d, setD] = useState<Any>(null)
  useEffect(() => { api.access().then(setD) }, [])
  if (!d) return null
  return (
    <div><h3>Access</h3><div className="grid-cards">
      <div className="panel cleared"><b>Reads</b>{d.reads.map((x: string) => <div key={x} className="t14">· {x}</div>)}</div>
      <div className="panel caution"><b>Drafts only</b>{d.drafts_only.map((x: string) => <div key={x} className="t14">· {x}</div>)}</div>
      <div className="panel recall"><b>Never</b>{d.never.map((x: string) => <div key={x} className="t14">· {x}</div>)}</div>
    </div><div className="t14 muted">{d.evidence}</div></div>
  )
}

export { lev }
