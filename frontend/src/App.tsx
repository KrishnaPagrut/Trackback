import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, dayLabel } from './api'
import Canvas from './deep/Canvas'
import { CounterStrip, Sidebar, Drawer, Scrubber, Footer, Palette, LedgerTable, type DrawerTab } from './deep/Panels'
import Stage from './stage/Stage'
import ProofPage from './pages/Proof'
import RealWorld from './pages/RealWorld'
import { Seg, RecallNotice } from './ui/primitives'
import { ancestors, descendants } from './model'

type World = 'tidewall' | 'lyft'
export default function App() {
  const qs = new URLSearchParams(window.location.search)
  const [mode, setMode] = useState<'stage' | 'deep'>(qs.get('mode') === 'deep' ? 'deep' : 'stage')
  const [world, setWorld] = useState<World>(qs.get('world') === 'lyft' ? 'lyft' : 'tidewall')
  const [view, setView] = useState<'graph' | 'ledger' | 'proof' | 'story'>(qs.get('view') === 'proof' ? 'proof' : qs.get('world') === 'lyft' ? 'story' : 'graph')
  const [state, setState] = useState<any>(null)
  const [correction, setCorrection] = useState<string | null>(null)
  const [graph, setGraph] = useState<any>(null)
  const [worldGraph, setWorldGraph] = useState<any>(null)
  const [pings, setPings] = useState<any[]>([])
  const [waves, setWaves] = useState<any[]>([])
  const [challenges, setChallenges] = useState<any[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [drawer, setDrawer] = useState<DrawerTab | null>(null)
  const [traceMode, setTraceMode] = useState<'on' | 'upon'>('on')
  const [rippleKey, setRippleKey] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const [palette, setPalette] = useState(false)
  const [help, setHelp] = useState(false)
  const [notice, setNotice] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pin, setPin] = useState('2026-07-08T09:00:00-07:00')
  const [doc, setDoc] = useState(qs.get('world') === 'lyft' ? 'lyft_q4_2023_release' : 'billing_export_2026_03')
  const [attempt, setAttempt] = useState<any>(null)
  const [sources, setSources] = useState<{ source_id: string; title: string }[]>([])
  const [artifacts, setArtifacts] = useState<any[]>([])
  const [headline, setHeadline] = useState<any>(null)
  const [evaluation, setEvaluation] = useState<any>(null)
  const [pending, setPending] = useState(0)
  const [laneFilter, setLaneFilter] = useState<string | null>(null)
  const [sound, setSound] = useState(false)
  const [kioskOn, setKioskOn] = useState(qs.get('kiosk') !== 'off')
  const idleSeconds = Number(qs.get('idle') || 60)
  const now = state?.now || '2026-07-08T09:00:00-07:00'

  const refresh = useCallback(() => { api.state().then(setState); setRefreshKey(k => k + 1) }, [])
  useEffect(() => { refresh(); api.sources().then(d => setSources(d.sources.map((s: any) => ({ source_id: s.source_id, title: s.title })))); api.evalLatest().then(e => setHeadline(e.headline)).catch(() => null) }, [refresh])
  useEffect(() => {
    let alive = true
    const load = (tries: number) => api.graph(world, null).then(g => { if (!alive) return; if (g.nodes.length || tries <= 0) setWorldGraph(g); else window.setTimeout(() => load(tries - 1), 400) }).catch(() => { if (alive && tries > 0) window.setTimeout(() => load(tries - 1), 400) })
    load(5); api.artifacts(world).then(d => setArtifacts(d.artifacts)).catch(() => null)
    return () => { alive = false }
  }, [world, refreshKey])
  useEffect(() => {
    if (!correction) { setGraph(worldGraph); setPings([]); setWaves([]); return }
    setGraph((g: any) => (g && g.correction?.correction_id === correction ? g : null))   // never lay out a correction on the idle graph
    api.graph(world, correction).then(setGraph); api.pings(correction).then(d => { setPings(d.pings); setWaves(d.waves) })
  }, [world, correction, refreshKey, worldGraph])
  useEffect(() => { if (!correction) { setEvaluation(null); return } api.evaluation(correction).then(setEvaluation).catch(() => setEvaluation(null)) }, [correction, refreshKey])
  useEffect(() => { api.challenges().then(d => setChallenges(d.challenges)).catch(() => null); api.approvals().then(d => setPending(d.actions.filter((a: any) => a.state === 'proposed' && correction && a.run_id === `correction:${correction}`).length)) }, [refreshKey, world, correction])

  const resetWorld = useCallback(async () => { await api.reset(); setCorrection(null); setSelected(null); setDrawer(null); setAttempt(null); setPin(now); setNotice(false); refresh() }, [now, refresh])
  const dropE11 = useCallback(async () => {
    setBusy(true)
    try { await api.liveE11(); setNotice(false); setWorld('tidewall'); setCorrection('E11'); setRippleKey(k => k + 1); refresh() } finally { setBusy(false) }
  }, [refresh])
  const travel = useCallback(async () => {
    setDoc('billing_export_2026_03'); const p = '2026-04-10T17:00:00-07:00'; setPin(p)
    const tm = await api.timemap('billing_export_2026_03'); const later = tm.versions.filter((v: any) => v.tx_from > '2026-07-01')
    if (later.length) setAttempt(await api.cheat('billing_export_2026_03', p, later[later.length - 1].version_id))
  }, [])

  const traceIds = useMemo(() => {
    if (!selected || !graph) return [] as string[]
    const s = traceMode === 'on' ? ancestors(graph.edges, selected) : descendants(graph.edges, selected)
    return [...s].filter(id => graph.nodes.find((n: any) => n.id === id && n.type === 'artifact'))
  }, [selected, graph, traceMode])
  const traceSet = useMemo(() => selected ? new Set([...traceIds, selected]) : null, [selected, traceIds])

  // keyboard: Stage mode handles its own keys; D and ⌘K work everywhere
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT')) return
      const k = e.key.toLowerCase()
      if (k === 'd' && !e.metaKey && !e.ctrlKey) { setMode(m => m === 'stage' ? 'deep' : 'stage'); return }
      if (k === 'k' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); setMode('deep'); setPalette(p => !p); return }
      if (mode === 'stage') return
      if (k === '?') setHelp(x => !x)
      else if (k === 'escape') { setDrawer(null); setPalette(false); setHelp(false); setNotice(false); setSelected(null) }
      else if (k === 'r') resetWorld()
      else if (k === 't') travel()
      else if (k === ' ' && !correction && world === 'tidewall') { e.preventDefault(); if (notice) dropE11(); else setNotice(true) }
      else if (k === 'a') setDrawer('approvals')
      else if (k === 's') setDrawer('pings')
      else if (k === 'b') setDrawer('who')
      else if (k === 'j') setDrawer('review')
      else if (k === 'e') setDrawer('lessons')
      else if (k === 'p') setView(v => v === 'proof' ? 'graph' : 'proof')
      else if (k === 'g') setView('graph')
      else if (k === 'l') setView('ledger')
      else if (k === 'm') setSound(s => !s)
    }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  })

  const header = (
    <header style={{ height: 56, flex: 'none', display: 'flex', alignItems: 'center', gap: 16, padding: '0 16px', borderBottom: '1px solid var(--rule)', background: 'var(--paper)', position: 'relative', zIndex: 20 }}>
      <div className="serif" style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.01em' }}>Trackback</div>
      <Seg value={world} onChange={(w: any) => { setWorld(w); setCorrection(null); setSelected(null); setAttempt(null); setDoc(w === 'lyft' ? 'lyft_q4_2023_release' : 'billing_export_2026_03'); setView(w === 'lyft' ? 'story' : 'graph') }}
        options={[{ v: 'tidewall', label: 'Tidewall' }, { v: 'lyft', label: 'Real world' }, { v: 'research' as World, label: 'Research', disabled: true, title: 'A second domain pack is not built in this version' }]} />
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        {mode === 'deep' && view !== 'proof' && !(world === 'lyft' && view === 'story') && <Seg value={view === 'ledger' ? 'ledger' : 'graph'} onChange={(v: any) => setView(v)} options={[{ v: 'graph', label: 'Graph' }, { v: 'ledger', label: 'Ledger' }]} />}
      </div>
      <span className="mono t14">Today · {dayLabel(now)}</span>
      <span className="chip" style={{ borderColor: 'var(--ink)' }}>{(state?.mode || 'replay') === 'replay' ? 'Replay' : state?.mode === 'record' ? 'Record' : 'Scripted'}</span>
      {mode === 'deep' && <button className="btn ghost" onClick={() => setView(v => v === 'proof' ? 'graph' : 'proof')}>{view === 'proof' ? 'Back to graph' : 'Proof'}</button>}
      <button className="btn primary" onClick={() => setMode(m => m === 'stage' ? 'deep' : 'stage')} title="D">{mode === 'stage' ? 'Deep mode' : 'Stage mode'}</button>
    </header>
  )

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {header}
      {/* Stage stays mounted so D never loses its place */}
      <div style={{ flex: 1, position: 'relative', display: mode === 'stage' ? 'block' : 'none' }}>
        {world === 'lyft' ? (mode === 'stage' && <RealWorld onShowLanes={() => { setMode('deep'); setView('graph'); setCorrection('LYFT_TYPO'); setRippleKey(k => k + 1) }} />)
          : <Stage world={{ graph: worldGraph }} onReset={resetWorld} kioskEnabled={kioskOn} idleSeconds={idleSeconds} active={mode === 'stage'} correction={correction} onCorrection={(c: string) => { setCorrection(c); setRippleKey(k => k + 1); refresh() }} />}
      </div>
      {mode === 'deep' && (view === 'proof' ? <div style={{ flex: 1, minHeight: 0 }}><ProofPage /></div>
        : world === 'lyft' && view === 'story' ? <div style={{ flex: 1, minHeight: 0 }}><RealWorld onShowLanes={() => { setView('graph'); setCorrection('LYFT_TYPO'); setRippleKey(k => k + 1) }} /></div>
        : <>
          <CounterStrip company={world} correction={correction} graph={graph} pings={pings} waves={waves} approvalsPending={pending} headline={headline} onRecall={world === 'tidewall' ? () => setNotice(true) : undefined} evaluation={evaluation} onJade={() => setDrawer('review')} />
          <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
            <Sidebar company={world} correction={correction} graph={graph} pings={pings} selected={selected} onSelect={id => { setSelected(id); setDrawer(d => d || 'who') }} traceMode={traceMode} setTraceMode={setTraceMode} traceIds={traceIds} />
            <main style={{ flex: 1, minWidth: 0, position: 'relative' }}>
              {view === 'ledger' ? <LedgerTable company={world} graph={graph} pings={pings} onSelect={id => { setSelected(id); setDrawer('who') }} laneFilter={laneFilter} />
                : <Canvas company={world} correction={correction} data={graph} pings={pings} selected={selected} onSelect={id => { setSelected(id); if (id) setDrawer(d => d || 'who') }} trace={selected ? traceSet : null} rippleKey={rippleKey} sound={sound}
                  onLaneMore={l => { setLaneFilter(l); setView('ledger') }} />}
              {notice && <div style={{ position: 'absolute', left: 24, top: 16, zIndex: 25 }}><RecallNotice id="E11" lot="7F3A" headline="March billing export: annual-plan revenue was released twice" reason="$118,000 counted twice across five gyms" issuer="Membership billing vendor" ts="Jul 8, 2026 · 9:05 AM" onDrop={dropE11} busy={busy} /></div>}
              {drawer && <Drawer tab={drawer} setTab={setDrawer} onClose={() => setDrawer(null)} selected={selected} company={world} refreshKey={refreshKey} onChanged={refresh} people={state?.people || {}} pings={pings} waves={waves} challenges={challenges} correction={correction} />}
              {palette && <Palette company={world} artifacts={artifacts} corrections={state?.corrections || []} onClose={() => setPalette(false)} onPick={p => {
                setPalette(false)
                if (p.kind === 'artifact') { setSelected(p.id); setDrawer('who'); setView('graph') }
                else if (p.kind === 'correction') { setCorrection(p.id); setRippleKey(k => k + 1); setView('graph') }
                else if (p.kind === 'date') { setPin(p.id); setDoc('billing_export_2026_03') }
                else if (p.kind === 'agent') { setLaneFilter(p.id); setView('ledger') }
              }} />}
              {help && <div className="drawer" style={{ width: 380 }}><div style={{ padding: 20 }}><div className="serif t32" style={{ marginBottom: 12 }}>Keys</div>
                {[['D', 'Stage mode or Deep mode'], ['Space', 'drop the recall notice'], ['⌘K', 'search anything'], ['T', 'time travel to April 10'], ['A', 'approvals'], ['S', 'ping log'], ['B', 'who built this'], ['J', "Jade's review"], ['E', 'lessons learned'], ['G / L', 'graph or ledger'], ['P', 'proof'], ['M', `sound ${sound ? 'on' : 'off'}`], ['R', 'reset'], ['Esc', 'close']].map(([k, v]) => <div key={k} style={{ display: 'flex', gap: 12, padding: '6px 0' }}><span className="kbd" style={{ minWidth: 56, textAlign: 'center' }}>{k}</span><span>{v}</span></div>)}
                <button className="btn" style={{ marginTop: 12 }} onClick={() => setKioskOn(k => !k)}>Kiosk loop in Stage mode: {kioskOn ? 'on' : 'off'}</button></div></div>}
            </main>
          </div>
          <Scrubber doc={doc} setDoc={setDoc} pin={pin} setPin={setPin} now={now} sources={sources} refreshKey={refreshKey} attempt={attempt} setAttempt={setAttempt} />
          <Footer state={state} pings={pings} />
        </>)}
    </div>
  )
}
