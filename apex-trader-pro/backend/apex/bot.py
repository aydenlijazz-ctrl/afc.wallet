"""telegram-command-handler: commands and inline-keyboard callbacks."""
from __future__ import annotations

from datetime import datetime, timezone

from . import db, monitor
from .settings import STRATEGIES, STRATEGY_LABELS, Settings

SERVICE = "telegram-command-handler"

HELP = ("<b>Apex Trader Pro</b>\n"
        "/status — bot status, uptime, open positions\n"
        "/positions — open positions with close buttons\n"
        "/strategies — enable / disable strategies\n"
        "/performance — today's P&L and win rate\n"
        "/balance — live balance\n"
        "/help — this list")


def main_menu() -> list[list[dict]]:
    return [
        [{"text": "📊 Status", "callback_data": "refresh_status"}, {"text": "📂 Positions", "callback_data": "positions"}],
        [{"text": "🧠 Strategies", "callback_data": "strategies"}, {"text": "📈 Performance", "callback_data": "performance"}],
        [{"text": "💰 Balance", "callback_data": "balance"}],
    ]


def handle_update(update: dict, user_id, exchange, tg, allowed_chat_id: str | None) -> dict:
    msg = update.get("message") or update.get("edited_message")
    cb = update.get("callback_query")
    chat_id = str(((msg or {}).get("chat") or {}).get("id") or (((cb or {}).get("message") or {}).get("chat") or {}).get("id") or "")
    if not allowed_chat_id or chat_id != str(allowed_chat_id):
        if cb:
            tg.answer_callback(cb["id"], "Unauthorized")
        return {"ok": False, "reason": "unauthorized chat"}
    st = Settings(user_id)
    if cb:
        text, kb = handle_callback(cb.get("data") or "", user_id, st, exchange)
        tg.answer_callback(cb["id"])
        tg.send(text, kb, chat_id=chat_id)
        return {"ok": True, "callback": cb.get("data")}
    command = ((msg or {}).get("text") or "").split()[0].split("@")[0].lower() if (msg or {}).get("text") else ""
    text, kb = handle_command(command, user_id, st, exchange)
    tg.send(text, kb, chat_id=chat_id)
    return {"ok": True, "command": command}


def handle_command(command: str, user_id, st: Settings, exchange) -> tuple[str, list | None]:
    if command == "/start":
        return HELP, main_menu()
    if command == "/status":
        return status_text(user_id, st), main_menu()
    if command == "/positions":
        return positions_view(user_id)
    if command == "/strategies":
        return strategies_view(st)
    if command == "/performance":
        return performance_text(user_id), None
    if command == "/balance":
        return balance_text(exchange), None
    return HELP, None


def handle_callback(data: str, user_id, st: Settings, exchange) -> tuple[str, list | None]:
    action, _, arg = data.partition(":")
    if action == "toggle_strategy" and arg in STRATEGIES:
        new = not st.sflag(arg, "enabled")
        st.set(f"strat_{arg}_enabled", str(new).lower())
        db.audit(user_id, SERVICE, "toggle_strategy", strategy=arg, request={"enabled": new})
        return strategies_view(st)
    if action == "close_position" and arg:
        try:
            r = monitor.close_symbol(user_id, exchange, arg, SERVICE)
            return f"🛑 {arg} closed @ {r['exit']:g} ({r['closed']} trade(s))", None
        except Exception as exc:
            return f"❌ Failed to close {arg}: {exc}", None
    if action == "close_all_positions":
        symbols = sorted({t["symbol"] for t in db.fetch(
            "SELECT symbol FROM trades WHERE user_id=%s AND status='OPEN'", (user_id,))})
        lines = []
        for s in symbols:
            try:
                r = monitor.close_symbol(user_id, exchange, s, SERVICE)
                lines.append(f"🛑 {s} @ {r['exit']:g}")
            except Exception as exc:
                lines.append(f"❌ {s}: {exc}")
        return "\n".join(lines) or "No open positions.", None
    if action == "toggle_armed":
        new = not st.flag("live_trading_armed")
        st.set("live_trading_armed", str(new).lower())
        db.audit(user_id, SERVICE, "toggle_armed", request={"armed": new})
        return status_text(user_id, st), main_menu()
    if action == "positions":
        return positions_view(user_id)
    if action == "strategies":
        return strategies_view(st)
    if action == "performance":
        return performance_text(user_id), None
    if action == "balance":
        return balance_text(exchange), None
    return status_text(user_id, st), main_menu()  # refresh_status and unknown


def status_text(user_id, st: Settings) -> str:
    n_open = db.fetch_one("SELECT COUNT(*) AS n FROM trades WHERE user_id=%s AND status='OPEN'", (user_id,))["n"]
    started = st.get("bot_started_at")
    uptime = ""
    if started:
        try:
            delta = datetime.now(timezone.utc) - datetime.fromisoformat(started)
            uptime = f"{delta.days}d {delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m"
        except ValueError:
            pass
    enabled = st.enabled_strategies()
    return (f"<b>Status</b>\nLive trading: {'🟢 ARMED' if st.flag('live_trading_armed') else '⏸ NOT ARMED (signals only)'}\n"
            f"Uptime: {uptime or 'n/a'}\nOpen positions: {n_open}\n"
            f"Enabled strategies: {', '.join(STRATEGY_LABELS[s] for s in enabled) or 'none'}")


def positions_view(user_id) -> tuple[str, list | None]:
    rows = db.fetch("SELECT * FROM trades WHERE user_id=%s AND status='OPEN' ORDER BY created_at", (user_id,))
    if not rows:
        return "No open positions.", None
    lines = ["<b>Open positions</b>"]
    for t in rows:
        lines.append(f"{t['symbol']} {t['direction']} · {STRATEGY_LABELS.get(t['strategy'], t['strategy'])} · "
                     f"entry {float(t['entry_price']):g} · SL {float(t['stop_loss']):g} · TP {float(t['take_profit']):g}")
    kb = [[{"text": f"Close {s}", "callback_data": f"close_position:{s}"}] for s in sorted({t["symbol"] for t in rows})]
    kb.append([{"text": "🛑 Close ALL", "callback_data": "close_all_positions"}])
    return "\n".join(lines), kb


def strategies_view(st: Settings) -> tuple[str, list]:
    kb = [[{"text": f"{'✅' if st.sflag(s, 'enabled') else '⬜'} {STRATEGY_LABELS[s]}",
            "callback_data": f"toggle_strategy:{s}"}] for s in STRATEGIES]
    kb.append([{"text": "⏯ Arm / disarm live trading", "callback_data": "toggle_armed"}])
    return "<b>Strategies</b> (tap to toggle)", kb


def performance_text(user_id) -> str:
    r = db.fetch_one(
        """SELECT COUNT(*) AS n, COALESCE(SUM(net_pnl),0) AS pnl, COUNT(*) FILTER (WHERE net_pnl > 0) AS wins
           FROM trades WHERE user_id=%s AND status='CLOSED'
           AND closed_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'""", (user_id,))
    n = r["n"]
    wr = (r["wins"] / n * 100) if n else 0
    return f"<b>Today</b>\nTrades closed: {n}\nNet P&L: {float(r['pnl']):+.2f} USDT\nWin rate: {wr:.1f}%"


def balance_text(exchange) -> str:
    try:
        b = exchange.wallet_balance()
        return (f"<b>Balance</b>\nEquity: {b['total_equity']:.2f} USDT\nAvailable: {b['available_balance']:.2f} USDT\n"
                f"Unrealised P&L: {b['unrealised_pnl']:+.2f} USDT")
    except Exception as exc:
        return f"❌ Balance unavailable: {exc}"
