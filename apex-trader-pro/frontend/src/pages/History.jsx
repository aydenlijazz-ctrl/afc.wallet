import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { fmt, fmtPrice, fmtTime, pnlClass } from '../format'

export function Filters({ value, onChange, strategies, labels }) {
  const t = useT()
  const set = (k) => (e) => onChange({ ...value, [k]: e.target.value })
  return (
    <div className="row card">
      <label className="field">{t('strategy')}
        <select value={value.strategy} onChange={set('strategy')}>
          <option value="">{t('all')}</option>
          {strategies.map((s) => <option key={s} value={s}>{labels[s] || s}</option>)}
        </select>
      </label>
      <label className="field">{t('reverseMode')}
        <select value={value.reversed} onChange={set('reversed')}>
          <option value="">{t('all')}</option><option value="true">{t('onlyReversed')}</option><option value="false">{t('onlyNormal')}</option>
        </select>
      </label>
      <label className="field">{t('from')}<input type="date" value={value.from} onChange={set('from')} /></label>
      <label className="field">{t('to')}<input type="date" value={value.to} onChange={set('to')} /></label>
    </div>
  )
}

export const emptyFilters = { strategy: '', reversed: '', from: '', to: '' }
export const toQuery = (f) => ({ ...f, from: f.from ? `${f.from}T00:00:00Z` : '', to: f.to ? `${f.to}T23:59:59Z` : '' })

export default function History() {
  const t = useT()
  const [filters, setFilters] = useState(emptyFilters)
  const settings = useApi(api.settings)
  const trades = useApi(() => api.trades(toQuery(filters)), [JSON.stringify(filters)])
  const labels = settings.data?.labels || {}
  return (
    <>
      <h1>{t('history')}</h1>
      <Filters value={filters} onChange={setFilters} strategies={settings.data?.strategies || []} labels={labels} />
      <div className="card table-wrap">
        <TradesTable trades={trades.data?.trades || []} labels={labels} />
        {trades.error && <p className="error">{trades.error}</p>}
      </div>
    </>
  )
}

export function TradesTable({ trades, labels }) {
  const t = useT()
  if (!trades.length) return <p className="muted">{t('none')}</p>
  return (
    <table>
      <thead><tr><th>{t('time')}</th><th>{t('symbol')}</th><th>{t('direction')}</th><th>{t('strategy')}</th><th>{t('entry')}</th><th>{t('exit')}</th><th>SL</th><th>TP</th><th>{t('status')}</th><th>{t('result')}</th><th>{t('netPnl')}</th><th>{t('score')}</th></tr></thead>
      <tbody>
        {trades.map((x) => (
          <tr key={x.id}>
            <td>{fmtTime(x.created_at)}</td><td>{x.symbol}</td>
            <td><span className={`badge ${x.direction}`}>{x.direction}</span>{x.reversed && <span title={`reversed from ${x.original_direction}`}> ↺</span>}</td>
            <td>{labels[x.strategy] || x.strategy}</td><td>{fmtPrice(x.entry_price)}</td><td>{fmtPrice(x.exit_price)}</td>
            <td>{fmtPrice(x.stop_loss)}</td><td>{fmtPrice(x.take_profit)}</td><td>{x.status}</td><td>{x.result || '—'}</td>
            <td className={pnlClass(x.net_pnl)}>{fmt(x.net_pnl)}</td><td>{x.signal_score ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
