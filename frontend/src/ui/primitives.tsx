import type { ReactNode } from 'react'
import { X, Check, AlertCircle, RefreshCw, CircleDashed, Mail, MinusCircle } from 'lucide-react'
import { fmt } from '../api'
import { nodeTitle, reasonText, STATE_WORD, type State, type Lane } from '../model'

const IC = { size: 18, strokeWidth: 1.5 }
export function StatusIcon({ state, size = 18 }: { state: State; size?: number }) {
  const p = { ...IC, size }
  if (state === 'invalidated') return <span className="status" style={{ color: 'var(--recall)' }} aria-label="invalidated"><X {...p} strokeWidth={2.25} /></span>
  if (state === 'cleared') return <span className="status" style={{ color: 'var(--cleared)' }} aria-label="still valid"><Check {...p} strokeWidth={2.25} /></span>
  if (state === 'caution') return <span className="status" style={{ color: 'var(--caution)' }} aria-label="needs a human"><AlertCircle {...p} strokeWidth={2} /></span>
  if (state === 'reworked') return <span className="status" style={{ color: 'var(--ping)' }} aria-label="reworked"><RefreshCw {...p} strokeWidth={2} /></span>
  if (state === 'skipped') return <span className="status" style={{ color: 'var(--ink-muted)' }} aria-label="skipped"><MinusCircle {...p} /></span>
  if (state === 'pending') return <span className="status" style={{ color: 'var(--ping)' }} aria-label="re-checking"><Mail {...p} /></span>
  if (state === 'superseded') return <span className="status" style={{ color: 'var(--ink-muted)' }}><CircleDashed {...p} /></span>
  return null
}

export const Lot = ({ code }: { code?: string | null }) => code ? <span className="lot">LOT {code}</span> : null

export function LedgerCard({ n, state, selected, dim, onClick }: { n: any; state: State; selected?: boolean; dim?: boolean; onClick?: () => void }) {
  const moved = n.verdict && n.old_value != null && n.new_value != null && n.old_value !== n.new_value
  const isProse = n.kind === 'sentence'
  const t = n.members ? `${nodeTitle({ id: n.members[0].replace(/_G\d(?=_|$)/, '') })}, ${n.members.length} gyms` : nodeTitle(n, 70)
  const val = n.members ? (moved ? '' : '') : n.kind === 'sentence' || n.type === 'source' ? '' : fmt(n.value, n.line_item)
  const cls = ['ledger', state === 'idle' ? '' : state, selected ? 'selected' : '', dim ? 'dim' : ''].join(' ')
  return (
    <div className={cls} onClick={onClick} role="button" tabIndex={0} aria-label={t}>
      <div className="top"><Lot code={n.lot} />{n.type === 'source' && <span className="muted t14">{(n.system || 'source').replace(/_/g, ' ')}</span>}<StatusIcon state={state} /></div>
      <div className={`title ${isProse ? 'prose' : ''}`} style={isProse ? { fontSize: 16 } : undefined}>{isProse ? `“${t}”` : t}</div>
      {moved ? <div className="value"><span className="old">{fmt(n.old_value, n.line_item)}</span>{fmt(n.new_value, n.line_item)}</div> : val ? <div className="value">{val}</div> : null}
      {n.members && <div className="t14 muted">{n.nInv ? `${n.nInv} of ${n.members.length} changed` : `${n.members.length} gyms`}</div>}
      {n.verdict && state !== 'idle' && <div className="why">{STATE_WORD[state]}{state !== 'skipped' && n.reason ? ` · ${reasonText(n.reason)}` : ''}</div>}
    </div>
  )
}

export function Monogram({ text, size = 40 }: { text: string; size?: number }) {
  return <div className="mono-avatar" style={{ width: size, height: size, fontSize: Math.max(16, Math.round(size * 0.42)) }}>{text}</div>
}

export function Rail({ lane, live, badge }: { lane: Lane; live?: string; badge?: ReactNode }) {
  return (
    <div style={{ width: 200, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <Monogram text={lane.mono} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 16, lineHeight: 1.2 }}>{lane.name}</div>
        <div className="t14 muted" style={{ lineHeight: 1.25 }}>{lane.seat}</div>
        {live && <div className="t14" style={{ marginTop: 4, whiteSpace: 'nowrap', color: live.startsWith('Re-checking') ? 'var(--ping)' : live.startsWith('Waiting') ? 'var(--caution-ink)' : 'var(--ink)' }}>{live}</div>}
        {badge}
      </div>
    </div>
  )
}

export function RecallNotice({ id, lot, headline, reason, issuer, ts, onDrop, busy, dropLabel = 'Drop on the source' }: { id: string; lot: string; headline: string; reason: string; issuer: string; ts: string; onDrop?: () => void; busy?: boolean; dropLabel?: string }) {
  return (
    <div className="recall-notice drop-in" role="dialog" aria-label="Recall notice">
      <div className="band"><span>RECALL NOTICE</span><span>{id}</span></div>
      <div className="body">
        <h3>{headline}</h3>
        <dl>
          <dt>Lot</dt><dd><Lot code={lot} /></dd>
          <dt>Reason</dt><dd>{reason}</dd>
          <dt>Issued by</dt><dd>{issuer}</dd>
          <dt>Time</dt><dd className="mono">{ts}</dd>
        </dl>
        {onDrop && <button className="btn primary" disabled={busy} onClick={onDrop}>{busy ? 'Tracing forward…' : dropLabel}</button>}
      </div>
    </div>
  )
}

export function RefusalStamp({ published, decision, animate = true }: { published: string; decision: string; animate?: boolean }) {
  return <span className={`stamp ${animate ? 'stamp-in' : ''}`}>REFUSED · published {published} · decision time {decision}</span>
}

export function Envelope({ postmark }: { postmark?: string }) {
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><span className="envelope"><Mail size={16} strokeWidth={1.5} /></span>{postmark && <span className="postmark">{postmark}</span>}</span>
}

export function Seg<T extends string>({ value, options, onChange }: { value: T; options: { v: T; label: string; disabled?: boolean; title?: string }[]; onChange: (v: T) => void }) {
  return <div className="seg" role="tablist">{options.map(o => <button key={o.v} role="tab" aria-selected={value === o.v} className={value === o.v ? 'on' : ''} disabled={o.disabled} title={o.title} onClick={() => onChange(o.v)}>{o.label}</button>)}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="serif" style={{ fontSize: 22, color: 'var(--ink-muted)', padding: 24, fontStyle: 'italic' }}>{children}</div>
}
