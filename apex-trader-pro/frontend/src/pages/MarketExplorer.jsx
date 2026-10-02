import { useMemo, useState } from 'react'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { anomalies, fmt, fmtPrice, pnlClass } from '../format'

export default function MarketExplorer() {
  const t = useT()
  const { data, error } = useApi(api.tickers, [], 60000)
  const [tab, setTab] = useState('heatmap')
  const [q, setQ] = useState('')
  const [minTurnover, setMinTurnover] = useState(10)
  const rows = useMemo(() => (data?.tickers || []).filter((r) => r.turnover >= minTurnover * 1e6 && r.symbol.includes(q.toUpperCase())), [data, q, minTurnover])
  return (
    <>
      <h1>{t('market')}</h1>
      <div className="row card">
        <label className="field">{t('search')}<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="BTC" /></label>
        <label className="field">{t('minTurnover')}<input type="number" value={minTurnover} onChange={(e) => setMinTurnover(Number(e.target.value))} /></label>
        <span className="muted">{rows.length} / {data?.tickers?.length || 0}</span>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="tabs">{['heatmap', 'leaderboard', 'bubbles', 'anomalies'].map((k) => <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{t(k)}</button>)}</div>
      <div className="card">
        {tab === 'heatmap' && (
          <div className="heatmap">{rows.slice(0, 120).map((r) => {
            const a = Math.min(1, Math.abs(r.change_pct) / 10)
            return <div key={r.symbol} className="heat" style={{ background: r.change_pct >= 0 ? `rgba(63,185,80,${0.15 + a * 0.75})` : `rgba(248,81,73,${0.15 + a * 0.75})` }}>
              <strong>{r.symbol.replace('USDT', '')}</strong><br />{fmt(r.change_pct)}%</div>
          })}</div>
        )}
        {tab === 'leaderboard' && (
          <div className="table-wrap"><table>
            <thead><tr><th>{t('symbol')}</th><th>Last</th><th>{t('change')}</th><th>{t('turnover')}</th><th>{t('funding')}</th><th>OI</th></tr></thead>
            <tbody>{[...rows].sort((a, b) => b.change_pct - a.change_pct).map((r) => (
              <tr key={r.symbol}><td>{r.symbol}</td><td>{fmtPrice(r.last)}</td><td className={pnlClass(r.change_pct)}>{fmt(r.change_pct)}%</td>
                <td>{fmt(r.turnover / 1e6, 1)}M</td><td>{fmt(r.funding, 4)}</td><td>{fmt(r.open_interest / 1e6, 1)}M</td></tr>))}
            </tbody></table></div>
        )}
        {tab === 'bubbles' && (
          <ResponsiveContainer width="100%" height={420}>
            <ScatterChart>
              <CartesianGrid stroke="#30363D" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="change_pct" name="24h %" stroke="#8B949E" />
              <YAxis type="number" dataKey="funding" name="Funding %" stroke="#8B949E" />
              <ZAxis type="number" dataKey="turnover" range={[30, 900]} />
              <Tooltip cursor={false} contentStyle={{ background: '#161B22', border: '1px solid #30363D' }} formatter={(v, n) => [fmt(v, 3), n]} labelFormatter={() => ''} />
              <Scatter data={rows.slice(0, 150)} fill="#00B4D8" fillOpacity={0.6} name="symbols" />
            </ScatterChart>
          </ResponsiveContainer>
        )}
        {tab === 'anomalies' && (
          <div className="table-wrap"><table>
            <thead><tr><th>{t('symbol')}</th><th>{t('change')}</th><th>{t('funding')}</th><th /></tr></thead>
            <tbody>{anomalies(rows).map((r) => <tr key={r.symbol}><td>{r.symbol}</td><td className={pnlClass(r.change_pct)}>{fmt(r.change_pct)}%</td><td>{fmt(r.funding, 4)}</td><td>{r.reasons.join(' · ')}</td></tr>)}</tbody>
          </table></div>
        )}
      </div>
    </>
  )
}
