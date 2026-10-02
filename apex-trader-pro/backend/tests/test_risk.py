from apex import risk
from apex.strategies import Signal
from tests.fakes import make_candles
import numpy as np


def sig(direction="LONG", entry=100.0, sl=98.0, tp=104.0, **kw):
    return Signal("x", "BTCUSDT", direction, entry, sl, tp, 1.0, **kw)


def test_reverse_long_becomes_short():
    s = risk.apply_reverse(sig())  # risk 2, reward 4
    assert s.direction == "SHORT" and s.original_direction == "LONG" and s.reversed
    assert s.sl == 104.0  # entry + original reward
    assert abs(s.tp - (100 - 4.8)) < 1e-9  # entry - max(2, 1.2*4)


def test_reverse_short_becomes_long():
    s = risk.apply_reverse(sig("SHORT", 100, 101, 90))  # risk 1, reward 10
    assert s.direction == "LONG" and s.sl == 90.0 and abs(s.tp - 112.0) < 1e-9


def test_quality_score():
    assert risk.quality_score(sig(adx=36, rsi=30, vol_ratio=1.6, mtf_aligned=True)) == 100  # capped
    assert risk.quality_score(sig(adx=26, rsi=50, vol_ratio=1.3)) == 20 + 15 + 15  # reward == 2*risk: no bonus
    assert risk.quality_score(sig(tp=104.5, adx=26, rsi=50, vol_ratio=1.3)) == 20 + 15 + 15 + 15
    assert risk.quality_score(sig("SHORT", 100, 102, 97, adx=10, rsi=70, vol_ratio=1.0)) == 25
    assert risk.quality_score(sig(adx=10, rsi=70, vol_ratio=1.0)) == 0  # RSI 70 earns nothing for LONG


def test_correlation_tiers():
    assert risk.tier("BTCUSDT") == 1 and risk.tier("SOLUSDT") == 2 and risk.tier("DOGEUSDT") == 3
    assert risk.correlation_allows("ETHUSDT", ["BTCUSDT"])
    assert not risk.correlation_allows("ETHUSDT", ["BTCUSDT", "ETHUSDT"])
    assert risk.correlation_allows("XRPUSDT", ["SOLUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT"])
    assert not risk.correlation_allows("XRPUSDT", ["SOLUSDT", "BNBUSDT", "AVAXUSDT"])
    assert not risk.correlation_allows("PEPEUSDT", ["DOGEUSDT", "WIFUSDT"])


def test_regime():
    trending = make_candles(np.linspace(100, 200, 150), spread=0.004)
    assert risk.market_regime(trending) == "TRENDING"
    flat = make_candles(np.full(150, 100.0), spread=0.0005)
    assert risk.market_regime(flat) == "LOW_VOL"
    rng = np.random.default_rng(3)
    chop = make_candles(100 + rng.normal(0, 1.0, 150), spread=0.004)
    assert risk.market_regime(chop) in ("RANGING", "TRANSITIONAL")
    assert risk.regime_allows("RANGING", ["TRENDING"], 90, 75)[0] is False
    assert risk.regime_allows("TRANSITIONAL", ["TRANSITIONAL"], 70, 75)[0] is False
    assert risk.regime_allows("TRANSITIONAL", ["TRANSITIONAL"], 80, 75)[0] is True


def test_cost_model():
    # 1 BTC long 100 -> 110: gross 10, costs (100+110)*0.001 = 0.21
    assert abs(risk.net_pnl("LONG", 100, 110, 1, 5, 5) - 9.79) < 1e-9
    assert abs(risk.net_pnl("SHORT", 100, 110, 1, 5, 5) - (-10.21)) < 1e-9


def test_trailing_never_widens():
    lvl = risk.trail_level("LONG", 110, 2, None)
    assert lvl == 108
    assert risk.trail_level("LONG", 109, 2, lvl) == 108  # price fell: stop stays
    assert risk.trail_level("LONG", 115, 2, lvl) == 113
    assert risk.trail_level("SHORT", 90, 2, 95) == 92
    assert risk.trail_level("SHORT", 96, 2, 92) == 92
