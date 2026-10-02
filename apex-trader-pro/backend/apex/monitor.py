"""monitor-positions: closes, partial TP, trailing stops, limit fills, notifications (every 30s)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import db, indicators as ind, reverse, risk
from .bybit import round_price, round_step
from .settings import STRATEGY_LABELS, Settings

log = logging.getLogger(__name__)
SERVICE = "monitor-positions"


def run(user_id, exchange, tg) -> dict:
    st = Settings(user_id)
    out: dict = {"closed": [], "partials": [], "trailing": [], "fills": [], "errors": [], "notified": 0}
    positions = {p["symbol"]: p for p in exchange.positions() if p["size"] > 0}
    _handle_pending(user_id, st, exchange, tg, out)

    open_trades = reverse.open_trades(user_id)
    pending_symbols = {r["symbol"] for r in db.fetch(
        "SELECT symbol FROM strategy_positions WHERE user_id=%s AND status='PENDING'", (user_id,))}
    by_symbol: dict[str, list[dict]] = {}
    for t in open_trades:
        by_symbol.setdefault(t["symbol"], []).append(t)

    for symbol, trades in by_symbol.items():
        try:
            if symbol in positions:
                _manage_open(user_id, st, exchange, tg, symbol, positions[symbol], out)
            elif symbol not in pending_symbols:
                _close_symbol_trades(user_id, st, exchange, symbol, trades, out)
        except Exception as exc:
            log.exception("monitor %s failed", symbol)
            out["errors"].append(f"{symbol}: {exc}")

    out["reversals"] = reverse.check_adaptive(user_id, st, exchange, tg, SERVICE)
    out["notified"] = send_close_notifications(user_id, tg)
    return out


# --- limit orders ---------------------------------------------------------------------------------
def _handle_pending(user_id, st: Settings, exchange, tg, out: dict) -> None:
    ttl = timedelta(minutes=st.num("limit_order_ttl_minutes", 45))
    for p in db.fetch("SELECT * FROM strategy_positions WHERE user_id=%s AND status='PENDING'", (user_id,)):
        t = db.fetch_one("SELECT * FROM trades WHERE aggregated_position_id=%s AND status='OPEN' LIMIT 1", (p["id"],))
        if not t:
            db.execute("UPDATE strategy_positions SET status='CANCELLED', updated_at=NOW() WHERE id=%s", (p["id"],))
            continue
        status = exchange.order_status(p["symbol"], t["order_id"])
        if status == "Filled":
            db.execute("UPDATE strategy_positions SET status='OPEN', updated_at=NOW() WHERE id=%s", (p["id"],))
            out["fills"].append(p["symbol"])
            tg.send(f"✅ {STRATEGY_LABELS.get(p['strategy'], p['strategy'])} limit {p['direction']} {p['symbol']} filled "
                    f"@ {float(p['average_entry_price']):g}")
        elif status in ("Cancelled", "Rejected", "Deactivated") or (
                status in ("New", "PartiallyFilled", None) and datetime.now(timezone.utc) - p["created_at"] > ttl):
            if status in ("New", "PartiallyFilled"):
                try:
                    exchange.cancel_order(p["symbol"], t["order_id"])
                except Exception as exc:
                    out["errors"].append(f"cancel {p['symbol']}: {exc}")
                    continue
            if status == "PartiallyFilled":
                # the filled part becomes a normal open position
                db.execute("UPDATE strategy_positions SET status='OPEN', updated_at=NOW() WHERE id=%s", (p["id"],))
                continue
            with db.conn() as c:
                c.execute("UPDATE trades SET status='FAILED', closed_at=NOW() WHERE id=%s", (t["id"],))
                c.execute("UPDATE strategy_positions SET status='CANCELLED', updated_at=NOW() WHERE id=%s", (p["id"],))
            db.audit(user_id, SERVICE, "limit_order_expired", symbol=p["symbol"], strategy=p["strategy"],
                     response={"order_status": status})


# --- closed positions -----------------------------------------------------------------------------
def classify(t: dict, pos: dict | None, exit_px: float) -> str:
    entry = float(t["entry_price"])
    tol = max(float((pos or {}).get("atr") or 0) * 0.25, entry * 0.002)
    trail = (pos or {}).get("trail_stop_level")
    if trail is not None and abs(exit_px - float(trail)) <= tol:
        return "TRAILING STOP HIT"
    tp, sl = float(t["take_profit"]), float(t["stop_loss"])
    if abs(exit_px - tp) <= tol or risk.reached(t["direction"], exit_px, tp):
        return "TP HIT"
    if abs(exit_px - sl) <= tol or risk.stop_hit(t["direction"], exit_px, sl):
        return "SL HIT"
    return "MANUAL CLOSE"


def _close_symbol_trades(user_id, st: Settings, exchange, symbol: str, trades: list[dict], out: dict,
                         result: str | None = None, exit_px: float | None = None) -> None:
    if exit_px is None:
        start_ms = int(min(t["created_at"] for t in trades).timestamp() * 1000)
        records = exchange.closed_pnl(symbol, start_ms)
        records.sort(key=lambda r: r["updated_ms"], reverse=True)
        exit_px = records[0]["avg_exit"] if records and records[0]["avg_exit"] else exchange.ticker(symbol)["last"]
    fees, slip = st.num("fees_bps", 5), st.num("slippage_bps", 5)
    pos_ids = {t["aggregated_position_id"] for t in trades if t["aggregated_position_id"]}
    pos_rows = {p["id"]: p for p in db.fetch("SELECT * FROM strategy_positions WHERE id = ANY(%s)", (list(pos_ids),))} \
        if pos_ids else {}
    with db.conn() as c:
        for t in trades:
            qty = float(t["actual_quantity"] or 0)
            entry = float(t["entry_price"])
            res = result or classify(t, pos_rows.get(t["aggregated_position_id"]), exit_px)
            c.execute(
                """UPDATE trades SET status='CLOSED', exit_price=%s, pnl=%s, net_pnl=%s, result=%s, closed_at=NOW()
                   WHERE id=%s AND status='OPEN'""",
                (exit_px, risk.gross_pnl(t["direction"], entry, exit_px, qty),
                 risk.net_pnl(t["direction"], entry, exit_px, qty, fees, slip), res, t["id"]))
            out["closed"].append({"symbol": symbol, "strategy": t["strategy"], "result": res, "exit": exit_px})
        if pos_ids:
            c.execute("UPDATE strategy_positions SET status='CLOSED', updated_at=NOW() WHERE id = ANY(%s)",
                      (list(pos_ids),))


def close_symbol(user_id, exchange, symbol: str, service: str) -> dict:
    """Manual close (Telegram / dashboard): market reduce-only order for the whole exchange position."""
    st = Settings(user_id)
    pos = next((p for p in exchange.positions() if p["symbol"] == symbol and p["size"] > 0), None)
    if pos:
        side = "Sell" if pos["side"] == "Buy" else "Buy"
        exchange.place_order(symbol, side, pos["size"], "Market", reduce_only=True)
    exit_px = exchange.ticker(symbol)["last"]
    trades = db.fetch("SELECT * FROM trades WHERE user_id=%s AND symbol=%s AND status='OPEN'", (user_id, symbol))
    out: dict = {"closed": []}
    if trades:
        _close_symbol_trades(user_id, st, exchange, symbol, trades, out, result="MANUAL CLOSE", exit_px=exit_px)
    db.audit(user_id, service, "manual_close", symbol=symbol, response={"exit": exit_px, "trades": len(trades)})
    return {"symbol": symbol, "exit": exit_px, "closed": len(out["closed"])}


# --- open positions: partial TP + trailing --------------------------------------------------------
def _manage_open(user_id, st: Settings, exchange, tg, symbol: str, ex_pos: dict, out: dict) -> None:
    mark = ex_pos["mark_price"]
    for p in db.fetch("SELECT * FROM strategy_positions WHERE user_id=%s AND symbol=%s AND status='OPEN'",
                      (user_id, symbol)):
        name, d = p["strategy"], p["direction"]
        avg = float(p["average_entry_price"])
        atr_v = float(p["atr"] or 0)
        tp = float(p["current_tp"]) if p["current_tp"] is not None else None
        inst = exchange.instrument(symbol)
        dist = st.snum(name, "trail_distance", 1.8) * atr_v
        partial_on = st.sflag(name, "partial_tp_enabled")
        trailing_on = st.sflag(name, "trailing_enabled") or partial_on
        new_sl = None

        if partial_on and not p["partial_tp_hit"] and tp is not None and atr_v:
            frac = 1.0 if name == "capitulation_absorber" else 0.5  # capitulation: partial at the full TP
            target = risk.partial_target(d, avg, tp, frac)
            if risk.reached(d, mark, target):
                pct = st.snum(name, "partial_tp_percent", 50) / 100
                close_qty = round_step(float(p["total_quantity"]) * pct, inst["qty_step"])
                if close_qty >= inst["min_qty"]:
                    exchange.place_order(symbol, "Sell" if d == "LONG" else "Buy", close_qty, "Market",
                                         reduce_only=True)
                    _record_partial(user_id, st, p, close_qty, mark)
                    level = risk.trail_level(d, mark, dist, avg) if dist else avg  # never worse than breakeven
                    new_sl = round_price(level, inst["tick_size"])
                    db.execute(
                        """UPDATE strategy_positions SET partial_tp_hit=true, total_quantity=total_quantity-%s,
                             trail_stop_level=%s, current_sl=%s, updated_at=NOW() WHERE id=%s""",
                        (close_qty, new_sl, new_sl, p["id"]))
                    exchange.set_trading_stop(symbol, stop_loss=new_sl)
                    out["partials"].append({"symbol": symbol, "strategy": name, "qty": close_qty, "price": mark})
                    tg.send(f"🎯 {STRATEGY_LABELS.get(name, name)} {d} {symbol}: PARTIAL TP HIT @ {mark:g}, "
                            f"closed {close_qty:g}. SL → {new_sl:g} (breakeven+)")
                    continue

        if not trailing_on or not atr_v:
            continue
        profit = (mark - avg) if d == "LONG" else (avg - mark)
        current = float(p["trail_stop_level"]) if p["trail_stop_level"] is not None else None
        if name == "trend_rider":
            if profit < 1.5 * atr_v and current is None:
                continue
            h = exchange.klines(symbol, "1h", 120)
            line, _ = ind.supertrend(h.high, h.low, h.close, 10, 3.0)
            level = float(line[-1])
            if current is not None:
                level = max(current, level) if d == "LONG" else min(current, level)
        else:
            if current is None and not p["partial_tp_hit"] and profit < dist:
                continue
            level = risk.trail_level(d, mark, dist, current)
        level = round_price(level, inst["tick_size"])
        sl_now = float(p["current_sl"]) if p["current_sl"] is not None else None
        improves = sl_now is None or (level > sl_now if d == "LONG" else level < sl_now)
        if improves and not risk.stop_hit(d, mark, level):
            exchange.set_trading_stop(symbol, stop_loss=level)
            db.execute("UPDATE strategy_positions SET trail_stop_level=%s, current_sl=%s, updated_at=NOW() WHERE id=%s",
                       (level, level, p["id"]))
            db.execute("UPDATE trades SET stop_loss=%s WHERE aggregated_position_id=%s AND status='OPEN'",
                       (level, p["id"]))
            out["trailing"].append({"symbol": symbol, "strategy": name, "level": level})


def _record_partial(user_id, st: Settings, p: dict, close_qty: float, price: float) -> None:
    """Split the closed fraction out of the open trade rows into CLOSED 'PARTIAL TP HIT' rows."""
    fees, slip = st.num("fees_bps", 5), st.num("slippage_bps", 5)
    trades = db.fetch("SELECT * FROM trades WHERE aggregated_position_id=%s AND status='OPEN'", (p["id"],))
    total = sum(float(t["actual_quantity"] or 0) for t in trades) or 1.0
    with db.conn() as c:
        for t in trades:
            q = float(t["actual_quantity"] or 0) * close_qty / total
            entry = float(t["entry_price"])
            c.execute("UPDATE trades SET actual_quantity=actual_quantity-%s WHERE id=%s", (q, t["id"]))
            c.execute(
                """INSERT INTO trades (user_id, created_at, symbol, direction, strategy, entry_price, stop_loss,
                     take_profit, order_id, status, exit_price, pnl, net_pnl, result, reversed, original_direction,
                     trading_mode, signal_score, signal_regime, aggregated_position_id, cost_usdt, leverage,
                     actual_quantity, close_notification_sent, closed_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'CLOSED',%s,%s,%s,'PARTIAL TP HIT',%s,%s,'live',%s,%s,%s,%s,%s,%s,
                     true,NOW())""",
                (user_id, t["created_at"], t["symbol"], t["direction"], t["strategy"], entry, t["stop_loss"],
                 t["take_profit"], t["order_id"], price, risk.gross_pnl(t["direction"], entry, price, q),
                 risk.net_pnl(t["direction"], entry, price, q, fees, slip), t["reversed"], t["original_direction"],
                 t["signal_score"], t["signal_regime"], p["id"], t["cost_usdt"], t["leverage"], q))


# --- notifications --------------------------------------------------------------------------------
def send_close_notifications(user_id, tg) -> int:
    """Claim un-notified closed trades atomically so each close is announced exactly once,
    even if two monitor invocations overlap."""
    with db.conn() as c:
        rows = c.execute(
            """UPDATE trades SET close_notification_sent=true
               WHERE id IN (SELECT id FROM trades WHERE user_id=%s AND status='CLOSED'
                            AND close_notification_sent=false FOR UPDATE SKIP LOCKED)
               RETURNING *""", (user_id,)).fetchall()
    for t in rows:
        net = float(t["net_pnl"] or 0)
        icon = "✅" if net >= 0 else "🔴"
        tg.send(f"{icon} <b>{STRATEGY_LABELS.get(t['strategy'], t['strategy'])}</b> {t['direction']} {t['symbol']} "
                f"closed — {t['result']}\nEntry: {float(t['entry_price']):g}  Exit: {float(t['exit_price']):g}\n"
                f"Net P&L: {net:+.2f} USDT")
    return len(rows)
