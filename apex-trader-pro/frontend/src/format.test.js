import { describe, expect, it } from 'vitest'
import { anomalies, fmtPrice, groupPerformance, whatIf } from './format'
import { dict } from './i18n'

const trade = (o) => ({ status: 'CLOSED', direction: 'LONG', entry_price: 100, stop_loss: 98, take_profit: 104,
  actual_quantity: 1, ...o })

describe('format helpers', () => {
  it('formats prices without eating integer zeros', () => {
    expect(fmtPrice(100000)).toBe('100000')
    expect(fmtPrice(97000)).toBe('97000')
    expect(fmtPrice(1500)).toBe('1500')
    expect(fmtPrice(0.12345678)).toBe('0.123457')
    expect(fmtPrice(31.5)).toBe('31.5')
    expect(fmtPrice(null)).toBe('—')
  })
  it('groups performance by strategy', () => {
    const g = groupPerformance([trade({ strategy: 'a', net_pnl: 5 }), trade({ strategy: 'a', net_pnl: -2 }), trade({ strategy: 'b', net_pnl: 1 })])
    expect(g[0]).toEqual({ strategy: 'a', trades: 2, wins: 1, net_pnl: 3 })
  })
  it('what-if rescales TP/SL exits and costs', () => {
    const trades = [trade({ result: 'TP HIT', exit_price: 104, net_pnl: 3.8 }), trade({ result: 'SL HIT', exit_price: 98, net_pnl: -2.2 })]
    const same = whatIf(trades, { slMult: 1, tpMult: 1, bps: 0 })
    expect(same.simulated).toBeCloseTo(4 - 2)
    const wider = whatIf(trades, { slMult: 1, tpMult: 1.5, bps: 0 })
    expect(wider.simulated).toBeCloseTo(6 - 2)
    expect(wider.original).toBeCloseTo(1.6)
  })
  it('flags anomalies', () => {
    const rows = Array.from({ length: 20 }, (_, i) => ({ symbol: `S${i}`, change_pct: i % 2 ? 1 : -1, funding: 0.01, high: 1, low: 1 }))
    rows.push({ symbol: 'PUMP', change_pct: 40, funding: 0.3, high: 2, low: 1 })
    const a = anomalies(rows)
    expect(a.map((r) => r.symbol)).toEqual(['PUMP'])
    expect(a[0].reasons.length).toBe(3)
  })
  it('has every English key translated to Russian', () => {
    expect(Object.keys(dict.en).filter((k) => !(k in dict.ru))).toEqual([])
  })
})
