from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    base = os.environ.get("KRYPT_TRADER_USERDATA")
    if base:
        d = Path(base) / "data"
    else:
        d = Path(__file__).resolve().parent / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return _data_dir() / "krypt-trader.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(str(db_path()), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()




SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    ticker TEXT PRIMARY KEY,
    event_ticker TEXT DEFAULT '',
    series_ticker TEXT DEFAULT '',
    title TEXT DEFAULT '',
    yes_sub_title TEXT DEFAULT '',
    category TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    close_time TEXT DEFAULT '',
    volume REAL DEFAULT 0,
    volume_24h REAL DEFAULT 0,
    open_interest REAL DEFAULT 0,
    yes_bid REAL DEFAULT 0,
    yes_ask REAL DEFAULT 0,
    last_price REAL DEFAULT 0,
    prev_yes_bid REAL DEFAULT 0,
    prev_price REAL DEFAULT 0,
    result TEXT DEFAULT '',
    settlement_value REAL DEFAULT NULL,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_ticker TEXT PRIMARY KEY,
    series_ticker TEXT DEFAULT '',
    title TEXT DEFAULT '',
    sub_title TEXT DEFAULT '',
    category TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_ticker TEXT DEFAULT '',
    count_fp REAL DEFAULT 0,
    yes_price REAL DEFAULT 0,
    no_price REAL DEFAULT 0,
    taker_side TEXT DEFAULT '',
    dollar_value REAL DEFAULT 0,
    category TEXT DEFAULT '',
    created_time TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    event_ticker TEXT DEFAULT '',
    title TEXT DEFAULT '',
    category TEXT DEFAULT '',
    signal_type TEXT DEFAULT '',
    direction TEXT DEFAULT '',
    volume_24h REAL DEFAULT 0,
    price REAL DEFAULT 0,
    price_change REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    discord_sent INTEGER DEFAULT 0,
    resolved INTEGER DEFAULT 0,
    outcome_correct INTEGER DEFAULT NULL,
    resolved_price REAL DEFAULT NULL,
    pnl_estimate REAL DEFAULT NULL,
    resolved_at TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS whale_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE,
    ticker TEXT NOT NULL,
    event_ticker TEXT DEFAULT '',
    title TEXT DEFAULT '',
    yes_sub_title TEXT DEFAULT '',
    category TEXT DEFAULT '',
    taker_side TEXT DEFAULT '',
    count_fp REAL DEFAULT 0,
    price REAL DEFAULT 0,
    dollar_value REAL DEFAULT 0,
    market_volume REAL DEFAULT 0,
    open_interest REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    discord_sent INTEGER DEFAULT 0,
    resolved INTEGER DEFAULT 0,
    outcome_correct INTEGER DEFAULT NULL,
    resolved_price REAL DEFAULT NULL,
    pnl_estimate REAL DEFAULT NULL,
    resolved_at TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    volume REAL DEFAULT 0,
    volume_24h REAL DEFAULT 0,
    open_interest REAL DEFAULT 0,
    yes_bid REAL DEFAULT 0,
    last_price REAL DEFAULT 0,
    snapshot_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bot_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_source TEXT NOT NULL,
    signal_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    event_ticker TEXT DEFAULT '',
    title TEXT DEFAULT '',
    category TEXT DEFAULT '',
    direction TEXT NOT NULL,
    action TEXT DEFAULT 'buy',
    target_contracts INTEGER NOT NULL,
    limit_price_cents INTEGER NOT NULL,
    filled_contracts INTEGER DEFAULT 0,
    avg_fill_price_cents REAL DEFAULT NULL,
    cost_usd REAL DEFAULT 0,
    fees_usd REAL DEFAULT 0,
    client_order_id TEXT UNIQUE NOT NULL,
    kalshi_order_id TEXT DEFAULT NULL,
    status TEXT NOT NULL,
    confidence REAL DEFAULT 0,
    edge_pts REAL DEFAULT 0,
    signal_price REAL DEFAULT 0,
    error TEXT DEFAULT NULL,
    resolved INTEGER DEFAULT 0,
    outcome_correct INTEGER DEFAULT NULL,
    settlement_usd REAL DEFAULT NULL,
    pnl_usd REAL DEFAULT NULL,
    closed_early INTEGER DEFAULT 0,
    balance_before_usd REAL DEFAULT NULL,
    kalshi_env TEXT DEFAULT 'demo',
    created_at TEXT DEFAULT (datetime('now')),
    last_updated TEXT DEFAULT (datetime('now')),
    resolved_at TEXT DEFAULT NULL,
    UNIQUE(signal_source, signal_id, kalshi_env)
);

CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    kalshi_status TEXT DEFAULT NULL,
    filled_contracts INTEGER DEFAULT NULL,
    fill_cost_cents INTEGER DEFAULT NULL,
    note TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_stats (
    day TEXT NOT NULL,
    kalshi_env TEXT NOT NULL,
    opened INTEGER DEFAULT 0,
    resolved INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    realized_pnl_usd REAL DEFAULT 0,
    ending_balance_usd REAL DEFAULT 0,
    last_updated TEXT DEFAULT (datetime('now')),
    PRIMARY KEY(day, kalshi_env)
);

CREATE TABLE IF NOT EXISTS pnl_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT DEFAULT (datetime('now')),
    kalshi_env TEXT DEFAULT 'demo',
    cash_usd REAL NOT NULL,
    portfolio_usd REAL NOT NULL,
    total_usd REAL NOT NULL,
    realized_pnl_usd REAL DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    open_positions INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS crypto15m_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    series TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,                 -- 'up' | 'down' (display)
    direction TEXT NOT NULL,            -- 'yes' | 'no' (Kalshi side bought)
    target_contracts INTEGER NOT NULL,
    filled_contracts INTEGER DEFAULT 0,
    entry_limit_cents INTEGER NOT NULL,
    avg_entry_cents REAL DEFAULT NULL,
    cost_usd REAL DEFAULT 0,
    client_order_id TEXT UNIQUE NOT NULL,
    kalshi_order_id TEXT DEFAULT NULL,
    -- stop-loss exit leg
    exit_client_order_id TEXT DEFAULT NULL,
    exit_kalshi_order_id TEXT DEFAULT NULL,
    exit_limit_cents INTEGER DEFAULT NULL,
    exit_filled_contracts INTEGER DEFAULT 0,
    proceeds_usd REAL DEFAULT NULL,
    -- lifecycle
    status TEXT NOT NULL,               -- dry_run|submitted|filled|exiting|exited|settled|canceled|error
    exit_reason TEXT DEFAULT NULL,      -- 'stop_loss' | 'settlement' | 'unfilled_expired'
    close_time TEXT DEFAULT '',
    confidence REAL DEFAULT 0,          -- favorite prob at entry (×100)
    entry_delta_usd REAL DEFAULT NULL,
    outcome_correct INTEGER DEFAULT NULL,
    settlement_usd REAL DEFAULT NULL,
    pnl_usd REAL DEFAULT NULL,
    resolved INTEGER DEFAULT 0,
    kalshi_env TEXT DEFAULT 'demo',
    dry_run INTEGER DEFAULT 0,
    error TEXT DEFAULT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_updated TEXT DEFAULT (datetime('now')),
    resolved_at TEXT DEFAULT NULL
);

-- crypto15m_signals: a passive research log for the 15-min crypto
-- strategy. One row per market (quarter window): a decision-point
-- snapshot captured live (favorite side + price + underlying delta a few
-- minutes before close), then the settled outcome filled in afterward.
-- This is what makes the 15m strategy backtestable — independent of
-- whether the user ever enables the executor. No orders, no money.
CREATE TABLE IF NOT EXISTS crypto15m_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset TEXT NOT NULL,
    series TEXT DEFAULT '',
    close_time TEXT DEFAULT '',
    observed_at TEXT DEFAULT (datetime('now')),
    mins_left REAL,                    -- minutes to close at the observation
    favorite TEXT,                     -- 'up' | 'down' at the decision point
    favorite_price REAL,               -- favorite mid probability (fraction)
    entry_cost REAL,                   -- cost to BUY the favorite (fraction)
    up_prob REAL,                      -- yes/up mid probability (fraction)
    delta_pct REAL,                    -- abs(open-live)/open underlying move
    open_spot REAL,
    obs_spot REAL,
    resolved INTEGER DEFAULT 0,
    up_won INTEGER DEFAULT NULL,       -- 1 if the up/yes side settled true
    settled_at TEXT DEFAULT NULL,
    kalshi_env TEXT DEFAULT 'demo'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_c15sig_ticker ON crypto15m_signals(ticker);
CREATE INDEX IF NOT EXISTS idx_c15sig_resolved ON crypto15m_signals(resolved, close_time);

-- crypto15m_ticks: high-frequency companion to crypto15m_signals. One
-- row per active 15-min market every ~25s across the WHOLE window (not
-- just the decision point), so strategies can be tested for entry
-- timing, quote staleness vs spot, and maker-fill behaviour. Outcomes
-- come from joining crypto15m_signals on ticker. Pruned by
-- cleanup_old_data after `_C15_TICKS_KEEP_DAYS`.
CREATE TABLE IF NOT EXISTS crypto15m_ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset TEXT NOT NULL,
    observed_at TEXT DEFAULT (datetime('now')),
    mins_left REAL,
    yes_bid REAL,                      -- fraction 0..1
    yes_ask REAL,                      -- fraction 0..1
    up_prob REAL,                      -- mid, fraction 0..1
    spot REAL,                         -- live underlying USD
    open_spot REAL,                    -- quarter-open underlying USD
    delta_pct REAL,                    -- abs(open-live)/open
    kalshi_env TEXT DEFAULT 'demo'
);
CREATE INDEX IF NOT EXISTS idx_c15tick_ticker ON crypto15m_ticks(ticker, observed_at);
CREATE INDEX IF NOT EXISTS idx_c15tick_time ON crypto15m_ticks(observed_at);

-- bot_runs: each row is a single launch of the bot (start → stop).
-- This is what powers the user-facing "session P&L" model — every
-- restart starts a fresh run, and `start_balance` is what we benchmark
-- against. Per-run aggregates (P&L, trades opened/won/lost) get
-- updated periodically and finalised on shutdown.
CREATE TABLE IF NOT EXISTS bot_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kalshi_env TEXT NOT NULL DEFAULT 'demo',
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ended_at TEXT,
    start_cash_usd REAL NOT NULL DEFAULT 0,
    start_portfolio_usd REAL NOT NULL DEFAULT 0,
    start_total_usd REAL NOT NULL DEFAULT 0,
    end_cash_usd REAL,
    end_portfolio_usd REAL,
    end_total_usd REAL,
    pnl_usd REAL DEFAULT 0,
    trades_opened INTEGER DEFAULT 0,
    trades_won INTEGER DEFAULT 0,
    trades_lost INTEGER DEFAULT 0,
    -- Lifetime counters captured at run start. The run's per-session
    -- trade/W/L counts are computed as `current_lifetime - start_lifetime`
    -- on every heartbeat. Without this baseline the heartbeat just
    -- stored lifetime totals into every run, which is why every row in
    -- the History → Run history table looked the same.
    start_trades_opened INTEGER DEFAULT 0,
    start_trades_won INTEGER DEFAULT 0,
    start_trades_lost INTEGER DEFAULT 0,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_env ON bot_runs(kalshi_env, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_open ON bot_runs(ended_at, kalshi_env);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(created_time DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON alerts(ticker, direction, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whale_trade_id ON whale_trades(trade_id);
CREATE INDEX IF NOT EXISTS idx_whale_cat ON whale_trades(category, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whale_convergence ON whale_trades(ticker, taker_side, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots ON market_snapshots(ticker, snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_markets_vol ON markets(volume DESC);
CREATE INDEX IF NOT EXISTS idx_bp_status ON bot_positions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bp_ticker ON bot_positions(ticker, direction, status);
CREATE INDEX IF NOT EXISTS idx_bp_resolved ON bot_positions(resolved, status);
CREATE INDEX IF NOT EXISTS idx_bp_created ON bot_positions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_oe_pos ON order_events(position_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pnl_at ON pnl_snapshots(at DESC);
CREATE INDEX IF NOT EXISTS idx_c15_open ON crypto15m_positions(resolved, status);
CREATE INDEX IF NOT EXISTS idx_c15_asset ON crypto15m_positions(asset, kalshi_env, resolved);
"""


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA)
        for migration in [
            "ALTER TABLE bot_positions ADD COLUMN closed_early INTEGER DEFAULT 0",
            "ALTER TABLE alerts ADD COLUMN yes_sub_title TEXT DEFAULT ''",
            "ALTER TABLE bot_runs ADD COLUMN start_trades_opened INTEGER DEFAULT 0",
            "ALTER TABLE bot_runs ADD COLUMN start_trades_won INTEGER DEFAULT 0",
            "ALTER TABLE bot_runs ADD COLUMN start_trades_lost INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass


def factory_reset(*, wipe_markets: bool = False) -> dict:
    targets = [
        "bot_positions",
        "bot_runs",
        "pnl_snapshots",
        "daily_stats",
        "order_events",
        "alerts",
        "whale_trades",
    ]
    if wipe_markets:
        targets.extend(["markets", "events", "trades", "market_snapshots"])

    summary: dict[str, int] = {}
    errors: dict[str, str] = {}

    for t in targets:
        try:
            with get_db() as conn:
                cur = conn.execute(f"SELECT COUNT(*) FROM {t}")
                count = int(cur.fetchone()[0])
                conn.execute(f"DELETE FROM {t}")
                summary[t] = count
        except sqlite3.OperationalError as e:
            errors[t] = str(e)
            summary[t] = -1

    try:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN "
                "('bot_positions','bot_runs','pnl_snapshots',"
                "'daily_stats','order_events','alerts','whale_trades',"
                "'markets','events','trades','market_snapshots')",
            )
    except sqlite3.OperationalError:
        pass

    try:
        conn = sqlite3.connect(str(db_path()), timeout=30)
        conn.isolation_level = None
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("VACUUM")
        except sqlite3.OperationalError:
            pass
        conn.close()
    except sqlite3.OperationalError:
        pass

    if errors:
        summary["_errors"] = errors  # type: ignore[assignment]
    return summary




def upsert_market(conn, market: dict) -> None:
    conn.execute(
        """
        INSERT INTO markets (ticker, event_ticker, series_ticker, title, yes_sub_title,
            category, status, close_time, volume, volume_24h, open_interest,
            yes_bid, yes_ask, last_price, prev_yes_bid, prev_price,
            result, settlement_value, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            event_ticker=excluded.event_ticker,
            series_ticker=excluded.series_ticker,
            title=COALESCE(excluded.title, title),
            yes_sub_title=COALESCE(excluded.yes_sub_title, yes_sub_title),
            category=COALESCE(NULLIF(excluded.category,''), category),
            status=excluded.status,
            close_time=excluded.close_time,
            prev_yes_bid=markets.yes_bid,
            prev_price=markets.last_price,
            volume=excluded.volume,
            volume_24h=excluded.volume_24h,
            open_interest=excluded.open_interest,
            yes_bid=excluded.yes_bid,
            yes_ask=excluded.yes_ask,
            last_price=excluded.last_price,
            result=excluded.result,
            settlement_value=excluded.settlement_value,
            last_updated=excluded.last_updated
        """,
        (
            market.get("ticker", ""),
            market.get("event_ticker", ""),
            market.get("series_ticker", ""),
            market.get("title", ""),
            market.get("yes_sub_title", ""),
            market.get("category", ""),
            market.get("status", "open"),
            market.get("close_time", ""),
            _to_float(market.get("volume", 0)),
            _to_float(market.get("volume_24h", 0)),
            _to_float(market.get("open_interest", 0)),
            _to_float(market.get("yes_bid", 0)),
            _to_float(market.get("yes_ask", 0)),
            _to_float(market.get("last_price", 0)),
            0,
            0,
            market.get("result", ""),
            _to_float(market.get("settlement_value")) if market.get("settlement_value") is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def get_market(conn, ticker: str) -> dict | None:
    row = conn.execute("SELECT * FROM markets WHERE ticker = ?", (ticker,)).fetchone()
    return dict(row) if row else None


def get_active_markets(conn, min_volume: float = 0, limit: int = 500) -> list:
    rows = conn.execute(
        "SELECT * FROM markets WHERE status IN ('active','open') AND volume >= ? "
        "ORDER BY volume DESC LIMIT ?",
        (min_volume, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_event(conn, event: dict) -> None:
    conn.execute(
        """
        INSERT INTO events (event_ticker, series_ticker, title, sub_title, category, status, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_ticker) DO UPDATE SET
            series_ticker=excluded.series_ticker,
            title=COALESCE(excluded.title, title),
            sub_title=COALESCE(excluded.sub_title, sub_title),
            category=COALESCE(NULLIF(excluded.category,''), category),
            status=excluded.status,
            last_updated=excluded.last_updated
        """,
        (
            event.get("event_ticker", ""),
            event.get("series_ticker", ""),
            event.get("title", ""),
            event.get("sub_title", ""),
            event.get("category", ""),
            event.get("status", "open"),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def trade_exists(conn, trade_id: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        is not None
    )


def insert_trade(conn, trade: dict) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO trades (trade_id, ticker, event_ticker, count_fp, yes_price,
                no_price, taker_side, dollar_value, category, created_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("trade_id", ""),
                trade.get("ticker", ""),
                trade.get("event_ticker", ""),
                _to_float(trade.get("count_fp", 0)),
                _to_float(trade.get("yes_price", 0)),
                _to_float(trade.get("no_price", 0)),
                trade.get("taker_side", ""),
                _to_float(trade.get("dollar_value", 0)),
                trade.get("category", ""),
                trade.get("created_time", ""),
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False




def insert_alert(conn, alert: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO alerts (ticker, event_ticker, title, yes_sub_title, category, signal_type,
            direction, volume_24h, price, price_change, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert.get("ticker", ""),
            alert.get("event_ticker", ""),
            alert.get("title", ""),
            alert.get("yes_sub_title", ""),
            alert.get("category", ""),
            alert.get("signal_type", ""),
            alert.get("direction", ""),
            alert.get("volume_24h", 0),
            alert.get("price", 0),
            alert.get("price_change", 0),
            alert.get("confidence", 0),
        ),
    )
    return cur.lastrowid


def mark_alert_discord_sent(conn, alert_id: int) -> None:
    conn.execute("UPDATE alerts SET discord_sent = 1 WHERE id = ?", (alert_id,))


def recent_alert_exists(
    conn, ticker: str, signal_type: str, direction: str, cooldown_minutes: int = 30
) -> bool:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    ).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        """
        SELECT 1 FROM alerts
        WHERE ticker = ? AND signal_type = ? AND direction = ? AND created_at >= ?
        """,
        (ticker, signal_type, direction, cutoff),
    ).fetchone()
    return row is not None


def fetch_tradeable_momentum_signals(
    conn,
    *,
    min_confidence: float,
    max_age_sec: int,
    allowed_types: list[str],
    seen_ids: set[int],
    limit: int = 50,
) -> list[dict]:
    if not allowed_types:
        return []
    placeholders = ",".join("?" for _ in allowed_types)
    rows = conn.execute(
        f"""SELECT a.* FROM alerts a
            WHERE a.confidence >= ?
              AND a.resolved = 0
              AND (julianday('now') - julianday(a.created_at)) * 86400 <= ?
              AND a.signal_type IN ({placeholders})
            ORDER BY a.created_at DESC
            LIMIT ?""",
        [min_confidence, max_age_sec, *allowed_types, limit * 2],
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        if int(d["id"]) in seen_ids:
            continue
        out.append(d)
        if len(out) >= limit:
            break
    return out




def whale_trade_exists(conn, trade_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM whale_trades WHERE trade_id = ?", (trade_id,)
        ).fetchone()
        is not None
    )


def insert_whale_trade(conn, trade: dict) -> int:
    try:
        cur = conn.execute(
            """
            INSERT INTO whale_trades
                (trade_id, ticker, event_ticker, title, yes_sub_title, category, taker_side,
                 count_fp, price, dollar_value, market_volume, open_interest, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("trade_id", ""),
                trade.get("ticker", ""),
                trade.get("event_ticker", ""),
                trade.get("title", ""),
                trade.get("yes_sub_title", ""),
                trade.get("category", ""),
                trade.get("taker_side", ""),
                _to_float(trade.get("count_fp", 0)),
                _to_float(trade.get("price", 0)),
                _to_float(trade.get("dollar_value", 0)),
                _to_float(trade.get("market_volume", 0)),
                _to_float(trade.get("open_interest", 0)),
                trade.get("confidence", 0),
            ),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return 0


def mark_whale_discord_sent(conn, whale_id: int) -> None:
    conn.execute("UPDATE whale_trades SET discord_sent = 1 WHERE id = ?", (whale_id,))


def fetch_tradeable_whale_signals(
    conn,
    *,
    min_confidence: float,
    max_age_sec: int,
    seen_ids: set[int],
    limit: int = 50,
) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM whale_trades
           WHERE confidence >= ?
             AND resolved = 0
             AND (julianday('now') - julianday(created_at)) * 86400 <= ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (min_confidence, max_age_sec, limit * 2),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        if int(d["id"]) in seen_ids:
            continue
        out.append(d)
        if len(out) >= limit:
            break
    return out


def get_recent_whales_for_convergence(conn, hours: int = 2) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows = conn.execute(
        """
        SELECT ticker, taker_side, dollar_value, confidence, price,
               count_fp, title, category, created_at
        FROM whale_trades WHERE created_at >= ?
        ORDER BY created_at DESC
        """,
        (cutoff,),
    ).fetchall()
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = (r[0], r[1])
        groups.setdefault(key, []).append(
            {
                "dollar_value": r[2],
                "confidence": r[3],
                "price": r[4],
                "count_fp": r[5],
                "title": r[6],
                "category": r[7],
                "created_at": r[8],
            }
        )
    return groups




def save_snapshot(conn, ticker: str, market: dict) -> None:
    conn.execute(
        """INSERT INTO market_snapshots (ticker, volume, volume_24h, open_interest, yes_bid, last_price)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            ticker,
            _to_float(market.get("volume", 0)),
            _to_float(market.get("volume_24h", 0)),
            _to_float(market.get("open_interest", 0)),
            _to_float(market.get("yes_bid", 0)),
            _to_float(market.get("last_price", 0)),
        ),
    )


def get_previous_snapshot(conn, ticker: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM market_snapshots WHERE ticker = ?
           ORDER BY snapshot_at DESC LIMIT 1 OFFSET 1""",
        (ticker,),
    ).fetchone()
    return dict(row) if row else None




def get_unresolved_alerts(conn, days: int = 30) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows = conn.execute(
        """SELECT id, ticker, direction, price, created_at
           FROM alerts WHERE resolved = 0 AND created_at >= ?""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_unresolved_whale_trades(conn, days: int = 30) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows = conn.execute(
        """SELECT id, ticker, taker_side, price, dollar_value, created_at
           FROM whale_trades WHERE resolved = 0 AND created_at >= ?""",
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_alert_resolved(
    conn, alert_id: int, correct: bool, resolved_price: float, pnl_est: float
) -> None:
    conn.execute(
        """UPDATE alerts SET resolved = 1, outcome_correct = ?, resolved_price = ?,
              pnl_estimate = ?, resolved_at = ? WHERE id = ?""",
        (
            1 if correct else 0,
            resolved_price,
            pnl_est,
            datetime.now(timezone.utc).isoformat(),
            alert_id,
        ),
    )


def mark_whale_resolved(
    conn, trade_id: int, correct: bool, resolved_price: float, pnl_est: float
) -> None:
    conn.execute(
        """UPDATE whale_trades SET resolved = 1, outcome_correct = ?, resolved_price = ?,
              pnl_estimate = ?, resolved_at = ? WHERE id = ?""",
        (
            1 if correct else 0,
            resolved_price,
            pnl_est,
            datetime.now(timezone.utc).isoformat(),
            trade_id,
        ),
    )




def insert_bot_position(conn, row: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO bot_positions (
            signal_source, signal_id, ticker, event_ticker, title, category,
            direction, action, target_contracts, limit_price_cents,
            filled_contracts, avg_fill_price_cents, cost_usd,
            client_order_id, kalshi_order_id, status,
            confidence, edge_pts, signal_price, error,
            balance_before_usd, kalshi_env
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            row["signal_source"],
            row["signal_id"],
            row["ticker"],
            row.get("event_ticker", ""),
            row.get("title", ""),
            row.get("category", ""),
            row["direction"],
            row.get("action", "buy"),
            int(row["target_contracts"]),
            int(row["limit_price_cents"]),
            int(row.get("filled_contracts", 0)),
            row.get("avg_fill_price_cents"),
            float(row.get("cost_usd", 0.0)),
            row["client_order_id"],
            row.get("kalshi_order_id"),
            row["status"],
            float(row.get("confidence", 0.0)),
            float(row.get("edge_pts", 0.0)),
            float(row.get("signal_price", 0.0)),
            row.get("error"),
            row.get("balance_before_usd"),
            row.get("kalshi_env", "demo"),
        ),
    )
    return cur.lastrowid


def update_bot_position(conn, bot_id: int, **fields) -> None:
    if not fields:
        return
    stamp_last = fields.pop("_stamp_last_updated", True)
    cols, vals = [], []
    for k, v in fields.items():
        cols.append(f"{k}=?")
        vals.append(v)
    if stamp_last:
        cols.append("last_updated=datetime('now')")
    vals.append(bot_id)
    conn.execute(
        f"UPDATE bot_positions SET {', '.join(cols)} WHERE id=?", vals
    )


def log_event(
    conn,
    position_id: int,
    kind: str,
    *,
    kalshi_status: str | None = None,
    filled_contracts: int | None = None,
    fill_cost_cents: int | None = None,
    note: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO order_events
              (position_id, kind, kalshi_status, filled_contracts,
               fill_cost_cents, note)
           VALUES (?,?,?,?,?,?)""",
        (position_id, kind, kalshi_status, filled_contracts, fill_cost_cents, note),
    )


def count_open_bot_positions(conn, env: str | None = None) -> int:
    sql = (
        "SELECT COUNT(*) FROM bot_positions "
        "WHERE status IN ('submitted','partial','filled') AND resolved=0"
    )
    args: tuple = ()
    if env:
        sql += " AND kalshi_env = ?"
        args = (env,)
    return conn.execute(sql, args).fetchone()[0]


def count_new_positions_today(conn, env: str | None = None) -> int:
    sql = (
        "SELECT COUNT(*) FROM bot_positions "
        "WHERE date(created_at)=date('now') "
        "AND status != 'dry_run' "
        "AND COALESCE(signal_source,'') != 'external'"
    )
    args: tuple = ()
    if env:
        sql += " AND kalshi_env = ?"
        args = (env,)
    return conn.execute(sql, args).fetchone()[0]


def recent_resolved_position_exists(
    conn,
    ticker: str,
    direction: str,
    env: str,
    within_hours: int = 24,
) -> bool:
    row = conn.execute(
        """SELECT 1 FROM bot_positions
           WHERE ticker = ? AND direction = ? AND kalshi_env = ?
             AND resolved = 1
             AND resolved_at IS NOT NULL
             AND resolved_at >= datetime('now', ?)
           LIMIT 1""",
        (ticker, direction, env, f"-{int(within_hours)} hours"),
    ).fetchone()
    return row is not None


def exists_position_in_event(conn, event_ticker: str, env: str) -> bool:
    if not event_ticker:
        return False
    row = conn.execute(
        """SELECT 1 FROM bot_positions
           WHERE event_ticker=? AND resolved=0 AND kalshi_env=?
             AND status IN ('submitted','partial','filled')
           LIMIT 1""",
        (event_ticker, env),
    ).fetchone()
    return row is not None


def exists_position_in_market(
    conn, ticker: str, direction: str, env: str
) -> bool:
    row = conn.execute(
        """SELECT 1 FROM bot_positions
           WHERE ticker=? AND direction=? AND resolved=0 AND kalshi_env=?
             AND status IN ('submitted','partial','filled')
           LIMIT 1""",
        (ticker, direction, env),
    ).fetchone()
    return row is not None


def current_total_exposure_usd(conn, env: str) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(cost_usd), 0) FROM bot_positions
           WHERE resolved=0 AND status IN ('submitted','partial','filled') AND kalshi_env=?""",
        (env,),
    ).fetchone()
    return float(row[0] or 0.0)


def get_pending_bot_positions(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM bot_positions
           WHERE resolved=0
             AND signal_source != 'external'
             AND kalshi_order_id IS NOT NULL
             AND (
               status IN ('submitted','partial')
               OR (status='filled' AND (cost_usd IS NULL OR cost_usd=0))
               OR (status IN ('canceled','expired','gone','error')
                   AND (cost_usd IS NULL OR cost_usd=0)
                   AND (julianday('now')-julianday(created_at))*86400 < 86400)
             )
           ORDER BY created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_open_bot_positions(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM bot_positions
           WHERE status IN ('submitted','partial','filled') AND resolved=0
           ORDER BY created_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_unresolved_bot_positions(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM bot_positions
           WHERE resolved=0 AND status IN ('filled','partial','expired','canceled','gone')
           ORDER BY created_at ASC"""
    ).fetchall()
    return [dict(r) for r in rows]


def already_traded_signal_ids(conn, source: str, env: str) -> set[int]:
    rows = conn.execute(
        "SELECT signal_id FROM bot_positions WHERE signal_source=? AND kalshi_env=?",
        (source, env),
    ).fetchall()
    return {int(r["signal_id"]) for r in rows}


def fetch_position_by_id(conn, pos_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM bot_positions WHERE id=?", (pos_id,)
    ).fetchone()
    return dict(row) if row else None




def insert_crypto15m_position(conn, row: dict) -> int:
    cur = conn.execute(
        """INSERT INTO crypto15m_positions (
              asset, series, ticker, side, direction, target_contracts,
              filled_contracts, entry_limit_cents, avg_entry_cents, cost_usd,
              client_order_id, kalshi_order_id, status, exit_reason, close_time,
              confidence, entry_delta_usd, kalshi_env, dry_run, error
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row["asset"], row["series"], row["ticker"], row["side"],
            row["direction"], int(row["target_contracts"]),
            int(row.get("filled_contracts", 0)),
            int(row["entry_limit_cents"]),
            row.get("avg_entry_cents"),
            float(row.get("cost_usd", 0.0)),
            row["client_order_id"], row.get("kalshi_order_id"),
            row["status"], row.get("exit_reason"), row.get("close_time", ""),
            float(row.get("confidence", 0.0)),
            row.get("entry_delta_usd"),
            row.get("kalshi_env", "demo"),
            1 if row.get("dry_run") else 0,
            row.get("error"),
        ),
    )
    return cur.lastrowid


def update_crypto15m_position(conn, pid: int, **fields) -> None:
    if not fields:
        return
    cols, vals = [], []
    for k, v in fields.items():
        cols.append(f"{k}=?")
        vals.append(v)
    cols.append("last_updated=datetime('now')")
    vals.append(pid)
    conn.execute(
        f"UPDATE crypto15m_positions SET {', '.join(cols)} WHERE id=?", vals
    )


def fetch_crypto15m_by_id(conn, pid: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM crypto15m_positions WHERE id=?", (pid,)
    ).fetchone()
    return dict(row) if row else None


def get_open_crypto15m(conn, env: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM crypto15m_positions
           WHERE resolved=0 AND kalshi_env=?
           ORDER BY created_at DESC""",
        (env,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_open_crypto15m_by_asset(conn, asset: str, env: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM crypto15m_positions
           WHERE resolved=0 AND asset=? AND kalshi_env=?
           ORDER BY created_at DESC LIMIT 1""",
        (asset, env),
    ).fetchone()
    return dict(row) if row else None


def count_open_crypto15m(conn, env: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM crypto15m_positions WHERE resolved=0 AND kalshi_env=?",
        (env,),
    ).fetchone()[0]


def crypto15m_errored_tickers(conn, env: str) -> set:
    rows = conn.execute(
        """SELECT DISTINCT ticker FROM crypto15m_positions
           WHERE kalshi_env=? AND status='error' AND ticker IS NOT NULL""",
        (env,),
    ).fetchall()
    return {r["ticker"] for r in rows}


def recent_crypto15m(conn, env: str, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM crypto15m_positions
           WHERE kalshi_env=?
           ORDER BY created_at DESC LIMIT ?""",
        (env, int(limit)),
    ).fetchall()
    return [dict(r) for r in rows]


def crypto15m_stats(conn, env: str) -> dict:
    row = conn.execute(
        """SELECT
              SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) AS open_count,
              SUM(CASE WHEN resolved=1 AND outcome_correct=1 THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN resolved=1 AND outcome_correct=0 THEN 1 ELSE 0 END) AS losses,
              COALESCE(SUM(CASE WHEN resolved=1 THEN pnl_usd END),0) AS realized_pnl,
              COUNT(*) AS total
           FROM crypto15m_positions WHERE kalshi_env=?""",
        (env,),
    ).fetchone()
    return {
        "openCount": int(row["open_count"] or 0),
        "wins": int(row["wins"] or 0),
        "losses": int(row["losses"] or 0),
        "realizedPnlUsd": float(row["realized_pnl"] or 0.0),
        "total": int(row["total"] or 0),
    }




def insert_crypto15m_signal(conn, row: dict) -> bool:
    cur = conn.execute(
        """INSERT OR IGNORE INTO crypto15m_signals (
              ticker, asset, series, close_time, mins_left, favorite,
              favorite_price, entry_cost, up_prob, delta_pct, open_spot,
              obs_spot, kalshi_env
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row["ticker"], row["asset"], row.get("series", ""),
            row.get("close_time", ""), row.get("mins_left"),
            row.get("favorite"), row.get("favorite_price"),
            row.get("entry_cost"), row.get("up_prob"), row.get("delta_pct"),
            row.get("open_spot"), row.get("obs_spot"),
            row.get("kalshi_env", "demo"),
        ),
    )
    return (cur.rowcount or 0) > 0


def unresolved_crypto15m_signals(conn, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM crypto15m_signals
           WHERE resolved=0
           ORDER BY close_time ASC LIMIT ?""",
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_crypto15m_signal(conn, ticker: str, up_won: int) -> None:
    conn.execute(
        """UPDATE crypto15m_signals
              SET resolved=1, up_won=?, settled_at=datetime('now')
            WHERE ticker=?""",
        (int(up_won), ticker),
    )


def fetch_resolved_crypto15m_signals(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM crypto15m_signals
           WHERE resolved=1 AND up_won IS NOT NULL"""
    ).fetchall()
    return [dict(r) for r in rows]


def crypto15m_signal_counts(conn) -> dict:
    row = conn.execute(
        """SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) AS resolved,
              SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) AS pending
           FROM crypto15m_signals"""
    ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "resolved": int(row["resolved"] or 0),
        "pending": int(row["pending"] or 0),
    }


_C15_TICKS_KEEP_DAYS = 45


def insert_crypto15m_tick(conn, row: dict) -> None:
    conn.execute(
        """INSERT INTO crypto15m_ticks (
              ticker, asset, mins_left, yes_bid, yes_ask, up_prob,
              spot, open_spot, delta_pct, kalshi_env
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            row["ticker"], row["asset"], row.get("mins_left"),
            row.get("yes_bid"), row.get("yes_ask"), row.get("up_prob"),
            row.get("spot"), row.get("open_spot"), row.get("delta_pct"),
            row.get("kalshi_env", "demo"),
        ),
    )


def crypto15m_tick_count(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM crypto15m_ticks").fetchone()[0])




def insert_pnl_snapshot(
    conn,
    *,
    cash_usd: float,
    portfolio_usd: float,
    realized_pnl_usd: float,
    wins: int,
    losses: int,
    open_positions: int,
    env: str,
) -> None:
    conn.execute(
        """INSERT INTO pnl_snapshots
              (kalshi_env, cash_usd, portfolio_usd, total_usd, realized_pnl_usd,
               wins, losses, open_positions)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            env,
            float(cash_usd),
            float(portfolio_usd),
            float(cash_usd) + float(portfolio_usd),
            float(realized_pnl_usd),
            int(wins),
            int(losses),
            int(open_positions),
        ),
    )


def earliest_pnl_total(conn, env: str) -> float | None:
    row = conn.execute(
        """SELECT total_usd FROM pnl_snapshots
           WHERE kalshi_env = ?
           ORDER BY at ASC LIMIT 1""",
        (env,),
    ).fetchone()
    if row is None:
        return None
    try:
        return float(row[0])
    except (TypeError, ValueError):
        return None


def first_snapshot_of_today(conn, env: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM pnl_snapshots
           WHERE kalshi_env = ? AND date(at) = date('now')
           ORDER BY at ASC LIMIT 1""",
        (env,),
    ).fetchone()
    return dict(row) if row else None


def latest_snapshot(conn, env: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM pnl_snapshots
           WHERE kalshi_env = ?
           ORDER BY at DESC LIMIT 1""",
        (env,),
    ).fetchone()
    return dict(row) if row else None




def start_bot_run(
    conn, *, env: str, cash_usd: float, portfolio_usd: float,
    lifetime_trades: int = 0, lifetime_wins: int = 0, lifetime_losses: int = 0,
) -> int:
    conn.execute(
        """UPDATE bot_runs
           SET ended_at = COALESCE(ended_at, strftime('%Y-%m-%dT%H:%M:%fZ','now')),
               notes    = COALESCE(notes, '') || ' [auto-closed on next start]'
           WHERE kalshi_env = ? AND ended_at IS NULL""",
        (env,),
    )
    total = float(cash_usd) + float(portfolio_usd)
    cur = conn.execute(
        """INSERT INTO bot_runs (
              kalshi_env, start_cash_usd, start_portfolio_usd,
              start_total_usd, end_cash_usd, end_portfolio_usd,
              end_total_usd, pnl_usd,
              start_trades_opened, start_trades_won, start_trades_lost,
              trades_opened, trades_won, trades_lost
           ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 0, 0, 0)""",
        (
            env, float(cash_usd), float(portfolio_usd), total,
            float(cash_usd), float(portfolio_usd), total,
            int(lifetime_trades), int(lifetime_wins), int(lifetime_losses),
        ),
    )
    return int(cur.lastrowid or 0)


def heartbeat_bot_run(
    conn, run_id: int, *, cash_usd: float, portfolio_usd: float,
    lifetime_trades: int = 0, lifetime_wins: int = 0, lifetime_losses: int = 0,
) -> None:
    if not run_id:
        return
    total = float(cash_usd) + float(portfolio_usd)
    conn.execute(
        """UPDATE bot_runs
              SET end_cash_usd = ?,
                  end_portfolio_usd = ?,
                  end_total_usd = ?,
                  pnl_usd = ? - start_total_usd,
                  trades_opened = MAX(0, ? - start_trades_opened),
                  trades_won    = MAX(0, ? - start_trades_won),
                  trades_lost   = MAX(0, ? - start_trades_lost)
            WHERE id = ?""",
        (
            float(cash_usd), float(portfolio_usd), total, total,
            int(lifetime_trades), int(lifetime_wins), int(lifetime_losses),
            int(run_id),
        ),
    )


def end_bot_run(conn, run_id: int) -> None:
    if not run_id:
        return
    conn.execute(
        "UPDATE bot_runs SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
        "WHERE id = ? AND ended_at IS NULL",
        (int(run_id),),
    )


def get_active_run(conn, env: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM bot_runs
            WHERE kalshi_env = ? AND ended_at IS NULL
            ORDER BY started_at DESC LIMIT 1""",
        (env,),
    ).fetchone()
    return dict(row) if row else None


def get_recent_runs(conn, env: str | None = None, limit: int = 50) -> list[dict]:
    if env:
        rows = conn.execute(
            """SELECT * FROM bot_runs
                WHERE kalshi_env = ?
                ORDER BY started_at DESC LIMIT ?""",
            (env, int(limit)),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM bot_runs ORDER BY started_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pnl_snapshots(conn, *, since_hours: int = 168, env: str | None = None) -> list[dict]:
    sql = (
        "SELECT * FROM pnl_snapshots WHERE (julianday('now')-julianday(at))*24 <= ?"
    )
    args: list = [int(since_hours)]
    if env:
        sql += " AND kalshi_env = ?"
        args.append(env)
    sql += " ORDER BY at ASC"
    rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def aggregate_stats(conn, env: str | None = None) -> dict:
    cond = ""
    args: list = []
    if env:
        cond = "AND kalshi_env=?"
        args = [env]
    row = conn.execute(
        f"""SELECT
              SUM(CASE WHEN status IN ('submitted','partial') AND resolved=0 THEN 1 ELSE 0 END) AS pending,
              SUM(CASE WHEN status='filled' AND resolved=0 THEN 1 ELSE 0 END) AS open_filled,
              SUM(CASE WHEN resolved=1 AND outcome_correct=1 THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN resolved=1 AND outcome_correct=0 THEN 1 ELSE 0 END) AS losses,
              COALESCE(SUM(CASE WHEN resolved=1 THEN pnl_usd END),0) AS realized_pnl,
              COALESCE(SUM(CASE WHEN resolved=1 AND date(resolved_at)=date('now') THEN pnl_usd END),0) AS today_pnl,
              SUM(CASE WHEN resolved=1 AND outcome_correct=1 AND date(resolved_at)=date('now') THEN 1 ELSE 0 END) AS today_wins,
              SUM(CASE WHEN resolved=1 AND outcome_correct=0 AND date(resolved_at)=date('now') THEN 1 ELSE 0 END) AS today_losses,
              COALESCE(SUM(CASE WHEN resolved=0 AND status IN ('filled','partial') THEN cost_usd END),0) AS open_cost,
              COALESCE(SUM(fees_usd),0) AS fees,
              SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) AS resolved_count,
              COUNT(*) AS total_opened
           FROM bot_positions
           WHERE status!='dry_run' {cond}""",
        args,
    ).fetchone()
    return {
        "pending": int(row["pending"] or 0),
        "open_filled": int(row["open_filled"] or 0),
        "wins": int(row["wins"] or 0),
        "losses": int(row["losses"] or 0),
        "realized_pnl": float(row["realized_pnl"] or 0.0),
        "today_pnl": float(row["today_pnl"] or 0.0),
        "today_wins": int(row["today_wins"] or 0),
        "today_losses": int(row["today_losses"] or 0),
        "open_cost": float(row["open_cost"] or 0.0),
        "fees": float(row["fees"] or 0.0),
        "resolved_count": int(row["resolved_count"] or 0),
        "total_opened": int(row["total_opened"] or 0),
    }



_DELETE_BATCH = 50_000


def _delete_batched(
    where_sql: str, params: tuple, table: str, *, batch: int = _DELETE_BATCH
) -> int:
    sql = (
        f"DELETE FROM {table} WHERE rowid IN "
        f"(SELECT rowid FROM {table} WHERE {where_sql} LIMIT ?)"
    )
    total = 0
    while True:
        with get_db() as conn:
            n = conn.execute(sql, (*params, batch)).rowcount or 0
        total += n
        if n < batch:
            return total


def cleanup_old_data(
    conn=None, *, trade_hours: int = 48, alert_days: int = 45,
    snapshot_hours: int = 6, pnl_days: int = 120,
) -> int:
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    trade_cutoff = (now - timedelta(hours=trade_hours)).strftime("%Y-%m-%d %H:%M:%S")
    alert_cutoff = (now - timedelta(days=alert_days)).strftime("%Y-%m-%d %H:%M:%S")
    snap_cutoff = (now - timedelta(hours=snapshot_hours)).strftime("%Y-%m-%d %H:%M:%S")
    pnl_cutoff = (now - timedelta(days=pnl_days)).strftime("%Y-%m-%d %H:%M:%S")
    settled_cutoff = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    ticks_cutoff = (now - timedelta(days=_C15_TICKS_KEEP_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

    deleted = 0
    deleted += _delete_batched("created_time < ?", (trade_cutoff,), "trades")
    deleted += _delete_batched("snapshot_at < ?", (snap_cutoff,), "market_snapshots")
    deleted += _delete_batched("observed_at < ?", (ticks_cutoff,), "crypto15m_ticks")
    deleted += _delete_batched(
        "status NOT IN ('active','open') AND last_updated < ?", (settled_cutoff,), "markets")
    deleted += _delete_batched(
        "close_time != '' AND close_time < ? AND last_updated < ?",
        (now_iso, settled_cutoff), "markets")
    deleted += _delete_batched("volume < 10 AND volume_24h < 5", (), "markets")
    with get_db() as c:
        deleted += c.execute(
            "DELETE FROM alerts WHERE resolved = 1 AND created_at < ?", (alert_cutoff,)
        ).rowcount or 0
        deleted += c.execute(
            "DELETE FROM whale_trades WHERE resolved = 1 AND created_at < ?", (alert_cutoff,)
        ).rowcount or 0
        deleted += c.execute(
            "DELETE FROM pnl_snapshots WHERE at < ?", (pnl_cutoff,)
        ).rowcount or 0
    return deleted


def _reclaimable_mb() -> float:
    with get_db() as conn:
        ps = conn.execute("PRAGMA page_size").fetchone()[0]
        fl = conn.execute("PRAGMA freelist_count").fetchone()[0]
    return fl * ps / 1e6


def vacuum() -> None:
    conn = sqlite3.connect(str(db_path()), timeout=120)
    conn.isolation_level = None
    try:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        conn.execute("VACUUM")
    finally:
        conn.close()


def run_maintenance(*, vacuum_min_free_mb: float = 200.0, force_vacuum: bool = False) -> dict:
    deleted = cleanup_old_data()
    free_mb = _reclaimable_mb()
    vacuumed = False
    if force_vacuum or free_mb >= vacuum_min_free_mb:
        vacuum()
        vacuumed = True
    return {"deleted": deleted, "reclaimable_mb": round(free_mb, 1), "vacuumed": vacuumed}
