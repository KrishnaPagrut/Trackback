import { LedgerCard, Rail, RecallNotice, RefusalStamp, Envelope, Seg, StatusIcon } from '../ui/primitives'
import { LANES, STATE_WORD, type State } from '../model'

/* /styleguide: tokens, type scale, the ledger card in every state, the lane rail and the three hero moments. */
const TOKENS: [string, string, string][] = [
  ['paper', '#F7F4EE', 'App background'], ['surface', '#FFFFFF', 'Cards, drawers'], ['ink', '#1C1B19', 'Primary text, the active path'], ['ink-muted', '#6B675F', 'Secondary text, idle edges'],
  ['rule', '#E3DED4', 'Hairlines, lane dividers'], ['recall', '#C62828', 'Invalidated, refusals, the trackback notice'], ['cleared', '#2E7D32', 'Still valid'], ['caution', '#B26A00', 'Needs a human'], ['ping', '#1F5FBF', 'Pings, reworked'],
]
const sample = (state: State, extra: any = {}) => ({ id: 'leverage_2026_q1', type: 'artifact', kind: 'number', lot: '02F3', value: 2.946, line_item: 'leverage', verdict: state === 'idle' ? null : state === 'cleared' || state === 'skipped' ? 'unaffected' : state === 'caution' ? 'needs_review' : 'invalidated', reason: state === 'cleared' ? 'conclusion_unchanged' : state === 'skipped' ? 'claim_unchanged' : state === 'reworked' ? 'rerendered' : 'conclusion_flipped', old_value: 2.946, new_value: state === 'invalidated' ? 3.03 : 2.946, ...extra })

export default function Styleguide() {
  const states: State[] = ['idle', 'invalidated', 'cleared', 'caution', 'reworked', 'skipped', 'superseded']
  return (
    <div className="scroll" style={{ height: '100%', padding: '32px 40px' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div className="smallcaps muted t16">Styleguide</div>
        <h1 className="serif" style={{ fontSize: 56, fontWeight: 500, margin: '4px 0 24px' }}>The ledger and the trackback notice</h1>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>Tokens</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, margin: '12px 0 32px' }}>
          {TOKENS.map(([n, hex, use]) => <div key={n} className="card" style={{ display: 'flex', gap: 12, padding: 12, alignItems: 'center' }}>
            <div style={{ width: 48, height: 48, borderRadius: 6, background: hex, border: '1px solid var(--rule)' }} /><div><div style={{ fontWeight: 600 }}>{n}</div><div className="mono t14">{hex}</div><div className="t14 muted">{use}</div></div></div>)}
          <div className="card" style={{ display: 'flex', gap: 12, padding: 12, alignItems: 'center' }}><div style={{ width: 48, height: 48, borderRadius: 6, background: 'rgba(28,27,25,0.4)' }} /><div><div style={{ fontWeight: 600 }}>superseded</div><div className="mono t14">ink at 40%</div><div className="t14 muted">Old versions</div></div></div>
        </div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>Type</h2>
        <div className="card" style={{ padding: 20, margin: '12px 0 32px' }}>
          <div className="serif t56" style={{ fontWeight: 500 }}>Newsreader 56 · 2 of 3</div>
          <div className="serif t32">Newsreader 32 · page titles</div>
          <div className="t22" style={{ fontWeight: 600 }}>IBM Plex Sans 22 · agent names</div>
          <div className="t18">IBM Plex Sans 18 · node labels</div>
          <div className="t16">IBM Plex Sans 16 · body text</div>
          <div className="t14 muted">IBM Plex Sans 14 · secondary</div>
          <div className="mono t18">IBM Plex Mono 18 · $10,302,000 · 3.030x · LOT 7F3A · v2</div>
          <div className="smallcaps t16 muted" style={{ marginTop: 8 }}>Layer 1 · close accountant</div>
        </div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>The ledger card, in every state</h2>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', margin: '12px 0 8px' }}>
          {states.map(s => <div key={s}><LedgerCard n={sample(s)} state={s} /><div className="t14 muted" style={{ marginTop: 6 }}>{s === 'idle' ? 'Idle' : STATE_WORD[s]}</div></div>)}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', margin: '12px 0 32px' }}>
          <div><LedgerCard n={{ id: 'deck_s_covenant', type: 'artifact', kind: 'sentence', lot: '8C21', content: 'We remain within our 3.00x covenant: net leverage was 2.95x.', verdict: 'invalidated', reason: 'prose_judged', rewrite: 'x' }} state="reworked" /><div className="t14 muted" style={{ marginTop: 6 }}>A sentence, reworked</div></div>
          <div><LedgerCard n={{ id: 'cert_send_q1_2026', type: 'artifact', kind: 'action', lot: 'A7A1', value: 2.95, line_item: 'leverage', verdict: 'invalidated', reason: 'conclusion_flipped' }} state="caution" /><div className="t14 muted" style={{ marginTop: 6 }}>An action that already happened</div></div>
        </div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>Icons, pattern and color, never color alone</h2>
        <div style={{ display: 'flex', gap: 24, margin: '12px 0 32px', alignItems: 'center' }}>{(['invalidated', 'cleared', 'caution', 'reworked', 'skipped', 'pending'] as State[]).map(s => <span key={s} style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><StatusIcon state={s} />{STATE_WORD[s]}</span>)}</div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>Lane rail</h2>
        <div className="card" style={{ padding: 16, display: 'flex', gap: 32, margin: '12px 0 32px' }}>
          <Rail lane={LANES.tidewall[1]} live="Re-checking 1 item" /><Rail lane={LANES.tidewall[4]} live="Waiting for a human" /><Rail lane={LANES.tidewall[3]} live="Not pinged" />
        </div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>The three hero moments</h2>
        <div style={{ display: 'flex', gap: 40, alignItems: 'flex-start', flexWrap: 'wrap', margin: '12px 0 32px' }}>
          <RecallNotice id="E11" lot="7F3A" headline="March billing export: annual-plan revenue was released twice" reason="$118,000 counted twice across five gyms" issuer="Membership billing vendor" ts="Jul 8, 2026 · 9:05 AM" onDrop={() => null} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 28, paddingTop: 24 }}>
            <Envelope postmark="CC · wave 1 · 9:05 AM" />
            <div className="card" style={{ padding: '12px 16px', maxWidth: 440, border: '1.5px solid var(--ping)', borderRadius: '14px 14px 14px 2px' }}>Your lender certificate rests on net leverage, which changed from 2.95x to 3.03x. It now crosses your 3.00x covenant. Still valid?</div>
            <div style={{ padding: '20px 0' }}><RefusalStamp published="July 8" decision="April 10" animate={false} /></div>
          </div>
        </div>

        <h2 className="serif t32" style={{ fontWeight: 500 }}>Controls</h2>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', margin: '12px 0 48px', flexWrap: 'wrap' }}>
          <button className="btn primary">Drop on the source</button><button className="btn">Secondary</button><button className="btn ghost">Ghost</button>
          <Seg value="graph" onChange={() => null} options={[{ v: 'graph', label: 'Graph' }, { v: 'ledger', label: 'Ledger' }]} />
          <Seg value="on" onChange={() => null} options={[{ v: 'on', label: 'Built on' }, { v: 'upon', label: 'Built upon' }]} />
          <span className="chip recall">Wrong now</span><span className="chip cleared">Still valid</span><span className="chip caution">Waiting for the CFO</span><span className="chip ping">Reworked</span><span className="lot">LOT 7F3A</span><span className="kbd">⌘K</span>
        </div>
      </div>
    </div>
  )
}
