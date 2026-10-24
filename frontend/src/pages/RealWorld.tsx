import { useEffect, useState } from 'react'
import { api, fmt } from '../api'
import { title } from '../labels'
import { StatusIcon, RefusalStamp } from '../ui/primitives'
import { stateOf, STATE_WORD, reasonText } from '../model'

/* Lyft, February 13, 2024. Left: inside the finance team, with Trackback (reconstructed). Right: what actually happened (public record). */
const et = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' }) + ' ET'
void RefusalStamp

export default function RealWorld({ onShowLanes }: { onShowLanes: () => void }) {
  const [d, setD] = useState<any>(null); const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api.lyft().then(setD).catch(e => setErr(String(e))) }, [])
  if (err) return <div style={{ padding: 32 }} className="muted">The Lyft story is not loaded. Run make world. ({err})</div>
  if (!d) return <div style={{ padding: 32 }} className="muted">Loading…</div>
  const { inside, outside } = d
  const c = outside.correction
  const Tag = ({ real }: { real: boolean }) => <span className={`chip ${real ? '' : 'ping'}`} style={real ? { borderColor: 'var(--ink)' } : undefined}>{real ? 'public record' : 'reconstruction'}</span>
  return (
    <div className="scroll" style={{ height: '100%', padding: '28px 40px' }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div className="mono t14 muted">Lyft · February 13, 2024 · 4:06 PM ET</div>
        <h1 className="serif" style={{ fontSize: 56, fontWeight: 500, lineHeight: 1.02, margin: '6px 0 10px', maxWidth: 960 }}>The release said 500 basis points. The model it came from said 50.</h1>
        <p className="t18 muted" style={{ maxWidth: 760, margin: 0 }}>Shares rose as much as {outside.tape.after_hours_peak_pct}% after hours before the CFO corrected it on the call. Here is the same afternoon with Trackback inside the finance team.</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginTop: 28 }}>
          <section>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}><h2 className="serif" style={{ fontSize: 22, margin: 0, fontWeight: 600 }}>Inside the finance team</h2><Tag real={false} /></div>
            <div className="card" style={{ padding: '12px 16px' }}><div className="t14 muted">FP&A agent · guidance model</div><div className="mono t22">{inside.model ? `${fmt(inside.model.value_num, 'bps')} bps` : '…'} <span className="t16 muted" style={{ fontFamily: 'var(--sans)' }}>of margin expansion</span></div></div>
            <div className="t14 muted" style={{ padding: '6px 16px' }}>cited by</div>
            <div className="card" style={{ padding: '12px 16px' }}><div className="t14 muted">Reporting / IR agent · release draft</div><div className="serif t18" style={{ fontStyle: 'italic' }}>“…approximately 500 basis points year-over-year.”</div></div>
            <div className="t14 muted" style={{ padding: '6px 16px' }}>the CFO approves at {inside.approval ? et(inside.approval.decided_at) : '3:30 PM ET'}; the fence runs before anything is published</div>
            {inside.fence.blocked ? <div className="card" style={{ padding: '18px 20px', borderColor: 'var(--recall)', background: 'var(--hatch-red), var(--surface)', position: 'relative' }}>
              <span className="stamp stamp-in" style={{ fontSize: 22 }}>BLOCKED · states 500 · cites 50</span>
              <div className="t16" style={{ marginTop: 16 }}>The sentence says <b className="mono">500</b>. The number it cites is <b className="mono">50</b>. Same digits, different magnitude, so the release does not go out.</div>
              {inside.fence.fix && <div className="t16" style={{ marginTop: 8 }}>Proposed fix: <i className="serif">“{inside.fence.fix}”</i></div>}
            </div> : <div className="card" style={{ padding: 16 }}>The fence did not fire. Check the build.</div>}
          </section>
          <section>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}><h2 className="serif" style={{ fontSize: 22, margin: 0, fontWeight: 600 }}>What actually happened</h2><Tag real /></div>
            <div style={{ borderLeft: '1px solid var(--ink)', marginLeft: 6 }}>
              {outside.timeline.map((t: any, i: number) => <div key={i} style={{ position: 'relative', padding: '0 0 14px 18px' }}>
                <span style={{ position: 'absolute', left: -5, top: 6, width: 9, height: 9, borderRadius: 5, background: t.real ? 'var(--ink)' : 'var(--ping)' }} />
                <div className="mono t14 muted">{et(t.t)}{t.t.startsWith('2024-02-14') ? ', next day' : ''}</div>
                <div className="t16">{t.what.replace(' (reconstruction)', '')} {!t.real && <Tag real={false} />}</div>
              </div>)}
            </div>
            {c && <div className="card" style={{ padding: '14px 16px', marginTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><b>After the correction, outside the company</b><button className="btn primary" onClick={onShowLanes}>Show the ripple</button></div>
              {c.findings.map((f: any) => { const s = stateOf(f); return <div key={f.artifact_id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--rule)' }}>
                <StatusIcon state={s} /><span className="t16" style={{ flex: 1 }}>{title(f, 56)}</span><span className="t14 muted">{STATE_WORD[s]} · {reasonText(f.reason)}</span></div> })}
            </div>}
          </section>
        </div>
        <p className="t14 muted" style={{ marginTop: 24, maxWidth: 900 }}>Public record: the as-filed Exhibit 99.1, the CFO's correction on the call, the corrected release and the tape. Reconstructed from those numbers: the internal model, the drafts, and the outside notes and orders. Sources: {outside.tape.sources.join('; ')}.</p>
      </div>
    </div>
  )
}
