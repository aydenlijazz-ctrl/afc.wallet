import math

import numpy as np
import pytest

from apex import strategies
from apex.strategies import REGISTRY, Context
from tests.fakes import FakeExchange, make_candles
from tests.market import Market, MarketExchange, synth_5m

CUSTOM = {"timeframe": "15m", "direction": "both",
          "conditions": {"long": [{"left": {"ind": "rsi", "period": 14}, "op": "<", "right": 30}],
                         "short": [{"left": {"ind": "rsi", "period": 14}, "op": ">", "right": 70}]},
          "sl_atr": 1.5, "tp_atr": 3}

# First bar (5m index, scanning from 13_000 in steps of 3) at which each strategy fires on
# synth_5m(40_000, seed=7). Recorded by a full scan; proves every strategy is reachable.
SCAN_START = 13_000
FIRST_SIGNAL_BAR: dict[str, int] = {
    "wide_atr": 13000,
    "silver_scalper": 13000,
    "custom": 13009,
    "adaptive_nexus": 13102,
    "dynamic_order_flow": 13183,
    "momentum_breakout": 13201,
    "trend_rider": 15373,
    "squeeze_hunter": 16585,
    "apex_mtf": 17839,
    "capitulation_absorber": 19885,
    "rsi_divergence": 29272,
}


@pytest.fixture(scope="module")
def market():
    base = synth_5m(40_000, seed=7)
    return base, Market(base)


def check_geometry(s):
    assert s.direction in ("LONG", "SHORT")
    assert all(math.isfinite(v) for v in (s.entry, s.sl, s.tp, s.atr)) and s.atr > 0
    if s.direction == "LONG":
        assert s.sl < s.entry < s.tp
    else:
        assert s.tp < s.entry < s.sl


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_strategy_fires_on_synthetic_market(name, market):
    base, m = market
    k = FIRST_SIGNAL_BAR[name]
    ex = MarketExchange(m, base.ts[k] + 300_000)
    s = REGISTRY[name](Context(ex, "SOLUSDT", {}, params=CUSTOM if name == "custom" else {}))
    assert s is not None and s.strategy == name
    check_geometry(s)
    if k == SCAN_START:
        return
    # and nothing fired at the previously scanned bar (first-signal property holds)
    ex_prev = MarketExchange(m, base.ts[k - 3] + 300_000)
    assert REGISTRY[name](Context(ex_prev, "SOLUSDT", {}, params=CUSTOM if name == "custom" else {})) is None


def test_signals_have_valid_geometry_on_scan(market):
    base, m = market
    seen = 0
    for k in range(20_000, 21_500, 15):
        ex = MarketExchange(m, base.ts[k] + 300_000)
        cache = {}
        for name, fn in REGISTRY.items():
            s = fn(Context(ex, "SOLUSDT", cache, params=CUSTOM if name == "custom" else {}))
            if s:
                check_geometry(s)
                seen += 1
    assert seen > 0


def test_momentum_breakout_handcrafted():
    ex = FakeExchange()
    rng = np.random.default_rng(0)
    closes = list(100 + np.cumsum(rng.normal(0, 0.05, 120)) - np.linspace(0, 3, 120))  # drifting down: EMA9 < EMA21
    closes += [closes[-1] + 1.5, closes[-1] + 3.5]  # thrust candles
    vol = np.r_[np.full(len(closes) - 1, 100.0), 400.0]
    c = make_candles(closes, spread=0.004, volume=vol)
    ex.candles[("SOLUSDT", "15m")] = c
    ex.candles[("SOLUSDT", "1h")] = make_candles(np.linspace(80, 100, 120), spread=0.004)
    from apex import indicators as ind
    e9, e21 = ind.ema(c.close, 9), ind.ema(c.close, 21)
    s = strategies.momentum_breakout(Context(ex, "SOLUSDT"))
    if ind.crossed_above(e9, e21):
        assert s is not None and s.direction == "LONG"
        assert abs((s.entry - s.sl) / s.atr - 1.8) < 1e-9 and abs((s.tp - s.entry) / s.atr - 3.5) < 1e-9
    else:
        assert s is None


def test_silver_scalper_spread_filter(market):
    base, m = market
    k = 20_000
    hits = 0
    for kk in range(k, k + 3000, 3):
        wide = MarketExchange(m, base.ts[kk] + 300_000, spread_pct=0.002)  # 0.2% > 0.08%
        assert strategies.silver_scalper(Context(wide, "XAGUSDT", {})) is None
        if strategies.silver_scalper(Context(MarketExchange(m, base.ts[kk] + 300_000), "XAGUSDT", {})):
            hits += 1
    assert hits > 0


def test_custom_evaluator_operators():
    ex = FakeExchange()
    ex.candles[("BTCUSDT", "15m")] = make_candles(np.linspace(100, 130, 120), spread=0.004)
    ctx = Context(ex, "BTCUSDT")
    ev = lambda c: strategies.eval_condition(ctx, c, "15m")  # noqa: E731
    assert ev({"left": {"ind": "close"}, "op": ">", "right": {"ind": "ema", "period": 21}})
    assert ev({"left": {"ind": "ema", "period": 9}, "op": "rising"})
    assert ev({"left": {"ind": "rsi", "period": 14}, "op": "between", "range": [60, 100]})
    assert not ev({"left": {"ind": "close"}, "op": "crosses_below", "right": {"ind": "ema", "period": 21}})
    assert ev({"left": {"ind": "supertrend_dir"}, "op": ">", "right": 0})
    assert ev({"left": {"ind": "volume"}, "op": ">=", "right": {"ind": "volume_sma", "period": 20}, "factor": 1.0})
    s = strategies.custom(Context(ex, "BTCUSDT", params={
        "timeframe": "15m", "direction": "long", "sl_atr": 1, "tp_atr": 2,
        "conditions": {"long": [{"left": {"ind": "close"}, "op": ">", "right": {"ind": "ema", "period": 50}}]}}))
    assert s and s.direction == "LONG" and abs((s.tp - s.entry) - 2 * s.atr) < 1e-9


def test_nexus_regimes():
    trend = make_candles(np.linspace(100, 200, 200), spread=0.01)
    assert strategies.nexus_regime(trend) == "STRONG_TREND"
    assert strategies.nexus_regime(make_candles(np.full(200, 100.0), spread=0.001)) == "QUIET_RANGE"
