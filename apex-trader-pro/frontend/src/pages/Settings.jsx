import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { ArmBanner } from './Dashboard'

const REGIMES = ['TRENDING', 'TRANSITIONAL', 'RANGING']

function Toggle({ checked, onChange, label }) {
  return <label className="switch"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}</label>
}

function StrategyCard({ name, label, values, set, dragProps }) {
  const t = useT()
  const k = (f) => `strat_${name}_${f}`
  const v = (f) => values[k(f)] ?? ''
  const b = (f) => v(f) === 'true'
  const regimes = v('allowed_regimes').split(',').filter(Boolean)
  const toggleRegime = (r) => set(k('allowed_regimes'), (regimes.includes(r) ? regimes.filter((x) => x !== r) : [...regimes, r]).join(','))
  return (
    <details className="card strategy-card" {...dragProps}>
      <summary>
        <strong>⠿ {label}</strong>
        <span onClick={(e) => e.stopPropagation()}><Toggle checked={b('enabled')} onChange={(c) => set(k('enabled'), String(c))} label={t('enabled')} /></span>
      </summary>
      <br />
      <div className="form-grid">
        <label className="field">{t('symbols')}<input value={v('symbols')} onChange={(e) => set(k('symbols'), e.target.value.toUpperCase())} placeholder="BTCUSDT,ETHUSDT" /></label>
        <label className="field">{t('cost')}<input type="number" min="1" value={v('cost')} onChange={(e) => set(k('cost'), e.target.value)} /></label>
        <label className="field">{t('leverage')}<input type="number" min="1" max="100" value={v('leverage')} onChange={(e) => set(k('leverage'), e.target.value)} /></label>
        <label className="field">{t('activeHours')}<input value={v('active_hours')} onChange={(e) => set(k('active_hours'), e.target.value)} placeholder="0-23" /></label>
        <label className="field">{t('priority')}<input type="number" value={v('priority')} readOnly /></label>
      </div>
      <br />
      <div className="form-grid">
        <Toggle checked={b('reverse_enabled')} onChange={(c) => set(k('reverse_enabled'), String(c))} label={t('reverseMode')} />
        <Toggle checked={b('trailing_enabled')} onChange={(c) => set(k('trailing_enabled'), String(c))} label={t('trailing')} />
        <label className="field">{t('trailDistance')}<input type="number" step="0.1" value={v('trail_distance')} onChange={(e) => set(k('trail_distance'), e.target.value)} /></label>
        <Toggle checked={b('partial_tp_enabled')} onChange={(c) => set(k('partial_tp_enabled'), String(c))} label={t('partialTp')} />
        <label className="field">{t('partialPct')}<input type="number" min="10" max="90" value={v('partial_tp_percent')} onChange={(e) => set(k('partial_tp_percent'), e.target.value)} /></label>
      </div>
      <br />
      <div className="form-grid">
        <Toggle checked={b('adaptive_auto_reverse_enabled')} onChange={(c) => set(k('adaptive_auto_reverse_enabled'), String(c))} label={t('adaptive')} />
        <label className="field">{t('threshold')}<input type="number" value={v('adaptive_auto_reverse_threshold')} onChange={(e) => set(k('adaptive_auto_reverse_threshold'), e.target.value)} /></label>
        <Toggle checked={b('adaptive_auto_reverse_include_unrealized')} onChange={(c) => set(k('adaptive_auto_reverse_include_unrealized'), String(c))} label={t('includeUnreal')} />
      </div>
      <br />
      <div className="row"><span className="muted">{t('allowedRegimes')}:</span>
        {REGIMES.map((r) => <Toggle key={r} checked={regimes.includes(r)} onChange={() => toggleRegime(r)} label={r} />)}
      </div>
      {name === 'custom' && <CustomStrategy values={values} set={set} />}
    </details>
  )
}

function CustomStrategy({ values, set }) {
  const t = useT()
  const [text, setText] = useState(values.strat_custom_description || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const parse = async () => {
    setBusy(true); setError('')
    try {
      const r = await api.parseStrategy(text)
      set('strat_custom_definition', JSON.stringify(r.definition))
    } catch (e) { setError(e.message) }
    setBusy(false)
  }
  return (
    <>
      <h2 style={{ marginTop: 16 }}>{t('customStrategy')}</h2>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t('describe')} />
      <div className="row"><button onClick={parse} disabled={busy || !text.trim()}>{busy ? t('loading') : t('parse')}</button>{error && <span className="error">{error}</span>}</div>
      {values.strat_custom_definition && <pre className="card" style={{ overflowX: 'auto' }}>{JSON.stringify(JSON.parse(values.strat_custom_definition), null, 2)}</pre>}
    </>
  )
}

export default function Settings() {
  const t = useT()
  const remote = useApi(api.settings)
  const [values, setValues] = useState({})
  const [dirty, setDirty] = useState({})
  const [order, setOrder] = useState([])
  const [drag, setDrag] = useState(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!remote.data) return
    setValues(remote.data.settings)
    const saved = (remote.data.settings.strategy_order || '').split(',').filter((s) => remote.data.strategies.includes(s))
    setOrder([...saved, ...remote.data.strategies.filter((s) => !saved.includes(s))])
  }, [remote.data])

  const set = (key, value) => { setValues((v) => ({ ...v, [key]: value })); setDirty((d) => ({ ...d, [key]: value })) }
  const onDrop = (target) => {
    if (!drag || drag === target) return
    const next = order.filter((s) => s !== drag)
    next.splice(next.indexOf(target), 0, drag)
    setOrder(next)
    set('strategy_order', next.join(','))
    next.forEach((s, i) => set(`strat_${s}_priority`, String(i + 1)))
    setDrag(null)
  }
  const save = async () => {
    try { await api.saveSettings(dirty); setDirty({}); setMsg(t('saved')); setTimeout(() => setMsg(''), 2000) } catch (e) { setMsg(e.message) }
  }
  if (!remote.data) return <p className="muted">{remote.error || t('loading')}</p>
  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>{t('settings')}</h1>
        <div className="row">{msg && <span className="muted">{msg}</span>}<button onClick={save} disabled={!Object.keys(dirty).length}>{t('save')}</button></div>
      </div>
      <ArmBanner settings={remote.data.settings} onChange={remote.reload} />
      <div className="card">
        <h2>{t('global')}</h2>
        <div className="form-grid">
          <label className="field">{t('minScore')}<input type="number" value={values.min_signal_score || ''} onChange={(e) => set('min_signal_score', e.target.value)} /></label>
          <label className="field">fees_bps<input type="number" value={values.fees_bps || ''} onChange={(e) => set('fees_bps', e.target.value)} /></label>
          <label className="field">slippage_bps<input type="number" value={values.slippage_bps || ''} onChange={(e) => set('slippage_bps', e.target.value)} /></label>
          <Toggle checked={values.one_position_per_symbol === 'true'} onChange={(c) => set('one_position_per_symbol', String(c))} label="One position per symbol" />
        </div>
      </div>
      <p className="muted">{t('dragHint')}</p>
      {order.map((name) => (
        <StrategyCard key={name} name={name} label={remote.data.labels[name]} values={values} set={set}
          dragProps={{ draggable: true, className: `card strategy-card ${drag === name ? 'dragging' : ''}`,
            onDragStart: () => setDrag(name), onDragOver: (e) => e.preventDefault(), onDrop: () => onDrop(name) }} />
      ))}
    </>
  )
}
