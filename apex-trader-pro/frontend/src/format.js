export const fmt = (v, d = 2) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d))
export const fmtPrice = (v) => {
  if (v == null) return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1e5) return n.toFixed(Math.abs(n) >= 1e6 ? 0 : 1).replace(/\.0$/, '')
  const s = n.toPrecision(6)
  return s.includes('.') ? s.replace(/0+$/, '').replace(/\.$/, '') : s
}
export const pnlClass = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '')
export const fmtTime = (s) => (s ? new Date(s).toLocaleString() : '—')

export function groupPerformance(trades) {
  const by = {}
  for (const t of trades) {
    if (t.status !== 'CLOSED') continue
    const s = (by[t.strategy] ??= { strategy: t.strategy, trades: 0, wins: 0, net_pnl: 0 })
    s.trades += 1
    s.net_pnl += Number(t.net_pnl || 0)
    if (Number(t.net_pnl) > 0) s.wins += 1
  }
  return Object.values(by).sort((a, b) => b.net_pnl - a.net_pnl)
}

// What-if: re-price each closed trade's outcome with new SL/TP multipliers (relative to its original
// risk distance) and a new cost model. Trades that originally hit TP/SL map to the new TP/SL distance.
export function whatIf(trades, { slMult = 1, tpMult = 1, bps = 10 }) {
  let original = 0
  let simulated = 0
  for (const t of trades) {
    if (t.status !== 'CLOSED' || t.net_pnl == null) continue
    original += Number(t.net_pnl)
    const qty = Number(t.actual_quantity || 0)
    const entry = Number(t.entry_price)
    const sgn = t.direction === 'LONG' ? 1 : -1
    let exit = Number(t.exit_price)
    if (t.result === 'TP HIT') exit = entry + (Number(t.take_profit) - entry) * tpMult
    else if (t.result === 'SL HIT') exit = entry + (Number(t.stop_loss) - entry) * slMult
    const gross = sgn * (exit - entry) * qty
    simulated += gross - (entry + exit) * qty * (bps / 10000)
  }
  return { original, simulated }
}

export function anomalies(rows) {
  if (rows.length < 5) return []
  const ch = rows.map((r) => r.change_pct)
  const mean = ch.reduce((a, b) => a + b, 0) / ch.length
  const sd = Math.sqrt(ch.reduce((a, b) => a + (b - mean) ** 2, 0) / ch.length) || 1
  return rows
    .map((r) => ({ ...r, z: (r.change_pct - mean) / sd, reasons: [] }))
    .map((r) => {
      if (Math.abs(r.z) > 2.5) r.reasons.push(`24h move z=${r.z.toFixed(1)}`)
      if (Math.abs(r.funding) > 0.1) r.reasons.push(`funding ${r.funding.toFixed(3)}%`)
      if (r.low > 0 && (r.high - r.low) / r.low > 0.25) r.reasons.push(`range ${(((r.high - r.low) / r.low) * 100).toFixed(0)}%`)
      return r
    })
    .filter((r) => r.reasons.length)
}
