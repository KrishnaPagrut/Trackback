// Every number on screen comes from the API; the UI never types a figure.
/* eslint-disable @typescript-eslint/no-explicit-any */
export type Any = any
export type World = 'tidewall' | 'lyft'

async function j<T = Any>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, { headers: { 'content-type': 'application/json' }, ...init })
  const body = await r.json().catch(() => ({}))
  if (!r.ok && r.status !== 409 && r.status !== 403 && r.status !== 404) throw new Error(`${r.status} ${body.detail || r.statusText}`)
  return { ...body, _status: r.status } as T
}
const post = (url: string, body?: Any) => j(url, { method: 'POST', body: JSON.stringify(body ?? {}) })

export const api = {
  state: (w: World) => j(`/api/state?world=${w}`),
  stage: (w: World) => j(`/api/stage?world=${w}`),
  recons: (w: World, outcome?: string) => j(`/api/recons?world=${w}${outcome ? `&outcome=${outcome}` : ''}`),
  exceptions: (w: World) => j(`/api/exceptions?world=${w}`),
  evaluation: (w: World, id: string) => j(`/api/evaluations/${id}?world=${w}`),
  lineage: (w: World) => j(`/api/lineage?world=${w}`),
  file: (w: World, source: string, qs = '') => j(`/api/files/${source}?world=${w}${qs}`),
  ripple: (w: World, id: string) => j(`/api/ripple/${id}?world=${w}`),
  materiality: (w: World) => j(`/api/materiality?world=${w}`),
  approvals: (w: World) => j(`/api/approvals?world=${w}`),
  decide: (w: World, id: string, person: string, decision: string, reason = '') => post(`/api/approvals/${id}/decision?world=${w}`, { person, decision, reason }),
  act: (w: World, person: string) => post(`/api/people/${person}/act?world=${w}`),
  advance: (hours: number) => post('/api/clock/advance', { hours }),
  memo: (w: World, id: string) => j(`/api/memo/${id}?world=${w}`),
  memos: (w: World) => j(`/api/memos?world=${w}`),
  lessons: () => j('/api/lessons'),
  approveLesson: (id: string, person: string) => post(`/api/lessons/${id}/approve`, { person, decision: 'approved' }),
  gateLesson: (id: string) => post(`/api/lessons/${id}/gate`),
  rerun: () => post('/api/review/rerun'),
  scorecard: () => j('/api/scorecard'),
  timemap: (s: string) => j(`/api/memento/timemap/${s}`),
  timegate: (s: string, at: string) => j(`/api/memento/timegate/${s}?at=${encodeURIComponent(at)}`),
  attempt: (source: string, pin: string, version_id?: string) => post('/api/replay/attempt', { source, pin, version_id }),
  pings: (w: World) => j(`/api/pings?world=${w}`),
  built: (w: World, id: string) => j(`/api/built/${encodeURIComponent(id)}?world=${w}`),
  decision: (id: string) => j(`/api/decision/${encodeURIComponent(id)}`),
  correction: (free_text: string) => post('/api/corrections', { free_text }),
  s1: () => post('/api/s1'),
  events: () => j('/api/events?limit=120'),
  access: () => j('/api/access'),
  reset: () => post('/api/reset'),
  undo: () => post('/api/undo'),
}

// ---------------------------------------------------------------- formatting (figures arrive as numbers; display precision is chosen here)
export function money(v: Any, opts: { k?: boolean; m?: boolean; cents?: boolean } = {}): string {
  if (v == null || typeof v !== 'number' || Number.isNaN(v)) return v == null ? '—' : String(v)
  const neg = v < 0
  const a = Math.abs(v)
  let s: string
  if (opts.m || a >= 1e9) s = a >= 1e9 ? `$${(a / 1e9).toFixed(2)}B` : `$${(a / 1e6).toFixed(1)}M`
  else if (opts.k) s = `$${Math.round(a / 1000).toLocaleString()}K`
  else s = `$${a.toLocaleString(undefined, { minimumFractionDigits: opts.cents ? 2 : 0, maximumFractionDigits: opts.cents ? 2 : 0 })}`
  return neg ? `−${s}` : s
}
export function fig(v: Any, unit?: string | null, id = ''): string {
  if (v == null) return '—'
  if (typeof v === 'string') return v
  if (unit === 'ratio' || id.startsWith('leverage') || id.startsWith('policy.max')) return `${v.toFixed(2)}x`
  if (unit === 'pct' || id.startsWith('membership_growth')) return `${v.toFixed(1)}%`
  if (unit === 'bps') return `${v.toLocaleString()} bps`
  if (Math.abs(v) >= 1e9) return money(v)
  if (Math.abs(v) < 1 && v !== 0) return v.toFixed(2)
  return money(v)
}
export const lev = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(2)}x`)
export const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`)
export function when(ts?: string | null, withTime = true): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  const tz = ts.includes('-05:00') ? 'America/New_York' : 'America/Los_Angeles'
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() !== 2026 ? 'numeric' : undefined, timeZone: tz })
  if (!withTime) return date
  return `${date}, ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: tz })} ${tz === 'America/New_York' ? 'ET' : 'PT'}`
}

export const REASON: Record<string, string> = {
  value_changed: 'value changed', conclusion_flipped: 'conclusion flipped', stale_and_value_changed: 'stale, and the value changed', input_changed: 'an input changed',
  display_unchanged: 'moves, but not at the precision shown', value_unchanged: 'recomputed: same value', conclusion_unchanged: 'conclusion holds', not_consumed: 'never used the corrected figures',
  different_line_item: 'reads other accounts', different_period: 'reads another period', policy: 'a contract or policy term', inputs_unchanged: 'inputs unchanged', unlinked: 'no link found',
  below_materiality: 'no material change', pending_owner: 'owner pinged', early_cutoff: 'recomputed: identical',
}
export const reason = (r?: string | null) => (r ? REASON[r] || r.replace(/_/g, ' ') : '')
export const PEOPLE: Record<string, string> = { dana: 'Dana Ortiz', sam: 'Sam Whitfield', priya: 'Priya Nair', marco: 'Marco Bell', lena: 'Lena Park', cfo: 'Lyft CFO', general_counsel: 'General Counsel', editor: 'Newsroom editor', pm: 'Portfolio manager' }
export const AGENT: Record<string, string> = { close_accountant: 'Close Accountant', covenant_comp: 'Covenant and Comp', reporting_analyst: 'Reporting Analyst', newsroom: 'Newsroom', street_analyst: 'Sell-side desk', lyft_ir: 'Reporting and IR', lyft_fpa: 'FP&A', trackback: 'Trackback' }
export const who = (k?: string | null) => (k ? PEOPLE[k] || AGENT[k] || k : '—')
