import { useState } from 'react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useT } from '../i18n'
import { fmt, pnlClass, whatIf } from '../format'

const MODES = [
  ['chat', 'chat', ''],
  ['analyzer', 'analyzer', 'Analyze each strategy\'s performance over the last 30 days and suggest concrete parameter changes.'],
  ['context', 'context', 'Summarize the current market context for my traded symbols and which strategies fit it.'],
  ['journal', 'journal', 'Write a trade journal for my recent trades: what worked, what did not, lessons.'],
  ['auditor', 'auditor', 'Audit signal quality: do higher signal scores and regimes correlate with better results?'],
]

export default function AILab() {
  const t = useT()
  const [mode, setMode] = useState('chat')
  const [input, setInput] = useState('')
  const [log, setLog] = useState([])
  const [busy, setBusy] = useState(false)
  const send = async (text) => {
    if (!text.trim()) return
    setLog((l) => [...l, { role: 'user', text }]); setInput(''); setBusy(true)
    try { const r = await api.aiChat(text, mode); setLog((l) => [...l, { role: 'assistant', text: r.reply }]) } catch (e) { setLog((l) => [...l, { role: 'assistant', text: `⚠️ ${e.message}` }]) }
    setBusy(false)
  }
  return (
    <>
      <h1>{t('aiLab')}</h1>
      <div className="tabs">
        {MODES.map(([m, key]) => <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>{t(key)}</button>)}
        <button className={mode === 'whatif' ? 'active' : ''} onClick={() => setMode('whatif')}>{t('whatIf')}</button>
      </div>
      {mode === 'whatif' ? <WhatIf /> : (
        <div className="card">
          <div className="chat">{log.map((m, i) => <div key={i} className={`msg ${m.role}`}>{m.text}</div>)}</div>
          <div className="row">
            <input style={{ flex: 1 }} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send(input)} placeholder={t('ask')} />
            <button onClick={() => send(input)} disabled={busy}>{busy ? t('loading') : t('send')}</button>
            {MODES.find((m) => m[0] === mode)?.[2] && <button className="secondary" disabled={busy} onClick={() => send(MODES.find((m) => m[0] === mode)[2])}>▶ {t(mode)}</button>}
          </div>
        </div>
      )}
    </>
  )
}

function WhatIf() {
  const t = useT()
  const trades = useApi(() => api.trades({ status: 'CLOSED', limit: 5000 }))
  const [p, setP] = useState({ slMult: 1, tpMult: 1, bps: 10 })
  const r = whatIf(trades.data?.trades || [], p)
  const set = (k) => (e) => setP({ ...p, [k]: Number(e.target.value) })
  return (
    <div className="card">
      <p className="muted">{t('whatIfHint')}</p>
      <div className="row">
        <label className="field">{t('slMult')}<input type="number" step="0.1" value={p.slMult} onChange={set('slMult')} /></label>
        <label className="field">{t('tpMult')}<input type="number" step="0.1" value={p.tpMult} onChange={set('tpMult')} /></label>
        <label className="field">{t('fees')}<input type="number" value={p.bps} onChange={set('bps')} /></label>
      </div>
      <div className="grid" style={{ marginTop: 16 }}>
        <div className="card kpi"><div className="label">{t('original')}</div><div className={`value ${pnlClass(r.original)}`}>{fmt(r.original)} USDT</div></div>
        <div className="card kpi"><div className="label">{t('simulated')}</div><div className={`value ${pnlClass(r.simulated)}`}>{fmt(r.simulated)} USDT</div></div>
      </div>
    </div>
  )
}
