import math

import numpy as np

from apex import indicators as ind
from tests.fakes import make_candles


def test_sma_ema_basic():
    x = np.arange(1, 11, dtype=float)
    assert ind.sma(x, 3)[-1] == 9.0
    assert math.isnan(ind.sma(x, 3)[1])
    e = ind.ema(x, 3)
    assert e[2] == 2.0  # seeded with SMA
    assert abs(e[3] - (4 * 0.5 + 2.0 * 0.5)) < 1e-12


def test_rsi_extremes_and_range():
    up = np.linspace(100, 200, 60)
    assert ind.rsi(up, 14)[-1] == 100.0
    down = np.linspace(200, 100, 60)
    assert ind.rsi(down, 14)[-1] < 1e-9
    rng = np.random.default_rng(1)
    r = ind.rsi(100 + np.cumsum(rng.normal(0, 1, 500)), 14)
    valid = r[~np.isnan(r)]
    assert valid.min() >= 0 and valid.max() <= 100


def test_rsi_matches_wilder_reference():
    # Reference values computed with the classic Wilder smoothing (as TradingView ta.rsi)
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
              46.28, 46.00, 46.03, 46.41, 46.22, 45.64]
    r = ind.rsi(closes, 14)
    assert abs(r[14] - 70.46) < 0.1
    assert abs(r[19] - 57.92) < 0.5


def test_atr_constant_range():
    c = make_candles(np.full(50, 100.0), spread=0.01)
    a = ind.atr(c.high, c.low, c.close, 14)
    assert abs(a[-1] - 2.0) < 1e-9  # high-low = 101-99


def test_bollinger_width():
    bb = ind.bollinger(np.full(30, 50.0), 20, 2)
    assert bb.width[-1] == 0
    x = np.r_[np.full(19, 50.0), 60.0]
    bb = ind.bollinger(x, 20, 2)
    assert 60 > bb.upper[-1] > bb.mid[-1] > bb.lower[-1] and bb.width[-1] > 0


def test_adx_strong_trend_and_supertrend_flip():
    closes = np.r_[np.linspace(100, 160, 120), np.linspace(160, 110, 60)]
    c = make_candles(closes, spread=0.003)
    a, pdi, mdi = ind.adx(c.high, c.low, c.close, 14)
    assert a[119] > 40 and pdi[119] > mdi[119]
    assert mdi[-1] > pdi[-1]
    line, d = ind.supertrend(c.high, c.low, c.close, 10, 3.0)
    assert d[119] == 1 and line[119] < closes[119]
    assert d[-1] == -1 and line[-1] > closes[-1]


def test_macd_sign():
    line, sig, hist = ind.macd(np.linspace(10, 50, 100))
    assert line[-1] > 0 and not math.isnan(sig[-1])


def test_cross_helpers():
    a = np.array([1.0, 3.0])
    b = np.array([2.0, 2.0])
    assert ind.crossed_above(a, b) and not ind.crossed_below(a, b)
