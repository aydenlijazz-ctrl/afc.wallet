"""In-memory Bybit emulator used by the tests (one-way position mode, instant market fills)."""
from __future__ import annotations

import numpy as np

from apex.bybit import Candles


def make_candles(closes, spread=0.002, volume=None, start_ts=1_700_000_000_000, step_ms=60_000) -> Candles:
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) * (1 + spread)
    lows = np.minimum(opens, closes) * (1 - spread)
    vol = np.full(len(closes), 100.0) if volume is None else np.asarray(volume, dtype=float)
    ts = start_ts + np.arange(len(closes)) * step_ms
    return Candles(ts.astype(float), opens, highs, lows, closes, vol)


class FakeExchange:
    def __init__(self):
        self.candles: dict[tuple[str, str], Candles] = {}
        self.prices: dict[str, float] = {}
        self.spread_pct = 0.0002
        self.positions_: dict[str, dict] = {}  # symbol -> {side, size, avg_price}
        self.orders: list[dict] = []
        self.stops: dict[str, dict] = {}
        self.leverage: dict[str, float] = {}
        self.closed: dict[str, list[dict]] = {}
        self.order_states: dict[str, str] = {}
        self.balance = {"total_equity": 1234.5, "available_balance": 1000.0, "unrealised_pnl": 12.3}
        self.fail_orders = False

    # market data
    def klines(self, symbol, tf, limit=300, end_ms=None, closed_only=True):
        c = self.candles[(symbol, tf)]
        if end_ms is not None:
            m = c.ts <= end_ms
            c = Candles(c.ts[m], c.open[m], c.high[m], c.low[m], c.close[m], c.volume[m])
        return c.tail(limit)

    def ticker(self, symbol):
        p = self.prices[symbol]
        return {"symbol": symbol, "last": p, "mark": p, "bid": p * (1 - self.spread_pct / 2),
                "ask": p * (1 + self.spread_pct / 2)}

    def tickers(self):
        return [{"symbol": s, "lastPrice": str(p), "price24hPcnt": "0.01", "turnover24h": "1000000",
                 "volume24h": "10", "highPrice24h": str(p), "lowPrice24h": str(p), "fundingRate": "0.0001",
                 "openInterestValue": "5"} for s, p in self.prices.items()]

    def instrument(self, symbol):
        return {"qty_step": 0.001, "min_qty": 0.001, "tick_size": 0.01, "max_leverage": 100}

    # trading
    def wallet_balance(self):
        return dict(self.balance)

    def set_leverage(self, symbol, lev):
        self.leverage[symbol] = lev

    def place_order(self, symbol, side, qty, order_type="Market", price=None, reduce_only=False,
                    take_profit=None, stop_loss=None):
        if self.fail_orders:
            raise RuntimeError("insufficient balance")
        oid = f"o{len(self.orders) + 1}"
        self.orders.append({"id": oid, "symbol": symbol, "side": side, "qty": qty, "type": order_type, "price": price,
                            "reduce_only": reduce_only, "tp": take_profit, "sl": stop_loss})
        if order_type == "Limit":
            self.order_states[oid] = "New"
            return oid
        self._fill(symbol, side, qty, self.prices[symbol], reduce_only)
        return oid

    def fill_limit(self, oid):
        o = next(o for o in self.orders if o["id"] == oid)
        self._fill(o["symbol"], o["side"], o["qty"], o["price"], False)
        self.order_states[oid] = "Filled"

    def _fill(self, symbol, side, qty, price, reduce_only):
        sgn = 1 if side == "Buy" else -1
        p = self.positions_.get(symbol)
        cur = 0.0 if not p else (p["size"] if p["side"] == "Buy" else -p["size"])
        new = cur + sgn * qty
        if reduce_only and abs(new) > abs(cur):
            new = 0.0
        if p and cur and np.sign(new) != np.sign(cur):
            self._record_close(symbol, p, abs(cur), price)
            p = None
        elif p and abs(new) < abs(cur):
            self._record_close(symbol, p, abs(cur) - abs(new), price)
        if abs(new) < 1e-12:
            self.positions_.pop(symbol, None)
            return
        if p and np.sign(new) == np.sign(cur) and abs(new) > abs(cur):
            avg = (p["avg_price"] * abs(cur) + price * qty) / abs(new)
        elif p and np.sign(new) == np.sign(cur):
            avg = p["avg_price"]
        else:
            avg = price
        self.positions_[symbol] = {"side": "Buy" if new > 0 else "Sell", "size": round(abs(new), 9), "avg_price": avg}

    def _record_close(self, symbol, p, qty, price):
        self.closed.setdefault(symbol, []).append({"order_id": "c", "side": p["side"], "qty": qty,
                                                   "avg_entry": p["avg_price"], "avg_exit": price, "closed_pnl": 0,
                                                   "updated_ms": 2_000_000_000_000 + len(self.closed.get(symbol, []))})

    def set_trading_stop(self, symbol, take_profit=None, stop_loss=None):
        s = self.stops.setdefault(symbol, {})
        if take_profit is not None:
            s["tp"] = take_profit
        if stop_loss is not None:
            s["sl"] = stop_loss

    def positions(self):
        return [{"symbol": s, "side": p["side"], "size": p["size"], "avg_price": p["avg_price"],
                 "mark_price": self.prices.get(s, p["avg_price"]), "unrealised_pnl": 0.0}
                for s, p in self.positions_.items()]

    def closed_pnl(self, symbol, start_ms=None, limit=50):
        return list(self.closed.get(symbol, []))

    def order_status(self, symbol, oid):
        return self.order_states.get(oid)

    def cancel_order(self, symbol, oid):
        self.order_states[oid] = "Cancelled"

    # test helper: exchange-side stop/TP execution
    def hit(self, symbol, price):
        self.prices[symbol] = price
        p = self.positions_[symbol]
        self._fill(symbol, "Sell" if p["side"] == "Buy" else "Buy", p["size"], price, True)


class FakeTelegram:
    def __init__(self):
        self.sent: list[str] = []
        self.keyboards: list = []
        self.callbacks: list = []

    def send(self, text, keyboard=None, chat_id=None):
        self.sent.append(text)
        self.keyboards.append(keyboard)
        return {"ok": True}

    def answer_callback(self, cid, text=""):
        self.callbacks.append((cid, text))
