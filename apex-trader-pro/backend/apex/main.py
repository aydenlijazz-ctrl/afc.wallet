"""HTTP entrypoint. One image, deployed as several Cloud Run services.

APEX_SERVICE selects the routes a service exposes (comma separated, default "all"):
  run-apex-hybrid, monitor-positions, get-balance, save-settings, get-settings,
  telegram-command-handler, parse-custom-strategy, evolve-adaptive-nexus, reset-auto-reverse, dashboard-api
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from . import ai, bot, config, db, engine, evolve, monitor, reverse, settings
from .bybit import BybitClient
from .telegram import Telegram

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("apex")


# --- dependencies (overridable in tests) ----------------------------------------------------------
def get_exchange():
    return BybitClient()


def get_telegram():
    return Telegram()


def require_user(authorization: str = Header(default="")):
    """Firebase ID token; only OWNER_EMAIL may use the dashboard (the bot trades one Bybit account)."""
    if os.environ.get("APEX_AUTH_DISABLED") == "true":
        return config.owner_user_id()
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        import firebase_admin
        from firebase_admin import auth

        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        claims = auth.verify_id_token(authorization[7:])
    except Exception as exc:
        raise HTTPException(401, f"invalid token: {exc}") from exc
    email = (claims.get("email") or "").lower()
    if not claims.get("email_verified", False) and os.environ.get("APEX_REQUIRE_VERIFIED_EMAIL", "true") == "true":
        raise HTTPException(403, "email not verified")
    if email != config.owner_email():
        raise HTTPException(403, "this account is not the bot owner")
    return config.user_id_for_email(email)


def require_cron(x_admin_secret: str = Header(default="")):
    expected = config.secret("ADMIN_SECRET") or ""
    if not expected or not hmac.compare_digest(x_admin_secret, expected):
        raise HTTPException(403, "forbidden")
    return config.owner_user_id()


def telegram_webhook_secret() -> str:
    return hashlib.sha256(f"tg:{config.secret('ADMIN_SECRET') or ''}".encode()).hexdigest()


# --- cron ------------------------------------------------------------------------------------------
cron_run, cron_monitor, cron_reset, cron_evolve = (APIRouter() for _ in range(4))


@cron_run.post("/run-apex-hybrid")
def run_apex_hybrid(user_id=Depends(require_cron), ex=Depends(get_exchange), tg=Depends(get_telegram)):
    with db.advisory_lock("run-apex-hybrid") as got:
        if not got:
            return {"skipped": "previous run still in progress"}
        return engine.run(user_id, ex, tg)


@cron_monitor.post("/monitor-positions")
def monitor_positions(passes: int = Query(1, ge=1, le=2), interval: int = Query(30, ge=0, le=30),
                      user_id=Depends(require_cron), ex=Depends(get_exchange), tg=Depends(get_telegram)):
    """Cloud Scheduler's minimum period is 1 minute; passes=2 gives a 30-second cadence."""
    results = []
    for i in range(passes):
        if i:
            time.sleep(interval)
        with db.advisory_lock("monitor-positions") as got:
            results.append(monitor.run(user_id, ex, tg) if got else {"skipped": "in progress"})
    return {"passes": results}


@cron_reset.post("/reset-auto-reverse")
def reset_auto_reverse(user_id=Depends(require_cron)):
    return {"restored": reverse.reset_daily(user_id, settings.Settings(user_id))}


@cron_evolve.post("/evolve-adaptive-nexus")
def evolve_adaptive_nexus(days: int = Query(14, ge=3, le=60), user_id=Depends(require_cron),
                          ex=Depends(get_exchange)):
    return evolve.run(user_id, ex, days)


# --- frontend: balance / settings / AI -------------------------------------------------------------
balance_router, save_router, get_router, parse_router, dash = (APIRouter() for _ in range(5))


@balance_router.get("/get-balance")
def get_balance(user_id=Depends(require_user), ex=Depends(get_exchange)):
    try:
        return ex.wallet_balance()
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@save_router.post("/save-settings")
def save_settings(payload: dict = Body(...), user_id=Depends(require_user)):
    values = payload.get("settings", payload)
    if not isinstance(values, dict) or not values:
        raise HTTPException(400, "expected {settings: {key: value}}")
    try:
        n = settings.save(user_id, values)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.audit(user_id, "save-settings", "save", request={"keys": sorted(values)})
    return {"saved": n}


@get_router.get("/get-settings")
def get_settings(user_id=Depends(require_user)):
    return {"settings": settings.all_with_defaults(user_id), "strategies": settings.STRATEGIES,
            "labels": settings.STRATEGY_LABELS, "kinds": settings.STRATEGY_KIND}


@parse_router.post("/parse-custom-strategy")
def parse_custom_strategy(payload: dict = Body(...), user_id=Depends(require_user)):
    description = (payload.get("description") or "").strip()
    if not description or len(description) > 8000:
        raise HTTPException(400, "description is required (max 8000 chars)")
    try:
        definition = ai.parse_custom_strategy(user_id, description, payload.get("provider"))
    except (ai.AIError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if payload.get("save", True):
        settings.save(user_id, {"strat_custom_definition": json.dumps(definition),
                                "strat_custom_description": description})
    return {"definition": definition}


# --- dashboard data --------------------------------------------------------------------------------
def _num(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({k: (float(v) if v is not None and type(v).__name__ == "Decimal" else v) for k, v in r.items()})
    return out


@dash.get("/api/trades")
def list_trades(status: str | None = None, strategy: str | None = None, reversed: bool | None = None,
                date_from: datetime | None = Query(None, alias="from"), date_to: datetime | None = Query(None, alias="to"),
                limit: int = Query(500, le=5000), user_id=Depends(require_user)):
    sql = ["SELECT * FROM trades WHERE user_id=%s"]
    params: list[Any] = [user_id]
    for cond, val in (("status=%s", status), ("strategy=%s", strategy), ("reversed=%s", reversed),
                      ("created_at>=%s", date_from), ("created_at<=%s", date_to)):
        if val is not None:
            sql.append(f"AND {cond}")
            params.append(val)
    sql.append("ORDER BY created_at DESC LIMIT %s")
    params.append(limit)
    return {"trades": _num(db.fetch(" ".join(sql), tuple(params)))}


@dash.get("/api/positions")
def open_positions(user_id=Depends(require_user), ex=Depends(get_exchange)):
    trades = _num(db.fetch("SELECT * FROM trades WHERE user_id=%s AND status='OPEN' ORDER BY created_at DESC",
                           (user_id,)))
    try:
        marks = {p["symbol"]: p["mark_price"] for p in ex.positions() if p["size"]}
    except Exception:
        marks = {}
    for t in trades:
        m = marks.get(t["symbol"])
        t["mark_price"] = m
        if m and t["actual_quantity"]:
            sgn = 1 if t["direction"] == "LONG" else -1
            t["unrealized_pnl"] = sgn * (m - t["entry_price"]) * t["actual_quantity"]
    return {"positions": trades}


@dash.get("/api/signals")
def recent_signals(limit: int = Query(50, le=500), user_id=Depends(require_user)):
    rows = db.fetch("""SELECT created_at, service, action, symbol, strategy, request, response, success
                       FROM live_audit_log WHERE user_id=%s AND action IN ('open_position','signal_not_armed')
                       ORDER BY created_at DESC LIMIT %s""", (user_id, limit))
    return {"signals": rows}


@dash.get("/api/analytics")
def analytics(strategy: str | None = None, reversed: bool | None = None,
              date_from: datetime | None = Query(None, alias="from"), date_to: datetime | None = Query(None, alias="to"),
              user_id=Depends(require_user)):
    where = ["user_id=%s", "status='CLOSED'"]
    params: list[Any] = [user_id]
    for cond, val in (("strategy=%s", strategy), ("reversed=%s", reversed), ("closed_at>=%s", date_from),
                      ("closed_at<=%s", date_to)):
        if val is not None:
            where.append(cond)
            params.append(val)
    w = " AND ".join(where)
    p = tuple(params)
    kpi = db.fetch_one(f"""SELECT COUNT(*) AS trades, COALESCE(SUM(net_pnl),0) AS net_pnl,
            COUNT(*) FILTER (WHERE net_pnl>0) AS wins,
            COALESCE(SUM(net_pnl) FILTER (WHERE net_pnl>0),0) AS gross_win,
            COALESCE(-SUM(net_pnl) FILTER (WHERE net_pnl<=0),0) AS gross_loss,
            COALESCE(AVG(net_pnl),0) AS avg_trade FROM trades WHERE {w}""", p)
    kpi = _num([kpi])[0]
    kpi["win_rate"] = kpi["wins"] / kpi["trades"] * 100 if kpi["trades"] else 0
    kpi["profit_factor"] = kpi["gross_win"] / kpi["gross_loss"] if kpi["gross_loss"] else None
    daily = _num(db.fetch(f"""SELECT date_trunc('day', closed_at) AS day, SUM(net_pnl) AS pnl FROM trades WHERE {w}
                              GROUP BY 1 ORDER BY 1""", p))
    cum = 0.0
    for d in daily:
        cum += d["pnl"] or 0
        d["cumulative"] = cum
    by_strategy = _num(db.fetch(f"""SELECT strategy, COUNT(*) AS trades, SUM(net_pnl) AS net_pnl,
            COUNT(*) FILTER (WHERE net_pnl>0) AS wins, AVG(signal_score) AS avg_score FROM trades WHERE {w}
            GROUP BY strategy ORDER BY SUM(net_pnl) DESC""", p))
    by_hour = _num(db.fetch(f"""SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC')::int AS hour, COUNT(*) AS trades,
            SUM(net_pnl) AS net_pnl, COUNT(*) FILTER (WHERE net_pnl>0) AS wins FROM trades WHERE {w}
            GROUP BY 1 ORDER BY 1""", p))
    return {"kpi": kpi, "daily": daily, "by_strategy": by_strategy, "by_hour": by_hour}


@dash.post("/api/close-position")
def close_position(payload: dict = Body(...), user_id=Depends(require_user), ex=Depends(get_exchange)):
    symbol = (payload.get("symbol") or "").upper()
    if not symbol.isalnum():
        raise HTTPException(400, "invalid symbol")
    return monitor.close_symbol(user_id, ex, symbol, "dashboard-api")


@dash.get("/api/market/tickers")
def market_tickers(user_id=Depends(require_user), ex=Depends(get_exchange)):
    rows = []
    for t in ex.tickers():
        if not t.get("symbol", "").endswith("USDT"):
            continue
        try:
            rows.append({"symbol": t["symbol"], "last": float(t["lastPrice"]),
                         "change_pct": float(t.get("price24hPcnt") or 0) * 100,
                         "turnover": float(t.get("turnover24h") or 0), "volume": float(t.get("volume24h") or 0),
                         "high": float(t.get("highPrice24h") or 0), "low": float(t.get("lowPrice24h") or 0),
                         "funding": float(t.get("fundingRate") or 0) * 100,
                         "open_interest": float(t.get("openInterestValue") or 0)})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda r: r["turnover"], reverse=True)
    return {"tickers": rows}


@dash.post("/api/ai/chat")
def ai_chat(payload: dict = Body(...), user_id=Depends(require_user)):
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message is required")
    try:
        return {"reply": ai.lab_chat(user_id, message[:6000], payload.get("mode", "chat"))}
    except ai.AIError as exc:
        raise HTTPException(503, str(exc)) from exc


@dash.post("/api/ai/feedback")
def ai_feedback(payload: dict = Body(...), user_id=Depends(require_user)):
    db.execute("INSERT INTO ai_feedback (user_id, feature, rating, comment, context) VALUES (%s,%s,%s,%s,%s)",
               (user_id, payload.get("feature", "chat"), payload.get("rating"), payload.get("comment"),
                json.dumps(payload.get("context")) if payload.get("context") is not None else None))
    return {"ok": True}


# --- telegram ---------------------------------------------------------------------------------------
tg_router = APIRouter()


@tg_router.post("/telegram-command-handler")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default=""),
                           ex=Depends(get_exchange), tg=Depends(get_telegram)):
    if not hmac.compare_digest(x_telegram_bot_api_secret_token, telegram_webhook_secret()):
        raise HTTPException(403, "forbidden")
    update = await request.json()
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(bot.handle_update, update, config.owner_user_id(), ex, tg,
                                   config.secret("TELEGRAM_CHAT_ID"))


# --- app ----------------------------------------------------------------------------------------------
ROUTERS = {
    "run-apex-hybrid": cron_run, "monitor-positions": cron_monitor, "reset-auto-reverse": cron_reset,
    "evolve-adaptive-nexus": cron_evolve,
    "get-balance": balance_router, "save-settings": save_router, "get-settings": get_router,
    "parse-custom-strategy": parse_router, "dashboard-api": dash, "telegram-command-handler": tg_router,
}


def create_app(services: str | None = None, migrate: bool | None = None) -> FastAPI:
    do_migrate = migrate if migrate is not None else os.environ.get("APEX_MIGRATE", "true") == "true"

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if do_migrate:
            db.migrate()
        st = settings.Settings(config.owner_user_id())
        if not st.values.get("bot_started_at"):
            st.set("bot_started_at", datetime.now(timezone.utc).isoformat())
        yield

    app = FastAPI(title="Apex Trader Pro", lifespan=lifespan)
    origins = [o for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    wanted = (services or os.environ.get("APEX_SERVICE", "all")).split(",")
    for name, router in ROUTERS.items():
        if "all" in wanted or name in wanted:
            app.include_router(router)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}

    return app


app = create_app()
