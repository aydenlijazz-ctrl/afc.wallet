"""run-apex-hybrid: the signal engine (Cloud Scheduler, every minute)."""
from __future__ import annotations

import logging
from datetime import datetime

from . import db, reverse, risk
from .bybit import round_price, round_step
from .settings import STRATEGY_LABELS, Settings
from .strategies import REGISTRY, SCALING_STRATEGIES, Context, Signal, load_params

log = logging.getLogger(__name__)
SERVICE = "run-apex-hybrid"

# exchange TP is left off for strategies whose take-profit is a partial close handled by the monitor
MONITOR_MANAGED_TP = {"capitulation_absorber"}


def run(user_id, exchange, tg, now: datetime | None = None) -> dict:
    st = Settings(user_id)
    summary: dict = {"signals": [], "opened": [], "skipped": [], "errors": [], "reversals": []}
    summary["reversals"] = reverse.check_adaptive(user_id, st, exchange, tg, SERVICE)
    reverse.check_daily(user_id, st, tg)

    open_trades = reverse.open_trades(user_id)
    positions = {(p["strategy"], p["symbol"]): p for p in db.fetch(
        "SELECT * FROM strategy_positions WHERE user_id=%s AND status IN ('OPEN','PENDING')", (user_id,))}
    # one entry per open exchange position (symbol); used by the correlation filter
    open_symbols = sorted({t["symbol"] for t in open_trades})
    busy = {(t["strategy"], t["symbol"]) for t in open_trades}
    cache: dict = {}
    regimes: dict[str, str] = {}
    min_score = int(st.num("min_signal_score", 60))
    trans_min = int(st.num("transitional_min_score", 75))

    for name in st.enabled_strategies():
        if not st.in_active_hours(name, now):
            continue
        params = load_params(name, st.s(name, "params") if name == "adaptive_nexus" else st.s(name, "definition"))
        if name == "custom" and not params:
            continue
        symbols = st.symbols(name)
        if name == "custom" and params.get("symbols"):
            symbols = symbols or [s.upper() for s in params["symbols"]]
        for symbol in symbols:
            pos = positions.get((name, symbol))
            if pos and (name not in SCALING_STRATEGIES or pos["status"] == "PENDING"):
                continue
            if not pos and (name, symbol) in busy:
                continue
            if not pos and st.flag("one_position_per_symbol") and symbol in open_symbols:
                continue  # Bybit one-way mode nets positions per symbol across strategies
            ctx = Context(exchange, symbol, cache, position=pos, params=params)
            try:
                sig = REGISTRY[name](ctx)
            except Exception as exc:
                log.exception("strategy %s %s failed", name, symbol)
                summary["errors"].append(f"{name}/{symbol}: {exc}")
                continue
            if sig is None:
                continue
            if sig.is_addition:
                summary["opened"].append(_add_to_position(user_id, st, exchange, tg, sig, pos))
                continue

            if st.sflag(name, "reverse_enabled"):
                risk.apply_reverse(sig)
            sig.score = risk.quality_score(sig)
            summary["signals"].append(_brief(sig))
            if sig.score < min_score:
                summary["skipped"].append({**_brief(sig), "reason": f"score {sig.score} < {min_score}"})
                continue
            if symbol not in regimes:
                regimes[symbol] = risk.market_regime(ctx.candles("1h"))
            sig.regime = regimes[symbol]
            allowed = [r.strip() for r in (st.s(name, "allowed_regimes") or "").split(",") if r.strip()]
            ok, why = risk.regime_allows(sig.regime, allowed, sig.score, trans_min)
            if not ok:
                summary["skipped"].append({**_brief(sig), "reason": why})
                continue
            if not risk.correlation_allows(symbol, open_symbols):
                summary["skipped"].append({**_brief(sig), "reason": f"correlation tier {risk.tier(symbol)} cap"})
                continue
            result = open_position(user_id, st, exchange, tg, sig)
            if result.get("status") in ("OPEN", "PENDING"):
                open_symbols.append(symbol)
                busy.add((name, symbol))
                summary["opened"].append(result)
            else:
                summary["skipped"].append({**_brief(sig), "reason": result.get("reason", "failed")})
    return summary


def _brief(sig: Signal) -> dict:
    return {"strategy": sig.strategy, "symbol": sig.symbol, "direction": sig.direction, "entry": sig.entry,
            "sl": sig.sl, "tp": sig.tp, "score": sig.score, "regime": sig.regime, "reversed": sig.reversed}


def _qty(exchange, st: Settings, sig: Signal, price: float) -> tuple[float, float, float, dict]:
    inst = exchange.instrument(sig.symbol)
    cost = st.snum(sig.strategy, "cost", 20) * sig.size_fraction
    lev = max(1.0, min(st.snum(sig.strategy, "leverage", 5), inst.get("max_leverage", 100)))
    qty = round_step(cost * lev / price, inst["qty_step"])
    return qty, cost, lev, inst


def open_position(user_id, st: Settings, exchange, tg, sig: Signal) -> dict:
    name, symbol = sig.strategy, sig.symbol
    if not st.flag("live_trading_armed"):
        db.audit(user_id, SERVICE, "signal_not_armed", symbol=symbol, strategy=name, request=_brief(sig))
        return {**_brief(sig), "status": "NOT_ARMED", "reason": "live trading is not armed"}
    is_limit = sig.order_type == "Limit"
    try:
        price = sig.entry if is_limit else exchange.ticker(symbol)["last"]
        qty, cost, lev, inst = _qty(exchange, st, sig, price)
        if qty < inst["min_qty"]:
            raise ValueError(f"quantity {qty} below minimum {inst['min_qty']} (raise cost or leverage)")
        # keep the strategy's SL/TP distances relative to the actual entry price
        shift = price - sig.entry
        sl = round_price(sig.sl + shift, inst["tick_size"])
        tp = round_price(sig.tp + shift, inst["tick_size"])
        exchange_tp = None if name in MONITOR_MANAGED_TP else tp
        side = "Buy" if sig.direction == "LONG" else "Sell"
        exchange.set_leverage(symbol, lev)
        if is_limit:
            order_id = exchange.place_order(symbol, side, qty, "Limit", price=round_price(price, inst["tick_size"]),
                                            take_profit=exchange_tp, stop_loss=sl)
        else:
            order_id = exchange.place_order(symbol, side, qty, "Market")
            exchange.set_trading_stop(symbol, take_profit=exchange_tp, stop_loss=sl)
    except Exception as exc:
        db.execute(
            """INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit, status,
                 reversed, original_direction, signal_score, signal_regime) VALUES
                 (%s,%s,%s,%s,%s,%s,%s,'FAILED',%s,%s,%s,%s)""",
            (user_id, symbol, sig.direction, name, sig.entry, sig.sl, sig.tp, sig.reversed, sig.original_direction,
             sig.score, sig.regime))
        db.audit(user_id, SERVICE, "open_position", symbol=symbol, strategy=name, request=_brief(sig),
                 response={"error": str(exc)}, success=False)
        tg.send(f"❌ {STRATEGY_LABELS[name]} {sig.direction} {symbol} failed: {exc}")
        return {**_brief(sig), "status": "FAILED", "reason": str(exc)}

    status = "PENDING" if is_limit else "OPEN"
    with db.conn() as c:
        pos_id = c.execute(
            """INSERT INTO strategy_positions (user_id, strategy, symbol, direction, total_quantity, average_entry_price,
                 last_entry_price, current_sl, current_tp, status, atr) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING id""",
            (user_id, name, symbol, sig.direction, qty, price, price, sl, tp, status, sig.atr)).fetchone()["id"]
        trade_id = c.execute(
            """INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit, order_id,
                 status, reversed, original_direction, trading_mode, signal_score, signal_regime,
                 aggregated_position_id, cost_usdt, leverage, actual_quantity)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'OPEN',%s,%s,'live',%s,%s,%s,%s,%s,%s) RETURNING id""",
            (user_id, symbol, sig.direction, name, price, sl, tp, order_id, sig.reversed, sig.original_direction,
             sig.score, sig.regime, pos_id, cost, lev, qty)).fetchone()["id"]
    db.audit(user_id, SERVICE, "open_position", symbol=symbol, strategy=name, request=_brief(sig),
             response={"order_id": order_id, "qty": qty, "price": price})
    rev = f" (reversed from {sig.original_direction})" if sig.reversed else ""
    tg.send(f"🟢 <b>{STRATEGY_LABELS[name]}</b> {'LIMIT ' if is_limit else ''}{sig.direction} {symbol}{rev}\n"
            f"Entry: {price:g}  Qty: {qty:g}  Lev: {lev:g}x\nSL: {sl:g}  TP: {tp:g}\n"
            f"Score: {sig.score}  Regime: {sig.regime}")
    return {**_brief(sig), "status": status, "trade_id": str(trade_id), "order_id": order_id, "qty": qty,
            "entry": price, "sl": sl, "tp": tp}


def _add_to_position(user_id, st: Settings, exchange, tg, sig: Signal, pos: dict) -> dict:
    name, symbol = sig.strategy, sig.symbol
    if not st.flag("live_trading_armed"):
        return {**_brief(sig), "status": "NOT_ARMED"}
    try:
        price = exchange.ticker(symbol)["last"]
        qty, cost, lev, inst = _qty(exchange, st, sig, price)
        if qty < inst["min_qty"]:
            raise ValueError(f"quantity {qty} below minimum {inst['min_qty']}")
        side = "Buy" if sig.direction == "LONG" else "Sell"
        order_id = exchange.place_order(symbol, side, qty, "Market")
        total = float(pos["total_quantity"]) + qty
        avg = (float(pos["average_entry_price"]) * float(pos["total_quantity"]) + price * qty) / total
        sgn = 1 if sig.direction == "LONG" else -1
        atr_v = float(pos["atr"] or sig.atr)
        if name == "capitulation_absorber":
            sl, tp = price - sgn * 3 * atr_v, avg + sgn * 2.5 * atr_v
        else:
            sl, tp = avg - abs(sig.entry - sig.sl) * sgn, avg + abs(sig.tp - sig.entry) * sgn
        sl, tp = round_price(sl, inst["tick_size"]), round_price(tp, inst["tick_size"])
        exchange.set_trading_stop(symbol, take_profit=None if name in MONITOR_MANAGED_TP else tp, stop_loss=sl)
    except Exception as exc:
        db.audit(user_id, SERVICE, "add_to_position", symbol=symbol, strategy=name, response={"error": str(exc)},
                 success=False)
        tg.send(f"❌ {STRATEGY_LABELS[name]} add #{int(pos['addition_count']) + 1} {symbol} failed: {exc}")
        return {**_brief(sig), "status": "FAILED", "reason": str(exc)}
    with db.conn() as c:
        c.execute(
            """UPDATE strategy_positions SET total_quantity=%s, average_entry_price=%s, last_entry_price=%s,
                 addition_count=addition_count+1, current_sl=%s, current_tp=%s, updated_at=NOW() WHERE id=%s""",
            (total, avg, price, sl, tp, pos["id"]))
        c.execute("UPDATE trades SET stop_loss=%s, take_profit=%s WHERE aggregated_position_id=%s AND status='OPEN'",
                  (sl, tp, pos["id"]))
        c.execute(
            """INSERT INTO trades (user_id, symbol, direction, strategy, entry_price, stop_loss, take_profit, order_id,
                 status, trading_mode, aggregated_position_id, cost_usdt, leverage, actual_quantity, signal_score)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'OPEN','live',%s,%s,%s,%s,%s)""",
            (user_id, symbol, sig.direction, name, price, sl, tp, order_id, pos["id"], cost, lev, qty, sig.score))
    n = int(pos["addition_count"]) + 1
    tg.send(f"➕ <b>{STRATEGY_LABELS[name]}</b> entry #{n} {sig.direction} {symbol} @ {price:g} qty {qty:g}\n"
            f"Avg: {avg:g}  SL: {sl:g}  TP: {tp:g}")
    return {**_brief(sig), "status": "OPEN", "addition": n, "qty": qty, "entry": price}

