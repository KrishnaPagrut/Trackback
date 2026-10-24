export type Finding = {
  artifact_id: string; artifact_version: number; verdict: 'invalidated' | 'unaffected' | 'needs_review' | 'unprovable'; reason: string; reason_label?: string
  old_value: number | null; new_value: number | null; hop: number; judge_model?: string | null; judge_rationale?: string | null; proposed_rewrite?: string | null
  kind?: string; line_item?: string; period?: string; content?: string; lot?: string; correction_id?: string
}
export type Artifact = {
  artifact_id: string; version: number; kind: string; run_id: string; pinned_at: string; period: string | null; line_item: string | null; content: string | null
  value_num: number | null; conclusions: Record<string, unknown> | null; status: string; lot: string; badge: string; latest_finding: Finding | null; tx_from: string
}
export type GraphNode = {
  id: string; type: 'artifact' | 'source'; kind?: string; label: string; line_item?: string; period?: string; value?: number | null; lot?: string; status?: string; badge?: string
  run_id?: string; content?: string; verdict?: string | null; reason?: string | null; reason_label?: string | null; hop?: number | null; old_value?: number | null; new_value?: number | null
  rewrite?: string | null; system?: string; versions?: number; corrected?: boolean
}
export type GraphEdge = { id: string; source: string; target: string; dep: string; claim_changed?: boolean }

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let msg = r.statusText
    try { const b = await r.json(); msg = b.detail || JSON.stringify(b) } catch { /* ignore */ }
    throw new Error(`${r.status} ${msg}`)
  }
  return r.json()
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any
export const api = {
  state: () => j<Any>('/api/state'),
  artifacts: (company: string) => j<{ artifacts: Artifact[] }>(`/api/artifacts?company=${company}`),
  artifact: (id: string) => j<Any>(`/api/artifact/${encodeURIComponent(id)}`),
  graph: (company: string, correction?: string | null) => j<{ nodes: GraphNode[]; edges: GraphEdge[]; counts: Record<string, number>; naive_count: number | null; correction: Any }>(`/api/graph?company=${company}${correction ? `&correction=${correction}` : ''}`),
  corrections: () => j<Any>('/api/corrections'),
  correction: (id: string) => j<Any>(`/api/corrections/${id}`),
  postCorrection: (body: Any) => j<Any>('/api/corrections', { method: 'POST', body: JSON.stringify(body) }),
  parse: (text: string) => j<Any>('/api/corrections/parse', { method: 'POST', body: JSON.stringify({ free_text: text }) }),
  liveE11: () => j<Any>('/api/live/e11', { method: 'POST' }),
  scenarioB: () => j<Any>('/api/live/scenario-b', { method: 'POST' }),
  reset: () => j<Any>('/api/reset', { method: 'POST' }),
  undo: () => j<Any>('/api/undo', { method: 'POST' }),
  approvals: () => j<Any>('/api/approvals'),
  decide: (actionId: string, approver: string, decision: string, reason: string) => j<Any>(`/api/approvals/${encodeURIComponent(actionId)}`, { method: 'POST', body: JSON.stringify({ approver, decision, reason }) }),
  norms: () => j<Any>('/api/norms'),
  approveNorm: (id: string, approver: string) => j<Any>(`/api/norms/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver, decision: 'approved', reason: '' }) }),
  events: () => j<Any>('/api/events'),
  timemap: (doc: string) => j<Any>(`/api/timemap/${doc}`),
  lyft: () => j<Any>('/api/realworld/lyft'),
  sources: () => j<Any>('/api/sources'),
  memento: (doc: string, at: string) => j<Any>(`/api/memento/${doc}?at=${encodeURIComponent(at)}`),
  cheat: (doc_id: string, pin: string, version_id?: string) => j<Any>('/api/cheat', { method: 'POST', body: JSON.stringify({ doc_id, pin, version_id }) }),
  executed: () => j<Any>('/api/actions/executed'),
  decision: (id: string) => j<Any>(`/api/actions/${encodeURIComponent(id)}/decision`),
  evalLatest: () => j<Any>('/api/eval'),
  evalV2: () => j<Any>('/api/eval_v2'),
  answerKey: () => j<Any>('/api/answer-key'),
  claims: (q: string) => j<Any>(`/api/claims/search?q=${encodeURIComponent(q)}`),
  ledger: () => j<Any>('/api/ledger'),
  pings: (correction?: string | null) => j<Any>(`/pings${correction ? `?correction=${correction}` : ''}`),
  challenges: () => j<Any>('/challenges'),
  wellKnown: () => j<Any>('/.well-known/trackback'),
  misstatements: () => j<Any>('/api/misstatement-log'),
  evaluation: (c: string) => j<Any>(`/api/evaluations/${encodeURIComponent(c)}`),
  evaluations: () => j<Any>('/api/evaluations'),
  lessons: () => j<Any>('/api/lessons'),
  playbook: () => j<Any>('/api/playbook'),
  gateLesson: (id: string) => j<Any>(`/api/lessons/${encodeURIComponent(id)}/gate`, { method: 'POST' }),
  approveLesson: (id: string, approver: string) => j<Any>(`/api/lessons/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify({ approver }) }),
  approvePendingLessons: (approver: string) => j<Any>('/api/lessons/approve-pending', { method: 'POST', body: JSON.stringify({ approver }) }),
}
export const fmt = (v: number | null | undefined, line?: string | null): string => {
  if (v === null || v === undefined) return '—'
  const li = (line || '').toLowerCase()
  if (li.includes('leverage') || li === 'ratio') return `${v.toFixed(2)}x`
  if (li.includes('margin') || li.includes('growth') || li.includes('progress') || li.includes('payout_ratio')) return `${v.toFixed(1)}%`
  if (li === 'bps' || li.endsWith('_bps')) return `${v.toFixed(0)}`
  if (/(^|_)rate$|^fx|fixing/.test(li)) return v.toFixed(4)
  if (li.includes('aging') || li.includes('days')) return `${v.toFixed(0)} days`
  if (v < 0 && !(li.includes('leverage') || li === 'ratio' || li.includes('margin') || li.includes('growth') || li.includes('rate') || li.endsWith('bps') || li === 'bps')) return `-${fmt(-v, line)}`
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  if (Math.abs(v) >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}
export const dateLabel = (iso: string | null | undefined) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles' })
}
export const dayLabel = (iso: string | null | undefined) => iso ? new Date(iso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/Los_Angeles' }) : ''
