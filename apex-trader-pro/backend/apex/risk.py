"""Signal filters, reverse mode, quality score, cost model and trailing-stop math."""
from __future__ import annotations

import math

from . import indicators as ind
from .bybit import Candles
from .strategies import Signal

TIER1 = {"BTC", "ETH"}
TIER2 = {"SOL", "BNB", "XRP", "AVAX", "LINK", "DOT"}
TIER_CAPS = {1: 2, 2: 3, 3: 2}


# --- reverse mode -------------------------------------------------------------------------------
def apply_reverse(sig: Signal) -> Signal:
    """Invert the direction. The original reward becomes the new risk; the new reward is
    max(original_risk, 1.2 * original_reward)."""
    risk, reward = sig.risk, sig.reward
    new_reward = max(risk, 1.2 * reward)
    sig.original_direction = sig.direction
    sig.reversed = True
    if sig.direction == "LONG":  # inverted to SHORT
        sig.direction = "SHORT"
        sig.sl = sig.entry + reward
        sig.tp = sig.entry - new_reward
    else:  # inverted to LONG
        sig.direction = "LONG"
        sig.sl = sig.entry - reward
        sig.tp = sig.entry + new_reward
    return sig


# --- signal quality score -----------------------------------------------------------------------
def quality_score(sig: Signal) -> int:
    score = 0
    if sig.adx > 35:
        score += 30
    elif sig.adx > 25:
        score += 20
    rsi = sig.rsi
    if (sig.direction == "LONG" and 25 <= rsi <= 35) or (sig.direction == "SHORT" and 65 <= rsi <= 75):
        score += 25
    elif 40 <= rsi <= 60:
        score += 15
    if sig.vol_ratio > 1.5:
        score += 25
    elif sig.vol_ratio > 1.2:
        score += 15
    if sig.mtf_aligned:
        score += 20
    if sig.reward > 2 * sig.risk:
        score += 15
    return min(score, 100)


# --- regime filter ------------------------------------------------------------------------------
def market_regime(h1: Candles) -> str:
    a, _, _ = ind.adx(h1.high, h1.low, h1.close, 14)
    at = ind.atr(h1.high, h1.low, h1.close, 14)
    if math.isnan(a[-1]) or math.isnan(at[-1]):
        return "UNKNOWN"
    if at[-1] / h1.close[-1] < 0.003:
        return "LOW_VOL"
    if a[-1] > 25:
        return "TRENDING"
    if a[-1] >= 20:
        return "TRANSITIONAL"
    return "RANGING"


def regime_allows(regime: str, allowed: list[str], score: int, transitional_min_score: int) -> tuple[bool, str]:
    if regime == "LOW_VOL":
        return False, "low volatility (ATR < 0.3%)"
    if regime == "UNKNOWN":
        return False, "not enough 1h history for regime"
    if regime not in allowed:
        return False, f"regime {regime} not in {','.join(allowed)}"
    if regime == "TRANSITIONAL" and score < transitional_min_score:
        return False, f"transitional regime requires score >= {transitional_min_score}"
    return True, ""


# --- correlation filter -------------------------------------------------------------------------
def base_asset(symbol: str) -> str:
    for quote in ("USDT", "USDC", "PERP", "USD"):
        if symbol.endswith(quote):
            return symbol[: -len(quote)]
    return symbol


def tier(symbol: str) -> int:
    b = base_asset(symbol)
    if b in TIER1:
        return 1
    if b in TIER2:
        return 2
    return 3


def correlation_allows(symbol: str, open_symbols: list[str]) -> bool:
    """open_symbols: one entry per open position (including those accepted earlier in this run)."""
    t = tier(symbol)
    return sum(1 for s in open_symbols if tier(s) == t) + 1 <= TIER_CAPS[t]


# --- cost model ---------------------------------------------------------------------------------
def gross_pnl(direction: str, entry: float, exit_: float, qty: float) -> float:
    return (exit_ - entry) * qty if direction == "LONG" else (entry - exit_) * qty


def net_pnl(direction: str, entry: float, exit_: float, qty: float, fees_bps: float = 5,
            slippage_bps: float = 5) -> float:
    cost = (fees_bps + slippage_bps) / 10000
    return gross_pnl(direction, entry, exit_, qty) - entry * qty * cost - exit_ * qty * cost


# --- trailing stop ------------------------------------------------------------------------------
def trail_level(direction: str, mark: float, distance: float, current: float | None) -> float:
    """Trailing stop follows price and never widens."""
    if direction == "LONG":
        lvl = mark - distance
        return lvl if current is None else max(current, lvl)
    lvl = mark + distance
    return lvl if current is None else min(current, lvl)


def stop_hit(direction: str, mark: float, level: float) -> bool:
    return mark <= level if direction == "LONG" else mark >= level


def partial_target(direction: str, entry: float, tp: float, fraction: float = 0.5) -> float:
    return entry + (tp - entry) * fraction


def reached(direction: str, mark: float, level: float) -> bool:
    return mark >= level if direction == "LONG" else mark <= level
