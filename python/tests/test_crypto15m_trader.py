from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import crypto15m
import crypto15m_trader as ct
import db
import kalshi_api
import trader
from config import merge_with_defaults




@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    dbfile = tmp_path / "c15-test.db"
    monkeypatch.setattr(db, "db_path", lambda: dbfile)
    db.init_db()
    return dbfile


@pytest.fixture
def env_demo(monkeypatch):
    monkeypatch.setattr(trader, "get_env", lambda: "demo")
    return "demo"


@pytest.fixture
def env_prod(monkeypatch):
    monkeypatch.setattr(trader, "get_env", lambda: "production")
    return "production"


@pytest.fixture
def cfg():
    c = merge_with_defaults({})
    c["kalshi_env"] = "demo"
    c["crypto15m_enabled"] = True
    c["crypto15m_entry_style"] = "taker"
    return c


def _live_cfg(cfg):
    """Production + armed: the only mode that places 15m orders now that paper is gone."""
    cfg["kalshi_env"] = "production"
    cfg["crypto15m_live"] = True
    return cfg


def run_async(coro):
    return asyncio.run(coro)


def signal_asset(asset="BTC", favorite="up", entry_cost=0.86, signal=True, ticker="KXBTC15M-T1"):
    close = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    up = 0.9 if favorite == "up" else 0.1
    return {
        "asset": asset, "series": f"KX{asset}15M", "spotUsd": 100.0,
        "open15mUsd": 100.0, "deltaUsd": 0.5, "hasMarket": True,
        "ticker": ticker, "closeTime": close, "minsLeft": 5.0,
        "upProb": up, "downProb": 1 - up,
        "favorite": favorite, "favoritePrice": 0.86, "entryCost": entry_cost,
        "yesBid": 0.85, "yesAsk": 0.87,
        "inWindow": True, "signal": signal, "openMarketCount": 1, "error": None,
    }


def _stub_snapshot(assets):
    async def _snap(_cfg):
        return {"assets": assets, "constants": {}, "fetchedAt": "",
                "spotOk": True, "spotSource": "stub"}
    return _snap




def test_direction_for_favorite():
    assert ct.direction_for_favorite("up") == "yes"
    assert ct.direction_for_favorite("down") == "no"


def test_entry_limit_cents_marks_up_and_clamps():
    assert ct.entry_limit_cents(0.86, 0.02) == 88
    assert ct.entry_limit_cents(0.98, 0.02) == 99


def test_side_prob_from_market_respects_direction():
    m = {"yes_bid_dollars": 0.29, "yes_ask_dollars": 0.31}
    assert ct.side_prob_from_market(m, "yes") == pytest.approx(0.30)
    assert ct.side_prob_from_market(m, "no") == pytest.approx(0.70)
    assert ct.side_prob_from_market(None, "yes") is None


def test_should_enter_gate_matrix(cfg):
    a = signal_asset()
    assert ct.should_enter(a, cfg, has_open=False, open_count=0) == (True, "ok")
    assert ct.should_enter(a, cfg, has_open=True, open_count=0)[0] is False
    assert ct.should_enter(a, cfg, has_open=False, open_count=7)[0] is False
    assert ct.should_enter(signal_asset(signal=False), cfg, has_open=False, open_count=0) == (False, "no signal")

    off = dict(cfg)
    off["crypto15m_enabled"] = False
    assert ct.should_enter(a, off, has_open=False, open_count=0) == (False, "disabled")


def test_should_stop_loss(cfg):
    pos = {"status": "filled", "filled_contracts": 1}
    assert ct.should_stop_loss(pos, 0.30, cfg) is True
    assert ct.should_stop_loss(pos, 0.55, cfg) is False
    assert ct.should_stop_loss(pos, None, cfg) is False
    assert ct.should_stop_loss({"status": "submitted", "filled_contracts": 1}, 0.1, cfg) is False


def test_compute_entry_contracts_fixed(cfg):
    cfg["crypto15m_sizing_mode"] = "fixed"
    cfg["crypto15m_order_size"] = 3
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=88, balance_usd=0, order_size=3) == 3
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=88, balance_usd=1000, order_size=3) == 3


def test_compute_entry_contracts_balance_pct(cfg):
    cfg["crypto15m_sizing_mode"] = "balance_pct"
    cfg["crypto15m_balance_pct"] = 0.10
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=50, balance_usd=100, order_size=1) == 20
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=50, balance_usd=0, order_size=4) == 4


def test_compute_entry_contracts_max_loss_cap(cfg):
    cfg["crypto15m_sizing_mode"] = "fixed"
    cfg["crypto15m_max_loss_pct"] = 0.05
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=50, balance_usd=100, order_size=100) == 10
    assert ct.compute_entry_contracts(cfg, entry_limit_cents=90, balance_usd=10, order_size=5) == 0


def test_balance_pct_entry_sizes_the_live_order(fresh_db, env_prod, cfg, monkeypatch):
    _live_cfg(cfg)
    cfg["crypto15m_sizing_mode"] = "balance_pct"
    cfg["crypto15m_balance_pct"] = 0.10

    async def _bank(_cfg, _authed):
        return 100.0
    monkeypatch.setattr(ct, "_bankroll_usd", _bank)
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=True))

    assert len(calls) == 1
    assert calls[0]["count"] == 11
    with db.get_db() as conn:
        r = db.get_open_crypto15m(conn, "production")[0]
    assert r["target_contracts"] == 11
    assert r["status"] == "submitted"




def test_disabled_does_nothing(fresh_db, env_demo, cfg, monkeypatch):
    cfg["crypto15m_enabled"] = False
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    out = run_async(ct.run_tick(cfg, authed=False))
    assert out == []
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0


def test_demo_opens_no_positions(fresh_db, env_demo, cfg, monkeypatch):
    # Demo can't trade 15m markets and paper simulation was removed, so a
    # signal on demo opens nothing — the executor only monitors.
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    out = run_async(ct.run_tick(cfg, authed=True))
    assert out == []
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0


def test_one_position_per_asset(fresh_db, env_prod, cfg, monkeypatch):
    _live_cfg(cfg)
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    _capture_orders(monkeypatch)

    async def _open(_ticker):
        return {"yes_bid_dollars": 0.85, "yes_ask_dollars": 0.87, "status": "open", "result": ""}
    monkeypatch.setattr(kalshi_api, "fetch_market", _open)

    run_async(ct.run_tick(cfg, authed=True))
    run_async(ct.run_tick(cfg, authed=True))
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "production") == 1


def test_contrarian_mode_buys_the_underdog(fresh_db, env_prod, cfg, monkeypatch):
    _live_cfg(cfg)
    cfg["crypto15m_direction_mode"] = "contrarian"
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset(favorite="up")]))
    _capture_orders(monkeypatch)
    run_async(ct.run_tick(cfg, authed=True))
    with db.get_db() as conn:
        r = db.get_open_crypto15m(conn, "production")[0]
    assert r["side"] == "down"
    assert r["direction"] == "no"
    assert r["entry_limit_cents"] == 16




def _capture_orders(monkeypatch):
    calls = []

    async def _place(**kw):
        calls.append(kw)
        return {"order": {"order_id": "ord-1", "status": "resting"}}

    monkeypatch.setattr(kalshi_api, "place_limit_order", _place)
    return calls


def test_live_gate_is_independent_of_main_bot(fresh_db, env_prod, cfg, monkeypatch):
    cfg["crypto15m_live"] = True
    cfg["enable_trading"] = False
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=True))

    assert len(calls) == 1
    assert calls[0]["action"] == "buy"
    with db.get_db() as conn:
        r = db.get_open_crypto15m(conn, "production")[0]
    assert r["status"] == "submitted"
    assert r["dry_run"] == 0
    assert r["kalshi_order_id"] == "ord-1"


def test_main_bot_live_does_not_arm_15m(fresh_db, env_demo, cfg, monkeypatch):
    cfg["crypto15m_live"] = False
    cfg["enable_trading"] = True
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=True))

    assert calls == []
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0


def test_live_armed_without_auth_does_not_trade(fresh_db, env_demo, cfg, monkeypatch):
    cfg["crypto15m_live"] = True
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=False))

    assert calls == []
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0


def test_demo_never_trades_even_when_live_armed(fresh_db, env_demo, cfg, monkeypatch):
    async def _bal(_cfg, force=False):
        return 10_000, 0
    monkeypatch.setattr(trader, "refresh_balance", _bal)
    cfg["crypto15m_live"] = True
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=True))

    assert calls == []
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0

    st = run_async(ct.status(cfg, authed=True))
    assert st["liveSupported"] is False
    assert st["live"] is False
    assert st["liveArmed"] is True


def test_status_reports_live_armed_and_authed(fresh_db, env_prod, cfg, monkeypatch):
    async def _bal(_cfg, force=False):
        return 10_000, 0
    monkeypatch.setattr(trader, "refresh_balance", _bal)

    cfg["crypto15m_live"] = True
    st = run_async(ct.status(cfg, authed=True))
    assert st["live"] is True
    assert st["liveArmed"] is True
    assert st["authed"] is True

    st = run_async(ct.status(cfg, authed=False))
    assert st["live"] is False
    assert st["liveArmed"] is True
    assert st["authed"] is False




def test_failed_entry_resolves_immediately_and_blocks_retry(fresh_db, env_prod, cfg, monkeypatch):
    cfg["crypto15m_live"] = True

    async def _paused(**kw):
        raise RuntimeError("HTTP 409: exchange is paused")
    monkeypatch.setattr(kalshi_api, "place_limit_order", _paused)
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))

    run_async(ct.run_tick(cfg, authed=True))
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "production") == 0
        r = dict(conn.execute("SELECT * FROM crypto15m_positions").fetchone())
    assert r["status"] == "error"
    assert r["resolved"] == 1

    run_async(ct.run_tick(cfg, authed=True))
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM crypto15m_positions").fetchone()[0] == 1

    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset(ticker="KXBTC15M-T2")]))
    run_async(ct.run_tick(cfg, authed=True))
    with db.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM crypto15m_positions").fetchone()[0] == 2


def test_exiting_position_settles_when_sell_never_fills(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="exiting", direction="yes", target_contracts=1,
                    filled_contracts=1, cost_usd=0.88, exit_reason="stop_loss",
                    exit_kalshi_order_id="ord-x1", exit_filled_contracts=0,
                    close_time=_future())
    pid = pos["id"]

    canceled = []

    async def _order_unfilled(_kid):
        return {"order": {"fill_count_fp": "0", "remaining_count_fp": "1"}}

    async def _cancel(kid):
        canceled.append(kid)

    async def _settled_no(_ticker):
        return {"result": "no", "status": "finalized"}

    monkeypatch.setattr(kalshi_api, "get_order", _order_unfilled)
    monkeypatch.setattr(kalshi_api, "cancel_order", _cancel)
    monkeypatch.setattr(kalshi_api, "fetch_market", _settled_no)
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([]))

    run_async(ct.run_tick(cfg, authed=False))
    with db.get_db() as conn:
        assert db.count_open_crypto15m(conn, "demo") == 0
        r = dict(conn.execute("SELECT * FROM crypto15m_positions WHERE id=?", (pid,)).fetchone())
    assert r["status"] == "settled"
    assert r["resolved"] == 1
    assert r["exit_reason"] == "stop_loss"
    assert r["outcome_correct"] == 0
    assert r["pnl_usd"] == pytest.approx(-0.88)
    assert canceled == ["ord-x1"]


def test_legacy_stuck_error_row_is_swept(fresh_db, env_demo, cfg, monkeypatch):
    with db.get_db() as conn:
        pid = db.insert_crypto15m_position(conn, {
            "asset": "BNB", "series": "KXBNB15M", "ticker": "KXBNB15M-OLD",
            "side": "up", "direction": "yes", "target_contracts": 12,
            "entry_limit_cents": 90, "client_order_id": "c1",
            "close_time": "2026-06-10T15:15:00Z", "confidence": 90,
            "kalshi_env": "demo", "status": "error", "dry_run": False,
        })
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([]))
    run_async(ct.run_tick(cfg, authed=False))
    with db.get_db() as conn:
        r = dict(conn.execute("SELECT * FROM crypto15m_positions WHERE id=?", (pid,)).fetchone())
    assert r["resolved"] == 1
    assert r["status"] == "error"




def test_maker_limit_cents_joins_the_bid():
    assert ct.maker_limit_cents("up", 0.85, 0.87, 0.87) == 85
    assert ct.maker_limit_cents("down", 0.85, 0.87, 0.15) == 13
    assert ct.maker_limit_cents("up", None, None, 0.87) == 86
    assert ct.maker_limit_cents("up", None, None, 0.01) == 1


def test_live_maker_entry_places_resting_order_at_bid(fresh_db, env_prod, cfg, monkeypatch):
    cfg["crypto15m_entry_style"] = "maker"
    cfg["crypto15m_live"] = True
    monkeypatch.setattr(crypto15m, "snapshot", _stub_snapshot([signal_asset()]))
    calls = _capture_orders(monkeypatch)

    run_async(ct.run_tick(cfg, authed=True))

    assert len(calls) == 1
    assert calls[0]["price_cents"] == 85
    assert calls[0]["action"] == "buy"



_c15_seq = 0


def _seed_c15(**over) -> dict:
    global _c15_seq
    _c15_seq += 1
    n = _c15_seq
    row = {
        "asset": over.get("asset", "BTC"),
        "series": over.get("series", "KXBTC15M"),
        "ticker": over.get("ticker", f"KXBTC15M-T{n}"),
        "side": over.get("side", "up"),
        "direction": over.get("direction", "yes"),
        "target_contracts": over.get("target_contracts", 10),
        "filled_contracts": over.get("filled_contracts", 0),
        "cost_usd": over.get("cost_usd", 0.0),
        "entry_limit_cents": over.get("entry_limit_cents", 88),
        "client_order_id": f"co-{n}",
        "kalshi_order_id": over.get("kalshi_order_id"),
        "status": over.get("status", "submitted"),
        "exit_reason": over.get("exit_reason"),
        "close_time": over.get("close_time", ""),
        "kalshi_env": over.get("kalshi_env", "demo"),
        "dry_run": over.get("dry_run", False),
    }
    post = {k: over[k] for k in
            ("exit_kalshi_order_id", "exit_filled_contracts", "proceeds_usd", "avg_entry_cents")
            if k in over}
    with db.get_db() as conn:
        pid = db.insert_crypto15m_position(conn, row)
        if post:
            db.update_crypto15m_position(conn, pid, **post)
        return db.fetch_crypto15m_by_id(conn, pid)


def _order(filled, remaining, cost_dollars, status="resting") -> dict:
    return {"order": {
        "fill_count_fp": f"{filled}", "remaining_count_fp": f"{remaining}",
        "taker_fill_cost_dollars": f"{cost_dollars}", "maker_fill_cost_dollars": "0",
        "status": status,
    }}


def _future():
    return (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _past():
    return (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_partial_entry_keeps_polling_then_completes(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="submitted", kalshi_order_id="OID-E",
                    target_contracts=10, filled_contracts=0, close_time=_future())

    async def _get3(_kid):
        return _order(3, 7, 2.64)
    monkeypatch.setattr(kalshi_api, "get_order", _get3)

    out = run_async(ct._poll_entry(pos, cfg))
    assert out is None
    with db.get_db() as conn:
        r = db.fetch_crypto15m_by_id(conn, pos["id"])
    assert r["status"] == "submitted" and r["resolved"] == 0
    assert r["filled_contracts"] == 3
    assert r["cost_usd"] == pytest.approx(2.64)

    async def _get10(_kid):
        return _order(10, 0, 8.80, status="executed")
    monkeypatch.setattr(kalshi_api, "get_order", _get10)
    with db.get_db() as conn:
        r = db.fetch_crypto15m_by_id(conn, pos["id"])
    out = run_async(ct._poll_entry(r, cfg))
    assert out["status"] == "filled"
    assert out["filled_contracts"] == 10
    assert out["cost_usd"] == pytest.approx(8.80)


def test_partial_entry_then_expiry_keeps_filled_portion(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="submitted", kalshi_order_id="OID-E", target_contracts=10,
                    filled_contracts=3, cost_usd=2.64, close_time=_past())
    canceled = {"v": False}

    async def _cancel(_kid):
        canceled["v"] = True

    async def _get(_kid):
        return _order(3, 7, 2.64)
    monkeypatch.setattr(kalshi_api, "cancel_order", _cancel)
    monkeypatch.setattr(kalshi_api, "get_order", _get)

    out = run_async(ct._poll_entry(pos, cfg))
    assert canceled["v"] is True
    assert out["status"] == "filled"
    assert out["filled_contracts"] == 3
    assert out["resolved"] == 0
    assert out["exit_reason"] is None


def test_unfilled_entry_then_expiry_still_cancels(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="submitted", kalshi_order_id="OID-E",
                    target_contracts=10, filled_contracts=0, close_time=_past())

    async def _cancel(_kid):
        pass

    async def _get(_kid):
        return _order(0, 10, 0)
    monkeypatch.setattr(kalshi_api, "cancel_order", _cancel)
    monkeypatch.setattr(kalshi_api, "get_order", _get)

    out = run_async(ct._poll_entry(pos, cfg))
    assert out["status"] == "canceled"
    assert out["resolved"] == 1
    assert out["exit_reason"] == "unfilled_expired"


def test_partial_stop_loss_sell_stays_exiting(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="exiting", direction="yes", target_contracts=10,
                    filled_contracts=10, cost_usd=8.80,
                    exit_kalshi_order_id="OID-X", exit_filled_contracts=0)

    async def _get(_kid):
        return _order(3, 7, 0.93)
    monkeypatch.setattr(kalshi_api, "get_order", _get)

    out = run_async(ct._poll_exit(pos))
    assert out is None
    with db.get_db() as conn:
        r = db.fetch_crypto15m_by_id(conn, pos["id"])
    assert r["status"] == "exiting" and r["resolved"] == 0
    assert r["exit_filled_contracts"] == 3
    assert r["proceeds_usd"] == pytest.approx(0.93)


def test_partial_stop_then_settlement_accounts_for_sold_portion(fresh_db, env_demo, cfg, monkeypatch):
    pos = _seed_c15(status="exiting", direction="yes", target_contracts=10,
                    filled_contracts=10, cost_usd=8.80, exit_reason="stop_loss",
                    exit_kalshi_order_id="OID-X", exit_filled_contracts=3, proceeds_usd=0.93)

    async def _settled(_ticker):
        return {"result": "yes", "status": "finalized"}
    monkeypatch.setattr(kalshi_api, "fetch_market", _settled)

    out = run_async(ct._settle_if_closed(pos))
    assert out["status"] == "settled" and out["resolved"] == 1
    assert out["settlement_usd"] == pytest.approx(7.0)
    assert out["pnl_usd"] == pytest.approx(0.93 + 7.0 - 8.80)
    assert out["outcome_correct"] == 1




def test_hours_ok_default_is_always_on(cfg):
    for h in range(24):
        assert crypto15m.hours_ok(cfg, hour=h) is True


def test_hours_ok_simple_window(cfg):
    cfg["crypto15m_hours_start_utc"] = 6
    cfg["crypto15m_hours_end_utc"] = 12
    assert crypto15m.hours_ok(cfg, hour=6) is True
    assert crypto15m.hours_ok(cfg, hour=11) is True
    assert crypto15m.hours_ok(cfg, hour=12) is False
    assert crypto15m.hours_ok(cfg, hour=23) is False


def test_hours_ok_overnight_wrap(cfg):
    cfg["crypto15m_hours_start_utc"] = 22
    cfg["crypto15m_hours_end_utc"] = 6
    assert crypto15m.hours_ok(cfg, hour=23) is True
    assert crypto15m.hours_ok(cfg, hour=2) is True
    assert crypto15m.hours_ok(cfg, hour=6) is False
    assert crypto15m.hours_ok(cfg, hour=12) is False
