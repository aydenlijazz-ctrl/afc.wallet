import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { I18nContext, useT } from './i18n'
import { authDisabled, login, logout, watchUser } from './firebase'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import AILab from './pages/AILab'
import MarketExplorer from './pages/MarketExplorer'

function Login() {
  const t = useT()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    try { await login(email, password) } catch (err) { setError(err.message) }
  }
  return (
    <form className="card login" onSubmit={submit}>
      <div className="brand">Apex Trader Pro</div>
      <label className="field">{t('email')}<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></label>
      <br />
      <label className="field">{t('password')}<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required /></label>
      <br />
      <button type="submit">{t('login')}</button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

function Shell() {
  const t = useT()
  const links = [['/', 'dashboard'], ['/history', 'history'], ['/analytics', 'analytics'], ['/settings', 'settings'],
    ['/ai-lab', 'aiLab'], ['/market', 'market']]
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="brand">⚡ Apex Trader Pro</div>
        {links.map(([to, key]) => <NavLink key={to} to={to} end={to === '/'}>{t(key)}</NavLink>)}
        <div className="spacer" />
        <LangSwitch />
        {!authDisabled && <button className="secondary" onClick={logout}>{t('logout')}</button>}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/history" element={<History />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/ai-lab" element={<AILab />} />
          <Route path="/market" element={<MarketExplorer />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}

function LangSwitch() {
  return (
    <I18nContext.Consumer>
      {({ lang, setLang }) => (
        <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="language">
          <option value="en">English</option>
          <option value="ru">Русский</option>
        </select>
      )}
    </I18nContext.Consumer>
  )
}

export default function App() {
  const [user, setUser] = useState(undefined)
  const [lang, setLangState] = useState(() => {
    try { return localStorage.getItem('lang') || (navigator.language.startsWith('ru') ? 'ru' : 'en') } catch { return 'en' }
  })
  const setLang = (l) => { setLangState(l); try { localStorage.setItem('lang', l) } catch { /* ignore */ } }
  useEffect(() => watchUser(setUser), [])
  return (
    <I18nContext.Provider value={{ lang, setLang }}>
      {user === undefined ? null : user ? <Shell /> : <Login />}
    </I18nContext.Provider>
  )
}
