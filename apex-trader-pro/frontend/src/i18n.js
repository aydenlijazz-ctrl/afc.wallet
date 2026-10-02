import { createContext, useContext } from 'react'

// Trading terms (LONG, SHORT, TP, SL, ATR, P&L) intentionally stay in English in both languages.
export const dict = {
  en: {
    dashboard: 'Dashboard', history: 'History', analytics: 'Analytics', settings: 'Settings', aiLab: 'AI Lab',
    market: 'Market Explorer', logout: 'Log out', login: 'Log in', email: 'Email', password: 'Password',
    mode: 'Mode', equity: 'Equity', available: 'Available', unrealized: 'Unrealized P&L', openPositions: 'Open positions',
    recentSignals: 'Recent signals', strategyPerformance: 'Strategy performance', symbol: 'Symbol', direction: 'Direction',
    strategy: 'Strategy', entry: 'Entry', mark: 'Mark', qty: 'Qty', close: 'Close', closeAll: 'Close all',
    none: 'Nothing here yet', time: 'Time', status: 'Status', result: 'Result', exit: 'Exit', netPnl: 'Net P&L',
    score: 'Score', regime: 'Regime', all: 'All', from: 'From', to: 'To', reverseMode: 'Reverse mode',
    onlyReversed: 'Reversed only', onlyNormal: 'Normal only', trades: 'Trades', winRate: 'Win rate',
    profitFactor: 'Profit factor', avgTrade: 'Avg trade', bestHours: 'Best trading hours (UTC)',
    hourTrades: 'Trades opened at {h}:00 UTC', enabled: 'Enabled', symbols: 'Symbols', cost: 'Entry cost (USDT)',
    leverage: 'Leverage', trailing: 'Trailing stop', trailDistance: 'Trail distance (×ATR)', partialTp: 'Partial TP',
    partialPct: 'Partial close %', adaptive: 'Adaptive auto-reverse', threshold: 'Loss threshold (USDT)',
    includeUnreal: 'Include unrealized P&L', activeHours: 'Active hours UTC (e.g. 6-22)', priority: 'Priority',
    allowedRegimes: 'Allowed regimes', save: 'Save', saved: 'Saved', armed: 'LIVE trading armed',
    notArmed: 'Signals only — live trading NOT armed', arm: 'Arm live trading', disarm: 'Disarm',
    armConfirm: 'Arm LIVE trading on Bybit mainnet with real funds?', global: 'Global', minScore: 'Min signal score',
    customStrategy: 'Custom strategy (AI)', describe: 'Describe your strategy in plain language…', parse: 'Parse with AI',
    send: 'Send', chat: 'Chat', analyzer: 'Performance analyzer', context: 'Market context', journal: 'Trade journal',
    whatIf: 'What-if simulator', auditor: 'Signal quality auditor', ask: 'Ask about your trading…',
    heatmap: 'Heatmap', leaderboard: 'Leaderboard', bubbles: 'Bubble chart', anomalies: 'Anomalies',
    minTurnover: 'Min 24h turnover (M USDT)', search: 'Search', change: '24h %', turnover: 'Turnover 24h',
    funding: 'Funding %', loading: 'Loading…', error: 'Error', dragHint: 'Drag cards to reorder (sets priority)',
    whatIfHint: 'Re-computes history with different SL/TP multipliers and fees', slMult: 'SL multiplier',
    tpMult: 'TP multiplier', fees: 'Fees + slippage (bps per side)', simulate: 'Simulate', original: 'Original',
    simulated: 'Simulated', armedShort: 'ARMED', notArmedShort: 'NOT ARMED',
  },
  ru: {
    dashboard: 'Панель', history: 'История', analytics: 'Аналитика', settings: 'Настройки', aiLab: 'AI Лаборатория',
    market: 'Обзор рынка', logout: 'Выйти', login: 'Войти', email: 'Email', password: 'Пароль',
    mode: 'Режим', equity: 'Капитал', available: 'Доступно', unrealized: 'Нереализованный P&L',
    openPositions: 'Открытые позиции', recentSignals: 'Последние сигналы', strategyPerformance: 'Результаты стратегий',
    symbol: 'Символ', direction: 'Направление', strategy: 'Стратегия', entry: 'Вход', mark: 'Марк. цена', qty: 'Кол-во',
    close: 'Закрыть', closeAll: 'Закрыть все', none: 'Пока пусто', time: 'Время', status: 'Статус', result: 'Итог',
    exit: 'Выход', netPnl: 'Чистый P&L', score: 'Оценка', regime: 'Режим рынка', all: 'Все', from: 'С', to: 'По',
    reverseMode: 'Reverse-режим', onlyReversed: 'Только reversed', onlyNormal: 'Только обычные', trades: 'Сделки',
    winRate: 'Win rate', profitFactor: 'Profit factor', avgTrade: 'Средняя сделка',
    bestHours: 'Лучшие часы торговли (UTC)', hourTrades: 'Сделки, открытые в {h}:00 UTC', enabled: 'Включена',
    symbols: 'Символы', cost: 'Размер входа (USDT)', leverage: 'Плечо', trailing: 'Trailing stop',
    trailDistance: 'Дистанция трейлинга (×ATR)', partialTp: 'Частичный TP', partialPct: 'Закрыть %',
    adaptive: 'Адаптивный авто-реверс', threshold: 'Порог убытка (USDT)', includeUnreal: 'Учитывать нереализованный P&L',
    activeHours: 'Активные часы UTC (напр. 6-22)', priority: 'Приоритет', allowedRegimes: 'Разрешённые режимы',
    save: 'Сохранить', saved: 'Сохранено', armed: 'Реальная торговля ВКЛЮЧЕНА',
    notArmed: 'Только сигналы — реальная торговля ВЫКЛЮЧЕНА', arm: 'Включить торговлю', disarm: 'Выключить',
    armConfirm: 'Включить РЕАЛЬНУЮ торговлю на Bybit mainnet реальными средствами?', global: 'Общие',
    minScore: 'Мин. оценка сигнала', customStrategy: 'Своя стратегия (AI)',
    describe: 'Опишите стратегию обычным языком…', parse: 'Разобрать через AI', send: 'Отправить', chat: 'Чат',
    analyzer: 'Анализ результатов', context: 'Рыночный контекст', journal: 'Журнал сделок',
    whatIf: 'Симулятор «что если»', auditor: 'Аудит качества сигналов', ask: 'Спросите о своей торговле…',
    heatmap: 'Тепловая карта', leaderboard: 'Лидеры', bubbles: 'Пузырьковая диаграмма', anomalies: 'Аномалии',
    minTurnover: 'Мин. оборот 24ч (млн USDT)', search: 'Поиск', change: '24ч %', turnover: 'Оборот 24ч',
    funding: 'Funding %', loading: 'Загрузка…', error: 'Ошибка',
    dragHint: 'Перетаскивайте карточки, чтобы менять приоритет',
    whatIfHint: 'Пересчитывает историю с другими множителями SL/TP и комиссиями', slMult: 'Множитель SL',
    tpMult: 'Множитель TP', fees: 'Комиссия + проскальзывание (bps за сторону)', simulate: 'Рассчитать',
    original: 'Исходно', simulated: 'Симуляция', armedShort: 'ВКЛ', notArmedShort: 'ВЫКЛ',
  },
}

export const I18nContext = createContext({ lang: 'en', setLang: () => {} })

export function useT() {
  const { lang } = useContext(I18nContext)
  return (key, vars = {}) => {
    let s = dict[lang]?.[key] ?? dict.en[key] ?? key
    for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v)
    return s
  }
}
