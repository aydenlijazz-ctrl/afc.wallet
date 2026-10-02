"""Technical indicators on numpy arrays (oldest -> newest). Warm-up values are NaN."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

NAN = float("nan")


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def sma(x, n: int) -> np.ndarray:
    x = _arr(x)
    out = np.full(len(x), NAN)
    if len(x) >= n:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema(x, n: int) -> np.ndarray:
    """EMA seeded with the SMA of the first n values."""
    x = _arr(x)
    out = np.full(len(x), NAN)
    if len(x) < n:
        return out
    k = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def rma(x, n: int) -> np.ndarray:
    """Wilder's moving average (used by RSI, ATR, ADX). NaNs at the start are skipped."""
    x = _arr(x)
    out = np.full(len(x), NAN)
    valid = np.where(~np.isnan(x))[0]
    if len(valid) < n:
        return out
    start = valid[0]
    out[start + n - 1] = x[start:start + n].mean()
    for i in range(start + n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def rsi(close, n: int = 14) -> np.ndarray:
    c = _arr(close)
    d = np.diff(c, prepend=NAN)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    gain[0] = loss[0] = NAN
    ag, al = rma(gain, n), rma(loss, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = ag / al
        out = 100 - 100 / (1 + rs)
    out = np.where((al == 0) & (ag > 0), 100.0, out)
    out = np.where((al == 0) & (ag == 0), 50.0, out)
    out[np.isnan(ag)] = NAN
    return out


def true_range(high, low, close) -> np.ndarray:
    h, l, c = _arr(high), _arr(low), _arr(close)
    pc = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def atr(high, low, close, n: int = 14) -> np.ndarray:
    return rma(true_range(high, low, close), n)


def adx(high, low, close, n: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (adx, +DI, -DI)."""
    h, l = _arr(high), _arr(low)
    up = np.diff(h, prepend=NAN)
    dn = -np.diff(l, prepend=NAN)
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(high, low, close)
    plus_dm[0] = minus_dm[0] = tr[0] = NAN
    atr_ = rma(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * rma(plus_dm, n) / atr_
        mdi = 100 * rma(minus_dm, n) / atr_
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.where((pdi + mdi) == 0, 0.0, dx)
    return rma(dx, n), pdi, mdi


@dataclass
class Bands:
    mid: np.ndarray
    upper: np.ndarray
    lower: np.ndarray

    @property
    def width(self) -> np.ndarray:
        """(upper - lower) / mid, as a fraction (0.03 == 3%)."""
        with np.errstate(divide="ignore", invalid="ignore"):
            return (self.upper - self.lower) / self.mid


def bollinger(close, n: int = 20, k: float = 2.0) -> Bands:
    c = _arr(close)
    mid = sma(c, n)
    sd = np.full(len(c), NAN)
    if len(c) >= n:
        sd[n - 1:] = np.lib.stride_tricks.sliding_window_view(c, n).std(axis=1)  # population std, as TradingView
    return Bands(mid, mid + k * sd, mid - k * sd)


def macd(close, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    line = ema(close, fast) - ema(close, slow)
    sig = np.full(len(line), NAN)
    valid = ~np.isnan(line)
    if valid.sum() >= signal:
        first = int(np.argmax(valid))
        sig[first:] = ema(line[first:], signal)
    return line, sig, line - sig


def supertrend(high, low, close, n: int = 10, mult: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Returns (line, direction) where direction is +1 (green/up) or -1 (red/down)."""
    h, l, c = _arr(high), _arr(low), _arr(close)
    a = atr(h, l, c, n)
    hl2 = (h + l) / 2
    upper_basic, lower_basic = hl2 + mult * a, hl2 - mult * a
    upper, lower = upper_basic.copy(), lower_basic.copy()
    line = np.full(len(c), NAN)
    direction = np.zeros(len(c))
    start = int(np.argmax(~np.isnan(a))) if (~np.isnan(a)).any() else len(c)
    for i in range(start, len(c)):
        if i > start:
            upper[i] = upper_basic[i] if (upper_basic[i] < upper[i - 1] or c[i - 1] > upper[i - 1]) else upper[i - 1]
            lower[i] = lower_basic[i] if (lower_basic[i] > lower[i - 1] or c[i - 1] < lower[i - 1]) else lower[i - 1]
            prev = direction[i - 1]
            if prev == -1:
                direction[i] = 1 if c[i] > upper[i] else -1
            else:
                direction[i] = -1 if c[i] < lower[i] else 1
        else:
            direction[i] = 1 if c[i] >= hl2[i] else -1
        line[i] = lower[i] if direction[i] == 1 else upper[i]
    return line, direction


def crossed_above(a: np.ndarray, b: np.ndarray, i: int = -1) -> bool:
    return bool(a[i - 1] <= b[i - 1] and a[i] > b[i])


def crossed_below(a: np.ndarray, b: np.ndarray, i: int = -1) -> bool:
    return bool(a[i - 1] >= b[i - 1] and a[i] < b[i])


def last(x: np.ndarray, i: int = -1) -> float:
    return float(x[i])
