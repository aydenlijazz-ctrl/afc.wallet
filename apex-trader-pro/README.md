# Apex Trader Pro

Алгоритмический торговый бот для Bybit (USDT-перпетуалы) на Google Cloud: 11 стратегий, адаптивный риск-менеджмент,
авто-реверс с переворотом позиций, управление через Telegram и React-дашборд.

```
backend/    Python 3.11 + FastAPI — один образ, развёрнутый как 10 сервисов Cloud Run
  apex/
    engine.py       run-apex-hybrid: стратегии → reverse → score → regime → корреляция → ордера
    monitor.py      monitor-positions: закрытия, partial TP, trailing, лимитки, уведомления (ровно один раз)
    reverse.py      адаптивный авто-реверс с переворотом + дневной авто-реверс
    strategies.py   11 стратегий + универсальный исполнитель Custom-стратегий (JSON)
    indicators.py   EMA/SMA/RSI/ATR/ADX/Bollinger/MACD/Supertrend (Wilder)
    risk.py         reverse-математика, Signal Quality Score, regime, correlation, модель издержек, трейлинг
    bybit.py        Bybit v5 REST, HMAC-SHA256, recvWindow=5000, fallback api.bybit.com → api.bybitglobal.com
    bot.py          Telegram-команды и inline-кнопки
    ai.py           разбор стратегий и AI Lab (Anthropic / OpenAI / Gemini)
    evolve.py       еженедельный grid-search бэктест Adaptive Nexus + self-learning
    schema.sql      схема Cloud SQL (PostgreSQL 15)
  tests/            73 теста (реальный PostgreSQL + эмулятор Bybit)
frontend/   React + Vite: Dashboard, History, Analytics, Settings, AI Lab, Market Explorer (EN/RU)
deploy/     deploy.sh — полный деплой в GCP одной командой
```

## Безопасность по умолчанию

**Бот не торгует, пока вы явно не включите торговлю.** После деплоя он считает сигналы и пишет их в журнал
(`live_audit_log`, вкладка «Последние сигналы»), но ордера не отправляет. Включение — кнопка «Включить торговлю»
в дашборде или `/strategies` → «Arm / disarm» в Telegram. Это не было в ТЗ, но бот работает с реальными деньгами на mainnet.

Рекомендация: сначала прогоните бота на **Bybit testnet** — задайте сервисам переменную
`BYBIT_BASE_URLS=https://api-testnet.bybit.com` и ключи от testnet.

## Деплой

```bash
gcloud auth login && firebase login
export PROJECT_ID=my-project REGION=europe-west1 OWNER_EMAIL=me@example.com
export BYBIT_API_KEY=... BYBIT_API_SECRET=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
export ANTHROPIC_API_KEY=...   # или OPENAI_API_KEY / GEMINI_API_KEY — нужно только для AI-функций
cp frontend/.env.example frontend/.env   # вписать Firebase web config
./deploy/deploy.sh
```

Скрипт идемпотентен: включает API, создаёт Cloud SQL, секреты в Secret Manager, сервисные аккаунты, собирает образ
в Cloud Build, деплоит сервисы, создаёт задания Cloud Scheduler, ставит Telegram webhook и публикует фронтенд
в Firebase Hosting. После него: Firebase Console → Authentication → включить Email/Password и создать пользователя
`OWNER_EMAIL`.

| Сервис Cloud Run | Доступ | Вызов |
|---|---|---|
| run-apex-hybrid | приватный (OIDC + X-Admin-Secret) | Scheduler, каждую минуту |
| monitor-positions | приватный | Scheduler, каждую минуту × 2 прохода = каждые 30 с |
| reset-auto-reverse | приватный | Scheduler, 00:00 UTC |
| evolve-adaptive-nexus | приватный | Scheduler, воскресенье 00:00 UTC |
| get-balance, save-settings, get-settings, parse-custom-strategy, dashboard-api | Firebase ID token, только OWNER_EMAIL | фронтенд (rewrites Firebase Hosting) |
| telegram-command-handler | секретный токен webhook + проверка TELEGRAM_CHAT_ID | Telegram |

## Локальный запуск и тесты

```bash
cd backend && pip install -r requirements-dev.txt
# нужен PostgreSQL: postgresql://apex:apex@localhost:5432/ (тесты сами создают базу apex_test)
python -m pytest -q                       # 73 теста

APEX_AUTH_DISABLED=true ADMIN_SECRET=dev OWNER_EMAIL=me@example.com APEX_USE_SECRET_MANAGER=false \
  DATABASE_URL=postgresql://apex:apex@localhost:5432/apex uvicorn apex.main:app --port 8080

cd ../frontend && npm install && npx vitest run && VITE_AUTH_DISABLED=true npm run dev
```

## Где реализация отличается от ТЗ или уточняет его

1. **Переворот позиции — ордер на 2× объём.** В ТЗ: «opposite side, same qty… This flips the position».
   В one-way режиме Bybit ордер на тот же объём только *закрывает* позицию. Бот отправляет 2× объём: 1× закрывает, 1× открывает.
2. **30 секунд в Cloud Scheduler невозможно** (минимум 1 минута). `monitor-positions` вызывается раз в минуту
   и делает два прохода с паузой 30 с.
3. **Одна позиция на символ** (настройка `one_position_per_symbol`, по умолчанию включена). В one-way режиме Bybit позиции
   разных стратегий на одном символе сливаются, и TP/SL одной стратегии сработали бы на чужой объём.
4. **Trend Rider почти никогда не проходит Signal Quality Score ≥ 60.** На синтетическом рынке он дал 28 сигналов,
   и ни один не набрал 60: при развороте Supertrend ADX обычно низкий, а TP/SL = 4/2 ровно 2, не «> 2».
   Если хотите им торговать, снизьте порог (`min_signal_score`) или сделайте для него исключение.
5. **Части ТЗ, отсылающие к «previously defined», определены мной:** условия входа Adaptive Nexus по режимам,
   JSON-схема Custom-стратегии (`ai.py: SCHEMA_PROMPT`), структура таблиц `ai_cache / ai_usage / ai_feedback / live_audit_log`.
6. В таблицы добавлены `trades.closed_at` и `strategy_positions.atr` (нужны для дневного P&L, аналитики и трейлинга).
7. Один владелец: Bybit-аккаунт один, поэтому в дашборд пускается только `OWNER_EMAIL`.
8. Capitulation Absorber: TP на бирже не ставится, потому что TP — это частичное закрытие 50% с переносом SL в безубыток
   и трейлингом остатка. Это делает монитор.

## Что проверено, а что нет

Проверено: 73 backend-теста (индикаторы со сверкой RSI по Wilder, подпись Bybit, fallback хоста, все фильтры, открытие,
частичный TP, трейлинг, Supertrend-трейлинг, лимитки, авто-реверс с переворотом, уведомления ровно один раз, Telegram,
API, AI-парсер, бэктест). Каждая из 11 стратегий генерирует сигналы на синтетическом рынке. 5 frontend-тестов,
сборка и UI в браузере.

**Не проверено:** реальные запросы к Bybit и реальный деплой в GCP. Из среды разработки api.bybit.com был недоступен,
GCP-доступа не было. Прибыльность стратегий не проверялась: бэктест на синтетике проверяет код, а не edge.
