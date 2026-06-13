from __future__ import annotations

from datetime import datetime, timezone

import pytest

import db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    dbfile = tmp_path / "maint.db"
    monkeypatch.setattr(db, "db_path", lambda: dbfile)
    db.init_db()
    return dbfile


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


_OLD = "2000-01-01 00:00:00"


def _add_trade(c, tid: str, when: str) -> None:
    c.execute(
        "INSERT INTO trades (trade_id,ticker,event_ticker,count_fp,yes_price,"
        "no_price,taker_side,dollar_value,category,created_time) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tid, "KX", "E", 1.0, 50, 50, "yes", 100.0, "crypto", when),
    )


def test_cleanup_prunes_old_keeps_recent(fresh_db):
    now = _now()
    with db.get_db() as c:
        _add_trade(c, "old1", _OLD)
        _add_trade(c, "old2", _OLD)
        _add_trade(c, "fresh", now)
        c.execute(
            "INSERT INTO market_snapshots (ticker,volume,volume_24h,open_interest,"
            "yes_bid,last_price,snapshot_at) VALUES (?,?,?,?,?,?,?)",
            ("KX", 100, 50, 10, 50, 50, _OLD),
        )
        c.execute(
            "INSERT INTO market_snapshots (ticker,volume,volume_24h,open_interest,"
            "yes_bid,last_price,snapshot_at) VALUES (?,?,?,?,?,?,?)",
            ("KX", 100, 50, 10, 50, 50, now),
        )

    deleted = db.cleanup_old_data()

    with db.get_db() as c:
        trades = [r["trade_id"] for r in c.execute("SELECT trade_id FROM trades")]
        snaps = c.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
    assert trades == ["fresh"]
    assert snaps == 1
    assert deleted >= 3


def test_batched_delete_clears_a_large_backlog(fresh_db):
    import db as _db
    with db.get_db() as c:
        for i in range(250):
            _add_trade(c, f"t{i}", _OLD)
    n = _db._delete_batched("created_time < ?", (_now(),), "trades", batch=100)
    assert n == 250
    with db.get_db() as c:
        assert c.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0


def test_run_maintenance_compacts_when_forced(fresh_db):
    with db.get_db() as c:
        for i in range(1000):
            _add_trade(c, f"t{i}", _OLD)
    summary = db.run_maintenance(force_vacuum=True)
    assert summary["vacuumed"] is True
    assert summary["deleted"] >= 1000
    with db.get_db() as c:
        assert c.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
