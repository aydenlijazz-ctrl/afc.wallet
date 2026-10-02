"""evolve-adaptive-nexus: weekly grid search + self-learning of SL/TP multipliers."""
from __future__ import annotations

import itertools
import json
import time

import numpy as np

from . import db, indicators as ind
from .bybit import Candles
from .settings import Settings
from .strategies import nexus_regime, nexus_signal_at

GRID = {
    "sl_mult": [1.0, 1.5, 2.0],
    "tp_mult": [2.0, 3.0, 4.0],
    "rsi_low": [30, 35],
    "rsi_high": [65, 70],
    "ema_fast": [20],
    "ema_slow": [50],
}


def fetch_history(exchange, symbol: str, tf: str, days: int) -> Candles:
    """Pages backwards through /v5/market/kline (1000 candles per request)."""
    minutes = {"15m": 15, "1h": 60}[tf]
    need = days * 24 * 60 // minutes + 220  # + indicator warm-up
    rows: list = []
    end = int(time.time() * 1000)
    while len(rows) < need:
        c = exchange.klines(symbol, tf, min(1000, need - len(rows)), end_ms=end, closed_only=False)
        if len(c) == 0:
            break
        rows = [list(r) for r in zip(c.ts, c.open, c.high, c.low, c.close, c.volume)] + rows
        end = int(c.ts[0]) - 1
        if len(c) < 2:
            break
    return Candles.from_rows(rows[-need:])


def backtest(c15: Candles, c1h: Candles, p: dict, fees_bps: float = 10) -> dict:
    """Bar-by-bar simulation; enter at signal close, SL checked before TP inside a bar (conservative)."""
    at = ind.atr(c15.high, c15.low, c15.close, 14)
    gross_win = gross_loss = 0.0
    wins = losses = 0
    i = 220
    n = len(c15)
    while i < n - 1:
        h_idx = int(np.searchsorted(c1h.ts, c15.ts[i], side="right"))
        if h_idx < 60 or np.isnan(at[i]):
            i += 1
            continue
        h = Candles(c1h.ts[:h_idx], c1h.open[:h_idx], c1h.high[:h_idx], c1h.low[:h_idx], c1h.close[:h_idx],
                    c1h.volume[:h_idx])
        window = Candles(*(getattr(c15, f)[max(0, i - 250):i + 1] for f in ("ts", "open", "high", "low", "close", "volume")))
        d = nexus_signal_at(window, nexus_regime(h), p)
        if not d:
            i += 1
            continue
        entry = c15.close[i]
        sgn = 1 if d == "LONG" else -1
        sl, tp = entry - sgn * p["sl_mult"] * at[i], entry + sgn * p["tp_mult"] * at[i]
        j = i + 1
        outcome = None
        while j < n:
            lo, hi = c15.low[j], c15.high[j]
            if (sgn == 1 and lo <= sl) or (sgn == -1 and hi >= sl):
                outcome = sl
            elif (sgn == 1 and hi >= tp) or (sgn == -1 and lo <= tp):
                outcome = tp
            if outcome is not None:
                break
            j += 1
        if outcome is None:
            break
        ret = sgn * (outcome - entry) / entry - 2 * fees_bps / 10000
        if ret > 0:
            gross_win += ret
            wins += 1
        else:
            gross_loss += -ret
            losses += 1
        i = j + 1
    trades = wins + losses
    pf = gross_win / gross_loss if gross_loss else (float("inf") if gross_win else 0.0)
    return {"trades": trades, "wins": wins, "profit_factor": pf, "net_return": gross_win - gross_loss}


def grid_search(c15: Candles, c1h: Candles, min_trades: int = 5) -> tuple[dict, dict]:
    best, best_stats = None, {"profit_factor": -1.0}
    keys = list(GRID)
    for combo in itertools.product(*(GRID[k] for k in keys)):
        p = dict(zip(keys, combo))
        stats = backtest(c15, c1h, p)
        pf = stats["profit_factor"] if stats["trades"] >= min_trades else -1.0
        if pf == float("inf"):
            pf = 99.0
        if pf > best_stats["profit_factor"]:
            best, best_stats = p, {**stats, "profit_factor": pf}
    return best, best_stats


def self_learn(params: dict, recent_win_rate: float | None) -> dict:
    """Low win rate -> wider SL / closer TP; high win rate -> let winners run."""
    p = dict(params)
    if recent_win_rate is None:
        return p
    if recent_win_rate < 0.40:
        p["sl_mult"] = round(min(p["sl_mult"] * 1.1, 3.0), 3)
        p["tp_mult"] = round(max(p["tp_mult"] * 0.9, 1.5), 3)
    elif recent_win_rate > 0.60:
        p["tp_mult"] = round(min(p["tp_mult"] * 1.1, 6.0), 3)
    return p


def run(user_id, exchange, days: int = 14) -> dict:
    st = Settings(user_id)
    symbols = st.symbols("adaptive_nexus") or ["BTCUSDT"]
    results = {}
    agg: dict[str, list] = {}
    for s in symbols:
        c15 = fetch_history(exchange, s, "15m", days)
        c1h = fetch_history(exchange, s, "1h", days + 10)
        best, stats = grid_search(c15, c1h)
        results[s] = {"best": best, "stats": stats}
        if best:
            agg.setdefault(json.dumps(best, sort_keys=True), []).append(stats["profit_factor"])
    current = json.loads(st.s("adaptive_nexus", "params") or "{}")
    if agg:
        best_key = max(agg, key=lambda k: (len(agg[k]), sum(agg[k])))
        current.update(json.loads(best_key))
    wr = db.fetch_one(
        """SELECT COUNT(*) AS n, COUNT(*) FILTER (WHERE net_pnl > 0) AS w FROM (
             SELECT net_pnl FROM trades WHERE user_id=%s AND strategy='adaptive_nexus' AND status='CLOSED'
             ORDER BY closed_at DESC LIMIT 20) t""", (user_id,))
    win_rate = (wr["w"] / wr["n"]) if wr["n"] >= 5 else None
    current = self_learn(current, win_rate)
    st.set("strat_adaptive_nexus_params", json.dumps(current))
    db.audit(user_id, "evolve-adaptive-nexus", "evolve", strategy="adaptive_nexus",
             response={"params": current, "per_symbol": results, "recent_win_rate": win_rate})
    return {"params": current, "per_symbol": results, "recent_win_rate": win_rate}
