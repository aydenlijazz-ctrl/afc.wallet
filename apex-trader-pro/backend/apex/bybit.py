"""Bybit v5 REST client (linear USDT perpetuals) with HMAC-SHA256 signing and base-URL fallback."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

import httpx
import numpy as np

from . import config

INTERVALS = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}


class BybitError(RuntimeError):
    def __init__(self, code: int, msg: str, path: str = ""):
        super().__init__(f"Bybit {path} retCode={code}: {msg}")
        self.code = code
        self.msg = msg


@dataclass
class Candles:
    ts: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.close)

    def tail(self, n: int) -> "Candles":
        return Candles(*(getattr(self, f)[-n:] for f in ("ts", "open", "high", "low", "close", "volume")))

    @classmethod
    def from_rows(cls, rows: list[list]) -> "Candles":
        """rows: [[ts, open, high, low, close, volume, ...], ...] oldest first."""
        a = np.array([[float(v) for v in r[:6]] for r in rows]) if rows else np.zeros((0, 6))
        return cls(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5])


def sign(secret: str, timestamp: str, api_key: str, recv_window: str, payload: str) -> str:
    """payload = query string for GET, raw JSON body for POST (Bybit v5 spec)."""
    msg = f"{timestamp}{api_key}{recv_window}{payload}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


def round_step(value: float, step: float, mode=ROUND_DOWN) -> float:
    d, s = Decimal(str(value)), Decimal(str(step))
    return float((d / s).quantize(Decimal(1), rounding=mode) * s)


def fmt(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


class BybitClient:
    category = "linear"

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 base_urls: list[str] | None = None, http: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else (config.secret("BYBIT_API_KEY") or "")
        self.api_secret = api_secret if api_secret is not None else (config.secret("BYBIT_API_SECRET") or "")
        self.base_urls = base_urls or config.BYBIT_BASE_URLS
        self.http = http or httpx.Client(timeout=10.0)
        self._instruments: dict[str, dict] = {}

    # --- transport -------------------------------------------------------------------------
    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None,
                 signed: bool = False) -> dict:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        query = "&".join(f"{k}={v}" for k, v in params.items())
        raw_body = json.dumps(body, separators=(",", ":")) if body is not None else ""
        last_exc: Exception | None = None
        for base in self.base_urls:
            headers = {"Content-Type": "application/json"}
            if signed:
                if not self.api_key or not self.api_secret:
                    raise BybitError(-1, "BYBIT_API_KEY / BYBIT_API_SECRET are not configured", path)
                ts = str(int(time.time() * 1000))
                headers.update({
                    "X-BAPI-API-KEY": self.api_key,
                    "X-BAPI-TIMESTAMP": ts,
                    "X-BAPI-RECV-WINDOW": config.RECV_WINDOW,
                    "X-BAPI-SIGN-TYPE": "2",
                    "X-BAPI-SIGN": sign(self.api_secret, ts, self.api_key, config.RECV_WINDOW,
                                        query if method == "GET" else raw_body),
                })
            url = f"{base}{path}" + (f"?{query}" if query else "")
            try:
                resp = self.http.request(method, url, content=raw_body or None, headers=headers)
                if resp.status_code >= 500 or resp.status_code in (403, 451):
                    last_exc = BybitError(resp.status_code, resp.text[:200], path)
                    continue  # try the fallback host
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                continue
            if data.get("retCode") != 0:
                raise BybitError(data.get("retCode"), data.get("retMsg", ""), path)
            return data.get("result") or {}
        raise last_exc or BybitError(-1, "no base URL reachable", path)

    # --- market data -----------------------------------------------------------------------
    def klines(self, symbol: str, interval: str, limit: int = 300, end_ms: int | None = None,
               closed_only: bool = True) -> Candles:
        res = self._request("GET", "/v5/market/kline", {
            "category": self.category, "symbol": symbol, "interval": INTERVALS.get(interval, interval),
            "limit": min(limit + 1, 1000), "end": end_ms})
        rows = list(reversed(res.get("list", [])))  # Bybit returns newest first
        if closed_only and rows:
            rows = rows[:-1]  # the newest candle is still forming
        return Candles.from_rows(rows[-limit:])

    def ticker(self, symbol: str) -> dict:
        res = self._request("GET", "/v5/market/tickers", {"category": self.category, "symbol": symbol})
        t = res["list"][0]
        return {"symbol": symbol, "last": float(t["lastPrice"]), "mark": float(t["markPrice"]),
                "bid": float(t["bid1Price"] or 0), "ask": float(t["ask1Price"] or 0)}

    def tickers(self) -> list[dict]:
        res = self._request("GET", "/v5/market/tickers", {"category": self.category})
        return res.get("list", [])

    def instrument(self, symbol: str) -> dict:
        if symbol not in self._instruments:
            res = self._request("GET", "/v5/market/instruments-info", {"category": self.category, "symbol": symbol})
            i = res["list"][0]
            self._instruments[symbol] = {
                "qty_step": float(i["lotSizeFilter"]["qtyStep"]),
                "min_qty": float(i["lotSizeFilter"]["minOrderQty"]),
                "tick_size": float(i["priceFilter"]["tickSize"]),
                "max_leverage": float(i["leverageFilter"]["maxLeverage"]),
            }
        return self._instruments[symbol]

    # --- account / trading -----------------------------------------------------------------
    def wallet_balance(self) -> dict:
        res = self._request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"}, signed=True)
        acct = (res.get("list") or [{}])[0]
        return {"total_equity": float(acct.get("totalEquity") or 0),
                "available_balance": float(acct.get("totalAvailableBalance") or 0),
                "unrealised_pnl": float(acct.get("totalPerpUPL") or 0)}

    def set_leverage(self, symbol: str, leverage: float) -> None:
        try:
            self._request("POST", "/v5/position/set-leverage", body={
                "category": self.category, "symbol": symbol,
                "buyLeverage": fmt(leverage), "sellLeverage": fmt(leverage)}, signed=True)
        except BybitError as e:
            if e.code != 110043:  # leverage not modified
                raise

    def place_order(self, symbol: str, side: str, qty: float, order_type: str = "Market",
                    price: float | None = None, reduce_only: bool = False, take_profit: float | None = None,
                    stop_loss: float | None = None) -> str:
        body: dict[str, Any] = {"category": self.category, "symbol": symbol, "side": side, "orderType": order_type,
                                "qty": fmt(qty), "positionIdx": 0, "orderLinkId": f"apex-{uuid.uuid4().hex[:24]}"}
        if order_type == "Limit":
            body["price"] = fmt(price)
            body["timeInForce"] = "GTC"
        if reduce_only:
            body["reduceOnly"] = True
        if take_profit is not None:
            body["takeProfit"] = fmt(take_profit)
        if stop_loss is not None:
            body["stopLoss"] = fmt(stop_loss)
        return self._request("POST", "/v5/order/create", body=body, signed=True)["orderId"]

    def set_trading_stop(self, symbol: str, take_profit: float | None = None, stop_loss: float | None = None) -> None:
        body: dict[str, Any] = {"category": self.category, "symbol": symbol, "positionIdx": 0, "tpslMode": "Full"}
        if take_profit is not None:
            body["takeProfit"] = fmt(take_profit)
        if stop_loss is not None:
            body["stopLoss"] = fmt(stop_loss)
        try:
            self._request("POST", "/v5/position/trading-stop", body=body, signed=True)
        except BybitError as e:
            if e.code != 34040:  # not modified
                raise

    def positions(self) -> list[dict]:
        res = self._request("GET", "/v5/position/list", {"category": self.category, "settleCoin": "USDT"}, signed=True)
        out = []
        for p in res.get("list", []):
            size = float(p.get("size") or 0)
            out.append({"symbol": p["symbol"], "side": p.get("side") or "", "size": size,
                        "avg_price": float(p.get("avgPrice") or 0), "mark_price": float(p.get("markPrice") or 0),
                        "unrealised_pnl": float(p.get("unrealisedPnl") or 0)})
        return out

    def closed_pnl(self, symbol: str, start_ms: int | None = None, limit: int = 50) -> list[dict]:
        res = self._request("GET", "/v5/position/closed-pnl", {
            "category": self.category, "symbol": symbol, "startTime": start_ms, "limit": limit}, signed=True)
        return [{"order_id": r.get("orderId"), "side": r.get("side"), "qty": float(r.get("closedSize") or r.get("qty") or 0),
                 "avg_entry": float(r.get("avgEntryPrice") or 0), "avg_exit": float(r.get("avgExitPrice") or 0),
                 "closed_pnl": float(r.get("closedPnl") or 0), "updated_ms": int(r.get("updatedTime") or 0)}
                for r in res.get("list", [])]

    def order_status(self, symbol: str, order_id: str) -> str | None:
        res = self._request("GET", "/v5/order/realtime", {"category": self.category, "symbol": symbol,
                                                          "orderId": order_id}, signed=True)
        lst = res.get("list") or []
        if lst:
            return lst[0].get("orderStatus")
        res = self._request("GET", "/v5/order/history", {"category": self.category, "symbol": symbol,
                                                         "orderId": order_id}, signed=True)
        lst = res.get("list") or []
        return lst[0].get("orderStatus") if lst else None

    def cancel_order(self, symbol: str, order_id: str) -> None:
        self._request("POST", "/v5/order/cancel", body={"category": self.category, "symbol": symbol,
                                                        "orderId": order_id}, signed=True)


def round_price(price: float, tick: float) -> float:
    return round_step(price, tick, ROUND_HALF_UP)
