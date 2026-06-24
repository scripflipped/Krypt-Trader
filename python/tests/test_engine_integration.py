from __future__ import annotations

import asyncio
import itertools

import pytest

import db
import trader
from config import merge_with_defaults
from kalshi_api import KalshiAPIError




@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    dbfile = tmp_path / "krypt-test.db"
    monkeypatch.setattr(db, "db_path", lambda: dbfile)
    db.init_db()
    return dbfile


@pytest.fixture
def env_demo(monkeypatch):
    monkeypatch.setattr(trader, "get_env", lambda: "demo")
    return "demo"


@pytest.fixture
def cfg():
    c = merge_with_defaults({})
    c["kalshi_env"] = "demo"
    return c


def run_async(coro):
    return asyncio.run(coro)


_ids = itertools.count(1)


def seed_position(**over) -> int:
    n = next(_ids)
    row = {
        "signal_source": over.get("signal_source", "whale"),
        "signal_id": over.get("signal_id", n),
        "ticker": over.get("ticker", f"TCK-{n}"),
        "event_ticker": over.get("event_ticker", ""),
        "direction": over.get("direction", "yes"),
        "target_contracts": over.get("target_contracts", 10),
        "limit_price_cents": over.get("limit_price_cents", 50),
        "filled_contracts": over.get("filled_contracts", 0),
        "cost_usd": over.get("cost_usd", 0.0),
        "client_order_id": over.get("client_order_id", f"co-{n}"),
        "kalshi_order_id": over.get("kalshi_order_id"),
        "status": over.get("status", "filled"),
        "kalshi_env": over.get("kalshi_env", "demo"),
    }
    with db.get_db() as conn:
        pid = db.insert_bot_position(conn, row)
        if "created_at_offset_sec" in over:
            conn.execute(
                "UPDATE bot_positions SET created_at=datetime('now', ?) WHERE id=?",
                (f"{int(over['created_at_offset_sec'])} seconds", pid),
            )
    return pid


def whale_signal(**over) -> dict:
    s = {
        "id": 1, "ticker": "WHALE-1", "event_ticker": "", "title": "t",
        "category": "sports", "price": 0.60, "confidence": 80.0,
        "taker_side": "yes",
    }
    s.update(over)
    return s


def count_rows() -> int:
    with db.get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM bot_positions").fetchone()[0]


def fetch(pid: int) -> dict:
    with db.get_db() as conn:
        return db.fetch_position_by_id(conn, pid)


async def _stub_empty_book(_ticker):
    return {}




def test_execute_skips_when_max_open_positions_hit(fresh_db, env_demo, cfg):
    cfg["max_open_positions"] = 1
    seed_position(status="filled")
    result = run_async(
        trader.execute_signal(whale_signal(id=100, ticker="NEW"), "whale", cfg, 1000.0)
    )
    assert result is None
    assert count_rows() == 1


def test_execute_skips_when_daily_cap_hit(fresh_db, env_demo, cfg):
    cfg["max_open_positions"] = 100
    cfg["unlimited_daily_new_positions"] = False
    cfg["max_daily_new_positions"] = 2
    seed_position(status="filled")
    seed_position(status="filled")
    result = run_async(
        trader.execute_signal(whale_signal(id=101, ticker="NEW"), "whale", cfg, 1000.0)
    )
    assert result is None
    assert count_rows() == 2


def test_execute_skips_second_position_in_same_event(fresh_db, env_demo, cfg):
    cfg["max_positions_per_event"] = 1
    seed_position(status="filled", event_ticker="EVT-A", ticker="A-1")
    result = run_async(
        trader.execute_signal(
            whale_signal(id=102, ticker="A-2", event_ticker="EVT-A"),
            "whale", cfg, 1000.0,
        )
    )
    assert result is None


def test_execute_skips_duplicate_market_and_side(fresh_db, env_demo, cfg):
    seed_position(status="filled", ticker="DUP", direction="yes")
    result = run_async(
        trader.execute_signal(
            whale_signal(id=103, ticker="DUP", taker_side="yes"), "whale", cfg, 1000.0
        )
    )
    assert result is None


def test_execute_skips_when_exposure_leaves_under_one_dollar(fresh_db, env_demo, cfg):
    seed_position(status="filled", ticker="EXP-SEED", cost_usd=749.50)
    result = run_async(
        trader.execute_signal(
            whale_signal(id=104, ticker="EXP-NEW"), "whale", cfg, 1000.0
        )
    )
    assert result is None
    assert count_rows() == 1




def test_execute_skips_when_trading_disabled(fresh_db, env_demo, cfg, monkeypatch):
    cfg["enable_trading"] = False
    monkeypatch.setattr(trader, "get_orderbook", _stub_empty_book)

    def _boom(**_kw):
        raise AssertionError("place_limit_order must not be called when trading is disabled")

    monkeypatch.setattr(trader, "place_limit_order", _boom)

    row = run_async(
        trader.execute_signal(whale_signal(id=200, ticker="OFF"), "whale", cfg, 1000.0)
    )
    assert row is None
    assert count_rows() == 0


def test_execute_real_order_records_kalshi_order_id(fresh_db, env_demo, cfg, monkeypatch):
    cfg["enable_trading"] = True
    monkeypatch.setattr(trader, "get_orderbook", _stub_empty_book)

    calls: list[dict] = []

    async def _place(**kw):
        calls.append(kw)
        return {"order": {"order_id": "OID-1", "status": "resting"}}

    monkeypatch.setattr(trader, "place_limit_order", _place)

    row = run_async(
        trader.execute_signal(whale_signal(id=201, ticker="LIVE"), "whale", cfg, 1000.0)
    )
    assert row["status"] == "submitted"
    assert row["kalshi_order_id"] == "OID-1"
    assert len(calls) == 1
    assert calls[0]["count"] == 80
    assert calls[0]["price_cents"] == 62
    assert calls[0]["side"] == "yes"
    assert calls[0]["action"] == "buy"


def test_execute_api_error_is_persisted_as_error_row(fresh_db, env_demo, cfg, monkeypatch):
    cfg["enable_trading"] = True
    monkeypatch.setattr(trader, "get_orderbook", _stub_empty_book)

    async def _place(**_kw):
        raise KalshiAPIError(400, {"error": "insufficient_balance"})

    monkeypatch.setattr(trader, "place_limit_order", _place)

    row = run_async(
        trader.execute_signal(whale_signal(id=202, ticker="BAD"), "whale", cfg, 1000.0)
    )
    assert row["status"] == "error"
    assert "HTTP 400" in row["error"]
    assert row["kalshi_order_id"] is None


def test_execute_skips_when_live_cross_exceeds_entry_cap(fresh_db, env_demo, cfg, monkeypatch):
    cfg["enable_trading"] = True

    async def _moved_book(_ticker):
        return {"no": [[5, 100]]}

    monkeypatch.setattr(trader, "get_orderbook", _moved_book)

    def _boom(**_kw):
        raise AssertionError("place_limit_order must not be called above the cap")

    monkeypatch.setattr(trader, "place_limit_order", _boom)

    row = run_async(
        trader.execute_signal(whale_signal(id=203, ticker="MOVED"), "whale", cfg, 1000.0)
    )
    assert row is None
    assert count_rows() == 0




def test_poll_marks_order_filled_from_order_endpoint(fresh_db, env_demo, cfg, monkeypatch):
    trader._poll_failures.clear()
    pid = seed_position(status="submitted", kalshi_order_id="OID-9",
                        target_contracts=5, cost_usd=0.0)

    async def _no_positions(*_a, **_k):
        return []

    async def _get_order(_oid):
        return {"order": {
            "status": "executed", "taker_fill_count": 5, "maker_fill_count": 0,
            "taker_fill_cost": 300, "maker_fill_cost": 0,
            "place_count": 5, "remaining_count": 0,
        }}

    monkeypatch.setattr(trader, "get_positions", _no_positions)
    monkeypatch.setattr(trader, "get_order", _get_order)

    updated = run_async(trader.poll_open_orders(cfg))
    assert len(updated) == 1
    row = fetch(pid)
    assert row["status"] == "filled"
    assert row["filled_contracts"] == 5
    assert row["cost_usd"] == pytest.approx(3.0)
    assert row["avg_fill_price_cents"] == pytest.approx(60.0)


def test_poll_retires_order_to_gone_only_after_threshold(fresh_db, env_demo, cfg, monkeypatch):
    trader._poll_failures.clear()
    pid = seed_position(status="submitted", kalshi_order_id="OID-10",
                        target_contracts=5)

    async def _no_positions(*_a, **_k):
        return []

    async def _get_order_404(_oid):
        raise KalshiAPIError(404, "not found")

    monkeypatch.setattr(trader, "get_positions", _no_positions)
    monkeypatch.setattr(trader, "get_order", _get_order_404)

    run_async(trader.poll_open_orders(cfg))
    assert fetch(pid)["status"] == "submitted"

    for _ in range(5):
        run_async(trader.poll_open_orders(cfg))
    assert fetch(pid)["status"] == "gone"


def test_poll_auto_cancels_stale_resting_order(fresh_db, env_demo, cfg, monkeypatch):
    trader._poll_failures.clear()
    cfg["order_expiration_sec"] = 90
    pid = seed_position(status="submitted", kalshi_order_id="OID-11",
                        target_contracts=5, created_at_offset_sec=-200)

    async def _no_positions(*_a, **_k):
        return []

    async def _resting(_oid):
        return {"order": {
            "status": "resting", "taker_fill_count": 0, "maker_fill_count": 0,
            "taker_fill_cost": 0, "maker_fill_cost": 0,
            "place_count": 5, "remaining_count": 5,
        }}

    cancels: list[str] = []

    async def _cancel(oid):
        cancels.append(oid)
        return {}

    monkeypatch.setattr(trader, "get_positions", _no_positions)
    monkeypatch.setattr(trader, "get_order", _resting)
    monkeypatch.setattr(trader, "cancel_order", _cancel)

    run_async(trader.poll_open_orders(cfg))
    assert cancels == ["OID-11"]
    assert fetch(pid)["status"] == "canceled"




def _settled_market(result: str):
    async def _fetch(_ticker):
        return {"result": result, "status": "finalized"}
    return _fetch


def test_resolve_winning_yes_position(fresh_db, env_demo, cfg, monkeypatch):
    pid = seed_position(status="filled", ticker="RES-WIN", direction="yes",
                        filled_contracts=10, cost_usd=6.0)
    monkeypatch.setattr(trader, "fetch_market", _settled_market("yes"))

    updated = run_async(trader.mark_resolved_positions(cfg))
    assert len(updated) == 1
    row = fetch(pid)
    assert bool(row["resolved"]) is True
    assert row["outcome_correct"] == 1
    assert row["settlement_usd"] == pytest.approx(10.0)
    assert row["pnl_usd"] == pytest.approx(4.0)


def test_resolve_losing_no_position(fresh_db, env_demo, cfg, monkeypatch):
    pid = seed_position(status="filled", ticker="RES-LOSS", direction="no",
                        filled_contracts=10, cost_usd=4.0)
    monkeypatch.setattr(trader, "fetch_market", _settled_market("yes"))

    run_async(trader.mark_resolved_positions(cfg))
    row = fetch(pid)
    assert row["outcome_correct"] == 0
    assert row["settlement_usd"] == pytest.approx(0.0)
    assert row["pnl_usd"] == pytest.approx(-4.0)


def test_resolve_no_fill_row_closes_at_zero_with_null_outcome(fresh_db, env_demo, cfg):
    pid = seed_position(status="canceled", ticker="RES-NOFILL",
                        filled_contracts=0, cost_usd=0.0)
    run_async(trader.mark_resolved_positions(cfg))
    row = fetch(pid)
    assert bool(row["resolved"]) is True
    assert row["outcome_correct"] is None
    assert row["pnl_usd"] == pytest.approx(0.0)


def test_resolve_clamps_pnl_to_physical_bounds(fresh_db, env_demo, cfg, monkeypatch):
    pid = seed_position(status="filled", ticker="CLAMP", direction="yes",
                        filled_contracts=10, cost_usd=6.0)
    monkeypatch.setattr(trader, "fetch_market", _settled_market("yes"))
    monkeypatch.setattr(trader, "_market_yes_payout", lambda _m: 5.0)

    run_async(trader.mark_resolved_positions(cfg))
    row = fetch(pid)
    assert row["pnl_usd"] == pytest.approx(4.0)
    assert row["settlement_usd"] == pytest.approx(10.0)




def test_refresh_balance_is_per_env(monkeypatch):
    trader._balance_cache.clear()

    async def fake_balance():
        if trader.get_env() == "demo":
            return {"balance": 1000, "portfolio_value": 100}
        return {"balance": 5000, "portfolio_value": 500}

    monkeypatch.setattr(trader, "get_balance", fake_balance)
    cfg = {"balance_poll_interval": 60}

    monkeypatch.setattr(trader, "get_env", lambda: "demo")
    assert run_async(trader.refresh_balance(cfg, force=True)) == (1000, 100)

    monkeypatch.setattr(trader, "get_env", lambda: "production")
    assert run_async(trader.refresh_balance(cfg, force=True)) == (5000, 500)

    monkeypatch.setattr(trader, "get_env", lambda: "demo")
    assert run_async(trader.refresh_balance(cfg, force=False)) == (1000, 100)
