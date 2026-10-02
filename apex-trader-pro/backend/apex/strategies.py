"""Strategy entry logic. Every strategy is a pure function of market data -> Signal | None.

Each strategy only sees closed candles (the forming candle is dropped by the data layer).
Short conditions mirror long ones unless stated otherwise.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import indicators as ind
from .bybit import Candles


@dataclass
class Signal:
    strategy: str
    symbol: str
    direction: str  # LONG | SHORT
    entry: float
    sl: float
    tp: float
    atr: float
    order_type: str = "Market"
    adx: float = 0.0
    rsi: float = 50.0
    vol_ratio: float = 1.0
    mtf_aligned: bool = False
    is_addition: bool = False
    size_fraction: float = 1.0  # fraction of the strategy's cost used by this entry
    trailing_mode: str = "distance"  # distance | supertrend
    regime: str | None = None
    score: int = 0
    reversed: bool = False
    original_direction: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def risk(self) -> float:
        return abs(self.entry - self.sl)

    @property
    def reward(self) -> float:
        return abs(self.tp - self.entry)


class Context:
    """Lazily fetches and caches candles per (symbol, timeframe) for one engine run."""

    def __init__(self, exchange, symbol: str, cache: dict | None = None, position: dict | None = None,
                 params: dict | None = None):
        self.exchange = exchange
        self.symbol = symbol
        self.cache = cache if cache is not None else {}
        self.position = position  # open strategy_positions row for this strategy/symbol (scaling strategies)
        self.params = params or {}

    def candles(self, tf: str, limit: int = 300) -> Candles:
        key = (self.symbol, tf)
        if key not in self.cache:
            self.cache[key] = self.exchange.klines(self.symbol, tf, limit)
        return self.cache[key]

    def ticker(self) -> dict:
        key = (self.symbol, "ticker")
        if key not in self.cache:
            self.cache[key] = self.exchange.ticker(self.symbol)
        return self.cache[key]


def _ok(*vals: float) -> bool:
    return all(v is not None and not math.isnan(v) for v in vals)


def _mk(name, ctx, direction, c: Candles, atr_v, sl_m, tp_m, **kw) -> Signal:
    entry = float(c.close[-1])
    sgn = 1 if direction == "LONG" else -1
    return Signal(name, ctx.symbol, direction, entry, entry - sgn * sl_m * atr_v, entry + sgn * tp_m * atr_v,
                  atr_v, **kw)


def _vol(c: Candles) -> tuple[float, float]:
    v = ind.sma(c.volume, 20)[-1]
    return float(c.volume[-1]), float(v)


def _trend_1h(ctx: Context) -> int:
    h = ctx.candles("1h")
    e = ind.ema(h.close, 50)
    if not _ok(e[-1]):
        return 0
    return 1 if h.close[-1] > e[-1] else -1


# ---------------------------------------------------------------------------------------------
def apex_mtf(ctx: Context) -> Signal | None:
    c4, c1, c5 = ctx.candles("4h"), ctx.candles("1h"), ctx.candles("5m")
    st4, _ = ind.supertrend(c4.high, c4.low, c4.close, 10, 2.5)
    e4 = ind.ema(c4.close, 50)
    e1 = ind.ema(c1.close, 50)
    st5, _ = ind.supertrend(c5.high, c5.low, c5.close, 10, 2.5)
    r = ind.rsi(c5.close, 14)
    a, _, _ = ind.adx(c5.high, c5.low, c5.close, 14)
    bb = ind.bollinger(c5.close, 20, 2)
    at = ind.atr(c5.high, c5.low, c5.close, 14)
    vol, vsma = _vol(c5)
    if not _ok(st4[-1], e4[-4], e1[-1], st5[-1], r[-1], a[-2], bb.lower[-3], at[-1], vsma):
        return None
    common = dict(adx=a[-1], rsi=r[-1], vol_ratio=vol / vsma, mtf_aligned=True)
    px4, px1, px5 = c4.close[-1], c1.close[-1], c5.close[-1]
    adx_ok = a[-1] > 22 and a[-1] > a[-2]
    vol_ok = vol > vsma * 1.2
    long_ok = (px4 > st4[-1] and px4 > e4[-1] and e4[-1] > e4[-4] and px1 > e1[-1] and 40 <= r[-1] <= 70
               and px5 > st5[-1] and adx_ok and vol_ok
               and any(c5.low[i] <= bb.lower[i] for i in (-3, -2, -1)) and px5 > bb.lower[-1])
    if long_ok:
        return _mk("apex_mtf", ctx, "LONG", c5, at[-1], 1.5, 3.0, **common)
    short_ok = (px4 < st4[-1] and px4 < e4[-1] and e4[-1] < e4[-4] and px1 < e1[-1] and 30 <= r[-1] <= 60
                and px5 < st5[-1] and adx_ok and vol_ok
                and any(c5.high[i] >= bb.upper[i] for i in (-3, -2, -1)) and px5 < bb.upper[-1])
    if short_ok:
        return _mk("apex_mtf", ctx, "SHORT", c5, at[-1], 1.5, 3.0, **common)
    return None


def wide_atr(ctx: Context) -> Signal | None:
    c5 = ctx.candles("5m")
    trend = _trend_1h(ctx)
    r = ind.rsi(c5.close, 14)
    line, sig, _ = ind.macd(c5.close)
    e21 = ind.ema(c5.close, 21)
    at = ind.atr(c5.high, c5.low, c5.close, 14)
    a, _, _ = ind.adx(c5.high, c5.low, c5.close, 14)
    vol, vsma = _vol(c5)
    if not _ok(r[-1], line[-1], sig[-1], e21[-1], at[-1], vsma) or trend == 0:
        return None
    px = c5.close[-1]
    common = dict(adx=float(a[-1]) if _ok(a[-1]) else 0.0, rsi=r[-1], vol_ratio=vol / vsma, mtf_aligned=True)
    if trend > 0 and r[-1] > 45 and line[-1] > sig[-1] and px > e21[-1] and vol > vsma:
        return _mk("wide_atr", ctx, "LONG", c5, at[-1], 2.0, 4.0, **common)
    if trend < 0 and r[-1] < 55 and line[-1] < sig[-1] and px < e21[-1] and vol > vsma:
        return _mk("wide_atr", ctx, "SHORT", c5, at[-1], 2.0, 4.0, **common)
    return None


def momentum_breakout(ctx: Context) -> Signal | None:
    c = ctx.candles("15m")
    e9, e21 = ind.ema(c.close, 9), ind.ema(c.close, 21)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    at = ind.atr(c.high, c.low, c.close, 14)
    r = ind.rsi(c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(e9[-2], e21[-2], a[-1], at[-1], vsma):
        return None
    px = c.close[-1]
    if a[-1] <= 15 or vol <= vsma or at[-1] <= 0.004 * px:
        return None
    common = dict(adx=a[-1], rsi=float(r[-1]), vol_ratio=vol / vsma, mtf_aligned=_trend_1h(ctx) != 0)
    if ind.crossed_above(e9, e21) and px > c.high[-2]:
        common["mtf_aligned"] = _trend_1h(ctx) > 0
        return _mk("momentum_breakout", ctx, "LONG", c, at[-1], 1.8, 3.5, **common)
    if ind.crossed_below(e9, e21) and px < c.low[-2]:
        common["mtf_aligned"] = _trend_1h(ctx) < 0
        return _mk("momentum_breakout", ctx, "SHORT", c, at[-1], 1.8, 3.5, **common)
    return None


def trend_rider(ctx: Context) -> Signal | None:
    c = ctx.candles("1h")
    _, d = ind.supertrend(c.high, c.low, c.close, 10, 3.0)
    e200 = ind.ema(c.close, 200)
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    r = ind.rsi(c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(e200[-1], at[-1], vsma) or d[-2] == 0:
        return None
    px = c.close[-1]
    if vol <= vsma or at[-1] <= 0.005 * px:
        return None
    common = dict(adx=float(a[-1]), rsi=float(r[-1]), vol_ratio=vol / vsma, mtf_aligned=True,
                  trailing_mode="supertrend")
    if d[-2] == -1 and d[-1] == 1 and px > e200[-1]:
        return _mk("trend_rider", ctx, "LONG", c, at[-1], 2.0, 4.0, **common)
    if d[-2] == 1 and d[-1] == -1 and px < e200[-1]:
        return _mk("trend_rider", ctx, "SHORT", c, at[-1], 2.0, 4.0, **common)
    return None


def _divergence(c: Candles, r: np.ndarray, bullish: bool, recent: int = 5, lookback: int = 30) -> bool:
    """Bullish: price lower low but RSI higher low between the last `recent` bars and the window before."""
    if len(c) < lookback + 2:
        return False
    series = c.low if bullish else c.high
    win_prev = slice(-lookback, -recent)
    win_rec = slice(-recent, None)
    pick = np.argmin if bullish else np.argmax
    i_prev = len(c) - lookback + int(pick(series[win_prev]))
    i_rec = len(c) - recent + int(pick(series[win_rec]))
    if not _ok(r[i_prev], r[i_rec]):
        return False
    if bullish:
        return series[i_rec] < series[i_prev] and r[i_rec] > r[i_prev]
    return series[i_rec] > series[i_prev] and r[i_rec] < r[i_prev]


def rsi_divergence(ctx: Context) -> Signal | None:
    c = ctx.candles("15m")
    r = ind.rsi(c.close, 14)
    e50 = ind.ema(c.close, 50)
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(r[-1], e50[-4], at[-1], vsma) or vol <= vsma:
        return None
    common = dict(adx=float(a[-1]), rsi=r[-1], vol_ratio=vol / vsma)
    if r[-1] < 40 and e50[-1] > e50[-4] and _divergence(c, r, True):
        common["mtf_aligned"] = _trend_1h(ctx) > 0
        return _mk("rsi_divergence", ctx, "LONG", c, at[-1], 1.5, 3.0, **common)
    if r[-1] > 60 and e50[-1] < e50[-4] and _divergence(c, r, False):
        common["mtf_aligned"] = _trend_1h(ctx) < 0
        return _mk("rsi_divergence", ctx, "SHORT", c, at[-1], 1.5, 3.0, **common)
    return None


def silver_scalper(ctx: Context) -> Signal | None:
    c = ctx.candles("5m")
    r = ind.rsi(c.close, 14)
    line, sig, _ = ind.macd(c.close)
    e21 = ind.ema(c.close, 21)
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(r[-1], line[-1], sig[-1], e21[-1], at[-1], vsma):
        return None
    px = c.close[-1]
    if vol <= vsma or at[-1] <= 0.003 * px:
        return None
    t = ctx.ticker()
    mid = (t["bid"] + t["ask"]) / 2
    if not mid or (t["ask"] - t["bid"]) / mid >= 0.0008:
        return None
    common = dict(adx=float(a[-1]), rsi=r[-1], vol_ratio=vol / vsma)
    if px > e21[-1] and 40 <= r[-1] <= 65 and line[-1] > sig[-1]:
        common["mtf_aligned"] = _trend_1h(ctx) > 0
        return _mk("silver_scalper", ctx, "LONG", c, at[-1], 2.0, 3.5, **common)
    if px < e21[-1] and 35 <= r[-1] <= 60 and line[-1] < sig[-1]:
        common["mtf_aligned"] = _trend_1h(ctx) < 0
        return _mk("silver_scalper", ctx, "SHORT", c, at[-1], 2.0, 3.5, **common)
    return None


def dynamic_order_flow(ctx: Context) -> Signal | None:
    c = ctx.candles("15m")
    bb = ind.bollinger(c.close, 20, 3.0)
    r7 = ind.rsi(c.close, 7)
    e200 = ind.ema(c.close, 200)
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(bb.lower[-1], r7[-1], e200[-1], at[-1]):
        return None
    px = c.close[-1]
    common = dict(adx=float(a[-1]), rsi=r7[-1], vol_ratio=(vol / vsma) if _ok(vsma) and vsma else 1.0,
                  order_type="Limit")
    if c.low[-1] <= bb.lower[-1] and r7[-1] < 35 and px > e200[-1]:
        return _mk("dynamic_order_flow", ctx, "LONG", c, at[-1], 1.0, 3.0, mtf_aligned=_trend_1h(ctx) > 0, **common)
    if c.high[-1] >= bb.upper[-1] and r7[-1] > 65 and px < e200[-1]:
        return _mk("dynamic_order_flow", ctx, "SHORT", c, at[-1], 1.0, 3.0, mtf_aligned=_trend_1h(ctx) < 0, **common)
    return None


def squeeze_hunter(ctx: Context) -> Signal | None:
    c = ctx.candles("15m")
    bb = ind.bollinger(c.close, 20, 2.0)
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    r = ind.rsi(c.close, 14)
    vol, vsma = _vol(c)
    if not _ok(bb.width[-2], at[-1], a[-2], r[-1], vsma):
        return None
    major = ctx.symbol.startswith(("BTC", "ETH"))
    squeeze = bb.width[-2] < (0.03 if major else 0.045)
    rng = c.high - c.low
    wide_candle = rng[-1] > rng[-11:-1].mean()
    if not (squeeze and wide_candle and a[-1] > 20 and a[-1] > a[-2] and vol > 1.5 * vsma):
        return None
    common = dict(adx=a[-1], rsi=r[-1], vol_ratio=vol / vsma)
    px = c.close[-1]
    if px > bb.upper[-1] and 55 <= r[-1] <= 75:
        return _mk("squeeze_hunter", ctx, "LONG", c, at[-1], 1.5, 3.0, mtf_aligned=_trend_1h(ctx) > 0, **common)
    if px < bb.lower[-1] and 25 <= r[-1] <= 45:
        return _mk("squeeze_hunter", ctx, "SHORT", c, at[-1], 1.5, 3.0, mtf_aligned=_trend_1h(ctx) < 0, **common)
    return None


def capitulation_absorber(ctx: Context) -> Signal | None:
    """4-part scale-in. Entry 1 on capitulation, entries 2-4 as additions to the open strategy position."""
    h = ctx.candles("1h")
    at_h = ind.atr(h.high, h.low, h.close, 14)
    if not _ok(at_h[-1]):
        return None
    atr_v = float(at_h[-1])
    px = float(h.close[-1])
    pos = ctx.position
    if pos:
        px = float(ctx.ticker()["last"])  # scale-in reacts to the live price, not the last closed hour
        n = int(pos["addition_count"])
        if n >= 4:
            return None
        direction = pos["direction"]
        sgn = 1 if direction == "LONG" else -1
        last_px = float(pos["last_entry_price"])
        pos_atr = float(pos.get("atr") or atr_v)
        trigger = False
        if n == 1:
            trigger = sgn * (last_px - px) >= 2 * pos_atr
        elif n == 2:
            trigger = sgn * (last_px - px) >= 3 * pos_atr
        elif n == 3:
            c15 = ctx.candles("15m")
            trigger = _divergence(c15, ind.rsi(c15.close, 14), bullish=direction == "LONG")
        if not trigger:
            return None
        # TP/SL are recalculated by the engine from the new average entry
        return Signal("capitulation_absorber", ctx.symbol, direction, px, px - sgn * 3 * pos_atr,
                      px + sgn * 2.5 * pos_atr, pos_atr, is_addition=True, size_fraction=0.25,
                      rsi=50.0, adx=0.0, mtf_aligned=True, meta={"entry_no": n + 1})
    bb = ind.bollinger(h.close, 20, 2)
    r = ind.rsi(h.close, 14)
    a, _, _ = ind.adx(h.high, h.low, h.close, 14)
    vol, vsma = _vol(h)
    if not _ok(bb.lower[-1], r[-1]) or atr_v <= 0.02 * px:
        return None
    common = dict(adx=float(a[-1]), rsi=r[-1], vol_ratio=(vol / vsma) if _ok(vsma) and vsma else 1.0,
                  size_fraction=0.25, mtf_aligned=True, meta={"entry_no": 1})
    if px < bb.lower[-1] and r[-1] < 25:
        return Signal("capitulation_absorber", ctx.symbol, "LONG", px, px - 3 * atr_v, px + 2.5 * atr_v, atr_v,
                      **common)
    if px > bb.upper[-1] and r[-1] > 75:
        return Signal("capitulation_absorber", ctx.symbol, "SHORT", px, px + 3 * atr_v, px - 2.5 * atr_v, atr_v,
                      **common)
    return None


def nexus_regime(h: Candles) -> str:
    a, _, _ = ind.adx(h.high, h.low, h.close, 14)
    w = ind.bollinger(h.close, 20, 2).width
    if not _ok(a[-1], w[-1]):
        return "QUIET_RANGE"
    if a[-1] > 25 and w[-1] > 0.02:
        return "STRONG_TREND"
    if 20 <= a[-1] <= 25:
        return "WEAK_TREND"
    if a[-1] < 20 and w[-1] > 0.03:
        return "VOLATILE_RANGE"
    return "QUIET_RANGE"


def nexus_signal_at(c: Candles, regime: str, p: dict, i: int = -1) -> str | None:
    """Direction for Adaptive Nexus at bar i (shared by live trading and the weekly backtest)."""
    ef, es = ind.ema(c.close, int(p["ema_fast"])), ind.ema(c.close, int(p["ema_slow"]))
    r = ind.rsi(c.close, 14)
    if not _ok(ef[i], es[i], r[i], ef[i - 1]):
        return None
    px = c.close[i]
    if regime == "STRONG_TREND":
        # pullback to the fast EMA in the trend direction
        if ef[i] > es[i] and c.low[i] <= ef[i] < px and p["rsi_low"] + 10 <= r[i] <= p["rsi_high"]:
            return "LONG"
        if ef[i] < es[i] and c.high[i] >= ef[i] > px and 100 - p["rsi_high"] <= r[i] <= 90 - p["rsi_low"]:
            return "SHORT"
    elif regime == "WEAK_TREND":
        e9, e21 = ind.ema(c.close, 9), ind.ema(c.close, 21)
        if _ok(e9[i - 1], e21[i - 1]):
            if e9[i - 1] <= e21[i - 1] and e9[i] > e21[i] and r[i] > 50:
                return "LONG"
            if e9[i - 1] >= e21[i - 1] and e9[i] < e21[i] and r[i] < 50:
                return "SHORT"
    elif regime == "VOLATILE_RANGE":
        bb = ind.bollinger(c.close, 20, 2)
        if _ok(bb.lower[i]):
            if c.low[i] <= bb.lower[i] and px > bb.lower[i] and r[i] < p["rsi_low"]:
                return "LONG"
            if c.high[i] >= bb.upper[i] and px < bb.upper[i] and r[i] > p["rsi_high"]:
                return "SHORT"
    return None  # QUIET_RANGE: stand aside


def adaptive_nexus(ctx: Context) -> Signal | None:
    p = {"sl_mult": 1.5, "tp_mult": 3.0, "rsi_low": 35, "rsi_high": 65, "ema_fast": 20, "ema_slow": 50}
    p.update(ctx.params or {})
    regime = nexus_regime(ctx.candles("1h"))
    c = ctx.candles("15m")
    d = nexus_signal_at(c, regime, p)
    if not d:
        return None
    at = ind.atr(c.high, c.low, c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    r = ind.rsi(c.close, 14)
    vol, vsma = _vol(c)
    sig = _mk("adaptive_nexus", ctx, d, c, at[-1], float(p["sl_mult"]), float(p["tp_mult"]), adx=float(a[-1]),
              rsi=float(r[-1]), vol_ratio=(vol / vsma) if _ok(vsma) and vsma else 1.0,
              mtf_aligned=_trend_1h(ctx) == (1 if d == "LONG" else -1), meta={"nexus_regime": regime})
    return sig


# --- generic evaluator for AI-parsed custom strategies ------------------------------------------
def _series(c: Candles, spec) -> np.ndarray:
    if isinstance(spec, (int, float)):
        return np.full(len(c), float(spec))
    name = spec.get("ind", spec.get("indicator", "close")).lower()
    n = int(spec.get("period", 14))
    if name in ("close", "open", "high", "low", "volume"):
        return getattr(c, name)
    if name == "ema":
        return ind.ema(c.close, n)
    if name == "sma":
        return ind.sma(c.close, n)
    if name == "rsi":
        return ind.rsi(c.close, n)
    if name == "atr":
        return ind.atr(c.high, c.low, c.close, n)
    if name == "atr_pct":
        return ind.atr(c.high, c.low, c.close, n) / c.close * 100
    if name == "adx":
        return ind.adx(c.high, c.low, c.close, n)[0]
    if name == "volume_sma":
        return ind.sma(c.volume, n)
    if name in ("bb_upper", "bb_lower", "bb_mid", "bb_width"):
        b = ind.bollinger(c.close, n, float(spec.get("mult", 2.0)))
        return {"bb_upper": b.upper, "bb_lower": b.lower, "bb_mid": b.mid, "bb_width": b.width * 100}[name]
    if name in ("macd", "macd_signal", "macd_hist"):
        line, sig, hist = ind.macd(c.close)
        return {"macd": line, "macd_signal": sig, "macd_hist": hist}[name]
    if name in ("supertrend", "supertrend_dir"):
        line, d = ind.supertrend(c.high, c.low, c.close, n if "period" in spec else 10, float(spec.get("mult", 3.0)))
        return line if name == "supertrend" else d
    raise ValueError(f"unknown indicator {name}")


def eval_condition(ctx: Context, cond: dict, default_tf: str) -> bool:
    c = ctx.candles(cond.get("timeframe", default_tf))
    left = _series(c, cond.get("left", cond))
    right = _series(c, cond.get("right", cond.get("value", 0)))
    right = right * float(cond.get("factor", 1.0))
    op = cond.get("op", ">")
    if not _ok(left[-1], right[-1]):
        return False
    if op == "crosses_above":
        return ind.crossed_above(left, right)
    if op == "crosses_below":
        return ind.crossed_below(left, right)
    if op == "rising":
        return bool(left[-1] > left[-2])
    if op == "falling":
        return bool(left[-1] < left[-2])
    if op == "between":
        lo, hi = cond["range"]
        return lo <= left[-1] <= hi
    return {">": left[-1] > right[-1], "<": left[-1] < right[-1], ">=": left[-1] >= right[-1],
            "<=": left[-1] <= right[-1]}[op]


def custom(ctx: Context) -> Signal | None:
    d = ctx.params or {}
    if not d:
        return None
    tf = d.get("timeframe", "15m")
    c = ctx.candles(tf)
    at = ind.atr(c.high, c.low, c.close, 14)
    if not _ok(at[-1]):
        return None
    scaling = d.get("scaling") or {}
    if ctx.position:
        entries = int(scaling.get("entries", 1))
        if int(ctx.position["addition_count"]) >= entries:
            return None
        direction = ctx.position["direction"]
        sgn = 1 if direction == "LONG" else -1
        step = float(scaling.get("step_atr", 2.0)) * float(ctx.position.get("atr") or at[-1])
        px = float(ctx.ticker()["last"])
        if sgn * (float(ctx.position["last_entry_price"]) - px) < step:
            return None
        return _mk("custom", ctx, direction, c, float(ctx.position.get("atr") or at[-1]),
                   float(d.get("sl_atr", 1.5)), float(d.get("tp_atr", 3.0)), is_addition=True,
                   size_fraction=1.0 / entries, mtf_aligned=True)
    sides = d.get("direction", "both")
    r = ind.rsi(c.close, 14)
    a, _, _ = ind.adx(c.high, c.low, c.close, 14)
    vol, vsma = _vol(c)
    entries = int(scaling.get("entries", 1)) if scaling else 1
    for direction in ("LONG", "SHORT"):
        if sides not in ("both", direction.lower()):
            continue
        conds = (d.get("conditions") or {}).get(direction.lower()) or []
        if conds and all(eval_condition(ctx, cond, tf) for cond in conds):
            return _mk("custom", ctx, direction, c, float(at[-1]), float(d.get("sl_atr", 1.5)),
                       float(d.get("tp_atr", 3.0)), order_type="Limit" if d.get("order_type") == "limit" else "Market",
                       adx=float(a[-1]), rsi=float(r[-1]),
                       vol_ratio=(vol / vsma) if _ok(vsma) and vsma else 1.0,
                       mtf_aligned=bool(d.get("confirm_timeframe")), size_fraction=1.0 / entries)
    return None


REGISTRY: dict[str, Callable[[Context], Signal | None]] = {
    "apex_mtf": apex_mtf, "wide_atr": wide_atr, "momentum_breakout": momentum_breakout,
    "trend_rider": trend_rider, "rsi_divergence": rsi_divergence, "silver_scalper": silver_scalper,
    "dynamic_order_flow": dynamic_order_flow, "squeeze_hunter": squeeze_hunter,
    "capitulation_absorber": capitulation_absorber, "adaptive_nexus": adaptive_nexus, "custom": custom,
}

SCALING_STRATEGIES = {"capitulation_absorber", "custom"}


def load_params(name: str, raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
