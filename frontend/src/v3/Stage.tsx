/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from 'react'
import { X, Check, AlertCircle, RefreshCw, MinusCircle, Mail, Lock } from 'lucide-react'
import { api, money, fig, lev, when, reason, who, type Any, type World } from './api'

export const TIDEWALL_BEATS = ['Title', 'Reconcile', 'Evidence', 'Ripple', 'Jade', 'Approvals', 'Dana says no', 'Replay', 'Scorecard', 'Memo']
export const LYFT_BEATS = ['Title', 'Trace', 'Inside', 'Ripple', 'Jade', 'General Counsel', 'Tape']
const CAPTIONS: Record<World, string[]> = {
  tidewall: [
    '48 climbing gyms, about $185 million of revenue, a $105 million loan, and about half a million dollars of room under its limit.',
    "Most differences are noise. This one isn't: the billing migration double-counted $750,000.",
    'Nobody linked this spreadsheet to the books. Trackback found where every number came from.',
    'These are now wrong, including the certificate already sent to the bank. These it checked and cleared.',
    "Under 5% of profit, so a simple rule shrugs. Its reviewer didn't: this breaks the loan.",
    'It drafts, it never posts.',
    'And it handles being told no.',
    "It owns the miss: here's what the books showed that day.",
    'Our planted cases, step by step, versus a 5% rule and versus the agent without its reviewer.',
    'It writes the memo your auditor will ask for.',
  ],
  lyft: [
    "Lyft's release said 500 basis points. The model it came from said 50.",
    'The tracer reads the real filing: every figure ties to a source except one.',
    'With Trackback inside, the release never goes out: the sentence says 500, the figure it cites is 50.',
    'What actually happened: the correction lands at 5 pm, and only the work that built on the 500 is pinged.',
    'No P&L effect, so a 5% rule shrugs. Jade does not.',
    'A furnished release cannot be fixed quietly.',
    'What was real, what we reconstructed, and what the market did.',
  ],
}

export function Icon({ s, size = 22 }: { s: string; size?: number }) {
  const p = { size, strokeWidth: 2 }
  if (s === 'invalidated') return <X {...p} color="var(--recall)" aria-label="invalidated" />
  if (s === 'cleared' || s === 'still_valid') return <Check {...p} color="var(--cleared)" aria-label="still valid" />
  if (s === 'caution' || s === 'needs_human') return <AlertCircle {...p} color="var(--caution)" aria-label="needs a human" />
  if (s === 'reworked') return <RefreshCw {...p} color="var(--ping)" aria-label="reworked" />
  if (s === 'skipped') return <MinusCircle {...p} color="var(--ink-muted)" aria-label="skipped" />
  if (s === 'ping') return <Mail {...p} color="var(--ping)" aria-label="pinged" />
  return null
}

function Counter({ to, dur = 900, cls = '' }: { to: number; dur?: number; cls?: string }) {
  const [v, setV] = useState(0)
  useEffect(() => {
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / dur); setV(Math.round(to * k)); if (k < 1) raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [to, dur])
  return <span className={`counter ${cls}`}>{v.toLocaleString()}</span>
}

// ======================================================================================================================== Tidewall
export function TidewallStage({ data, step, onRefresh }: { data: Any; step: number; onRefresh: () => void }) {
  if (!data) return <div className="beat"><p className="lede">Loading the review…</p></div>
  const b = TIDEWALL_BEATS[step]
  return (
    <>
      {b === 'Title' && <TitleBeat d={data} />}
      {b === 'Reconcile' && <ReconBeat d={data} />}
      {b === 'Evidence' && <EvidenceBeat d={data} />}
      {b === 'Ripple' && <RippleBeat d={data} />}
      {b === 'Jade' && <JadeBeat d={data} />}
      {b === 'Approvals' && <ApprovalsBeat d={data} live={false} onRefresh={onRefresh} />}
      {b === 'Dana says no' && <ApprovalsBeat d={data} live onRefresh={onRefresh} />}
      {b === 'Replay' && <ReplayBeat />}
      {b === 'Scorecard' && <ScoreBeat d={data} />}
      {b === 'Memo' && <MemoBeat d={data} />}
    </>
  )
}

function TitleBeat({ d }: { d: Any }) {
  const t = d.title
  return (
    <div className="stage"><div className="title-card">
      <div className="smallcaps muted t22" style={{ marginBottom: '2vh' }}>Tidewall Climbing Co. · synthetic company · July 8, 2026</div>
      <h1>Tidewall told its bank leverage was {lev(t.leverage)}.</h1>
      <p>48 climbing gyms, {money(t.revenue_ttm, { m: true })} of revenue, a {money(t.loan, { m: true })} loan, and {money(t.headroom)} of room under its {t.max.toFixed(2)}x limit.</p>
    </div></div>
  )
}

function ReconBeat({ d }: { d: Any }) {
  const [lit, setLit] = useState(false)
  useEffect(() => { const t = setTimeout(() => setLit(true), 1300); return () => clearTimeout(t) }, [])
  const names: Record<string, string> = { billing_to_gl: 'Billing to GL', bank_to_book: 'Bank to cash book', cash_application: 'Cash application', ap_review: 'AP review' }
  const hero = d.hero
  return (
    <div className="beat">
      <h2>Four reconciliations run at 9:00 on July 8.</h2>
      <div className="grid4">
        {d.recons.map((r: Any) => (
          <div key={r.recon} className={`bcard ${lit && r.recon === hero.recon ? 'recall' : ''}`}>
            <h3>{names[r.recon] || r.recon}</h3>
            <div className="kv big">
              <span className="k">matched</span><Counter to={r.counts.matched} />
              <span className="k">cleared</span><Counter to={r.counts.cleared} />
              <span className="k">exceptions</span><Counter to={r.counts.exceptions} cls={r.counts.exceptions ? 'red' : ''} />
            </div>
            <div className="sub" style={{ marginTop: '1vh' }}>{Object.entries(r.cleared_by_reason || {}).map(([k, v]) => `${v} ${k.replace(/_/g, ' ')}`).join(' · ') || 'nothing to clear'}</div>
          </div>
        ))}
      </div>
      {lit && <div className="bcard recall fly-in" style={{ display: 'flex', alignItems: 'center', gap: '1.2vw' }}>
        <Icon s="invalidated" size={34} />
        <div><div className="big" style={{ fontWeight: 600 }}>{hero.title}</div>
          <div className="sub">{money(hero.amount)} · {Object.entries(hero.by_region || {}).map(([r, v]) => `${r} ${money(v as number, { k: true })}`).join(' · ')}</div></div>
      </div>}
      <div className="sub big muted">{d.exceptions.length} exceptions in all, each with a reason; the rest cleared: deposits in transit, outstanding checks, a one-cent FX difference, a bundled wire, a known short-pay, an alias, and Priya's half-finished handoff confirmed and finished.</div>
    </div>
  )
}

function EvidenceBeat({ d }: { d: Any }) {
  const e = d.evidence
  const imp = e.imports || []
  const cell = (l: Any, label: string, owner: string) => l && (
    <div className={`bcard ${l.status === 'stale' ? 'recall' : 'cleared'} fade-in`}>
      <div className="sub">{label} · made by {owner}</div>
      <div className="big" style={{ fontWeight: 600, margin: '0.6vh 0' }}>{l.locator}: <span className="num">{l.display || money(l.value_num, { cents: true })}</span></div>
      <div className="sub">{l.status === 'stale' ? <span className="red">Stale: {l.explanation}</span> : <>Linked to <b>{l.explanation?.split(' = ')[0]}</b> · confidence {Math.round((l.confidence || 0) * 100)}%</>}</div>
    </div>
  )
  return (
    <div className="beat">
      <h2>One number, four places, nobody linked them.</h2>
      <div className="grid3">
        <div className="bcard cleared">
          <div className="sub">Billing system · line-level export · captured Apr 9, 6:00 PM</div>
          <div className="big" style={{ fontWeight: 600, margin: '0.6vh 0' }}>Batch {d.hero.evidence[0]?.batch} · March · released once</div>
          <div className="kv"><span className="k">members</span><span className="v">{e.billing?.members?.toLocaleString()}</span><span className="k">release</span><span className="v">{money(e.billing?.release)}</span></div>
        </div>
        <div className="bcard recall" style={{ gridColumn: 'span 2' }}>
          <div className="sub">General ledger · 4010 imports from the billing summary</div>
          {imp.map((i: Any, k: number) => (
            <div key={i.import_id} className="big" style={{ display: 'flex', gap: '1vw', alignItems: 'baseline', marginTop: '0.6vh' }}>
              <span className="num" style={{ fontWeight: 600 }}>{i.import_id}</span><span className="num">{money(i.amount)}</span>
              <span className="sub">{when(i.posted_at)}</span><span className={k ? 'red' : 'sub'}>{i.status}</span>
            </div>
          ))}
          <div className="sub" style={{ marginTop: '0.8vh' }}>{d.hero.trust?.why}</div>
        </div>
      </div>
      <div className="grid3">
        {cell(e.workbook, "Priya's covenant workbook", 'Priya Nair')}
        {cell(e.deck, 'Board deck, slide 2', 'the CFO office')}
        {cell(e.certificate, 'Compliance certificate, signed', 'Covenant and Comp; signed by Sam Whitfield')}
      </div>
    </div>
  )
}

const LANES = [
  { k: 'Trackback', n: 'Trackback', s: 'recomputes every number itself' },
  { k: 'People', n: 'People', s: "files typed by hand: Priya's workbook, the CFO office's slide" },
  { k: 'close_accountant', n: 'Close Accountant', s: 'agent · Q1 close memo' },
  { k: 'covenant_comp', n: 'Covenant and Comp', s: 'agent · certificate, bonuses, tax' },
  { k: 'reporting_analyst', n: 'Reporting Analyst', s: 'agent · board deck slides 3 and 4' },
  { k: 'Actions', n: 'Executed actions', s: 'money already moved' },
]

function RippleBeat({ d }: { d: Any }) {
  const rp = d.ripple
  const [hop, setHop] = useState(0)
  useEffect(() => { const t = setInterval(() => setHop(h => (h < 8 ? h + 1 : h)), 420); return () => clearInterval(t) }, [])
  const pings: Record<string, Any> = {}
  for (const p of rp.wave?.pings || []) pings[p.agent] = p
  const items = Object.entries(rp.items as Record<string, Any>)
  const inv = items.filter(([, v]) => v.verdict === 'invalidated')
  const cleared = items.filter(([, v]) => v.verdict === 'still_valid')
  const metrics = ['ttm_adj_ebitda@2026Q1', 'leverage@2026Q1', 'covenant_status@2026Q1', 'covenant_headroom@2026Q1', 'tax_installment@2026Q2'].map(k => [k, rp.metrics[k]]).filter(([, v]) => v)
  const lane: Record<string, Any[]> = { Trackback: [], People: [], close_accountant: [], covenant_comp: [], reporting_analyst: [], Actions: [] }
  for (const [k, m] of metrics as Any[]) lane.Trackback.push({ id: k, t: m.label.split(',')[0], old: fig(m.old, m.unit, k), now: fig(m.new, m.unit, k), s: 'invalidated', w: m.conclusion_old !== m.conclusion_new ? `crosses ${m.conclusion_new === 'above' || m.conclusion_new === 'BREACH' ? 'the 3.00x covenant' : 'zero'}` : 'recomputed', hop: 1 })
  const wb = inv.filter(([i]) => i.startsWith('WB.'))
  const s2 = inv.filter(([i]) => i.startsWith('DECK.s2'))
  const notice = (rp.wave?.notices || []) as Any[]
  if (wb.length) lane.People.push({ id: 'wb', t: `Covenant workbook: ${wb.length} cells`, old: money(rp.items['WB.Covenant.B7']?.old), now: money(rp.items['WB.Covenant.B7']?.new), s: 'invalidated', w: `notice to ${notice.find(n => n.owner === 'priya')?.to === 'marco' ? 'Marco (Priya is out of office)' : 'Priya'}`, hop: 2 })
  if (s2.length) lane.People.push({ id: 's2', t: `Board deck slide 2: ${s2.length} lines`, old: '$32.6M', now: fig(rp.items['DECK.s2.l2']?.new, null), s: 'invalidated', w: 'stale since Apr 24; notice to Sam', hop: 2 })
  const pingItems = (a: string) => (pings[a]?.items || []) as Any[]
  const st = (v: string) => (v === 'reworked' ? 'reworked' : v === 'still_valid' ? 'cleared' : v === 'needs_human' ? 'caution' : 'invalidated')
  for (const it of pingItems('close_accountant')) lane.close_accountant.push({ id: it.artifact_id, t: 'Q1 close memo', s: st(it.verdict), w: it.verdict.replace('_', ' '), prose: (it.new_version?.content || '').slice(0, 90), hop: 3 })
  const cc = pingItems('covenant_comp')
  const certLines = cc.filter(i => i.artifact_id.startsWith('CERT.'))
  if (certLines.length) lane.covenant_comp.push({ id: 'cert', t: `Certificate: ${certLines.length} lines`, old: '2.95 to 1.00', now: lev(rp.metrics['leverage@2026Q1']?.new) + ' to 1.00', s: 'caution', w: 'needs the CFO', hop: 3 })
  lane.covenant_comp.push({ id: 'acts', t: `${cc.filter(i => i.artifact_id.startsWith('ACT')).length} executed actions`, s: 'caution', w: "can't un-send; compensations proposed", hop: 3 })
  const ra = pingItems('reporting_analyst')
  const s4 = ra.filter(i => i.artifact_id.startsWith('DECK.s4'))
  for (const it of ra.filter(i => !i.artifact_id.startsWith('DECK.s4'))) lane.reporting_analyst.push({ id: it.artifact_id, t: it.artifact_id === 'DECK.s3.l1' ? 'Slide 3: covenant sentence' : it.artifact_id.includes('growth') ? '“Membership revenue grew”' : '“All six regions were profitable”', s: st(it.verdict), w: it.verdict === 'still_valid' ? 'still valid: ' + (it.reason || '').split(';')[0].slice(0, 60) : it.verdict, prose: it.verdict === 'reworked' ? (it.new_version?.content || '').slice(0, 90) : '', hop: 4 })
  if (s4.length) lane.reporting_analyst.splice(1, 0, { id: 's4', t: `Slide 4: ${s4.length} regions re-rendered`, s: 'reworked', w: 'figures from Trackback', hop: 4 })
  for (const [aid, a] of Object.entries(rp.actions as Record<string, Any>)) {
    if (a.verdict === 'invalidated') lane.Actions.push({ id: aid, t: a.label.split('(')[0].replace('Q1 GM bonus paid, ', 'Bonus ').replace('Q1 compliance certificate sent to Redwood', 'Certificate sent').replace('Q2 estimated tax paid', 'Q2 tax paid'), s: 'invalidated', w: a.compensation?.amount ? `${money(a.compensation.amount)} ${a.compensation.direction} → ${who(a.compensation.approver)}` : `corrected certificate → ${who(a.compensation?.approver)}`, hop: 5 })
  }
  const actCleared = Object.values(rp.actions as Record<string, Any>).filter((a: Any) => a.verdict === 'still_valid').length
  const skipped = Object.values(rp.agent_nodes as Record<string, Any>).filter((n: Any) => n.skipped)
  return (
    <div className="beat" style={{ gap: '1.2vh' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '2vw' }}>
        <h2 style={{ fontSize: 'clamp(30px, 2.4vw, 50px)' }}>The ripple</h2>
        <span className="big"><span className="red num">{rp.counts.invalidated}</span> now wrong · <span className="green num">{rp.counts.still_valid}</span> checked and still valid · <span className="amber num">{rp.counts.compensations}</span> compensations · {rp.counts.metrics_recomputed} of {rp.counts.metrics_total} metrics recomputed · naive count {rp.counts.naive}</span>
      </div>
      <div className="rlanes">
        {LANES.map(L => (
          <div key={L.k} className="rlane">
            <div className="rname"><div className="n">{L.n}</div><div className="s">{L.s}</div>
              {pings[L.k] && hop >= 3 && <div style={{ marginTop: 4 }}><span className="envchip"><Mail size={16} /> pinged · {pings[L.k].state.replace('_', ' ')}</span></div>}</div>
            <div className="rnodes">
              {lane[L.k].filter(n => n.hop <= hop).map(n => (
                <div key={n.id} className={`rnode ${n.s}`}>
                  <span className="ic"><Icon s={n.s} size={18} /></span>
                  <div className="t">{n.t}</div>
                  {n.old && <div className="v"><span className="strike-old">{n.old}</span>{n.now}</div>}
                  {n.prose && <div className="w" style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', color: 'var(--ink)' }}>“{n.prose}”</div>}
                  <div className="w">{n.w}</div>
                </div>
              ))}
              {L.k === 'Actions' && hop >= 6 && <span className="rmore"><Check size={16} /> {actCleared} actions still valid (R3 and R5 stay $0; R6 never used it)</span>}
              {L.k === 'reporting_analyst' && hop >= 6 && skipped.length > 0 && <div className="rnode skipped"><span className="ic"><Icon s="skipped" size={18} /></span><div className="t">13-week cash forecast</div><div className="w">skipped: no material change</div></div>}
              {L.k === 'People' && hop >= 6 && <span className="rmore"><Check size={16} /> {cleared.length} lines checked and still valid ({Object.entries(cleared.reduce((a: Any, [, v]) => { a[reason(v.reason)] = (a[reason(v.reason)] || 0) + 1; return a }, {})).slice(0, 3).map(([k, v]) => `${v} ${k}`).join(', ')})</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function JadeBeat({ d }: { d: Any }) {
  const ev = d.evaluation
  const a = ev.agent
  const jq = (k: string) => (ev.jade as Any[]).find((x: Any) => x.claim_key === k)
  const agg = d.materiality.aggregate
  const lev1 = d.ripple.metrics['leverage@2026Q1']
  const route = jq('q7_fix.approvers.lender_document')
  return (
    <div className="beat">
      <h2>The agent's draft says immaterial. Jade disagrees.</h2>
      <div className="grid2">
        <div className="bcard ink">
          <div className="sub">The agent, playbook {ev.playbook}</div>
          <div className="big" style={{ margin: '1vh 0', fontWeight: 600 }}>Materiality: {a.q5_matters.material ? 'material' : 'immaterial'}</div>
          <div className="big">{a.q5_matters.why}</div>
          <div className="sub" style={{ marginTop: '1.4vh' }}>Correcting entry dated {a.q7_fix.posting_period}; lender documents to {who(a.q7_fix.approvers.lender_document)}.</div>
        </div>
        <div className="bcard recall overrule fly-in">
          <span className="stamp stamp-in">OVERRULED</span>
          <div className="sub">Jade, the reviewer</div>
          <div className="kv big" style={{ marginTop: '1vh' }}>
            <span className="k">Rollover</span><span className="v">{money(agg.rollover)} <Check size={20} color="var(--cleared)" /> passes</span>
            <span className="k">Iron curtain</span><span className="v red">{money(agg.iron_curtain)} <X size={20} /> fails ({money(d.materiality.thresholds.overall)})</span>
            <span className="k">Covenant</span><span className="v red">{lev(lev1?.old)} → {lev(lev1?.new)} <X size={20} /> breaches 3.00x</span>
            <span className="k">Compensation</span><span className="v red">R1, R2, R4 bonuses overpaid</span>
          </div>
          <div className="sub" style={{ marginTop: '1.2vh' }}>{jq('q5_matters')?.why}</div>
        </div>
      </div>
      {route && <div className="bcard caution fade-in big"><AlertCircle size={22} color="var(--caution)" style={{ verticalAlign: 'middle' }} /> Flag: {route.why}.</div>}
      <div className="bcard caution big">Escalated, not overruled: the entry is dated in locked March. Period locks are the Controller's call.</div>
    </div>
  )
}

function ApprovalsBeat({ d, live, onRefresh }: { d: Any; live: boolean; onRefresh: () => void }) {
  const [items, setItems] = useState<Any[]>(d.approvals)
  const [holds, setHolds] = useState<Any[]>(d.holds)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!live) return
    let gone = false
    ;(async () => {
      setBusy(true)
      const already = (d.approvals as Any[]).some(a => a.kind === 'journal_entry' && a.state === 'rejected')
      if (!already) await api.act('tidewall', 'dana')
      const r = await api.approvals('tidewall')
      if (!gone) { setItems(r.items.filter((a: Any) => a.exception_id === d.hero.exception_id || a.kind === 'notice')); setHolds(r.holds); setBusy(false); onRefresh() }
    })()
    return () => { gone = true }
  }, [live]) // eslint-disable-line react-hooks/exhaustive-deps
  const je = items.filter(a => a.kind === 'journal_entry')
  const others = items.filter(a => a.kind !== 'journal_entry' && a.kind !== 'notice').slice(0, 5)
  const rej = je.find(a => a.state === 'rejected')
  return (
    <div className="beat">
      <h2>{live ? 'Dana says no. The agent re-drafts.' : 'Everything goes to a person who did not prepare it.'}</h2>
      <div className="grid2">
        <div>
          {je.map(a => (
            <div key={a.action_id} className={`bcard ${a.state === 'rejected' ? 'recall' : a.state === 'executed' ? 'cleared' : 'ink'} fade-in`} style={{ marginBottom: '1.2vh' }}>
              <div className="sub">{a.action_id} · draft {a.draft_no} · to {a.assignee_name}</div>
              <div className="big" style={{ fontWeight: 600 }}>{a.summary}</div>
              <div className="sub">posting {a.params.posting_period}{a.params.orig_period !== a.params.posting_period ? ` · orig_period ${a.params.orig_period}` : ''} · state <b>{a.state}</b></div>
              {a.state === 'rejected' && <div className="big red" style={{ marginTop: '0.8vh' }}>“{a.approvals.find((x: Any) => x.decision === 'rejected')?.reason}”</div>}
            </div>
          ))}
          {live && busy && <div className="big muted">Dana is reading her inbox…</div>}
        </div>
        <div>
          {others.map(a => <div key={a.action_id} className="bcard" style={{ marginBottom: '1vh' }}><div className="sub">to {a.assignee_name} · {a.state}</div><div>{a.summary}</div></div>)}
          <div className="bcard caution">
            <h3><Lock size={22} style={{ verticalAlign: 'middle' }} /> On hold</h3>
            {holds.filter(h => h.state === 'held').map(h => <div key={h.hold_id}>{h.target}</div>)}
          </div>
        </div>
      </div>
      {live && rej && <div className="big">It never posts, and the proposer can never approve: the schema refuses it.</div>}
    </div>
  )
}

function ReplayBeat() {
  const [then, setThen] = useState<Any>(null)
  const [log, setLog] = useState<Any[]>([])
  const [peek, setPeek] = useState<Any>(null)
  useEffect(() => {
    ;(async () => {
      const tm = await api.timemap('billing_release_lines')
      const v1 = tm.versions[0]
      const f = await api.file('tidewall', 'billing_release_lines', `&version=${v1.version_id}&batch=B07&period=2026-03&limit=4`)
      setThen({ ...f, tm })
      const l = await api.timemap('gl_import_log')
      const lf = await api.file('tidewall', 'gl_import_log', `&version=${l.versions[0].version_id}&q=B07&limit=20`)
      setLog((lf.rows || []).filter((r: Any) => r.period === '2026-03'))
      setTimeout(async () => setPeek(await api.attempt('billing_release_lines', '2026-04-10T17:00:00-07:00', tm.versions[tm.versions.length - 1].version_id)), 2200)
    })()
  }, [])
  return (
    <div className="beat">
      <h2>April 9, 6:00 PM: what the books showed that day.</h2>
      <div className="grid2">
        <div className="bcard cleared">
          <div className="sub">Billing export as captured {then ? when(then.captured_at) : '…'}</div>
          {then && Object.entries(then.totals || {}).map(([k, v]) => <div key={k} className="big"><b>{k}</b>: <span className="num">{money(v as number)}</span> released once ({then.n.toLocaleString()} member lines)</div>)}
        </div>
        <div className="bcard recall">
          <div className="sub">GL import log as of the same moment</div>
          {log.map(r => <div key={r.import_id} className="big"><span className="num">{r.import_id}</span> · {when(r.posted_at)} · <span className={r.status.includes('retry') ? 'red' : ''}>{r.status}</span></div>)}
        </div>
      </div>
      <div className="big">The duplicate was visible before the Q1 close at 5:00 PM on April 10. The agent owns the miss.</div>
      {peek && <div className="fade-in" style={{ display: 'flex', alignItems: 'center', gap: '2vw' }}>
        <span className="stamp stamp-in">REFUSED · {peek.status}</span>
        <span className="big">Asked for the July 8 export while pinned to the close: captured {when(peek.problem?.requested)}, decision time {when(peek.problem?.pinned_at)}. It cannot read its own future.</span>
      </div>}
    </div>
  )
}

function ScoreBeat({ d }: { d: Any }) {
  const c = d.configs || {}
  const h = d.scorecard || {}
  const cols = [['naive_5pct_rule', '5% rule'], ['agent_v1_no_jade', 'Agent alone'], ['agent_v1_with_jade', 'Agent + Jade'], ['agent_v2_with_jade', 'After lessons']]
  const steps = [['detect', 'Detect'], ['classify', 'Classify'], ['size', 'Size'], ['materiality', 'Materiality'], ['fix', 'Fix']]
  return (
    <div className="beat">
      <h2>{c.agent_v1_with_jade?.cases?.n ?? 34} planted cases, scored step by step.</h2>
      <table className="ledger-table" style={{ fontSize: 'clamp(22px, 1.4vw, 30px)' }}>
        <thead><tr><th>Step</th>{cols.map(([, n]) => <th key={n} className="n">{n}</th>)}</tr></thead>
        <tbody>{steps.map(([k, n]) => (
          <tr key={k}><td>{n}</td>{cols.map(([ck]) => { const s = c[ck]?.[k]; return <td key={ck} className="n">{s && s.n ? `${s.correct}/${s.n}` : '—'}</td> })}</tr>
        ))}</tbody>
      </table>
      <div className="grid4">
        <div className="bcard"><div className="sub">Lineage</div><div className="counter">{h.lineage}</div></div>
        <div className="bcard"><div className="sub">Jade catches planted mistakes</div><div className="counter">{Math.round((h.jade_catch_rate || 0) * 100)}%</div><div className="sub">{Math.round((h.jade_false_overrule_rate || 0) * 100)}% false overrules</div></div>
        <div className="bcard"><div className="sub">Held-out cases passed</div><div className="counter">{Math.round((h.heldout_pass_v1 || 0) * 100)}% → {Math.round((h.heldout_pass_v2 || 0) * 100)}%</div><div className="sub">v1 → v2 after approved lessons</div></div>
        <div className="bcard"><div className="sub">Future reads leaked</div><div className="counter">{h.replay_leaks ?? 0}</div></div>
      </div>
    </div>
  )
}

function MemoBeat({ d }: { d: Any }) {
  const [m, setM] = useState<Any>(null)
  useEffect(() => { api.memo('tidewall', d.hero.exception_id).then(setM) }, [d.hero.exception_id])
  const summary = useMemo(() => (m?.markdown || '').split('## 1. Summary')[1]?.split('##')[0]?.trim(), [m])
  return (
    <div className="stage"><div className="payoff">
      <div className="smallcaps muted t22">Error memo · {d.hero.exception_id}</div>
      <div className="serif" style={{ fontSize: 'clamp(26px, 2vw, 40px)', maxWidth: '62ch', marginTop: '2vh', lineHeight: 1.3 }}>{summary || '…'}</div>
      <div className="line" style={{ maxWidth: '70ch', fontFamily: 'var(--sans)' }}>{d.seat_line}</div>
      <div className="tag">{d.tagline}</div>
    </div></div>
  )
}

// ======================================================================================================================== Lyft
export function LyftStage({ data, step, onRefresh }: { data: Any; step: number; onRefresh: () => void }) {
  if (!data) return <div className="beat"><p className="lede">Loading…</p></div>
  const b = LYFT_BEATS[step]
  const rp = data.ripple
  const ev = data.evaluation
  if (b === 'Title') return (
    <div className="stage"><div className="title-card">
      <div className="smallcaps muted t22" style={{ marginBottom: '2vh' }}><span className="world-tag real">Real</span> &nbsp;Lyft · February 13, 2024 · 4:06 PM ET</div>
      <h1>Lyft's release said 500 basis points.</h1>
      <p>The model it came from said 50. Shares rose as much as {data.tape.after_hours_peak_pct}% after hours before the CFO corrected it on the call.</p>
    </div></div>
  )
  if (b === 'Trace') {
    const items = data.trace.files[Object.keys(data.trace.files)[0]] || []
    return (
      <div className="beat">
        <h2>The tracer reads the filing as filed.</h2>
        <p className="lede">{items.filter((i: Any) => i.status === 'linked').length} of {items.length} figures tie to the close pack or the guidance model. One does not.</p>
        <div style={{ columns: 2, columnGap: '2vw' }}>
          {items.map((i: Any) => (
            <div key={i.item_id} className={`bcard ${i.status === 'unlinked' ? 'recall' : ''}`} style={{ breakInside: 'avoid', marginBottom: '0.8vh', padding: '0.5vh 0.8vw', fontSize: 'clamp(18px, 1vw, 22px)' }}>
              <Icon s={i.status === 'unlinked' ? 'invalidated' : 'cleared'} size={18} /> <span className="num">{i.display}</span> <span className="muted">{(i.label || '').slice(-60)}</span>
              {i.status === 'unlinked' && <div className="red">No source has 500. The guidance model has 50: the same digits at another power of ten.</div>}
            </div>
          ))}
        </div>
      </div>
    )
  }
  if (b === 'Inside') {
    const f = data.fence
    return (
      <div className="beat">
        <h2>Inside Lyft, with Trackback: the release never goes out.</h2>
        <div className="grid2">
          <div className="bcard ink"><div className="sub">Reporting and IR agent · draft, Feb 12</div><div className="serif big" style={{ fontStyle: 'italic', marginTop: '1vh' }}>“Adjusted EBITDA margin expansion … of approximately <span className="red">500</span> basis points year-over-year.”</div>
            <div className="sub" style={{ marginTop: '1vh' }}>cites the guidance model: margin expansion = <b>50</b> basis points</div></div>
          <div className="bcard recall overrule"><span className="stamp stamp-in">BLOCKED</span><div className="sub">Pre-execution fence · 3:30 PM, after the CFO approved</div>
            <div className="big" style={{ marginTop: '1vh' }}>{f?.stale?.[0] ? `States ${f.stale[0].stated} but rests on ${f.stale[0].cited_value}: same digits, different magnitude.` : ''}</div>
            <div className="sub" style={{ marginTop: '1vh' }}>Fix proposed: “{f?.fix}”</div></div>
        </div>
        <div className="big muted">Not a Lyft rule: every sentence that cites a figure must show it, on every action.</div>
      </div>
    )
  }
  if (b === 'Ripple') {
    const pings = (rp.wave?.pings || []) as Any[]
    return (
      <div className="beat">
        <h2>What actually happened: the correction lands at 5:00 PM ET.</h2>
        <div className="grid2">
          {pings.map(p => (
            <div key={p.agent} className="bcard ping fade-in">
              <h3><Mail size={22} style={{ verticalAlign: 'middle' }} /> {who(p.agent)} (outside, reconstructed) · pinged</h3>
              {p.items.map((i: Any) => (
                <div key={i.artifact_id} style={{ marginTop: '1vh' }}><Icon s={i.verdict === 'reworked' ? 'reworked' : 'caution'} size={20} /> <b>{i.artifact_id.split('.').pop()}</b>: {i.verdict.replace('_', ' ')}
                  {i.new_version?.content && <div className="serif" style={{ fontStyle: 'italic' }}>“{i.new_version.content}”</div>}
                  {i.verdict === 'needs_human' && <div className="sub">{i.reason}</div>}</div>
              ))}
            </div>
          ))}
        </div>
        <div className="bcard"><Icon s="skipped" /> Skipped, no ping: {(rp.wave?.skipped || []).map((s: Any) => s.node_id.split('.').slice(1).join(' ')).join(' and ')}: they cite only the Q4 bookings and revenue, which never changed.</div>
      </div>
    )
  }
  if (b === 'Jade') {
    const jq = (k: string) => (ev.jade as Any[]).find((x: Any) => x.claim_key === k)
    return (
      <div className="beat">
        <h2>“No P&L effect”: the 5% rule shrugs. Jade does not.</h2>
        <div className="grid2">
          <div className="bcard ink"><div className="sub">The agent, playbook v1</div><div className="big" style={{ marginTop: '1vh' }}>{ev.agent.q5_matters.why}</div><div className="sub" style={{ marginTop: '1vh' }}>Fix: {ev.agent.q7_fix.why}; route to the {ev.agent.q7_fix.approvers.disclosure}.</div></div>
          <div className="bcard recall overrule"><span className="stamp stamp-in">OVERRULED</span><div className="sub">Jade</div><div className="big" style={{ marginTop: '1vh' }}>{jq('q5_matters')?.why}</div>
            <div className="sub" style={{ marginTop: '1vh' }}>{jq('q7_fix.approvers.disclosure')?.why}</div></div>
        </div>
      </div>
    )
  }
  if (b === 'General Counsel') return <LyftGC data={data} onRefresh={onRefresh} />
  return (
    <div className="beat">
      <h2>What was real, and what we reconstructed.</h2>
      <div className="grid2">
        <div className="bcard ink"><h3>Real</h3>{data.real_vs_reconstructed.real.map((x: string) => <div key={x}>· {x}</div>)}</div>
        <div className="bcard"><h3>Reconstructed (labeled on every line)</h3>{data.real_vs_reconstructed.reconstructed.map((x: string) => <div key={x}>· {x}</div>)}</div>
      </div>
      <div className="big">Next close: up {data.tape.next_close_pct}% at ${data.tape.next_close_px}. Sources: {data.tape.sources.slice(0, 2).join('; ')}.</div>
    </div>
  )
}

function LyftGC({ data, onRefresh }: { data: Any; onRefresh: () => void }) {
  const [items, setItems] = useState<Any[]>(data.approvals)
  useEffect(() => {
    ;(async () => {
      if (!(data.approvals as Any[]).some(a => a.state === 'rejected')) { await api.act('lyft', 'general_counsel'); await api.act('lyft', 'cfo') }
      setItems((await api.approvals('lyft')).items); onRefresh()
    })()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const fixes = items.filter(a => a.kind === 'disclosure_fix')
  return (
    <div className="beat">
      <h2>The General Counsel says no to a quiet fix.</h2>
      {fixes.map(a => (
        <div key={a.action_id} className={`bcard ${a.state === 'rejected' ? 'recall' : a.state === 'executed' ? 'cleared' : 'ink'} fade-in`}>
          <div className="sub">{a.action_id} · draft {a.draft_no} · to {who(a.assignee)} · <b>{a.state}</b></div>
          <div className="big" style={{ fontWeight: 600 }}>{a.summary}</div>
          {a.state === 'rejected' && <div className="big red">“{a.approvals.find((x: Any) => x.decision === 'rejected')?.reason}”</div>}
        </div>
      ))}
    </div>
  )
}

export { CAPTIONS }
