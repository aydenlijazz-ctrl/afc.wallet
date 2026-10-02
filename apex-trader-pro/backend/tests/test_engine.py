import numpy as np
import pytest

from apex import db, engine, strategies
from apex.settings import Settings, save
from apex.strategies import Signal
from tests.fakes import make_candles

TREND_1H = make_candles(np.linspace(100, 200, 200), spread=0.004)


def stub(direction="LONG", order_type="Market", **kw):
    def fn(ctx):
        p = ctx.exchange.prices[ctx.symbol]
        sgn = 1 if direction == "LONG" else -1
        return Signal("wide_atr", ctx.symbol, direction, p, p - sgn * 2, p + sgn * 5, 1.0, order_type=order_type,
                      adx=36, rsi=50, vol_ratio=1.6, mtf_aligned=True, **kw)
    return fn


@pytest.fixture
def market(ex):
    for s, p in {"BTCUSDT": 200.0, "ETHUSDT": 100.0, "SOLUSDT": 50.0, "AVAXUSDT": 30.0}.items():
        ex.prices[s] = p
        ex.candles[(s, "1h")] = make_candles(np.linspace(p / 2, p, 200), spread=0.004)
    return ex


def enable(uid, name="wide_atr", **extra):
    save(uid, {f"strat_{name}_enabled": "true", f"strat_{name}_symbols": "BTCUSDT", f"strat_{name}_cost": "100",
               f"strat_{name}_leverage": "2", **extra})


def test_not_armed_logs_signal_without_trading(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    enable(uid)
    out = engine.run(uid, market, tg)
    assert market.orders == []
    assert out["opened"] == [] and out["skipped"][0]["reason"] == "live trading is not armed"
    assert db.fetch_one("SELECT COUNT(*) n FROM live_audit_log WHERE action='signal_not_armed'")["n"] == 1


def test_armed_opens_market_order_with_tp_sl(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    enable(uid, live_trading_armed="true")
    out = engine.run(uid, market, tg)
    assert len(out["opened"]) == 1
    o = market.orders[0]
    assert o["side"] == "Buy" and o["type"] == "Market" and o["qty"] == 1.0  # 100 USDT * 2x / 200
    assert market.leverage["BTCUSDT"] == 2
    assert market.stops["BTCUSDT"] == {"tp": 205.0, "sl": 198.0}
    t = db.fetch_one("SELECT * FROM trades")
    assert t["status"] == "OPEN" and t["trading_mode"] == "live" and t["signal_score"] == 100
    assert t["signal_regime"] == "TRENDING" and float(t["actual_quantity"]) == 1.0
    assert db.fetch_one("SELECT * FROM strategy_positions")["status"] == "OPEN"
    assert "Wide ATR" in tg.sent[0] and "LONG BTCUSDT" in tg.sent[0]
    # second run: already in a position for this strategy/symbol -> nothing new
    engine.run(uid, market, tg)
    assert len(market.orders) == 1


def test_reverse_mode_inverts_signal(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    enable(uid, live_trading_armed="true", strat_wide_atr_reverse_enabled="true")
    engine.run(uid, market, tg)
    t = db.fetch_one("SELECT * FROM trades")
    assert t["direction"] == "SHORT" and t["reversed"] and t["original_direction"] == "LONG"
    assert float(t["stop_loss"]) == 205.0 and float(t["take_profit"]) == 194.0  # 200 - max(2, 1.2*5)
    assert market.orders[0]["side"] == "Sell"


def test_low_score_and_wrong_regime_are_filtered(uid, market, tg, monkeypatch):
    def weak(ctx):
        return Signal("wide_atr", ctx.symbol, "LONG", 200, 198, 205, 1.0, adx=10, rsi=70, vol_ratio=1.0)
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", weak)
    enable(uid, live_trading_armed="true")
    out = engine.run(uid, market, tg)
    assert "score" in out["skipped"][0]["reason"] and market.orders == []

    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    save(uid, {"strat_wide_atr_allowed_regimes": "RANGING"})
    out = engine.run(uid, market, tg)
    assert "regime TRENDING" in out["skipped"][0]["reason"] and market.orders == []


def test_correlation_cap(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    monkeypatch.setitem(strategies.REGISTRY, "trend_rider", stub())
    enable(uid, live_trading_armed="true")
    save(uid, {"strat_wide_atr_symbols": "BTCUSDT,ETHUSDT", "strat_trend_rider_enabled": "true",
               "strat_trend_rider_symbols": "SOLUSDT", "strat_trend_rider_allowed_regimes": "TRENDING"})
    # pretend two tier-1 positions are open already from another strategy run
    for s in ("BTCUSDT", "ETHUSDT"):
        db.execute("""INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit,
                      actual_quantity) VALUES (%s,%s,'LONG','apex_mtf',1,0.5,2,1)""", (uid, s))
    save(uid, {"one_position_per_symbol": "false", "strat_wide_atr_symbols": "BTCUSDT,ETHUSDT"})
    out = engine.run(uid, market, tg)
    reasons = [s["reason"] for s in out["skipped"]]
    assert reasons.count("correlation tier 1 cap") == 2
    assert [o["symbol"] for o in out["opened"]] == ["SOLUSDT"]


def test_one_position_per_symbol(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    monkeypatch.setitem(strategies.REGISTRY, "apex_mtf", stub())
    enable(uid, live_trading_armed="true")
    enable(uid, "apex_mtf")
    engine.run(uid, market, tg)
    assert len(market.orders) == 1  # second strategy on the same symbol is skipped


def test_limit_order_creates_pending_position(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "dynamic_order_flow", stub(order_type="Limit"))
    enable(uid, "dynamic_order_flow", live_trading_armed="true", strat_dynamic_order_flow_allowed_regimes="TRENDING")
    engine.run(uid, market, tg)
    o = market.orders[0]
    assert o["type"] == "Limit" and o["price"] == 200.0 and o["tp"] == 205.0 and o["sl"] == 198.0
    assert db.fetch_one("SELECT status FROM strategy_positions")["status"] == "PENDING"
    assert "BTCUSDT" not in market.positions_


def test_order_failure_records_failed_trade(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    enable(uid, live_trading_armed="true")
    market.fail_orders = True
    out = engine.run(uid, market, tg)
    assert db.fetch_one("SELECT status FROM trades")["status"] == "FAILED"
    assert "insufficient balance" in out["skipped"][0]["reason"] and tg.sent[0].startswith("❌")


def test_min_qty_rejected(uid, market, tg, monkeypatch):
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    enable(uid, live_trading_armed="true", strat_wide_atr_cost="0.01", strat_wide_atr_leverage="1")
    engine.run(uid, market, tg)
    assert market.orders == [] and db.fetch_one("SELECT status FROM trades")["status"] == "FAILED"


def test_capitulation_scale_in(uid, ex, tg):
    """Entry 1 on capitulation, entry 2 after a further -2 ATR move, TP/SL recomputed from the average."""
    closes = np.r_[np.full(150, 100.0) + np.sin(np.arange(150)) * 0.5, np.linspace(100, 70, 12)]
    c = make_candles(closes, spread=0.012)
    ex.candles[("DOGEUSDT", "1h")] = c
    ex.prices["DOGEUSDT"] = float(closes[-1])
    save(uid, {"strat_capitulation_absorber_enabled": "true", "strat_capitulation_absorber_symbols": "DOGEUSDT",
               "strat_capitulation_absorber_cost": "100", "strat_capitulation_absorber_leverage": "1",
               "strat_capitulation_absorber_allowed_regimes": "TRENDING,TRANSITIONAL,RANGING",
               "live_trading_armed": "true", "min_signal_score": "0"})
    out = engine.run(uid, ex, tg)
    assert len(out["opened"]) == 1, out
    pos = db.fetch_one("SELECT * FROM strategy_positions")
    assert pos["direction"] == "LONG" and pos["addition_count"] == 1
    assert abs(float(pos["total_quantity"]) - round(25 / 70, 3)) < 1e-9  # 25% of capital
    assert "tp" not in ex.stops["DOGEUSDT"]  # TP handled by the monitor (partial close)
    atr_v = float(pos["atr"])
    ex.prices["DOGEUSDT"] = 70 - 2.1 * atr_v
    out = engine.run(uid, ex, tg)
    pos = db.fetch_one("SELECT * FROM strategy_positions")
    assert pos["addition_count"] == 2
    avg = float(pos["average_entry_price"])
    assert abs(float(pos["current_tp"]) - (avg + 2.5 * atr_v)) < 0.02
    assert abs(float(pos["current_sl"]) - (ex.prices["DOGEUSDT"] - 3 * atr_v)) < 0.02
    assert db.fetch_one("SELECT COUNT(*) n FROM trades WHERE status='OPEN'")["n"] == 2


def test_active_hours(uid):
    from datetime import datetime, timezone
    st = Settings(uid, {"strat_wide_atr_active_hours": "22-3"})
    assert st.in_active_hours("wide_atr", datetime(2026, 1, 1, 23, tzinfo=timezone.utc))
    assert not st.in_active_hours("wide_atr", datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
