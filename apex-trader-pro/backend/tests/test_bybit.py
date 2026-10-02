import hashlib
import hmac
import json

import httpx
import pytest

from apex.bybit import BybitClient, BybitError, round_step, sign


def test_sign_matches_bybit_v5_spec():
    expected = hmac.new(b"secret", b"1700000000000key5000category=linear&symbol=BTCUSDT", hashlib.sha256).hexdigest()
    assert sign("secret", "1700000000000", "key", "5000", "category=linear&symbol=BTCUSDT") == expected


def _client(handler, bases=("https://a.test", "https://b.test")):
    return BybitClient("key", "secret", list(bases), http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_signed_post_headers_and_body():
    seen = {}

    def handler(req: httpx.Request):
        seen["headers"] = req.headers
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={"retCode": 0, "result": {"orderId": "abc"}})

    oid = _client(handler).place_order("BTCUSDT", "Buy", 0.0012, "Market")
    assert oid == "abc"
    h = seen["headers"]
    assert h["X-BAPI-RECV-WINDOW"] == "5000" and h["X-BAPI-API-KEY"] == "key"
    assert h["X-BAPI-SIGN"] == sign("secret", h["X-BAPI-TIMESTAMP"], "key", "5000", seen["body"])
    body = json.loads(seen["body"])
    assert body["qty"] == "0.0012" and body["category"] == "linear" and body["orderType"] == "Market"


def test_signed_get_signs_query_string():
    seen = {}

    def handler(req):
        seen["q"] = req.url.query.decode()
        seen["h"] = req.headers
        return httpx.Response(200, json={"retCode": 0, "result": {"list": [{"totalEquity": "100.5",
                                                                           "totalAvailableBalance": "90"}]}})

    bal = _client(handler).wallet_balance()
    assert bal["total_equity"] == 100.5
    assert seen["q"] == "accountType=UNIFIED"
    assert seen["h"]["X-BAPI-SIGN"] == sign("secret", seen["h"]["X-BAPI-TIMESTAMP"], "key", "5000", seen["q"])


def test_fallback_to_second_base_url():
    hosts = []

    def handler(req):
        hosts.append(req.url.host)
        if req.url.host == "a.test":
            return httpx.Response(403, text="geo blocked")
        return httpx.Response(200, json={"retCode": 0, "result": {"list": []}})

    _client(handler).positions()
    assert hosts == ["a.test", "b.test"]


def test_api_error_raises():
    c = _client(lambda r: httpx.Response(200, json={"retCode": 10001, "retMsg": "params error"}))
    with pytest.raises(BybitError) as e:
        c.cancel_order("BTCUSDT", "1")
    assert e.value.code == 10001


def test_klines_are_reversed_and_forming_candle_dropped():
    rows = [[str(1000 * i), "1", "2", "0.5", str(i), "10", "0"] for i in (5, 4, 3, 2, 1)]  # newest first
    c = _client(lambda r: httpx.Response(200, json={"retCode": 0, "result": {"list": rows}}))
    k = c.klines("BTCUSDT", "5m", 10)
    assert list(k.close) == [1.0, 2.0, 3.0, 4.0]


def test_round_step():
    assert round_step(0.123456, 0.001) == 0.123
    assert round_step(17.99, 1) == 17
