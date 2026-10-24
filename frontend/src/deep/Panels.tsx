import { useEffect, useMemo, useState } from 'react'
import { X as Close, Search } from 'lucide-react'
import { api, dateLabel, dayLabel, fmt } from '../api'
import { title } from '../labels'
import { LANES, laneOf, stateOf, reasonText, STATE_WORD, compText, agentLane, pingStory, type State } from '../model'
import { StatusIcon, Lot, Seg, Envelope, RefusalStamp, Empty } from '../ui/primitives'

/* ---------------------------------------------------------------- counter strip */
export function CounterStrip({ company, correction, graph, pings, waves, approvalsPending, headline, onRecall, evaluation, onJade }: { company: string; correction: string | null; graph: any; pings: any[]; waves: any[]; approvalsPending: number; headline: any; onRecall?: () => void; evaluation?: any; onJade?: () => void }) {
  const agents = LANES[company].filter(l => !['sources', 'trackback', 'humans'].includes(l.id)).length
  const pinged = new Set(pings.map(p => p.target_agent_id)).size
  const inspected = graph ? graph.nodes.filter((n: any) => n.verdict && !['different_period', 'different_line_item', 'claim_unchanged'].includes(n.reason || '')).length : 0
  const total = graph ? graph.nodes.filter((n: any) => n.type === 'artifact').length : 0
  const st = waves[0]?.stats_json ? JSON.parse(waves[0].stats_json) : null
  return (
    <div style={{ height: 52, flex: 'none', display: 'flex', alignItems: 'center', gap: 32, padding: '0 20px', borderBottom: '1px solid var(--rule)', background: 'var(--paper)' }}>
      {correction ? <div className="serif" style={{ fontSize: 30, lineHeight: 1 }}><span className="num" style={{ fontFamily: 'var(--serif)' }}>{pinged} of {agents}</span> agents pinged</div>
        : <div className="serif" style={{ fontSize: 24, fontStyle: 'italic', color: 'var(--ink-muted)' }}>Nothing's been recalled. Yet.</div>}
      {!correction && onRecall && <button className="btn primary" style={{ marginLeft: 'auto' }} onClick={onRecall}>A recall notice arrived</button>}
      {correction && <div className="mono t14" style={{ display: 'flex', gap: 24, color: 'var(--ink)' }}>
        <span title="How many pieces of work Trackback had to look at; the rest were cleared structurally (different period, different line, never read the changed rows)"><span className="muted">looked at</span> {inspected} of {total} pieces of work</span>
        <span title="Model calls spent on this correction, against what rerunning every agent from scratch would cost"><span className="muted">LLM calls</span> {st?.llm_calls ?? 0} <span className="muted">(rerunning every agent: {headline?.llm_calls_rerun_all ?? '…'})</span></span>
        <span title="Fixes for actions that already happened (a sent certificate, a paid bonus), waiting for the right person to approve"><span className="muted">fixes waiting for a person</span> {approvalsPending}</span>
      </div>}
      {correction && evaluation && <button className={`chip ${evaluation.jade?.summary?.overruled ? 'recall' : 'cleared'}`} style={{ marginLeft: 'auto', height: 28, cursor: 'pointer', fontSize: 14 }} onClick={onJade} title="J">
        Jade · {evaluation.jade?.summary?.overruled ? `overruled ${evaluation.jade.summary.overruled_claims.join(', ')}` : 'every claim approved'} · playbook {evaluation.playbook_version}</button>}
    </div>
  )
}

/* ---------------------------------------------------------------- left sidebar: results of the current correction, and Built on / Built upon */
export function Sidebar({ company, correction, graph, pings, selected, onSelect, traceMode, setTraceMode, traceIds }: { company: string; correction: string | null; graph: any; pings: any[]; selected: string | null; onSelect: (id: string) => void
  traceMode: 'on' | 'upon'; setTraceMode: (m: 'on' | 'upon') => void; traceIds: string[] }) {
  const [q, setQ] = useState('')
  const pinged = useMemo(() => new Set<string>(pings.flatMap((p: any) => (p.items || []).map((i: any) => i.artifact_id))), [pings])
  const rows = useMemo(() => {
    if (!graph || !correction) return []
    const order: Record<State, number> = { caution: 0, invalidated: 1, reworked: 2, cleared: 3, skipped: 4, idle: 9, superseded: 9, pending: 9 }
    return graph.nodes.filter((n: any) => n.verdict && n.type === 'artifact').map((n: any) => ({ n, s: stateOf(n, pinged) }))
      .filter((r: any) => !q || title(r.n).toLowerCase().includes(q.toLowerCase())).sort((a: any, b: any) => order[a.s as State] - order[b.s as State] || (a.n.hop ?? 0) - (b.n.hop ?? 0))
  }, [graph, correction, pinged, q])
  const c = (s: State) => rows.filter((r: any) => r.s === s).length
  return (
    <aside style={{ width: 260, borderRight: '1px solid var(--rule)', display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 }}>
      {selected && <div style={{ borderBottom: '1px solid var(--rule)', padding: '12px 14px' }}>
        <div className="t14 muted">Selected</div>
        <div style={{ fontWeight: 600, fontSize: 16, lineHeight: 1.25, margin: '2px 0 8px' }}>{title({ id: selected }, 60)}</div>
        <Seg value={traceMode} onChange={setTraceMode} options={[{ v: 'on', label: 'Built on' }, { v: 'upon', label: 'Built upon' }]} />
        <div className="t14" style={{ marginTop: 8, maxHeight: 132, overflow: 'auto' }}>
          {traceIds.length === 0 ? <span className="muted">{traceMode === 'on' ? 'Rests directly on sources.' : 'Nothing rests on it yet.'}</span>
            : traceIds.slice(0, 12).map(id => <div key={id} className="row" style={{ padding: '4px 0', borderBottom: 0 }} onClick={() => onSelect(id)}>{title({ id }, 44)}</div>)}
          {traceIds.length > 12 && <div className="muted">and {traceIds.length - 12} more</div>}
        </div>
      </div>}
      <div style={{ padding: '12px 14px 8px' }}>
        <div style={{ position: 'relative' }}><Search size={16} strokeWidth={1.5} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--ink-muted)' }} />
          <input className="field" style={{ width: '100%', paddingLeft: 32 }} placeholder="Filter results" value={q} onChange={e => setQ(e.target.value)} aria-label="Filter results" /></div>
        <div className="t14 muted" style={{ marginTop: 8 }}>{correction ? `${c('invalidated')} invalidated · ${c('cleared') + c('skipped')} cleared · ${c('caution')} need a human · ${c('reworked')} reworked · sorted by impact` : 'No correction selected'}</div>
      </div>
      <div className="scroll" style={{ flex: 1, minHeight: 0 }}>
        {!correction && <Empty>Nothing's been recalled. Yet.</Empty>}
        {rows.map(({ n, s }: any) => <button key={n.id} className={`row ${selected === n.id ? 'on' : ''}`} onClick={() => onSelect(n.id)}>
          <StatusIcon state={s} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontWeight: 500, lineHeight: 1.25 }}>{title(n, 54)}</div>
            <div className="muted" style={{ fontSize: 13 }}>{agentLane(company, n.agent_id || '')?.name || 'Trackback'} · {s === 'skipped' ? 'skipped, no material change' : reasonText(n.reason)}</div>
          </div>
          {n.old_value != null && n.new_value != null && n.old_value !== n.new_value && <div className="mono" style={{ fontSize: 13, textAlign: 'right', whiteSpace: 'nowrap' }}>{fmt(n.new_value, n.line_item)}</div>}
        </button>)}
      </div>
    </aside>
  )
}

/* ---------------------------------------------------------------- right drawer */
export type DrawerTab = 'who' | 'history' | 'approvals' | 'pings' | 'review' | 'lessons' | 'norms'
export function Drawer({ tab, setTab, onClose, selected, company, refreshKey, onChanged, people, pings, waves, challenges, correction }: { tab: DrawerTab; setTab: (t: DrawerTab) => void; onClose: () => void; selected: string | null; company: string
  refreshKey: number; onChanged: () => void; people: Record<string, string>; pings: any[]; waves: any[]; challenges: any[]; correction?: string | null }) {
  const tabs: [DrawerTab, string][] = [['who', 'Built it'], ['history', 'History'], ['approvals', 'Approvals'], ['pings', 'Pings'], ['review', 'Jade'], ['lessons', 'Lessons'], ['norms', 'Norms']]
  return (
    <div className="drawer" role="complementary" aria-label="Details">
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div className="tabs" style={{ flex: 1 }}>{tabs.map(([t, l]) => <button key={t} className={`tab ${tab === t ? 'on' : ''}`} onClick={() => setTab(t)}>{l}</button>)}</div>
        <button className="btn ghost" style={{ height: 32, padding: '0 8px', marginRight: 8 }} onClick={onClose} aria-label="Close drawer"><Close size={18} strokeWidth={1.5} /></button>
      </div>
      <div className="scroll" style={{ flex: 1, padding: '14px 16px' }}>
        {tab === 'who' && <WhoBuilt id={selected} company={company} refreshKey={refreshKey} />}
        {tab === 'history' && <ClaimHistory id={selected} refreshKey={refreshKey} />}
        {tab === 'approvals' && <Approvals refreshKey={refreshKey} onChanged={onChanged} people={people} company={company} />}
        {tab === 'pings' && <PingLog pings={pings} waves={waves} challenges={challenges} company={company} />}
        {tab === 'review' && <Review correction={correction || null} refreshKey={refreshKey} />}
        {tab === 'lessons' && <Lessons refreshKey={refreshKey} onChanged={onChanged} people={people} />}
        {tab === 'norms' && <Norms refreshKey={refreshKey} onChanged={onChanged} people={people} />}
      </div>
    </div>
  )
}

function WhoBuilt({ id, company, refreshKey }: { id: string | null; company: string; refreshKey: number }) {
  const [chain, setChain] = useState<any[] | null>(null)
  useEffect(() => {
    if (!id) { setChain(null); return }
    let alive = true
    ;(async () => {
      const seen = new Set<string>(); const out: any[] = []
      const walk = async (aid: string, depth: number) => {
        if (seen.has(aid) || depth > 7) return; seen.add(aid)
        const r = await api.artifact(aid); out.push({ depth, ...r.artifact, supporters: r.supporters })
        const arts = r.supporters.filter((s: any) => s.supporter_kind === 'artifact')
        for (const s of arts.slice(0, 3)) await walk(s.supporter_id, depth + 1)
        if (!arts.length) { const src = r.supporters.find((s: any) => s.claim); if (src) out.push({ depth: depth + 1, source: src.claim.source_id, captured: src.claim.tx_from, version: src.supporter_version }) }
      }
      await walk(id, 0); if (alive) setChain(out)
    })()
    return () => { alive = false }
  }, [id, refreshKey])
  if (!id) return <Empty>Select a card to see who built it, on top of whom.</Empty>
  if (!chain) return <div className="muted">Reading the receipts…</div>
  return <div>
    <div className="t14 muted" style={{ marginBottom: 10 }}>Each line is a receipt: who made it, from which version of what.</div>
    {chain.map((a, i) => a.source ? <div key={i} style={{ marginLeft: a.depth * 14, borderLeft: '2px solid var(--ink)', padding: '4px 0 8px 10px' }}>
      <div className="t14"><b>Source</b> · {a.source.replace(/_/g, ' ')}</div><div className="mono" style={{ fontSize: 13 }}>captured {dateLabel(a.captured)}</div></div>
      : <div key={i} style={{ marginLeft: a.depth * 14, borderLeft: `2px solid ${a.depth === 0 ? 'var(--ink)' : 'var(--rule)'}`, padding: '4px 0 8px 10px' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Lot code={a.lot} /><span className="mono" style={{ fontSize: 13 }}>v{a.version}</span></div>
        <div style={{ fontWeight: 600, fontSize: 16, lineHeight: 1.25, marginTop: 2 }}>{title(a, 70)}</div>
        <div className="t14 muted">by {agentLane(company, a.agent_id || '')?.name || (a.agent_id || 'Trackback').replace(/_/g, ' ')} · {dateLabel(a.pinned_at)}{a.kind !== 'sentence' && a.value_num != null ? '' : ''}</div>
        {a.kind !== 'sentence' && a.value_num != null && <div className="mono t16">{fmt(a.value_num, a.line_item)}</div>}
      </div>)}
  </div>
}

function ClaimHistory({ id, refreshKey }: { id: string | null; refreshKey: number }) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { if (id) api.artifact(id).then(setD).catch(() => setD(null)); else setD(null) }, [id, refreshKey])
  if (!id) return <Empty>Select a card to see its versions and what each rested on.</Empty>
  if (!d) return <div className="muted">Loading…</div>
  const a = d.artifact
  return <div>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Lot code={a.lot} /><span className="t14 muted">{a.kind} · {a.period}</span></div>
    <div className={a.kind === 'sentence' ? 'serif' : ''} style={{ fontSize: a.kind === 'sentence' ? 18 : 22, fontWeight: 600, fontStyle: a.kind === 'sentence' ? 'italic' : undefined, margin: '6px 0' }}>{a.kind === 'sentence' ? `“${(a.content || '').replace(/\s*\(corrected[^)]*\)/g, '')}”` : title(a)}</div>
    <table className="ledger-table" style={{ marginTop: 8 }}><thead><tr><th>Version</th><th>Recorded</th><th className="n">Value</th></tr></thead><tbody>
      {d.versions.map((v: any) => <tr key={v.version} className={v.status === 'superseded' ? '' : ''}><td className="mono">v{v.version} <span className="muted">{v.origin === 'rerender' ? 'updated in place' : v.origin === 'rework' ? 'reworked' : v.origin === 'revision' ? 'revised' : ''}</span></td>
        <td className="mono">{dateLabel(v.tx_from)}</td><td className="n"><span className={v.status === 'superseded' ? 'strike' : ''}>{v.kind === 'sentence' ? '' : fmt(v.value_num, v.line_item)}</span></td></tr>)}
    </tbody></table>
    <div style={{ fontWeight: 600, margin: '14px 0 4px' }}>Rests on</div>
    <table className="ledger-table"><tbody>{d.supporters.slice(0, 14).map((s: any) => { const c = s.claim; const art = s.artifact; const stale = c ? c.tx_to !== '9999-12-31T00:00:00+00:00' : art?.status !== 'valid'
      return <tr key={s.edge_id}><td><Lot code={s.lot} /></td><td>{c ? `${(c.line_item || '').replace(/_/g, ' ')}${c.entity ? ' · ' + c.entity : ''}` : title(art, 40)}<div className="muted" style={{ fontSize: 13 }}>{c ? (c.source_id || '').replace(/_/g, ' ') : `v${art?.version}`}</div></td>
        <td className="n"><span className={stale ? 'strike' : ''}>{c ? (c.value_num != null ? fmt(c.value_num, c.line_item) : c.value_text) : fmt(art?.value_num, art?.line_item)}</span></td></tr> })}</tbody></table>
  </div>
}

export function Approvals({ refreshKey, onChanged, people, company }: { refreshKey: number; onChanged: () => void; people: Record<string, string>; company: string }) {
  const [d, setD] = useState<any>(null); const [msg, setMsg] = useState<string | null>(null); const [all, setAll] = useState(false)
  useEffect(() => { api.approvals().then(setD) }, [refreshKey])
  if (!d) return <div className="muted">Loading the inbox…</div>
  const mine = (a: any) => (company === 'lyft') === /lyft/.test(a.action_id)
  const rej = (a: any) => (a.approvals || []).some((p: any) => p.decision === 'rejected')
  const rank = (a: any) => (/e11|E11/.test(a.action_id) || a.run_id === 'correction:E11' || /R1[23]_E11|e11/i.test(a.run_id || '') ? 0 : 10) + (rej(a) ? 0 : a.state === 'proposed' ? 1 : 2)
  const rows = d.actions.filter((a: any) => mine(a) && (all || a.state === 'proposed' || rej(a))).sort((a: any, b: any) => rank(a) - rank(b))
  const roleName = (r: string) => (d.roles[r] || r).replace(/_/g, ' ')
  const decide = async (a: any, decision: string, approver: string, reason: string) => {
    setMsg(null)
    try { const r = await api.decide(a.action_id, approver, decision, reason); setMsg(`${decision === 'approved' ? 'Approved' : 'Rejected'}${r.execution ? (r.execution.executed ? ' and executed' : ', blocked by the fence') : ''}.`); onChanged() }
    catch (e) { setMsg(String(e).replace(/^Error: /, '')) }
  }
  const preset = (a: any) => a.params?.period_locked ? 'Q1 is locked; book in Q2 with an out-of-period tag' : 'Needs more support'
  return <div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}><span className="t14 muted">{rows.length} memo{rows.length === 1 ? '' : 's'}</span><button className="btn" style={{ height: 30 }} onClick={() => setAll(x => !x)}>{all ? 'Open only' : 'Show all'}</button></div>
    {msg && <div className="memo" style={{ background: 'var(--caution-wash)' }}>{msg}</div>}
    {rows.length === 0 && <Empty>Nothing waiting for a person.</Empty>}
    {rows.map((a: any) => {
      const roles = (a.approver_role || 'controller').split('+'); const approver = people[roles[0]] || roleName(roles[0])
      const rejected = (a.approvals || []).find((p: any) => p.decision === 'rejected')
      return <div key={a.action_id} className={`memo ${a.params?.period_locked || rejected ? 'locked' : a.state === 'proposed' ? 'waiting' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><span className="mono t14 muted">MEMO · {a.kind.replace(/_/g, ' ').toUpperCase()}</span><span className={`chip ${a.state === 'proposed' ? 'caution' : rejected ? 'recall' : 'cleared'}`}>{a.state === 'proposed' ? 'waiting' : rejected ? 'rejected' : a.state.replace(/_/g, ' ')}</span></div>
        <div className="t16" style={{ fontWeight: 600, margin: '6px 0' }}>{a.params?.summary || a.params?.memo}</div>
        {a.params?.lines && <table className="ledger-table" style={{ margin: '4px 0 8px' }}><tbody>{a.params.lines.map((l: any, i: number) => <tr key={i}><td>{l.amount_cents > 0 ? 'Dr' : 'Cr'} {l.account}{l.gym ? ` · ${l.gym}` : ''}</td><td className="n">{fmt(Math.abs(l.amount_cents / 100))}</td></tr>)}</tbody></table>}
        {a.params?.lines && <div className="t14 muted">Posts to <span className="mono">{a.params.posting_period}</span>{a.params.out_of_period ? <>, tagged to <span className="mono">{a.params.orig_period}</span> (out of period)</> : null}</div>}
        {a.params?.period_locked && <div className="t14" style={{ color: 'var(--recall)', fontWeight: 600 }}>Period {a.params.posting_period} is locked.</div>}
        {a.params?.amount != null && <div className="t14">Amount <span className="mono">{fmt(Math.abs(a.params.amount))}</span></div>}
        <div className="t14 muted" style={{ marginTop: 6 }}>From {(a.proposer || '').replace('agent:', '').replace('trackback:engine', 'Trackback').replace(/_/g, ' ')} · for {roles.map(roleName).join(' and ')}</div>
        {rejected && <div className="t14" style={{ marginTop: 6, color: 'var(--recall)' }}>Rejected by {rejected.approver}: “{rejected.reason}”</div>}
        {a.state === 'proposed' && <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <button className="btn primary" onClick={() => decide(a, 'approved', approver, 'approved')}>Approve as {approver}</button>
          <button className="btn" onClick={() => decide(a, 'rejected', approver, preset(a))}>Reject: “{preset(a).slice(0, 30)}…”</button>
          <button className="btn ghost" title="A CHECK constraint stops anyone approving their own proposal" onClick={() => decide(a, 'approved', a.proposer, 'self-approve')}>Try self-approve</button>
        </div>}
      </div>
    })}
  </div>
}

function PingLog({ pings, waves, challenges, company }: { pings: any[]; waves: any[]; challenges: any[]; company: string }) {
  const [comps, setComps] = useState<Record<string, any>>({})
  useEffect(() => { api.approvals().then(d => { const m: Record<string, any> = {}; d.actions.forEach((a: any) => { if (a.params?.compensates) { const art = a.params.compensates.replace(/^ACT-/, ''); m[art] = a } }); setComps(m) }) }, [pings])
  if (!pings.length) return <Empty>No pings yet. Nothing's been recalled.</Empty>
  const st = waves[0]?.stats_json ? JSON.parse(waves[0].stats_json) : null
  return <div>
    {st && <div className="mono t14 muted" style={{ marginBottom: 12 }}>wave 1 · {st.pings} pings · {st.suspects} items · {st.llm_calls || 0} LLM calls</div>}
    {pings.map((p: any) => { const s = pingStory(p, comps); const lane = agentLane(company, p.target_agent_id)
      return <div key={p.ping_id} className="memo" style={{ paddingTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><b>To {lane?.name || p.target_agent_id}</b><Envelope postmark={s.postmark} /></div>
        <div className="t16" style={{ margin: '8px 0' }}>{s.ask}</div>
        <div className="t16" style={{ color: s.replyTone === 'caution' ? 'var(--caution-ink)' : s.replyTone === 'reworked' ? 'var(--ping)' : s.replyTone === 'cleared' ? 'var(--cleared)' : 'var(--ink)' }}>{s.reply}</div>
        {s.extra.map((x, k) => <div key={k} className="t14" style={{ color: x.startsWith('Still') ? 'var(--cleared)' : x.startsWith('Reworked') ? 'var(--ping)' : 'var(--caution-ink)' }}>{x}</div>)}
        <details style={{ marginTop: 6 }}><summary className="t14 muted" style={{ cursor: 'pointer' }}>All {p.n_items} items</summary>
          {(p.response?.items || []).map((it: any, i: number) => <div key={i} className="t14" style={{ display: 'flex', gap: 6, padding: '4px 0' }}><StatusIcon state={it.verdict === 'still_valid' ? 'cleared' : it.verdict === 'reworked' ? 'reworked' : 'caution'} /><span>{title({ id: it.artifact_id }, 60)}</span></div>)}
        </details>
      </div> })}
    {challenges.map((c: any) => <div key={c.challenge_id} className="memo waiting"><b>{agentLane(company, c.from_agent_id)?.name} questioned {title({ id: c.target_artifact_id })}</b><div className="t14" style={{ marginTop: 4 }}>{c.reason}</div><div className="t14 muted" style={{ marginTop: 4 }}>Agents cannot ping each other; a person decides.</div></div>)}
  </div>
}

function Norms({ refreshKey, onChanged, people }: { refreshKey: number; onChanged: () => void; people: Record<string, string> }) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api.norms().then(setD) }, [refreshKey])
  if (!d) return <div className="muted">Loading…</div>
  return <div>{d.norms.map((n: any) => <div key={n.norm_id} className={`memo ${n.status === 'approved' ? '' : 'waiting'}`}>
    <div style={{ display: 'flex', justifyContent: 'space-between' }}><b>{n.name}</b><span className={`chip ${n.status === 'approved' ? 'cleared' : 'caution'}`}>{n.status}</span></div>
    <div className="t14" style={{ marginTop: 4 }}>Learned from {n.evidence.n} past closes{n.evidence.median_residual_pct != null ? `, median +${n.evidence.median_residual_pct}%` : ''}. {n.status === 'approved' ? `Approved by ${n.approved_by}, from ${n.valid_from}, never applied backwards.` : 'Inactive until the Controller approves.'}</div>
    {n.status === 'proposed' && <button className="btn primary" style={{ marginTop: 8 }} onClick={async () => { await api.approveNorm(n.norm_id, people.controller); onChanged() }}>Approve as {people.controller}</button>}
  </div>)}</div>
}

/* ---------------------------------------------------------------- Jade: the agent's four judgment calls, checked claim by claim */
const CLAIM_WORD: Record<string, string> = { classification: 'What is it?', materiality: 'Does it matter?', posting: 'Where to book it?', routing: 'Who approves?' }
const val = (k: string, v: any) => k === 'materiality' ? (v ? 'material' : 'not material') : Array.isArray(v) ? v.map(r => r.replace(/_/g, ' ')).join(' + ') : String(v)
export function Review({ correction, refreshKey }: { correction: string | null; refreshKey: number }) {
  const [ev, setEv] = useState<any>(null); const [missing, setMissing] = useState(false)
  useEffect(() => { setMissing(false); if (!correction) { setEv(null); return } api.evaluation(correction).then(setEv).catch(() => { setEv(null); setMissing(true) }) }, [correction, refreshKey])
  if (!correction) return <Empty>Drop a recall notice first. Jade reviews the agent's call on every correction.</Empty>
  if (missing) return <Empty>No review for this correction.</Empty>
  if (!ev) return <div className="muted">Reading Jade's notes…</div>
  const j = ev.jade; const over = j.summary?.overruled || 0
  return <div>
    <div className="t14 muted">Jade is a second AI that checks the agent's judgment against the engines: Memento for timing, the materiality memo and the graph, the period locks, the approval matrix. She never writes a number.</div>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '12px 0 4px' }}><span className={`chip ${over ? 'recall' : 'cleared'}`}>{over ? `${over} of 4 overruled` : '4 of 4 approved'}</span><span className="chip">playbook {ev.playbook_version}</span><span className="mono t14 muted">{dateLabel(ev.ts)}</span></div>
    {ev.recalled?.length > 0 && <div className="memo" style={{ marginTop: 10, background: 'var(--ping-wash)' }}><b className="t14">Recalled from memory</b>
      {ev.recalled.map((r: any) => <div key={r.lesson_id} className="t14" style={{ marginTop: 4 }}><span className="mono">{r.lesson_id}</span> · {Math.round(r.score * 100)}% like {r.from_case} · {r.applied ? <span style={{ color: 'var(--cleared)' }}>applied</span> : <span style={{ color: 'var(--caution-ink)' }}>{r.status}, not yet active</span>}<div className="muted">{r.rule}</div></div>)}</div>}
    {['classification', 'materiality', 'posting', 'routing'].map(k => { const c = ev.claims[k]; const v = j[k]; const o = v.verdict === 'overrule'
      return <div key={k} className={`claimrow ${o ? 'over' : ''}`}>
        <div className="k">{CLAIM_WORD[k]}</div>
        <div>
          <div className="said"><b>Agent:</b> {val(k, c.value)} <span className="muted">· {c.basis}</span></div>
          <div className="jd" style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}><StatusIcon state={o ? 'invalidated' : 'cleared'} size={16} /><span><b>Jade:</b> {o ? `${val(k, v.jade)}. ` : ''}{v.why}</span></div>
          <div className="ev">{(v.evidence || []).slice(0, 3).join(' · ')}</div>
        </div>
      </div> })}
    <div className="claimrow"><div className="k">How big?</div><div><div><b>Agent and Jade agree:</b> {fmt(j.size?.agent)}</div><div className="ev">{j.size?.why}</div></div></div>
  </div>
}

/* ---------------------------------------------------------------- the lessons memory: proposed → gate → approved → active */
export function Lessons({ refreshKey, onChanged, people }: { refreshKey: number; onChanged: () => void; people: Record<string, string> }) {
  const [d, setD] = useState<any>(null); const [msg, setMsg] = useState<string | null>(null); const [busy, setBusy] = useState(false)
  const load = () => api.lessons().then(setD)
  useEffect(() => { load() }, [refreshKey])
  if (!d) return <div className="muted">Reading the memory…</div>
  const pb = d.playbook; const controller = people.controller || 'Dana Ortiz'
  const act = async (fn: () => Promise<any>, done: string) => { setBusy(true); setMsg(null); try { await fn(); setMsg(done); await load(); onChanged() } catch (e) { setMsg(String(e).replace(/^Error: /, '')) } finally { setBusy(false) } }
  const order = (l: any) => l.status === 'proposed' ? 0 : l.status === 'active' ? 1 : 2
  return <div>
    <div className="t14 muted">A mistake becomes a lesson only when Jade or a person catches it. A lesson is a named check; before it turns on, every past case is re-run with it (the gate), then the Controller approves it, prospectively.</div>
    <div className="memo" style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><b>Playbook {pb.version}</b><span className="mono t14 muted">{pb.lessons.active} active · {pb.lessons.proposed} proposed · {pb.lessons.rejected_by_gate} rejected</span></div>
      {pb.weaknesses.map((w: any) => <div key={w.check} className="t14" style={{ display: 'flex', gap: 6, marginTop: 6 }}><StatusIcon state={w.lifted ? 'cleared' : 'invalidated'} size={16} /><span>{w.lifted ? 'Learned: ' : 'Still a weakness: '}{w.rule}</span></div>)}
    </div>
    {pb.lessons.proposed > 0 && <button className="btn primary" disabled={busy} style={{ marginBottom: 12 }} onClick={() => act(() => api.approvePendingLessons(controller), `Reviewed as ${controller}: the gate decided.`)}>Review all pending as {controller}</button>}
    {msg && <div className="memo" style={{ background: 'var(--caution-wash)' }}>{msg}</div>}
    {[...d.lessons].sort((a: any, b: any) => order(a) - order(b)).map((l: any) => { const g = l.gate
      return <div key={l.lesson_id} className={`memo ${l.status === 'proposed' ? 'waiting' : l.status === 'rejected_by_gate' ? 'locked' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><span className="mono t14 muted">{l.lesson_id} · {l.mistake_kind}</span><span className={`chip ${l.status === 'active' ? 'cleared' : l.status === 'proposed' ? 'caution' : 'recall'}`}>{l.status.replace(/_/g, ' ')}</span></div>
        <div className="t16" style={{ fontWeight: 600, margin: '6px 0' }}>{l.rule}</div>
        <div className="t14 muted">{l.guidance}</div>
        <div className="t14" style={{ marginTop: 6 }}>From {l.cases.length} case{l.cases.length === 1 ? '' : 's'}: <span className="mono">{l.cases.join(', ')}</span> · proposed by {String(l.proposed_by).replace('human:', '').replace(/^jade$/, 'Jade')}{l.approved_by ? ` · approved by ${l.approved_by} ${dateLabel(l.approved_at)}` : ''}</div>
        {g && <div className="t14" style={{ marginTop: 6, color: g.passed ? 'var(--cleared)' : 'var(--recall)' }}>Gate: {g.pass_after} of {g.claims} past claims pass ({g.pass_before} before) · {g.newly_failing.length} newly failing{g.newly_failing.length ? `: ${g.newly_failing.map((x: any) => `${x.case_id} ${x.claim}`).join(', ')}` : ''} · {g.newly_passing.length} newly passing</div>}
        {l.status === 'proposed' && <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <button className="btn" disabled={busy} onClick={() => act(() => api.gateLesson(l.lesson_id), 'Gate run.')}>Run the gate</button>
          <button className="btn primary" disabled={busy} onClick={() => act(() => api.approveLesson(l.lesson_id, controller), `Decided as ${controller}.`)}>Approve as {controller}</button>
          <button className="btn ghost" disabled={busy} title="Only the Controller approves a lesson" onClick={() => act(() => api.approveLesson(l.lesson_id, 'agent:close_accountant'), 'Approved.')}>Try as the agent</button>
        </div>}
      </div> })}
  </div>
}

/* ---------------------------------------------------------------- time travel: what could the agents see on a given date? Collapsed until asked. */
const START = Date.parse('2026-01-01T00:00:00-08:00')
export function Scrubber({ doc, setDoc, pin, setPin, now, sources, refreshKey, attempt, setAttempt, open, setOpen }: { doc: string; setDoc: (d: string) => void; pin: string; setPin: (p: string) => void; now: string; sources: { source_id: string; title: string }[]
  refreshKey: number; attempt: any; setAttempt: (a: any) => void; open: boolean; setOpen: (o: boolean) => void }) {
  const [tm, setTm] = useState<any>(null)
  const END = Date.parse(now)
  useEffect(() => { api.timemap(doc).then(setTm).catch(() => setTm(null)) }, [doc, refreshKey])
  const pct = (iso: string) => Math.min(100, Math.max(0, ((Date.parse(iso) - START) / (END - START)) * 100))
  const cursor = pct(pin)
  const versions: any[] = tm?.versions || []
  const future = versions.filter((v: any) => Date.parse(v.tx_from) > Date.parse(pin))
  const visible = versions.length - future.length
  const docTitle = (sources.find(s => s.source_id === doc)?.title || doc).replace(/^(REAL|RECONSTRUCTION):\s*/, '')
  if (!open) return (
    <div style={{ height: 40, flex: 'none', borderTop: '1px solid var(--rule)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px' }}>
      <button className="btn" style={{ height: 28 }} onClick={() => setOpen(true)}>Time travel <span className="kbd" style={{ marginLeft: 4 }}>T</span></button>
      <span className="t14 muted">See exactly what the agents could see on any past date. Trackback refuses to show anything published after that date, so a replay can never cheat with hindsight.</span>
    </div>
  )
  return (
    <div style={{ flex: 'none', borderTop: '1px solid var(--rule)', background: 'var(--surface)', padding: '8px 16px 10px', position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
        <span className="t14" style={{ fontWeight: 600 }}>Time travel</span>
        <span className="t14 muted">Pick a document, drag the slider. Left of the line: what the agents could see. Hatched: published later, refused.</span>
        <button className="btn ghost" style={{ height: 26, marginLeft: 'auto' }} onClick={() => { setOpen(false); setAttempt(null) }} aria-label="Collapse time travel"><Close size={16} strokeWidth={1.5} /></button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <label className="t14 muted" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>Document
          <select className="field" value={doc} onChange={e => { setDoc(e.target.value); setAttempt(null) }} style={{ width: 220 }} aria-label="Document">{sources.map(s => <option key={s.source_id} value={s.source_id}>{s.title.replace(/^(REAL|RECONSTRUCTION):\s*/, '')}</option>)}</select></label>
        <div className="mono t14" style={{ width: 190 }}><span className="muted">as of</span> {dayLabel(pin).replace(/, 2026/, '')}</div>
        <div style={{ position: 'relative', flex: 1, height: 32, border: '1px solid var(--rule)', borderRadius: 4, background: 'var(--paper)' }} title="Drag to change the date">
          <div className="hatch" style={{ position: 'absolute', top: 0, bottom: 0, left: `${cursor}%`, right: 0 }} />
          {cursor < 60 && <div className="t14 muted" style={{ position: 'absolute', top: 6, left: `calc(${cursor}% + 10px)`, whiteSpace: 'nowrap', overflow: 'hidden', maxWidth: `calc(${100 - cursor}% - 16px)` }}>not knowable yet</div>}
          {versions.map((v: any) => <div key={v.version_id} title={`${v.version_id} · ${dateLabel(v.tx_from)}`} style={{ position: 'absolute', left: `${pct(v.tx_from)}%`, top: 0, bottom: 0, width: 2, background: v.correction_id ? 'var(--recall)' : 'var(--ink)', opacity: Date.parse(v.tx_from) > Date.parse(pin) ? 0.35 : 1 }} />)}
          <input type="range" aria-label="As-of date" min={0} max={1000} value={Math.round(cursor * 10)} onChange={e => { setAttempt(null); setPin(new Date(START + (Number(e.target.value) / 1000) * (END - START)).toISOString()) }} style={{ position: 'absolute', inset: 0, width: '100%', opacity: 0, cursor: 'ew-resize' }} />
          <div style={{ position: 'absolute', top: -4, bottom: -4, left: `calc(${cursor}% - 1px)`, width: 3, background: 'var(--ink)', pointerEvents: 'none' }} />
        </div>
        {future.length > 0 && <button className="btn" onClick={async () => setAttempt(await api.cheat(doc, pin, future[future.length - 1].version_id))} title="Ask for a version published after the pinned date; Trackback answers 403 with both timestamps">Try to peek at the {dayLabel(future[future.length - 1].tx_from).replace(/, 2026/, '')} version</button>}
      </div>
      <div className="t14 muted" style={{ marginTop: 6 }}>{docTitle}: {visible} of {versions.length} version{versions.length === 1 ? '' : 's'} visible on {dayLabel(pin).replace(/, 2026/, '')}{future.length ? `; ${future.length} published later` : ''}</div>
      {attempt?.refused && <div style={{ position: 'absolute', right: 24, bottom: 118, zIndex: 35, transform: 'scale(0.9)', transformOrigin: 'right bottom', pointerEvents: 'none' }}><RefusalStamp published={dayLabel(attempt.memento_datetime).replace(/, 2026/, '')} decision={dayLabel(attempt.pin).replace(/, 2026/, '')} /></div>}
    </div>
  )
}

/* ---------------------------------------------------------------- first visit: how to read this screen */
export function Legend({ company, onClose }: { company: string; onClose: () => void }) {
  const states: [State, string][] = [['invalidated', 'wrong now: a number or sentence that no longer holds'], ['cleared', 'still valid: checked, with the reason'], ['caution', 'needs a person: it already went out, a fix is proposed'], ['reworked', 'reworked by its owner'], ['skipped', 'skipped: not worth a look']]
  return <div className="card" style={{ position: 'absolute', left: 16, bottom: 16, width: 420, zIndex: 24, padding: '14px 16px', boxShadow: 'var(--shadow)', borderColor: 'var(--ink)' }} role="note" aria-label="How to read this">
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><span className="serif t22" style={{ fontWeight: 600 }}>How to read this</span><button className="btn ghost" style={{ height: 28, padding: '0 6px' }} onClick={onClose} aria-label="Close"><Close size={16} strokeWidth={1.5} /></button></div>
    <div className="t14" style={{ marginTop: 6 }}>Each row is one {company === 'lyft' ? 'seat' : 'agent'}; each card is a piece of work it made (a number, a sentence, a forecast cell, an action that already happened). A line means "rests on". Hover a card for what happened to it; click it for who built it, on top of whom.</div>
    <div style={{ display: 'grid', gridTemplateColumns: '24px 1fr', gap: '4px 6px', marginTop: 8, alignItems: 'center' }} className="t14">
      {states.map(([st, w]) => <><StatusIcon key={st + 'i'} state={st} size={16} /><span key={st + 't'}>{w}</span></>)}
    </div>
    <div className="t14 muted" style={{ marginTop: 8 }}><span className="kbd">Space</span> drops the recall notice · <span className="kbd">J</span> Jade's review · <span className="kbd">E</span> lessons · <span className="kbd">T</span> time travel · <span className="kbd">?</span> all keys</div>
  </div>
}

/* ---------------------------------------------------------------- footer status bar */
export function Footer({ state, pings }: { state: any; pings: any[] }) {
  return <footer style={{ height: 30, flex: 'none', borderTop: '1px solid var(--rule)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', fontSize: 13, background: 'var(--paper)' }}>
    <span className="mono" title="Pieces of work the agents made; receipts record exactly what each one read; pings are the notices sent to agents for this correction">{state?.artifacts ?? '…'} pieces of work · {state?.receipts ?? '…'} receipts of who read what · {pings.length} ping{pings.length === 1 ? '' : 's'} sent</span>
    <span className="muted" style={{ display: 'flex', gap: 14 }}><span><span className="kbd">Space</span> next</span><span><span className="kbd">D</span> deep mode</span><span><span className="kbd">⌘K</span> search</span><span><span className="kbd">T</span> time travel</span><span><span className="kbd">J</span> Jade</span><span><span className="kbd">E</span> lessons</span><span><span className="kbd">R</span> reset</span><span><span className="kbd">?</span> help</span></span>
  </footer>
}

/* ---------------------------------------------------------------- ⌘K command palette */
export function Palette({ company, artifacts, corrections, onClose, onPick }: { company: string; artifacts: any[]; corrections: string[]; onClose: () => void
  onPick: (p: { kind: 'artifact' | 'agent' | 'correction' | 'date'; id: string }) => void }) {
  const [q, setQ] = useState(''); const [i, setI] = useState(0)
  const items = useMemo(() => {
    const ql = q.toLowerCase()
    const agents = LANES[company].filter(l => !['sources', 'humans'].includes(l.id)).map(l => ({ kind: 'agent' as const, id: l.id, label: l.name, sub: l.seat }))
    const arts = artifacts.map(a => ({ kind: 'artifact' as const, id: a.artifact_id, label: title(a, 70), sub: `LOT ${a.lot} · ${agentLane(company, a.agent_id || '')?.name || 'Trackback'}` }))
    const corr = corrections.map(c => ({ kind: 'correction' as const, id: c, label: `Correction ${c}`, sub: 'show its ripple' }))
    const dates = [{ kind: 'date' as const, id: '2026-04-10T17:00:00-07:00', label: 'April 10, 2026', sub: 'the Q1 close, as it was' }, { kind: 'date' as const, id: '2026-05-15T11:00:00-07:00', label: 'May 15, 2026', sub: 'the day the certificate went out' }]
    return [...agents, ...corr, ...dates, ...arts].filter(x => !ql || x.label.toLowerCase().includes(ql) || x.sub.toLowerCase().includes(ql) || x.id.toLowerCase().includes(ql)).slice(0, 12)
  }, [q, company, artifacts, corrections])
  return <>
    <div className="overlay" onClick={onClose} />
    <div className="palette" role="dialog" aria-label="Search">
      <input autoFocus className="field" style={{ width: '100%', height: 48, border: 0, borderBottom: '1px solid var(--rule)', borderRadius: 0, fontSize: 18 }} placeholder="Jump to an agent, artifact, lot code, correction or date" value={q}
        onChange={e => { setQ(e.target.value); setI(0) }} onKeyDown={e => { if (e.key === 'Escape') onClose(); if (e.key === 'ArrowDown') setI(x => Math.min(items.length - 1, x + 1)); if (e.key === 'ArrowUp') setI(x => Math.max(0, x - 1)); if (e.key === 'Enter' && items[i]) onPick(items[i]) }} />
      <div className="scroll" style={{ maxHeight: 400 }}>{items.map((x, k) => <button key={x.kind + x.id} className={`row ${k === i ? 'on' : ''}`} onClick={() => onPick(x)}>
        <span className="chip" style={{ width: 84, justifyContent: 'center' }}>{x.kind}</span><div style={{ minWidth: 0 }}><div style={{ fontWeight: 600 }}>{x.label}</div><div className="muted" style={{ fontSize: 13 }}>{x.sub}</div></div></button>)}
        {items.length === 0 && <div className="muted" style={{ padding: 16 }}>Nothing by that name.</div>}</div>
    </div>
  </>
}

/* ---------------------------------------------------------------- Ledger view (the table side of Graph | Ledger) */
export function LedgerTable({ company, graph, pings, onSelect, laneFilter }: { company: string; graph: any; pings: any[]; onSelect: (id: string) => void; laneFilter: string | null }) {
  const pinged = new Set<string>(pings.flatMap((p: any) => (p.items || []).map((i: any) => i.artifact_id)))
  if (!graph) return null
  const order: Record<State, number> = { caution: 0, invalidated: 1, reworked: 2, cleared: 3, skipped: 4, idle: 5, superseded: 6, pending: 7 }
  const rows = graph.nodes.filter((n: any) => n.type === 'artifact' && (!laneFilter || laneOf(n) === laneFilter)).map((n: any) => ({ n, s: stateOf(n, pinged) })).sort((a: any, b: any) => order[a.s as State] - order[b.s as State])
  return <div className="scroll" style={{ height: '100%', padding: '0 0 24px' }}>
    <table className="ledger-table"><thead><tr><th>Lot</th><th>Artifact</th><th>Agent</th><th className="n">Before</th><th className="n">Now</th><th>State</th></tr></thead><tbody>
      {rows.map(({ n, s }: any) => <tr key={n.id} onClick={() => onSelect(n.id)} style={{ cursor: 'pointer' }}><td><Lot code={n.lot} /></td><td style={{ maxWidth: 420 }}>{n.kind === 'sentence' ? <i className="serif">“{title(n, 90)}”</i> : title(n)}</td>
        <td>{agentLane(company, n.agent_id || '')?.name || 'Trackback'}</td><td className="n">{n.old_value != null && n.new_value != null && n.old_value !== n.new_value ? <span className="strike">{fmt(n.old_value, n.line_item)}</span> : ''}</td>
        <td className="n">{n.kind === 'sentence' || (n.new_value ?? n.value) == null ? '' : fmt(n.new_value ?? n.value, n.line_item)}</td><td><span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><StatusIcon state={s} size={16} />{STATE_WORD[s as State] || 'Unchanged'}</span></td></tr>)}
    </tbody></table>
  </div>
}

export { compText, RefusalStamp }
