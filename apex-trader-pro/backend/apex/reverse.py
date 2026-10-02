"""Adaptive auto-reverse with position flip, and the simpler daily auto-reverse."""
from __future__ import annotations

from datetime import datetime, timezone

from . import db
from .settings import STRATEGY_LABELS, Settings


def _switch_time(st: Settings, name: str) -> datetime:
    raw = st.s(name, "last_reverse_switch")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    # first run: start counting now
    now = datetime.now(timezone.utc)
    st.set(f"strat_{name}_last_reverse_switch", now.isoformat())
    return now


def open_trades(user_id, strategy: str | None = None) -> list[dict]:
    if strategy:
        return db.fetch("SELECT * FROM trades WHERE user_id=%s AND status='OPEN' AND strategy=%s ORDER BY created_at",
                        (user_id, strategy))
    return db.fetch("SELECT * FROM trades WHERE user_id=%s AND status='OPEN' ORDER BY created_at", (user_id,))


def unrealized(trades: list[dict], marks: dict[str, float]) -> float:
    total = 0.0
    for t in trades:
        mark = marks.get(t["symbol"])
        qty = float(t["actual_quantity"] or 0)
        if mark is None or not qty:
            continue
        entry = float(t["entry_price"])
        total += (mark - entry) * qty if t["direction"] == "LONG" else (entry - mark) * qty
    return total


def check_adaptive(user_id, st: Settings, exchange, tg, service: str) -> list[dict]:
    """Returns a list of reversal events (one per strategy that crossed its threshold)."""
    events = []
    marks: dict[str, float] | None = None
    for name in st.enabled_strategies():
        if not st.sflag(name, "adaptive_auto_reverse_enabled"):
            continue
        threshold = abs(st.snum(name, "adaptive_auto_reverse_threshold", 50))
        since = _switch_time(st, name)
        realized = float(db.fetch_one(
            """SELECT COALESCE(SUM(net_pnl),0) AS s FROM trades
               WHERE user_id=%s AND strategy=%s AND status='CLOSED' AND created_at >= %s""",
            (user_id, name, since))["s"])
        trades = open_trades(user_id, name)
        unreal = 0.0
        if st.sflag(name, "adaptive_auto_reverse_include_unrealized") and trades:
            if marks is None:
                marks = {p["symbol"]: p["mark_price"] for p in exchange.positions() if p["size"]}
            unreal = unrealized(trades, marks)
        total = realized + unreal
        if total > -threshold:
            continue
        flipped, errors = flip_positions(user_id, st, exchange, trades, service)
        new_state = not st.sflag(name, "reverse_enabled")
        st.set(f"strat_{name}_reverse_enabled", "true" if new_state else "false")
        st.set(f"strat_{name}_last_reverse_switch", datetime.now(timezone.utc).isoformat())
        db.execute(
            """INSERT INTO adaptive_reverse_log (user_id, strategy, realized_loss, unrealized_loss, total_loss,
                 threshold, action, new_reverse_state, details) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (user_id, name, realized, unreal, total, threshold, "REVERSE_AND_FLIP", new_state,
             f"flipped={flipped}; errors={'; '.join(errors) or 'none'}"))
        tg.send(f"⚠️ {STRATEGY_LABELS[name]}: accumulated loss {abs(total):.2f} USDT reached threshold "
                f"{threshold:.2f} USDT. All positions REVERSED. Reverse Mode {'ON' if new_state else 'OFF'}."
                + (f"\nErrors: {'; '.join(errors)}" if errors else ""))
        events.append({"strategy": name, "total_loss": total, "flipped": flipped, "reverse_enabled": new_state})
    return events


def flip_positions(user_id, st: Settings, exchange, trades: list[dict], service: str) -> tuple[int, list[str]]:
    """Flip every open trade with one market order of 2x its size (one-way mode: 1x closes, 1x opens).

    Note: sending only 1x the size, as a naive reading of "same qty" suggests, would just close the
    position on Bybit instead of flipping it.
    """
    flipped, errors = 0, []
    fees, slip = st.num("fees_bps", 5), st.num("slippage_bps", 5)
    from .risk import net_pnl, gross_pnl  # local import to avoid a cycle

    for t in trades:
        qty = float(t["actual_quantity"] or 0)
        if not qty:
            continue
        old_dir = t["direction"]
        new_dir = "SHORT" if old_dir == "LONG" else "LONG"
        side = "Sell" if old_dir == "LONG" else "Buy"
        try:
            order_id = exchange.place_order(t["symbol"], side, qty * 2, "Market")
            px = exchange.ticker(t["symbol"])["last"]
            entry = float(t["entry_price"])
            # mirror the old SL/TP distances around the flip price
            sl_d, tp_d = abs(entry - float(t["stop_loss"])), abs(float(t["take_profit"]) - entry)
            sgn = 1 if new_dir == "LONG" else -1
            sl, tp = px - sgn * sl_d, px + sgn * tp_d
            exchange.set_trading_stop(t["symbol"], take_profit=tp, stop_loss=sl)
            with db.conn() as c:
                c.execute(
                    """UPDATE trades SET status='CLOSED', result='REVERSED', exit_price=%s, pnl=%s, net_pnl=%s,
                         closed_at=NOW(), close_notification_sent=true WHERE id=%s""",
                    (px, gross_pnl(old_dir, entry, px, qty), net_pnl(old_dir, entry, px, qty, fees, slip), t["id"]))
                c.execute(
                    """INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit,
                         order_id, status, reversed, original_direction, trading_mode, signal_score, signal_regime,
                         aggregated_position_id, cost_usdt, leverage, actual_quantity)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'OPEN',true,%s,'live',%s,%s,%s,%s,%s,%s)""",
                    (user_id, t["symbol"], new_dir, t["strategy"], px, sl, tp, order_id, old_dir, t["signal_score"],
                     t["signal_regime"], t["aggregated_position_id"], t["cost_usdt"], t["leverage"], qty))
                if t["aggregated_position_id"]:
                    c.execute(
                        """UPDATE strategy_positions SET direction=%s, average_entry_price=%s, last_entry_price=%s,
                             current_sl=%s, current_tp=%s, partial_tp_hit=false, trail_stop_level=NULL,
                             updated_at=NOW() WHERE id=%s""",
                        (new_dir, px, px, sl, tp, t["aggregated_position_id"]))
            db.audit(user_id, service, "flip_position", symbol=t["symbol"], strategy=t["strategy"],
                     request={"side": side, "qty": qty * 2}, response={"order_id": order_id})
            flipped += 1
        except Exception as exc:  # keep flipping the others
            errors.append(f"{t['symbol']}: {exc}")
            db.audit(user_id, service, "flip_position", symbol=t["symbol"], strategy=t["strategy"],
                     response={"error": str(exc)}, success=False)
    return flipped, errors


def check_daily(user_id, st: Settings, tg) -> list[str]:
    """Daily auto-reverse: toggle reverse mode once per UTC day when daily P&L <= -threshold."""
    toggled = []
    for name in st.enabled_strategies():
        if not st.sflag(name, "auto_reverse_enabled"):
            continue
        if st.s(name, "auto_reverse_day") == datetime.now(timezone.utc).date().isoformat():
            continue
        threshold = abs(st.snum(name, "auto_reverse_daily_threshold", 30))
        daily = float(db.fetch_one(
            """SELECT COALESCE(SUM(net_pnl),0) AS s FROM trades WHERE user_id=%s AND strategy=%s
               AND status='CLOSED' AND closed_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'""",
            (user_id, name))["s"])
        if daily > -threshold:
            continue
        if st.s(name, "auto_reverse_base") is None or st.s(name, "auto_reverse_base") == "":
            st.set(f"strat_{name}_auto_reverse_base", st.s(name, "reverse_enabled") or "false")
        new_state = not st.sflag(name, "reverse_enabled")
        st.set(f"strat_{name}_reverse_enabled", str(new_state).lower())
        st.set(f"strat_{name}_auto_reverse_day", datetime.now(timezone.utc).date().isoformat())
        db.execute("INSERT INTO auto_reverse_log (user_id, strategy, daily_pnl, threshold, action) VALUES (%s,%s,%s,%s,%s)",
                   (user_id, name, daily, threshold, "TOGGLE_ON" if new_state else "TOGGLE_OFF"))
        tg.send(f"🔁 {STRATEGY_LABELS[name]}: daily P&L {daily:.2f} USDT ≤ -{threshold:.2f}. "
                f"Reverse Mode {'ON' if new_state else 'OFF'} for the rest of the day.")
        toggled.append(name)
    return toggled


def reset_daily(user_id, st: Settings) -> list[str]:
    """00:00 UTC: restore each strategy's reverse mode to its pre-toggle value."""
    restored = []
    for key, value in list(st.values.items()):
        if key.startswith("strat_") and key.endswith("_auto_reverse_base") and value not in (None, ""):
            name = key[len("strat_"):-len("_auto_reverse_base")]
            st.set(f"strat_{name}_reverse_enabled", value)
            st.set(key, "")
            st.set(f"strat_{name}_auto_reverse_day", "")
            db.execute("INSERT INTO auto_reverse_log (user_id, strategy, action) VALUES (%s,%s,%s)",
                       (user_id, name, "DAILY_RESET"))
            restored.append(name)
    return restored
