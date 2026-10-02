import json

import numpy as np

from apex.bybit import Candles

from apex import db, evolve
from apex.settings import Settings, save
from tests.market import Market, synth_5m


class HistExchange:
    def __init__(self, m):
        self.m = m

    def klines(self, symbol, tf, limit=300, end_ms=None, closed_only=True):
        c = self.m.tf[tf]
        idx = len(c) if end_ms is None else int(np.searchsorted(c.ts, end_ms, side="right"))
        return Candles(*(getattr(c, f)[max(0, idx - limit):idx] for f in ("ts", "open", "high", "low", "close", "volume")))


def test_backtest_and_grid_search():
    m = Market(synth_5m(12_000, seed=11))
    stats = evolve.backtest(m.tf["15m"], m.tf["1h"], {"sl_mult": 1.5, "tp_mult": 3.0, "rsi_low": 35, "rsi_high": 65,
                                                       "ema_fast": 20, "ema_slow": 50})
    assert stats["trades"] > 0 and stats["profit_factor"] >= 0


def test_fetch_history_pages_backwards():
    m = Market(synth_5m(30_000, seed=3))
    c = evolve.fetch_history(HistExchange(m), "BTCUSDT", "15m", 14)
    assert len(c) == 14 * 96 + 220
    assert (c.ts[1:] > c.ts[:-1]).all()  # strictly increasing, no duplicated page boundaries


def test_self_learning():
    p = {"sl_mult": 1.5, "tp_mult": 3.0}
    assert evolve.self_learn(p, 0.3) == {"sl_mult": 1.65, "tp_mult": 2.7}
    assert evolve.self_learn(p, 0.7)["tp_mult"] == 3.3
    assert evolve.self_learn(p, None) == p


def test_evolve_run_updates_settings(uid, monkeypatch):
    monkeypatch.setattr(evolve, "GRID", {"sl_mult": [1.0, 2.0], "tp_mult": [2.0, 3.0], "rsi_low": [35],
                                          "rsi_high": [65], "ema_fast": [20], "ema_slow": [50]})
    save(uid, {"strat_adaptive_nexus_symbols": "BTCUSDT"})
    m = Market(synth_5m(30_000, seed=5))
    out = evolve.run(uid, HistExchange(m), days=14)
    params = json.loads(Settings(uid).s("adaptive_nexus", "params"))
    assert params["sl_mult"] in (1.0, 2.0) and params == out["params"]
    assert db.fetch_one("SELECT action FROM live_audit_log")["action"] == "evolve"
