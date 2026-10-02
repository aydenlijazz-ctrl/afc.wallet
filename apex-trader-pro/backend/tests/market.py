"""Synthetic multi-timeframe market with trend, chop, squeeze and crash phases."""
from __future__ import annotations

import numpy as np

from apex.bybit import Candles

TF_MIN = {"5m": 5, "15m": 15, "1h": 60, "4h": 240}


def synth_5m(n: int = 60_000, seed: int = 7, start: float = 100.0) -> Candles:
    rng = np.random.default_rng(seed)
    rets = np.empty(n)
    vols = np.empty(n)
    i = 0
    while i < n:
        phase = rng.choice(["up", "down", "chop", "squeeze", "crash", "pump"], p=[.25, .25, .2, .15, .075, .075])
        length = int(rng.integers(200, 1500))
        drift = {"up": 4e-4, "down": -4e-4, "chop": 0, "squeeze": 0, "crash": -2.5e-3, "pump": 2.5e-3}[phase]
        sigma = {"up": 2.5e-3, "down": 2.5e-3, "chop": 3e-3, "squeeze": 6e-4, "crash": 6e-3, "pump": 6e-3}[phase]
        if phase in ("crash", "pump"):
            length = int(rng.integers(60, 200))
        j = min(n, i + length)
        rets[i:j] = drift + rng.normal(0, sigma, j - i)
        vols[i:j] = rng.lognormal(4.6, 0.5, j - i) * (3 if phase in ("crash", "pump") else 1)
        i = j
    close = start * np.exp(np.cumsum(rets))
    open_ = np.r_[start, close[:-1]]
    wick = np.abs(rng.normal(0, 1.2e-3, n)) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 1.2e-3, n)) * close
    ts = 1_700_000_000_000 + np.arange(n) * 300_000.0
    return Candles(ts, open_, high, low, close, vols)


def resample(c: Candles, k: int) -> Candles:
    n = len(c) // k * k
    sl = lambda a: a[:n].reshape(-1, k)  # noqa: E731
    return Candles(sl(c.ts)[:, 0], sl(c.open)[:, 0], sl(c.high).max(1), sl(c.low).min(1), sl(c.close)[:, -1],
                   sl(c.volume).sum(1))


class Market:
    def __init__(self, base: Candles):
        self.tf = {"5m": base, "15m": resample(base, 3), "1h": resample(base, 12), "4h": resample(base, 48)}

    def upto(self, tf: str, t_end: float, limit: int) -> Candles:
        c = self.tf[tf]
        # a candle is closed when its open time + duration <= t_end
        idx = int(np.searchsorted(c.ts, t_end - TF_MIN[tf] * 60_000, side="right"))
        lo = max(0, idx - limit)
        return Candles(*(getattr(c, f)[lo:idx] for f in ("ts", "open", "high", "low", "close", "volume")))


class MarketExchange:
    """Read-only exchange view of a synthetic market at time `now`."""

    def __init__(self, market: Market, now: float, spread_pct: float = 0.0003):
        self.m, self.now, self.spread = market, now, spread_pct

    def klines(self, symbol, tf, limit=300, end_ms=None, closed_only=True):
        return self.m.upto(tf, self.now, limit)

    def ticker(self, symbol):
        p = float(self.m.upto("5m", self.now, 1).close[-1])
        return {"symbol": symbol, "last": p, "mark": p, "bid": p * (1 - self.spread / 2), "ask": p * (1 + self.spread / 2)}
