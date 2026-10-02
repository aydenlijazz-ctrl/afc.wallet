"""bot_settings access with typed getters and per-strategy defaults."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import db

STRATEGIES = [
    "apex_mtf", "wide_atr", "momentum_breakout", "trend_rider", "rsi_divergence", "silver_scalper",
    "dynamic_order_flow", "squeeze_hunter", "capitulation_absorber", "adaptive_nexus", "custom",
]

STRATEGY_LABELS = {
    "apex_mtf": "Apex MTF", "wide_atr": "Wide ATR", "momentum_breakout": "Momentum Breakout",
    "trend_rider": "Trend Rider", "rsi_divergence": "RSI Divergence", "silver_scalper": "Silver Scalper",
    "dynamic_order_flow": "Dynamic Order Flow", "squeeze_hunter": "Squeeze Hunter",
    "capitulation_absorber": "Capitulation Cascade Absorber", "adaptive_nexus": "Adaptive Nexus",
    "custom": "Custom Strategy",
}

# trend strategies run in TRENDING/TRANSITIONAL regimes, mean-reversion ones in RANGING/TRANSITIONAL
STRATEGY_KIND = {
    "apex_mtf": "trend", "wide_atr": "trend", "momentum_breakout": "trend", "trend_rider": "trend",
    "squeeze_hunter": "trend", "silver_scalper": "any", "rsi_divergence": "range",
    "dynamic_order_flow": "range", "capitulation_absorber": "range", "adaptive_nexus": "any", "custom": "any",
}

DEFAULT_ALLOWED_REGIMES = {
    "trend": "TRENDING,TRANSITIONAL",
    "range": "RANGING,TRANSITIONAL",
    "any": "TRENDING,TRANSITIONAL,RANGING",
}

GLOBAL_DEFAULTS = {
    "live_trading_armed": "false",  # kill switch: signals are only logged until armed
    "min_signal_score": "60",
    "transitional_min_score": "75",
    "fees_bps": "5",
    "slippage_bps": "5",
    "one_position_per_symbol": "true",
    "limit_order_ttl_minutes": "45",
    "bot_started_at": "",
    "strategy_order": ",".join(STRATEGIES),
}


def strategy_defaults(name: str) -> dict[str, str]:
    kind = STRATEGY_KIND[name]
    d = {
        "enabled": "false",
        "symbols": "XAGUSDT" if name == "silver_scalper" else "BTCUSDT,ETHUSDT,SOLUSDT",
        "cost": "20",
        "leverage": "5",
        "reverse_enabled": "false",
        "trailing_enabled": "true" if name == "trend_rider" else "false",
        "trail_distance": "1.5" if name in ("momentum_breakout", "trend_rider", "capitulation_absorber") else "1.8",
        "partial_tp_enabled": "true" if name == "capitulation_absorber" else "false",
        "partial_tp_percent": "50",
        "adaptive_auto_reverse_enabled": "false",
        "adaptive_auto_reverse_threshold": "50",
        "adaptive_auto_reverse_include_unrealized": "true",
        "last_reverse_switch": "",
        "auto_reverse_enabled": "false",
        "auto_reverse_daily_threshold": "30",
        "allowed_regimes": DEFAULT_ALLOWED_REGIMES[kind],
        "active_hours": "",  # e.g. "6-22" UTC; empty = always
        "priority": str(STRATEGIES.index(name) + 1),
    }
    if name == "adaptive_nexus":
        d["params"] = json.dumps({"sl_mult": 1.5, "tp_mult": 3.0, "rsi_low": 35, "rsi_high": 65, "ema_fast": 20,
                                  "ema_slow": 50})
    if name == "custom":
        d["definition"] = ""
    return d


class Settings:
    """Snapshot of a user's settings with defaults applied."""

    def __init__(self, user_id, values: dict[str, str | None] | None = None):
        self.user_id = user_id
        self.values = values if values is not None else load(user_id)

    def get(self, key: str, default: str | None = None) -> str | None:
        if key in self.values and self.values[key] is not None:
            return self.values[key]
        if key in GLOBAL_DEFAULTS:
            return GLOBAL_DEFAULTS[key]
        if key.startswith("strat_"):
            for name in sorted(STRATEGIES, key=len, reverse=True):
                prefix = f"strat_{name}_"
                if key.startswith(prefix):
                    return strategy_defaults(name).get(key[len(prefix):], default)
        return default

    def flag(self, key: str) -> bool:
        return (self.get(key) or "").lower() == "true"

    def num(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key) or default)
        except ValueError:
            return default

    def s(self, name: str, field: str) -> str | None:
        return self.get(f"strat_{name}_{field}")

    def sflag(self, name: str, field: str) -> bool:
        return self.flag(f"strat_{name}_{field}")

    def snum(self, name: str, field: str, default: float = 0.0) -> float:
        return self.num(f"strat_{name}_{field}", default)

    def symbols(self, name: str) -> list[str]:
        return [x.strip().upper() for x in (self.s(name, "symbols") or "").split(",") if x.strip()]

    def enabled_strategies(self) -> list[str]:
        order = [s for s in (self.get("strategy_order") or "").split(",") if s in STRATEGIES]
        order += [s for s in STRATEGIES if s not in order]
        return [s for s in order if self.sflag(s, "enabled")]

    def set(self, key: str, value: str) -> None:
        save(self.user_id, {key: value})
        self.values[key] = value

    def in_active_hours(self, name: str, now: datetime | None = None) -> bool:
        spec = (self.s(name, "active_hours") or "").strip()
        if not spec:
            return True
        hour = (now or datetime.now(timezone.utc)).hour
        for part in spec.split(","):
            a, _, b = part.partition("-")
            try:
                start, end = int(a), int(b or a)
            except ValueError:
                continue
            if (start <= hour <= end) if start <= end else (hour >= start or hour <= end):
                return True
        return False


def load(user_id) -> dict[str, str | None]:
    return {r["key"]: r["value"] for r in db.fetch("SELECT key, value FROM bot_settings WHERE user_id = %s", (user_id,))}


def save(user_id, values: dict[str, object]) -> int:
    n = 0
    with db.conn() as c:
        for key, value in values.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError(f"invalid settings key: {key!r}")
            v = None if value is None else (value if isinstance(value, str) else json.dumps(value) if isinstance(value, (dict, list)) else str(value).lower() if isinstance(value, bool) else str(value))
            c.execute(
                """INSERT INTO bot_settings (user_id, key, value, updated_at) VALUES (%s, %s, %s, NOW())
                   ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
                (user_id, key, v))
            n += 1
    return n


def all_with_defaults(user_id) -> dict[str, str | None]:
    out: dict[str, str | None] = dict(GLOBAL_DEFAULTS)
    for name in STRATEGIES:
        out.update({f"strat_{name}_{k}": v for k, v in strategy_defaults(name).items()})
    out.update(load(user_id))
    return out
