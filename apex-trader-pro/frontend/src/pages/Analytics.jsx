import { useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { fmt, pnlClass } from '../format'
import { Filters, TradesTable, emptyFilters, toQuery } from './History'

const axis = { stroke: '#8B949E', fontSize: 11 }

export default function Analytics() {
  const t = useT()
  const [filters, setFilters] = useState(emptyFilters)
  const [hour, setHour] = useState(null)
  const settings = useApi(api.settings)
  const data = useApi(() => api.analytics(toQuery(filters)), [JSON.stringify(filters)])
  const trades = useApi(() => api.trades({ ...toQuery(filters), status: 'CLOSED', limit: 5000 }), [JSON.stringify(filters)])
  const labels = settings.data?.labels || {}
  const k = data.data?.kpi || {}
  const hours = Array.from({ length: 24 }, (_, h) => data.data?.by_hour?.find((x) => x.hour === h) || { hour: h, trades: 0, net_pnl: 0 })
  const maxAbs = Math.max(1, ...hours.map((h) => Math.abs(h.net_pnl || 0)))
  const hourTrades = (trades.data?.trades || []).filter((x) => hour !== null && new Date(x.created_at).getUTCHours() === hour)

  return (
    <>
      <h1>{t('analytics')}</h1>
      <Filters value={filters} onChange={setFilters} strategies={settings.data?.strategies || []} labels={labels} />
      <div className="grid">
        <div className="card kpi"><div className="label">{t('netPnl')}</div><div className={`value ${pnlClass(k.net_pnl)}`}>{fmt(k.net_pnl)} USDT</div></div>
        <div className="card kpi"><div className="label">{t('trades')}</div><div className="value">{k.trades ?? 0}</div></div>
        <div className="card kpi"><div className="label">{t('winRate')}</div><div className="value">{fmt(k.win_rate, 1)}%</div></div>
        <div className="card kpi"><div className="label">{t('profitFactor')}</div><div className="value">{k.profit_factor == null ? '—' : fmt(k.profit_factor)}</div></div>
        <div className="card kpi"><div className="label">{t('avgTrade')}</div><div className={`value ${pnlClass(k.avg_trade)}`}>{fmt(k.avg_trade)}</div></div>
      </div>
      <div className="card">
        <h2>P&L</h2>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={(data.data?.daily || []).map((d) => ({ ...d, day: d.day?.slice(0, 10) }))}>
            <CartesianGrid stroke="#30363D" strokeDasharray="3 3" />
            <XAxis dataKey="day" {...axis} /><YAxis {...axis} />
            <Tooltip contentStyle={{ background: '#161B22', border: '1px solid #30363D' }} />
            <Area type="monotone" dataKey="cumulative" stroke="#00B4D8" fill="#00B4D833" name="Cumulative P&L" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="card table-wrap">
        <h2>{t('strategyPerformance')}</h2>
        <table>
          <thead><tr><th>{t('strategy')}</th><th>{t('trades')}</th><th>{t('winRate')}</th><th>{t('netPnl')}</th><th>{t('score')}</th></tr></thead>
          <tbody>{(data.data?.by_strategy || []).map((s) => (
            <tr key={s.strategy}><td>{labels[s.strategy] || s.strategy}</td><td>{s.trades}</td><td>{fmt((s.wins / s.trades) * 100, 1)}%</td>
              <td className={pnlClass(s.net_pnl)}>{fmt(s.net_pnl)}</td><td>{fmt(s.avg_score, 0)}</td></tr>))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>{t('bestHours')}</h2>
        <div className="hours">
          {hours.map((h) => {
            const a = Math.abs(h.net_pnl || 0) / maxAbs
            const bg = h.trades ? (h.net_pnl >= 0 ? `rgba(63,185,80,${0.15 + a * 0.7})` : `rgba(248,81,73,${0.15 + a * 0.7})`) : '#21262D'
            return (
              <div key={h.hour} className={`hour ${hour === h.hour ? 'selected' : ''}`} style={{ background: bg }} onClick={() => setHour(hour === h.hour ? null : h.hour)} title={`${h.trades} trades, ${fmt(h.net_pnl)} USDT`}>
                {String(h.hour).padStart(2, '0')}<br />{h.trades ? fmt(h.net_pnl, 0) : ''}
              </div>
            )
          })}
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={hours}><XAxis dataKey="hour" {...axis} /><YAxis {...axis} />
            <Bar dataKey="net_pnl" onClick={(d) => setHour(d.hour)}>{hours.map((h) => <Cell key={h.hour} fill={h.net_pnl >= 0 ? '#3FB950' : '#F85149'} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
        {hour !== null && (
          <div className="table-wrap"><h2>{t('hourTrades', { h: String(hour).padStart(2, '0') })}</h2><TradesTable trades={hourTrades} labels={labels} /></div>
        )}
      </div>
    </>
  )
}
