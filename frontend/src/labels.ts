/* Human names for everything the engine calls by id. The ids stay available under "Technical" in the detail card. */
export const GYM: Record<string, string> = { G1: 'Oakland', G2: 'San Jose', G3: 'Sacramento', G4: 'Fresno', G5: 'Santa Cruz', G6: 'Berkeley' }

export const AGENT: Record<string, string> = {
  close_accountant: 'Close Accountant', reporting_analyst: 'Reporting Analyst', covenant_comp: 'Covenant & Comp', trackback: 'Trackback',
  lyft_fpa: 'FP&A', lyft_ir: 'Reporting / IR', lyft_disclosure: 'Disclosure', street_analyst: 'Street analyst', newsroom: 'Newsroom', humans: 'People',
}
export const agentName = (id?: string | null) => (id && AGENT[id]) || (id || '').replace(/_/g, ' ') || 'unknown'

/* Short, plain reasons. Shown as a stamp on a node and as the first line of its card. */
export const WHY: Record<string, string> = {
  value_changed: 'Number changed', conclusion_flipped: 'Conclusion flipped', prose_judged: 'Sentence no longer true', rerendered: 'Figure updated in place',
  compensation_proposed: 'Already acted on; fix proposed', claim_unchanged: 'Did not use the changed rows', different_period: 'Different period', different_line_item: 'Different line',
  below_materiality: 'Moved less than the threshold', conclusion_unchanged: 'Conclusion still holds', early_cutoff: 'Change too small to carry', estimate_change: 'Estimate change, left as is',
  fields_not_read: 'Did not read that field', supporters_cleared: 'Everything it rests on cleared', parameters_within_materiality: 'Within tolerance', supporter_retracted: 'A source was retracted',
  ping_pending: 'Waiting on its owner', upstream_pending: 'Waiting on something upstream', not_reached: 'Never touched', redraft: 'Redraft from the corrected inputs', needs_human: 'Needs a person',
}
export const why = (reason?: string | null) => (reason && WHY[reason]) || (reason || '').replace(/_/g, ' ')

export const TITLES: Record<string, string> = {
  memo_q1_deferred_revenue: 'March deferred-revenue memo', q1_deferred_release_2026_03: 'March deferred revenue release', cf_2026_weekly_dues: '13-week cash forecast, dues',
  tile_q1_net_leverage: 'Deck tile: net leverage', billing_export_2026_03: 'Billing export, March', cert_s_compliance: 'Certificate compliance sentence',
  cert_send_q1_2026: 'Lender certificate, sent', cert_send_q4_2025: 'Lender certificate Q4 2025, sent', leverage_2026_q1: 'Net leverage, Q1', leverage_2025_q4: 'Net leverage, Q4 2025',
  covenant_headroom_2026_q1: 'Covenant headroom, Q1', ttm_adj_ebitda_2026_q1: 'TTM adjusted EBITDA', ttm_adj_ebitda_2025_q4: 'TTM adjusted EBITDA, Q4 2025', net_debt_2026_q1: 'Net debt, Q1', net_debt_2025_q4: 'Net debt, Q4 2025',
  q1_ebitda: 'EBITDA, Q1', q1_pretax: 'Pretax income, Q1', q1_revenue_total: 'Revenue, Q1', q1_membership_revenue_total: 'Membership revenue, Q1', q1_corporate_costs: 'Corporate costs, Q1',
  q1_wellness_revenue: 'Wellness revenue, Q1', q1_wallbuild_revenue: 'Wall-build revenue, Q1', q1_utilities_expense: 'Utilities, Q1', q1_route_setting_expense: 'Route setting, Q1', q1_payroll_tax_expense: 'Payroll tax, Q1',
  gm_bonus_q1_total: 'GM bonus pool, Q1', bonus_payout_q1_2026: 'GM bonuses, paid', tax_payment_q2_2026: 'Q2 estimated tax, paid', q2_estimated_tax: 'Q2 estimated tax',
  deck_publish_q1_2026: 'Board deck, published', payment_run_0612: 'AP payment run, Jun 12', payment_run_0612_v2: 'AP payment run, Jun 12 (second)', commission_payout_0620: 'Sales commissions, paid',
  dunning_email_pacific_lumen_0616: 'Dunning email to Pacific Lumen', fc_wellness_h2_total: 'Wellness forecast, H2',
  lyft_margin_expansion_bps: 'Margin expansion, bps', lyft_fy24_margin_target: '2024 margin target', lyft_fy23_adj_ebitda_margin: '2023 adjusted EBITDA margin', lyft_q4_gross_bookings_growth: 'Q4 gross bookings growth',
  lyft_publish_release: 'Earnings release, publish', lyft_file_8k: 'Form 8-K, file', lyft_ext_fy24_margin: '2024 margin, implied', lyft_ext_fy24_gross_bookings: '2024 gross bookings, implied',
  lyft_ext_fy24_adj_ebitda: '2024 adjusted EBITDA, implied', lyft_ext_buy_order: 'Buy order, filled', lyft_ext_publish_story: 'Story, published',
}
const WORD: Record<string, string> = {
  q1: 'Q1', q2: 'Q2', q3: 'Q3', q4: 'Q4', h1: 'H1', h2: 'H2', ebitda: 'EBITDA', ttm: 'TTM', adj: 'adjusted', bva: 'budget vs actual', tile: 'Deck tile', kpi: 'KPI', cf: 'Cash forecast', fc: 'Forecast',
  ap: 'AP', gm: 'GM', je: 'Journal entry', est: 'estimate', ext: '', fy23: 'FY2023', fy24: 'FY2024', bps: 'bps', qoq: 'quarter over quarter', yoy: 'year over year', pl: 'Pacific Lumen', ar: 'receivables',
  accrual: 'accrual', prelim: 'preliminary', wallbuild: 'wall-build', uc: 'UC', sierra: 'Sierra', pct: '', trueup: 'true-up', lyft: '', mpwr: '', comp: 'Fix:', s: '', memo: 'Memo:', deck: 'Deck', tidewall: '', ytd: 'year to date', w: 'week', margin: 'margin',
}
const MONTH = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function humanize(id: string): string {
  if (TITLES[id]) return TITLES[id]
  if (id.startsWith('comp_')) return `Fix for ${humanize(id.replace(/^comp_/, '').replace(/_(E\d+|LYFT_TYPO|REV-[^_]+)$/, ''))}`
  const parts = id.split('_').filter(Boolean)
  const out: string[] = []
  for (const p of parts) {
    const lo = p.toLowerCase()
    if (/^g[1-6]$/i.test(p)) { out.push(GYM[p.toUpperCase()]); continue }
    if (/^w\d{1,2}$/i.test(p)) { out.push(`week ${p.slice(1)}`); continue }
    if (/^\d{4}$/.test(p) && Number(p) < 1300) { out.push(`${MONTH[Number(p.slice(0, 2)) - 1]} ${Number(p.slice(2))}`); continue }   // 0612 -> Jun 12
    if (/^\d{4}-\d{2}$/.test(p)) { out.push(`${MONTH[Number(p.slice(5, 7)) - 1]} ${p.slice(0, 4)}`); continue }
    if (/^\d{4}$/.test(p)) { out.push(p); continue }
    if (lo in WORD) { if (WORD[lo]) out.push(WORD[lo]); continue }
    out.push(lo)
  }
  const s = out.join(' ').replace(/\s+/g, ' ').trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function cleanText(s?: string | null): string {
  return (s || '').replace(/\s*\(corrected [^)]*\)/g, '').replace(/\s*\[recalculated[^\]]*\]/g, '').trim()
}

/* The title shown on a node or a card. Sentences show themselves; everything else gets a plain name. */
export function title(n: { id?: string; artifact_id?: string; kind?: string; content?: string | null; label?: string; type?: string; members?: unknown[] }, max = 72): string {
  const id = n.id || n.artifact_id || ''
  if (n.type === 'source') return (n.label || id).replace(/^(REAL|RECONSTRUCTION):\s*/i, '')
  if (n.members) return `${humanize(id.replace(/^grp:[^|]*\|/, '').replace('_G×', ''))}, all gyms`
  if (n.kind === 'sentence' && n.content) { const t = cleanText(n.content); return t.length > max ? t.slice(0, max - 1).trimEnd() + '…' : t }
  return humanize(id)
}

export const statusChip = (badge?: string | null): { label: string; cls: string } => {
  const b = (badge || 'VALID').toUpperCase()
  if (b.startsWith('STALE')) return { label: 'Wrong', cls: 'chip red' }
  if (b.startsWith('RECALC')) return { label: 'Recomputed', cls: 'chip blue' }
  if (b.startsWith('NEEDS') || b.startsWith('COMP')) return { label: 'Needs a person', cls: 'chip amber' }
  if (b.startsWith('UNPROV')) return { label: 'Unprovable', cls: 'chip grey' }
  return { label: 'Holds', cls: 'chip green' }
}
