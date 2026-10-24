import { fmt, type GraphNode, type GraphEdge } from './api'
import { title, GYM } from './labels'

/* ---------------------------------------------------------------- lanes */
export type Lane = { id: string; name: string; seat: string; mono: string }
export const LANES: Record<string, Lane[]> = {
  tidewall: [
    { id: 'sources', name: 'Sources', seat: 'What the agents read', mono: 'S' },
    { id: 'close_accountant', name: 'Close Accountant', seat: 'Senior Accountant, Close', mono: 'CA' },
    { id: 'trackback', name: 'Trackback', seat: 'Recomputes every number', mono: 'T' },
    { id: 'reporting_analyst', name: 'Reporting Analyst', seat: 'FP&A, deck and cash', mono: 'RA' },
    { id: 'covenant_comp', name: 'Covenant and Comp', seat: 'Certificate, bonuses, tax', mono: 'CC' },
    { id: 'humans', name: 'Humans', seat: 'Controller, CFO, HR', mono: 'H' },
  ],
  lyft: [
    { id: 'sources', name: 'Sources', seat: 'Model, close pack, release', mono: 'S' },
    { id: 'lyft_fpa', name: 'FP&A', seat: 'Guidance model', mono: 'FP' },
    { id: 'lyft_ir', name: 'Reporting / IR', seat: 'Release and call script', mono: 'IR' },
    { id: 'lyft_disclosure', name: 'Disclosure', seat: 'The 8-K', mono: 'DC' },
    { id: 'trackback', name: 'Trackback', seat: 'Recomputes every number', mono: 'T' },
    { id: 'street_analyst', name: 'Street analyst', seat: 'Outside: notes, orders', mono: 'SA' },
    { id: 'newsroom', name: 'Newsroom', seat: 'Outside: the headline', mono: 'NR' },
    { id: 'humans', name: 'Humans', seat: 'Approvers', mono: 'H' },
  ],
}
export const AGENT_LANES = (company: string) => LANES[company].filter(l => !['sources', 'trackback', 'humans'].includes(l.id))
export const agentLane = (company: string, id: string) => LANES[company].find(l => l.id === id)

export function laneOf(n: GraphNode & any): string {
  if (n.type === 'source') return 'sources'
  if (n.comp) return 'humans'
  if (n.node_kind === 'calc' || n.kind === 'number' || n.kind === 'forecast_cell') return 'trackback'
  return n.agent_id || 'trackback'
}

/* ---------------------------------------------------------------- one state per node: icon + pattern + color */
export type State = 'invalidated' | 'cleared' | 'caution' | 'reworked' | 'superseded' | 'skipped' | 'idle' | 'pending'
export function stateOf(n: any, pingedNodes?: Set<string>): State {
  if (!n.verdict) return 'idle'
  if (n.verdict === 'invalidated' && n.kind === 'action') return 'caution'
  if (n.verdict === 'needs_review') return 'caution'
  if (n.verdict === 'invalidated' && (n.reason === 'rerendered' || (n.kind === 'sentence' && n.rewrite))) return 'reworked'
  if (n.verdict === 'invalidated') return 'invalidated'
  if (n.verdict === 'unaffected') return pingedNodes && !pingedNodes.has(n.id) && ['claim_unchanged', 'different_period', 'different_line_item', 'fields_not_read', 'supporters_cleared', 'below_materiality'].includes(n.reason) ? 'skipped' : 'cleared'
  return 'idle'
}
export const STATE_WORD: Record<State, string> = {
  invalidated: 'Wrong now', cleared: 'Still valid', caution: 'Needs a human', reworked: 'Reworked', superseded: 'Superseded', skipped: 'Skipped, no material change', idle: '', pending: 'Re-checking',
}
export const REASON: Record<string, string> = {
  value_changed: 'number changed', conclusion_flipped: 'conclusion flipped', prose_judged: 'sentence no longer true', rerendered: 'figure updated in place',
  compensation_proposed: 'already acted on', claim_unchanged: 'did not read the changed rows', different_period: 'different period', different_line_item: 'different line',
  below_materiality: 'moved less than the threshold', conclusion_unchanged: 'conclusion still holds', early_cutoff: 'change too small to carry', estimate_change: 'estimate change, left as is',
  fields_not_read: 'did not read that field', supporters_cleared: 'everything it rests on cleared', parameters_within_materiality: 'within tolerance', supporter_retracted: 'a source was retracted',
}
export const reasonText = (r?: string | null) => (r && REASON[r]) || (r || '').replace(/_/g, ' ')

/* ---------------------------------------------------------------- reduced graph: keep a subset, connect it through hidden nodes */
export function reduceEdges(edges: GraphEdge[], keep: Set<string>): { source: string; target: string }[] {
  const out: Record<string, string[]> = {}
  edges.forEach(e => { (out[e.source] ||= []).push(e.target) })
  const res: { source: string; target: string }[] = []; const seen = new Set<string>()
  keep.forEach(s => {
    const stack = [...(out[s] || [])]; const visited = new Set<string>()
    while (stack.length) {
      const x = stack.pop()!
      if (visited.has(x)) continue; visited.add(x)
      if (keep.has(x)) { const k = `${s}>${x}`; if (!seen.has(k)) { seen.add(k); res.push({ source: s, target: x }) } continue }
      ;(out[x] || []).forEach(y => stack.push(y))
    }
  })
  return res
}
export function ancestors(edges: GraphEdge[], id: string): Set<string> {
  const into: Record<string, string[]> = {}; edges.forEach(e => { (into[e.target] ||= []).push(e.source) })
  const seen = new Set<string>(); const st = [id]
  while (st.length) { const x = st.pop()!; (into[x] || []).forEach(y => { if (!seen.has(y)) { seen.add(y); st.push(y) } }) }
  return seen
}
export function descendants(edges: GraphEdge[], id: string): Set<string> {
  const out: Record<string, string[]> = {}; edges.forEach(e => { (out[e.source] ||= []).push(e.target) })
  const seen = new Set<string>(); const st = [id]
  while (st.length) { const x = st.pop()!; (out[x] || []).forEach(y => { if (!seen.has(y)) { seen.add(y); st.push(y) } }) }
  return seen
}

/* ---------------------------------------------------------------- display */
export const valueText = (n: any) => (n.kind === 'sentence' || n.type === 'source') ? '' : n.kind === 'action' ? (n.value != null ? fmt(n.value, n.line_item) : '') : fmt(n.value, n.line_item)
export const nodeTitle = (n: any, max = 64) => title(n, max)
export const gymName = (g: string) => GYM[g] || g

/* ---------------------------------------------------------------- plain-language pings (from the real ping payload) */
const KEEP = /^(January|February|March|April|May|June|July|August|September|October|November|December|Q[1-4]|TTM|EBITDA|GM|AP|FY|H[12]|[A-Z]{2,})\b/
const lc = (s: string) => KEEP.test(s) ? s : s.charAt(0).toLowerCase() + s.slice(1)
const fieldName = (id: string) => lc(title({ id }).replace(/, Q1$/, ''))
export type PingStory = { agent: string; ask: string; reply: string; replyTone: State; extra: string[]; postmark: string; items: number; focus: string | null }
const crossed = (i: any) => (i.changed_fields || []).some((c: any) => c.crossed_threshold)
export function pingStory(p: any, compByArtifact: Record<string, any>): PingStory {
  const items: any[] = p.items || []
  const resp: any[] = p.response?.items || []
  const pick = items.find(i => i.kind === 'action' && crossed(i)) || items.find(i => crossed(i)) || items.find(i => i.kind === 'sentence') || items[0]
  const fields: any[] = (pick?.changed_fields || []).filter((c: any) => c.old != null && c.new != null && !c.claim)
  const f = fields.find(c => c.crossed_threshold) || [...fields].sort((a, b) => Math.abs((b.new - b.old) / (b.old || 1)) - Math.abs((a.new - a.old) / (a.old || 1)))[0] || (pick?.changed_fields || [])[0]
  const what = pick ? title({ id: pick.artifact_id }).replace(/, sent$|, paid$|, published$/, '') : 'work'
  const line = f?.claim ? (f.label || 'a source row').replace(/_/g, ' ') : f ? fieldName(f.field) : 'an input'
  const unit = f?.field?.includes('leverage') ? 'leverage' : pick?.line_item
  const max = pick?.conclusions?.covenant_max
  const ask = f && f.old != null && f.new != null
    ? `Your ${lc(what)} rests on ${line}, which changed from ${fmt(f.old, unit)} to ${fmt(f.new, unit)}.${f.crossed_threshold || crossed(pick) ? (max ? ` It now crosses your ${max.toFixed(2)}x covenant.` : ' It now crosses your threshold.') : ''} Still valid?`
    : `Something your ${what.toLowerCase()} rests on changed. Still valid?`
  const order = (v: string) => v === 'needs_human' ? 0 : v === 'reworked' ? 1 : 2
  const sorted = [...resp].sort((a, b) => order(a.verdict) - order(b.verdict))
  const top = sorted[0]
  let reply = 'No reply yet.'; let replyTone: State = 'pending'; const extra: string[] = []
  if (top) {
    const t = title({ id: top.artifact_id })
    if (top.verdict === 'needs_human') { const comp = compByArtifact[top.artifact_id]; reply = `Needs a human: ${comp ? compText(comp, t) : `${t.toLowerCase()} already went out; a fix waits for approval`}.`; replyTone = 'caution' }
    else if (top.verdict === 'reworked') { reply = `Reworked: ${top.artifact_id.startsWith('memo') ? 'the memo now states the corrected figure' : t.startsWith('“') ? 'the sentence is rewritten with the new figure' : `${t} is redone`}.`; replyTone = 'reworked' }
    else { reply = `Still valid: ${(top.reason || 'it still holds').split('.')[0].toLowerCase()}.`; replyTone = 'cleared' }
    const others = resp.filter(r => r !== top)
    const nh = others.filter(r => r.verdict === 'needs_human').length, rw = others.filter(r => r.verdict === 'reworked').length
    if (nh) extra.push(`${nh} more already acted on, each with a fix for a person`)
    if (rw) extra.push(`Reworked: ${rw} sentence${rw === 1 ? '' : 's'} rewritten with the new figures`)
    const sv = others.find(r => r.verdict === 'still_valid')
    if (sv) extra.push(`Still valid: “${title({ id: sv.artifact_id }, 52).replace(/^“|”$/g, '')}” still holds`)
  }
  const ini = (agentLane('tidewall', p.target_agent_id) || agentLane('lyft', p.target_agent_id))?.mono || '?'
  const tm = new Date(p.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles' })
  return { agent: p.target_agent_id, ask, reply, replyTone, extra, postmark: `${ini} · wave 1 · ${tm}`, items: items.length, focus: pick?.artifact_id || null }
}
export function compText(comp: any, t: string): string {
  const k = comp.kind || ''
  const amt = comp.params?.amount != null ? ` (${fmt(Math.abs(comp.params.amount))})` : ''
  if (k === 'corrected_certificate') return 'a corrected certificate and lender notice are drafted for the CFO'
  if (k === 'offset_next_bonus') return `the overpaid bonuses are offset against the next payout${amt}`
  if (k === 'reduce_next_installment') return `the next tax installment is reduced${amt}`
  if (k === 'artifact_supersession') return 'deck v2 with a corrected banner waits for the Controller'
  if (k === 'issue_correction_note') return 'a correction note waits for the editor'
  if (k === 'position_review') return 'the filled order goes to the PM for review'
  return `${t}: ${k.replace(/_/g, ' ')}`
}

/* ---------------------------------------------------------------- hover: what happened to this card, in two lines */
const LONG: Record<string, string> = {
  value_changed: 'a number it rests on changed, so Trackback recomputed it from its own formula. No agent was asked about the arithmetic.',
  conclusion_flipped: 'the conclusion it states no longer holds at the new value.',
  prose_judged: 'the sentence states something that is no longer true.',
  rerendered: 'the figure it cites moved, so Trackback updated the figure in place. The claim itself still holds.',
  claim_unchanged: 'it never read the rows that changed.',
  different_period: 'it covers a different period.',
  different_line_item: 'it reads a different line.',
  below_materiality: 'it moved by less than the threshold in the materiality memo.',
  conclusion_unchanged: 'the number underneath moved, but the conclusion it states still holds.',
  early_cutoff: 'the change was too small to carry any further.',
  estimate_change: 'this was a change in estimate: closed periods stay as booked (ASC 250).',
  fields_not_read: 'it did not read the field that changed.',
  supporters_cleared: 'everything it rests on cleared.',
  parameters_within_materiality: 'it stayed within tolerance.',
  supporter_retracted: 'a source it rests on was retracted; nothing can prove it until a replacement arrives.',
  compensation_proposed: 'it already went out, so it cannot be un-done: a fix is proposed for a person to approve.',
}
export type Explain = { head: string; tone: State; lines: string[] }
export function explain(n: any, st: State, comp?: any): Explain {
  const t = title(n, 90)
  const who = n.type === 'source' ? (n.system || 'source').replace(/_/g, ' ') : n.agent_id ? (agentLane('tidewall', n.agent_id) || agentLane('lyft', n.agent_id))?.name || n.agent_id : 'Trackback'
  const lines: string[] = []
  if (n.type === 'source') {
    if (n.corrected) return { head: 'Source corrected', tone: 'invalidated', lines: [`${t}: the trackback notice replaced the version the agents read with a corrected one.`, `${n.versions ?? 1} stored version${n.versions === 1 ? '' : 's'} · ${who}`] }
    return { head: t, tone: 'idle', lines: [`A ${who} document the agents read. ${n.versions ?? 1} stored version${n.versions === 1 ? '' : 's'}, each pinned to the moment it was captured.`] }
  }
  const moved = n.old_value != null && n.new_value != null && n.old_value !== n.new_value
  const what = n.kind === 'sentence' ? 'This sentence' : n.kind === 'action' ? 'This action' : n.kind === 'forecast_cell' ? 'This forecast cell' : 'This number'
  if (st === 'idle' || !n.verdict) {
    lines.push(`${what} was built by the ${who}${n.period ? ` for ${n.period}` : ''}${n.kind !== 'sentence' && n.value != null ? `: ${fmt(n.value, n.line_item)}` : ''}.`)
    if (n.kind === 'sentence' && n.content) lines.push(`“${n.content.replace(/\s*\(corrected[^)]*\)/g, '').slice(0, 140)}”`)
    lines.push('Not touched by the current correction.' + (n.verdict === null && n.kind !== 'action' ? ' Click for who built it, on top of whom.' : ''))
    return { head: t, tone: 'idle', lines }
  }
  const reason = LONG[n.reason] || reasonText(n.reason)
  if (st === 'invalidated') { lines.push(`Wrong now: ${reason}`); if (moved) lines.push(`${fmt(n.old_value, n.line_item)} → ${fmt(n.new_value, n.line_item)}`) }
  else if (st === 'caution') { lines.push(n.kind === 'action' ? `Needs a human: this already went out${moved ? ` resting on ${fmt(n.old_value, n.line_item)}, now ${fmt(n.new_value, n.line_item)}` : ''}.` : `Needs a human: ${reason}`); if (comp) lines.push(`Fix proposed: ${compText(comp, t)}, waiting for ${(comp.approver_role || 'the Controller').replace('cfo', 'the CFO').replace('controller', 'the Controller').replace('hr', 'HR').replace('vp_sales', 'VP Sales').replace('+', ' and ')}.`) }
  else if (st === 'reworked') { lines.push(`Reworked by its owner: the figure it cited moved${moved ? ` (${fmt(n.old_value, n.line_item)} → ${fmt(n.new_value, n.line_item)})` : ''}.`); if (n.rewrite) lines.push(`Now reads: “${String(n.rewrite).slice(0, 150)}”`) }
  else if (st === 'skipped') lines.push(`Skipped without a ping: ${reason}`)
  else if (st === 'cleared') lines.push(`Still valid: ${reason}` + (moved ? ` (${fmt(n.old_value, n.line_item)} → ${fmt(n.new_value, n.line_item)})` : ''))
  else if (st === 'pending') lines.push('Pinged: its owner is re-checking it against the corrected inputs.')
  lines.push(`${who}${n.hop != null && n.hop >= 0 ? ` · ${n.hop} hop${n.hop === 1 ? '' : 's'} from the correction` : ''}`)
  return { head: `${STATE_WORD[st]} · ${t}`, tone: st, lines }
}
