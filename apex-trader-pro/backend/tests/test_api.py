import json

import pytest
from fastapi.testclient import TestClient

from apex import ai, db, main
from apex.settings import Settings, save

ADMIN = {"X-Admin-Secret": "test-admin-secret"}


@pytest.fixture
def client(uid, ex, tg):
    app = main.create_app("all", migrate=False)
    app.dependency_overrides[main.require_user] = lambda: uid
    app.dependency_overrides[main.get_exchange] = lambda: ex
    app.dependency_overrides[main.get_telegram] = lambda: tg
    with TestClient(app) as c:
        yield c


def test_settings_roundtrip(client, uid):
    r = client.post("/save-settings", json={"settings": {"strat_wide_atr_enabled": True, "strat_wide_atr_cost": 25}})
    assert r.json() == {"saved": 2}
    s = client.get("/get-settings").json()
    assert s["settings"]["strat_wide_atr_enabled"] == "true" and s["settings"]["strat_wide_atr_cost"] == "25"
    assert s["settings"]["strat_apex_mtf_leverage"] == "5"  # defaults filled in
    assert len(s["strategies"]) == 11
    assert client.post("/save-settings", json={"settings": {}}).status_code == 400


def test_auth_required_without_override(uid):
    app = main.create_app("all", migrate=False)
    with TestClient(app) as c:
        assert c.get("/get-settings").status_code == 401
        assert c.post("/run-apex-hybrid").status_code == 403
        assert c.post("/run-apex-hybrid", headers={"X-Admin-Secret": "wrong"}).status_code == 403


def test_cron_endpoints(client, ex):
    r = client.post("/run-apex-hybrid", headers=ADMIN)
    assert r.status_code == 200 and set(r.json()) >= {"signals", "opened", "skipped"}
    r = client.post("/monitor-positions?passes=2&interval=0", headers=ADMIN)
    assert len(r.json()["passes"]) == 2
    assert client.post("/reset-auto-reverse", headers=ADMIN).json() == {"restored": []}


def test_balance(client):
    assert client.get("/get-balance").json()["total_equity"] == 1234.5


def test_service_selection():
    app = main.create_app("get-balance", migrate=False)
    paths = set(app.openapi()["paths"])
    assert "/get-balance" in paths and "/run-apex-hybrid" not in paths and "/save-settings" not in paths
    paths = set(main.create_app("monitor-positions", migrate=False).openapi()["paths"])
    assert paths == {"/monitor-positions", "/healthz"}


def tg_update(text=None, data=None, chat=777):
    if data:
        return {"callback_query": {"id": "cb1", "data": data, "message": {"chat": {"id": chat}}}}
    return {"message": {"text": text, "chat": {"id": chat}}}


def test_telegram_webhook(client, tg, uid, ex):
    h = {"X-Telegram-Bot-Api-Secret-Token": main.telegram_webhook_secret()}
    assert client.post("/telegram-command-handler", json=tg_update("/status")).status_code == 403
    r = client.post("/telegram-command-handler", json=tg_update("/status", chat=999), headers=h)
    assert r.json()["ok"] is False and tg.sent == []  # foreign chat ignored
    client.post("/telegram-command-handler", json=tg_update("/status"), headers=h)
    assert "NOT ARMED" in tg.sent[-1]
    client.post("/telegram-command-handler", json=tg_update(data="toggle_strategy:apex_mtf"), headers=h)
    assert Settings(uid).sflag("apex_mtf", "enabled")
    assert any("✅ Apex MTF" == b[0]["text"] for b in tg.keyboards[-1])
    client.post("/telegram-command-handler", json=tg_update("/balance"), headers=h)
    assert "1234.50" in tg.sent[-1]
    client.post("/telegram-command-handler", json=tg_update("/positions"), headers=h)
    assert tg.sent[-1] == "No open positions."
    # open a position, then close all via callback
    ex.prices["BTCUSDT"] = 100.0
    ex._fill("BTCUSDT", "Buy", 1.0, 100.0, False)
    db.execute("""INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit,
                  actual_quantity) VALUES (%s,'BTCUSDT','LONG','wide_atr',100,98,104,1)""", (uid,))
    client.post("/telegram-command-handler", json=tg_update("/positions"), headers=h)
    assert tg.keyboards[-1][0][0]["callback_data"] == "close_position:BTCUSDT"
    client.post("/telegram-command-handler", json=tg_update(data="close_all_positions"), headers=h)
    assert "BTCUSDT" not in ex.positions_ and "🛑 BTCUSDT" in tg.sent[-1]
    client.post("/telegram-command-handler", json=tg_update("/performance"), headers=h)
    assert "Trades closed: 1" in tg.sent[-1]


def test_parse_custom_strategy(client, uid, monkeypatch):
    reply = json.dumps({"name": "RSI dip", "timeframe": "15m", "direction": "long", "sl_atr": 1.5, "tp_atr": 3,
                        "conditions": {"long": [{"left": {"ind": "rsi", "period": 14}, "op": "<", "right": 30}]}})
    monkeypatch.setattr(ai, "complete", lambda *a, **k: f"Here you go:\n```json\n{reply}\n```")
    r = client.post("/parse-custom-strategy", json={"description": "Buy when RSI(14) < 30 on 15m"})
    assert r.status_code == 200 and r.json()["definition"]["name"] == "RSI dip"
    assert json.loads(Settings(uid).s("custom", "definition"))["direction"] == "long"
    bad = json.dumps({"timeframe": "3m", "conditions": {"long": [{"op": ">", "left": {"ind": "rsi"}}]}})
    monkeypatch.setattr(ai, "complete", lambda *a, **k: bad)
    assert client.post("/parse-custom-strategy", json={"description": "something else"}).status_code == 422


def test_dashboard_endpoints(client, uid, ex):
    for i, net in enumerate([10.0, -4.0, 6.0]):
        db.execute("""INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit,
                      status, net_pnl, closed_at, result) VALUES (%s,'BTCUSDT','LONG','wide_atr',1,0.5,2,'CLOSED',%s,
                      NOW(),'TP HIT')""", (uid, net))
    a = client.get("/api/analytics").json()
    assert a["kpi"]["trades"] == 3 and abs(a["kpi"]["net_pnl"] - 12) < 1e-9
    assert abs(a["kpi"]["profit_factor"] - 4.0) < 1e-9 and a["by_strategy"][0]["strategy"] == "wide_atr"
    assert a["daily"][-1]["cumulative"] == 12
    assert len(client.get("/api/trades?status=CLOSED&strategy=wide_atr").json()["trades"]) == 3
    assert client.get("/api/trades?strategy=apex_mtf").json()["trades"] == []
    ex.prices["ETHUSDT"] = 10.0
    assert client.get("/api/market/tickers").json()["tickers"][0]["symbol"] == "ETHUSDT"
    assert client.get("/api/positions").json() == {"positions": []}
    assert client.post("/api/close-position", json={"symbol": "BTC;DROP"}).status_code == 400


def test_ai_chat_without_provider(client):
    r = client.post("/api/ai/chat", json={"message": "How is my bot doing?"})
    assert r.status_code == 503 and "No AI provider" in r.json()["detail"]


def test_ai_provider_request_shape(uid):
    import httpx
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}],
                                         "usage": {"input_tokens": 5, "output_tokens": 1}})

    import os
    os.environ["ANTHROPIC_API_KEY"] = "k"
    from apex import config
    config.secret.cache_clear()
    try:
        out = ai.complete("sys", "hi", user_id=uid, http=httpx.Client(transport=httpx.MockTransport(handler)))
    finally:
        os.environ.pop("ANTHROPIC_API_KEY")
        config.secret.cache_clear()
    assert out == "ok" and seen["url"].endswith("/v1/messages") and seen["body"]["system"] == "sys"
    assert db.fetch_one("SELECT * FROM ai_usage")["input_tokens"] == 5
