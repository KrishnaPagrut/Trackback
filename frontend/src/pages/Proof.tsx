import { useEffect, useState } from 'react'
import { api } from '../api'

const pct = (x: number | null | undefined) => x == null ? '…' : `${(x * 100).toFixed(1)}%`
const r2 = (x: number | null | undefined) => x == null ? '…' : x.toFixed(2)

/* Every number on this page is read from data/eval/latest.json, which `make eval` writes. Nothing is typed. */
export default function Proof() {
  const [e, setE] = useState<any>(null); const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api.evalLatest().then(setE).catch(x => setErr(String(x))) }, [])
  if (err) return <div style={{ padding: 32 }}><div className="serif t32">No eval output yet</div><p className="muted">Run <span className="mono">make eval</span>, then reload. ({err})</p></div>
  if (!e) return <div style={{ padding: 32 }} className="muted">Reading data/eval/latest.json…</div>
  const h = e.headline || {}; const ma = e.multi_agent || {}
  const tiles: [string, string, string, boolean][] = [
    [`${pct(h.ping_precision)} / ${pct(h.ping_recall)}`, 'pinged the right agents', `precision / recall over ${ma.n_events ?? '…'} events; exact agent set in ${ma.agents_match ?? '…'}`, true],
    [`${h.false_still_valid ?? '…'}`, 'wrongly waved through', `false still_valid rate ${pct(h.false_still_valid_rate)}`, true],
    [`${r2(h.over_invalidation_trackback)} vs ${r2(h.over_invalidation_B1)}`, 'over-invalidation, Trackback vs flag-everything (B1)', 'flagged ÷ truly affected, per correction', true],
    [`${h.llm_calls_in_waves ?? '…'} vs ${h.llm_calls_rerun_all ?? '…'}`, 'LLM calls in waves vs rerunning every agent', 'the hub recomputes numbers in plain code', true],
    [`${h.memento_leaks ?? '…'} of ${h.memento_attempts ?? '…'}`, 'future documents leaked into a past decision', 'adversarial fetches, including a backdated memo', h.memento_leaks === 0],
    [`${h.replay_identical ?? '…'} of ${h.replay_artifacts ?? '…'}`, 'artifacts rebuilt byte for byte on replay', `replay fidelity ${pct(h.replay_fidelity)}`, true],
  ]
  return (
    <div className="scroll" style={{ height: '100%', padding: '32px 40px' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div className="smallcaps muted t16">Proof</div>
        <h1 className="serif" style={{ fontSize: 56, fontWeight: 500, lineHeight: 1.02, margin: '4px 0 12px', maxWidth: 900 }}>Two answer keys, written before the engine was tuned.</h1>
        <p className="t18 muted" style={{ maxWidth: 760, margin: 0 }}>{e.n_corrections} planted corrections scored artifact by artifact, and {ma.n_events ?? '…'} events scored on who should have been pinged. Every figure below is read from <span className="mono">data/eval/latest.json</span> ({e.generated_at}, {e.llm_mode} mode).</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16, marginTop: 28 }}>
          {tiles.map(([n, l, s, good]) => <div key={l} className="card" style={{ padding: '18px 20px', borderColor: good ? 'var(--ink)' : 'var(--rule)' }}>
            <div className="mono" style={{ fontSize: 32, fontWeight: 500, lineHeight: 1.1 }}>{n}</div>
            <div className="t16" style={{ fontWeight: 600, marginTop: 8 }}>{l}</div>
            <div className="t14 muted">{s}</div>
          </div>)}
        </div>
        <details style={{ marginTop: 28 }}><summary className="t16" style={{ cursor: 'pointer', fontWeight: 600 }}>All the numbers</summary>
          <table className="ledger-table" style={{ marginTop: 12 }}><thead><tr><th>Correction</th><th>Title</th><th className="n">Precision</th><th className="n">Recall</th><th className="n">Verdicts</th><th className="n">Flag-everything</th><th className="n">Trackback</th></tr></thead><tbody>
            {e.per_correction.map((s: any) => <tr key={s.correction}><td className="mono">{s.correction}</td><td>{s.title}</td><td className="n">{pct(s.precision)}</td><td className="n">{pct(s.recall)}</td><td className="n">{s.verdict_matches}/{s.n_expected}</td><td className="n">{s.naive_flagged}</td><td className="n">{s.trackback_flagged}</td></tr>)}
          </tbody></table>
          <p className="t14 muted">Key sha256 <span className="mono">{e.answer_key?.sha256}</span>, frozen {e.answer_key?.frozen}; later edits are logged in data/answer_key/CHANGELOG.md.</p>
        </details>
      </div>
    </div>
  )
}
