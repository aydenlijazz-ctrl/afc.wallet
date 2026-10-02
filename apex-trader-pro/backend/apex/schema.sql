-- Apex Trader Pro schema (PostgreSQL 15+). Idempotent: safe to run on every start.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('LONG','SHORT')),
  strategy TEXT NOT NULL,
  entry_price NUMERIC NOT NULL,
  stop_loss NUMERIC NOT NULL,
  take_profit NUMERIC NOT NULL,
  order_id TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','FAILED')),
  exit_price NUMERIC,
  pnl NUMERIC,
  net_pnl NUMERIC,
  result TEXT CHECK (result IN ('TP HIT','SL HIT','MANUAL CLOSE','PARTIAL TP HIT','TRAILING STOP HIT','REVERSED')),
  reversed BOOLEAN NOT NULL DEFAULT false,
  original_direction TEXT,
  trading_mode TEXT NOT NULL DEFAULT 'live',
  signal_score INTEGER,
  signal_regime TEXT,
  aggregated_position_id UUID,
  cost_usdt NUMERIC,
  leverage NUMERIC,
  actual_quantity NUMERIC,
  close_notification_sent BOOLEAN NOT NULL DEFAULT false,
  closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS trades_user_status ON trades (user_id, status);
CREATE INDEX IF NOT EXISTS trades_user_strategy_created ON trades (user_id, strategy, created_at);

CREATE TABLE IF NOT EXISTS bot_settings (
  user_id UUID NOT NULL,
  key TEXT NOT NULL,
  value TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS strategy_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  strategy TEXT NOT NULL,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  total_quantity NUMERIC NOT NULL,
  average_entry_price NUMERIC NOT NULL,
  last_entry_price NUMERIC NOT NULL,
  addition_count INTEGER NOT NULL DEFAULT 1,
  current_sl NUMERIC,
  current_tp NUMERIC,
  partial_tp_hit BOOLEAN NOT NULL DEFAULT false,
  trail_stop_level NUMERIC,
  status TEXT NOT NULL DEFAULT 'OPEN',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atr NUMERIC
);
CREATE INDEX IF NOT EXISTS strategy_positions_open ON strategy_positions (user_id, status);

CREATE TABLE IF NOT EXISTS adaptive_reverse_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  strategy TEXT NOT NULL,
  realized_loss NUMERIC,
  unrealized_loss NUMERIC,
  total_loss NUMERIC NOT NULL,
  threshold NUMERIC NOT NULL,
  action TEXT NOT NULL,
  new_reverse_state BOOLEAN,
  details TEXT
);

CREATE TABLE IF NOT EXISTS auto_reverse_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  strategy TEXT NOT NULL,
  daily_pnl NUMERIC,
  threshold NUMERIC,
  action TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_cache (
  cache_key TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  response JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  provider TEXT NOT NULL,
  model TEXT,
  feature TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER
);

CREATE TABLE IF NOT EXISTS ai_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  feature TEXT NOT NULL,
  rating INTEGER,
  comment TEXT,
  context JSONB
);

CREATE TABLE IF NOT EXISTS live_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  service TEXT NOT NULL,
  action TEXT NOT NULL,
  symbol TEXT,
  strategy TEXT,
  request JSONB,
  response JSONB,
  success BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS live_audit_log_user_created ON live_audit_log (user_id, created_at DESC);
