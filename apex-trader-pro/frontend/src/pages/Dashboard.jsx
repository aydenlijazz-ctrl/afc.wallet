import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { fmt, fmtPrice, fmtTime, pnlClass } from '../format'

export function ArmBanner({ settings, onChange }) {
  const t = useT()
  if (!settings) return null
  const armed = settings.live_trading_armed === 'true'
  const toggle = async () => {
    if (!armed && !window.confirm(t('armConfirm'))) return
    await api.saveSettings({ live_trading_armed: armed ? 'false' : 'true' })
    onChange?.()
  }
  return (
    <div className={`banner ${armed ? 'armed' : 'idle'}`}>
      <span>{armed ? '🟢 ' + t('armed') : '⏸ ' + t('notArmed')}</span>
      <button className={armed ? 'danger' : ''} onClick={toggle}>{armed ? t('disarm') : t('arm')}</button>
    </div>
  )
}

export default function Dashboard() {
  const t = useT()
  const balance = useApi(api.balance, [], 30000)
  const positions = useApi(api.positions, [], 15000)
  const signals = useApi(api.signals, [], 30000)
  const settings = useApi(api.settings)
  const perf = useApi(() => api.analytics(), [], 60000)
  const labels = settings.data?.labels || {}

  const close = async (symbol) => {
    if (!window.confirm(`${t('close')} ${symbol}?`)) return
    await api.closePosition(symbol)
    positions.reload()
  }
  const closeAll = async () => {
    if (!window.confirm(t('closeAll') + '?')) return
    for (const s of new Set((positions.data?.positions || []).map((p) => p.symbol))) await api.closePosition(s)
    positions.reload()
  }

  return (
    <>
      <h1>{t('dashboard')}</h1>
      <ArmBanner settings={settings.data?.settings} onChange={settings.reload} />
      <div className="grid">
        <div className="card kpi"><div className="label">{t('mode')}</div><div className="value"><span className="badge live">LIVE</span></div></div>
        <div className="card kpi"><div className="label">{t('equity')}</div><div className="value">{balance.error ? <span className="error" title={balance.error}>—</span> : `${fmt(balance.data?.total_equity)} USDT`}</div></div>
        <div className="card kpi"><div className="label">{t('available')}</div><div className="value">{fmt(balance.data?.available_balance)}</div></div>
        <div className="card kpi"><div className="label">{t('unrealized')}</div><div className={`value ${pnlClass(balance.data?.unrealised_pnl)}`}>{fmt(balance.data?.unrealised_pnl)}</div></div>
      </div>

      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>{t('openPositions')}</h2>
          {positions.data?.positions?.length > 0 && <button className="danger" onClick={closeAll}>{t('closeAll')}</button>}
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>{t('symbol')}</th><th>{t('direction')}</th><th>{t('strategy')}</th><th>{t('entry')}</th><th>{t('mark')}</th><th>SL</th><th>TP</th><th>{t('qty')}</th><th>{t('unrealized')}</th><th /></tr></thead>
            <tbody>
              {(positions.data?.positions || []).map((p) => (
                <tr key={p.id}>
                  <td>{p.symbol}</td><td><span className={`badge ${p.direction}`}>{p.direction}</span>{p.reversed && ' ↺'}</td>
                  <td>{labels[p.strategy] || p.strategy}</td><td>{fmtPrice(p.entry_price)}</td><td>{fmtPrice(p.mark_price)}</td>
                  <td>{fmtPrice(p.stop_loss)}</td><td>{fmtPrice(p.take_profit)}</td><td>{p.actual_quantity}</td>
                  <td className={pnlClass(p.unrealized_pnl)}>{fmt(p.unrealized_pnl)}</td>
                  <td><button className="secondary" onClick={() => close(p.symbol)}>{t('close')}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!positions.data?.positions?.length && <p className="muted">{t('none')}</p>}
        </div>
      </div>

      <div className="card">
        <h2>{t('recentSignals')}</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>{t('time')}</th><th>{t('strategy')}</th><th>{t('symbol')}</th><th>{t('direction')}</th><th>{t('entry')}</th><th>{t('score')}</th><th>{t('regime')}</th><th>{t('status')}</th></tr></thead>
            <tbody>
              {(signals.data?.signals || []).slice(0, 20).map((s, i) => (
                <tr key={i}>
                  <td>{fmtTime(s.created_at)}</td><td>{labels[s.strategy] || s.strategy}</td><td>{s.symbol}</td>
                  <td><span className={`badge ${s.request?.direction}`}>{s.request?.direction}</span></td>
                  <td>{fmtPrice(s.request?.entry)}</td><td>{s.request?.score}</td><td>{s.request?.regime}</td>
                  <td>{s.action === 'signal_not_armed' ? t('notArmedShort') : s.success ? 'OPEN' : <span className="error">{s.response?.error}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!signals.data?.signals?.length && <p className="muted">{t('none')}</p>}
        </div>
      </div>

      <h2>{t('strategyPerformance')}</h2>
      <div className="grid">
        {(perf.data?.by_strategy || []).map((s) => (
          <div className="card kpi" key={s.strategy}>
            <div className="label">{labels[s.strategy] || s.strategy}</div>
            <div className={`value ${pnlClass(s.net_pnl)}`}>{fmt(s.net_pnl)} USDT</div>
            <div className="muted">{s.trades} {t('trades').toLowerCase()} · {t('winRate')} {fmt((s.wins / s.trades) * 100, 0)}%</div>
          </div>
        ))}
      </div>
    </>
  )
}
