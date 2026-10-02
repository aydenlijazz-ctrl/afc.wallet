from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from apex import db, engine, monitor, strategies
from apex.settings import save
from apex.strategies import Signal
from tests.fakes import make_candles


def stub(name="wide_atr", order_type="Market", trailing_mode="distance"):
    def fn(ctx):
        p = ctx.exchange.prices[ctx.symbol]
        return Signal(name, ctx.symbol, "LONG", p, p - 2, p + 6, 1.0, order_type=order_type, adx=36, rsi=50,
                      vol_ratio=1.6, mtf_aligned=True, trailing_mode=trailing_mode)
    return fn


@pytest.fixture
def opened(uid, ex, tg, monkeypatch):
    ex.prices["BTCUSDT"] = 100.0
    ex.candles[("BTCUSDT", "1h")] = make_candles(np.linspace(50, 100, 200), spread=0.004)
    monkeypatch.setitem(strategies.REGISTRY, "wide_atr", stub())
    save(uid, {"strat_wide_atr_enabled": "true", "strat_wide_atr_symbols": "BTCUSDT", "strat_wide_atr_cost": "100",
               "strat_wide_atr_leverage": "1", "live_trading_armed": "true"})
    engine.run(uid, ex, tg)
    tg.sent.clear()
    return ex


def test_tp_close_detected_and_notified_exactly_once(uid, opened, tg):
    opened.hit("BTCUSDT", 106.0)  # exchange TP executes
    out = monitor.run(uid, opened, tg)
    assert out["closed"][0]["result"] == "TP HIT"
    t = db.fetch_one("SELECT * FROM trades")
    assert t["status"] == "CLOSED" and float(t["exit_price"]) == 106.0
    assert abs(float(t["pnl"]) - 6.0) < 1e-9
    assert abs(float(t["net_pnl"]) - (6.0 - (100 + 106) * 0.001)) < 1e-9
    assert t["close_notification_sent"] is True and t["closed_at"] is not None
    assert len(tg.sent) == 1 and "TP HIT" in tg.sent[0] and "+5.79" in tg.sent[0]
    monitor.run(uid, opened, tg)
    monitor.run(uid, opened, tg)
    assert len(tg.sent) == 1  # exactly once
    assert db.fetch_one("SELECT status FROM strategy_positions")["status"] == "CLOSED"


def test_sl_and_manual_classification(uid, opened, tg):
    opened.hit("BTCUSDT", 98.0)
    assert monitor.run(uid, opened, tg)["closed"][0]["result"] == "SL HIT"
    t = {"entry_price": 100, "take_profit": 106, "stop_loss": 98, "direction": "LONG"}
    assert monitor.classify(t, {"atr": 1}, 101.0) == "MANUAL CLOSE"
    assert monitor.classify(t, {"atr": 1, "trail_stop_level": 103}, 103.1) == "TRAILING STOP HIT"


def test_partial_tp_then_trailing(uid, opened, tg):
    save(uid, {"strat_wide_atr_partial_tp_enabled": "true", "strat_wide_atr_trail_distance": "1.5"})
    opened.prices["BTCUSDT"] = 103.2  # 50% of the TP distance (100 -> 106) is 103
    out = monitor.run(uid, opened, tg)
    assert out["partials"][0]["qty"] == 0.5
    reduce = opened.orders[-1]
    assert reduce["reduce_only"] and reduce["side"] == "Sell" and reduce["qty"] == 0.5
    assert opened.positions_["BTCUSDT"]["size"] == 0.5
    pos = db.fetch_one("SELECT * FROM strategy_positions")
    assert pos["partial_tp_hit"] and float(pos["current_sl"]) == 101.7  # max(BE 100, 103.2 - 1.5)
    assert opened.stops["BTCUSDT"]["sl"] == 101.7
    rows = db.fetch("SELECT * FROM trades ORDER BY status")
    assert [r["status"] for r in rows] == ["CLOSED", "OPEN"]
    assert rows[0]["result"] == "PARTIAL TP HIT" and float(rows[1]["actual_quantity"]) == 0.5
    assert "PARTIAL TP HIT" in tg.sent[-1]
    # price rises: stop follows; price dips: stop holds
    opened.prices["BTCUSDT"] = 105.0
    monitor.run(uid, opened, tg)
    assert opened.stops["BTCUSDT"]["sl"] == 103.5
    opened.prices["BTCUSDT"] = 104.0
    monitor.run(uid, opened, tg)
    assert opened.stops["BTCUSDT"]["sl"] == 103.5
    opened.hit("BTCUSDT", 103.5)
    out = monitor.run(uid, opened, tg)
    assert out["closed"][0]["result"] == "TRAILING STOP HIT"


def test_trailing_only_activates_after_profit(uid, opened, tg):
    save(uid, {"strat_wide_atr_trailing_enabled": "true", "strat_wide_atr_trail_distance": "2"})
    opened.prices["BTCUSDT"] = 101.0  # profit 1 < distance 2
    assert monitor.run(uid, opened, tg)["trailing"] == []
    opened.prices["BTCUSDT"] = 102.5
    assert monitor.run(uid, opened, tg)["trailing"][0]["level"] == 100.5


def test_limit_fill_and_expiry(uid, ex, tg, monkeypatch):
    ex.prices.update({"BTCUSDT": 100.0, "ETHUSDT": 50.0})
    for s in ("BTCUSDT", "ETHUSDT"):
        ex.candles[(s, "1h")] = make_candles(np.linspace(50, 100, 200), spread=0.004)
    monkeypatch.setitem(strategies.REGISTRY, "dynamic_order_flow", stub("dynamic_order_flow", "Limit"))
    save(uid, {"strat_dynamic_order_flow_enabled": "true", "strat_dynamic_order_flow_symbols": "BTCUSDT,ETHUSDT",
               "strat_dynamic_order_flow_allowed_regimes": "TRENDING", "live_trading_armed": "true",
               "strat_dynamic_order_flow_cost": "100", "strat_dynamic_order_flow_leverage": "1"})
    engine.run(uid, ex, tg)
    btc, eth = ex.orders
    out = monitor.run(uid, ex, tg)  # nothing filled yet: still pending, nothing closed
    assert out["closed"] == [] and db.fetch_one("SELECT COUNT(*) n FROM trades WHERE status='OPEN'")["n"] == 2
    ex.fill_limit(btc["id"])
    out = monitor.run(uid, ex, tg)
    assert out["fills"] == ["BTCUSDT"]
    db.execute("UPDATE strategy_positions SET created_at=%s WHERE symbol='ETHUSDT'",
               (datetime.now(timezone.utc) - timedelta(hours=2),))
    monitor.run(uid, ex, tg)
    assert ex.order_states[eth["id"]] == "Cancelled"
    assert db.fetch_one("SELECT status FROM trades WHERE symbol='ETHUSDT'")["status"] == "FAILED"
    assert db.fetch_one("SELECT status FROM trades WHERE symbol='BTCUSDT'")["status"] == "OPEN"


def test_manual_close(uid, opened, tg):
    opened.prices["BTCUSDT"] = 101.0
    r = monitor.close_symbol(uid, opened, "BTCUSDT", "test")
    assert r["closed"] == 1 and "BTCUSDT" not in opened.positions_
    assert db.fetch_one("SELECT result FROM trades")["result"] == "MANUAL CLOSE"


def test_trend_rider_supertrend_trailing(uid, ex, tg, monkeypatch):
    closes = np.linspace(80, 100, 200)
    ex.candles[("BTCUSDT", "1h")] = make_candles(closes, spread=0.0015)  # tight ATR (above LOW_VOL): supertrend ~99 > SL 98
    ex.prices["BTCUSDT"] = 100.0
    monkeypatch.setitem(strategies.REGISTRY, "trend_rider", stub("trend_rider", trailing_mode="supertrend"))
    save(uid, {"strat_trend_rider_enabled": "true", "strat_trend_rider_symbols": "BTCUSDT",
               "strat_trend_rider_allowed_regimes": "TRENDING", "live_trading_armed": "true",
               "strat_trend_rider_cost": "100", "strat_trend_rider_leverage": "1"})
    engine.run(uid, ex, tg)
    ex.prices["BTCUSDT"] = 101.0  # < 1.5 ATR profit: no trailing yet
    assert monitor.run(uid, ex, tg)["trailing"] == []
    ex.prices["BTCUSDT"] = 101.6
    out = monitor.run(uid, ex, tg)
    assert out["trailing"] and out["trailing"][0]["level"] > 98  # supertrend line is above the initial SL
    assert ex.stops["BTCUSDT"]["sl"] == out["trailing"][0]["level"]
