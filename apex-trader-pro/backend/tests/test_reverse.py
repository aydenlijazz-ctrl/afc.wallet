from datetime import datetime, timedelta, timezone

from apex import db, reverse
from apex.settings import Settings, save


def add_trade(uid, status="OPEN", direction="LONG", net=None, symbol="BTCUSDT", qty=1.0, entry=100.0,
              created=None):
    db.execute("""INSERT INTO trades (user_id, created_at, symbol, direction, strategy, entry_price, stop_loss,
                  take_profit, status, net_pnl, actual_quantity, result) VALUES
                  (%s,%s,%s,%s,'wide_atr',%s,%s,%s,%s,%s,%s,%s)""",
               (uid, created or datetime.now(timezone.utc), symbol, direction, entry, entry - 2, entry + 4, status,
                net, qty, "SL HIT" if status == "CLOSED" else None))


def test_adaptive_reverse_flips_positions(uid, ex, tg):
    switch = datetime.now(timezone.utc) - timedelta(hours=1)
    save(uid, {"strat_wide_atr_enabled": "true", "strat_wide_atr_adaptive_auto_reverse_enabled": "true",
               "strat_wide_atr_adaptive_auto_reverse_threshold": "50",
               "strat_wide_atr_last_reverse_switch": switch.isoformat()})
    add_trade(uid, "CLOSED", net=-40)
    add_trade(uid, "CLOSED", net=-100, created=switch - timedelta(hours=2))  # before the switch: ignored
    add_trade(uid, "OPEN", "LONG", qty=1.0, entry=100)
    ex.prices["BTCUSDT"] = 88.0
    ex._fill("BTCUSDT", "Buy", 1.0, 100.0, False)
    st = Settings(uid)
    events = reverse.check_adaptive(uid, st, ex, tg, "test")
    assert events and events[0]["flipped"] == 1 and events[0]["reverse_enabled"] is True
    assert abs(events[0]["total_loss"] - (-52.0)) < 1e-9  # -40 realized + -12 unrealized
    o = ex.orders[-1]
    assert o["side"] == "Sell" and o["qty"] == 2.0 and o["type"] == "Market"
    assert ex.positions_["BTCUSDT"] == {"side": "Sell", "size": 1.0, "avg_price": 88.0}  # flipped, not just closed
    old = db.fetch_one("SELECT * FROM trades WHERE result='REVERSED'")
    assert old["status"] == "CLOSED" and float(old["exit_price"]) == 88.0
    new = db.fetch_one("SELECT * FROM trades WHERE status='OPEN'")
    assert new["direction"] == "SHORT" and new["reversed"] and new["original_direction"] == "LONG"
    assert float(new["stop_loss"]) == 90.0 and float(new["take_profit"]) == 84.0
    assert Settings(uid).sflag("wide_atr", "reverse_enabled")
    log = db.fetch_one("SELECT * FROM adaptive_reverse_log")
    assert log["action"] == "REVERSE_AND_FLIP" and log["new_reverse_state"] is True
    assert "accumulated loss 52.00 USDT reached threshold 50.00 USDT. All positions REVERSED. Reverse Mode ON" in tg.sent[0]
    # counters restart after the switch
    assert reverse.check_adaptive(uid, Settings(uid), ex, tg, "test") == []


def test_adaptive_reverse_below_threshold(uid, ex, tg):
    save(uid, {"strat_wide_atr_enabled": "true", "strat_wide_atr_adaptive_auto_reverse_enabled": "true",
               "strat_wide_atr_adaptive_auto_reverse_threshold": "50",
               "strat_wide_atr_adaptive_auto_reverse_include_unrealized": "false",
               "strat_wide_atr_last_reverse_switch": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()})
    add_trade(uid, "CLOSED", net=-49)
    assert reverse.check_adaptive(uid, Settings(uid), ex, tg, "test") == []


def test_daily_auto_reverse_and_reset(uid, tg):
    save(uid, {"strat_wide_atr_enabled": "true", "strat_wide_atr_auto_reverse_enabled": "true",
               "strat_wide_atr_auto_reverse_daily_threshold": "30"})
    add_trade(uid, "CLOSED", net=-35)
    db.execute("UPDATE trades SET closed_at=NOW()")
    assert reverse.check_daily(uid, Settings(uid), tg) == ["wide_atr"]
    assert Settings(uid).sflag("wide_atr", "reverse_enabled")
    assert reverse.check_daily(uid, Settings(uid), tg) == []  # once per day
    assert reverse.reset_daily(uid, Settings(uid)) == ["wide_atr"]
    assert not Settings(uid).sflag("wide_atr", "reverse_enabled")
    actions = [r["action"] for r in db.fetch("SELECT action FROM auto_reverse_log ORDER BY created_at")]
    assert actions == ["TOGGLE_ON", "DAILY_RESET"]
