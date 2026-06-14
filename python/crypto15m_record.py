"""Passive research logger for the 15-minute crypto strategy.

Builds the dataset that makes the 15m strategy backtestable: once per
quarter per asset it captures a *decision-point* snapshot (which side is
the favorite, its price, and the underlying delta a few minutes before
close), then fills in the settled outcome afterward. It NEVER places an
order or touches money — it only reads public market data, exactly like
the monitor. Runs in the background regardless of whether the executor is
enabled, so anyone accumulates data to test their own strategies against.

The captured features are raw (favorite price, delta %), so the backtest
can sweep ANY entry threshold / delta filter / favorite-vs-contrarian
choice after the fact without re-collecting data.

It also appends a `crypto15m_ticks` row for every active market on every
pass (~25s cadence, the whole window — bid/ask, mid, spot, delta), the
raw series needed to study entry timing, quote staleness vs spot, and
maker-fill behaviour. Ticks are pruned after ~45 days by db maintenance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import crypto15m
import db
import kalshi_api
import kalshi_auth

logger = logging.getLogger(__name__)

CAPTURE_LOOKBACK_MIN = 8.0
_RESOLVE_PER_TICK = 8


def _settled_up_won(m: dict) -> Optional[bool]:
    """Did the up/yes side win? None if the market isn't settled yet.

    Mirrors trader._market_yes_payout but local (no import cycle): reads
    `result`, else the settlement value (dollar or legacy cents)."""
    if not isinstance(m, dict):
        return None
    result = (m.get("result") or "").lower()
    if result == "yes":
        return True
    if result == "no":
        return False
    status = (m.get("status") or "").lower()
    if status not in ("settled", "finalized", "closed", "determined"):
        return None
    sv = m.get("settlement_value_dollars")
    if sv is not None:
        try:
            return float(sv) >= 0.5
        except (TypeError, ValueError):
            return None
    sv = m.get("settlement_value")
    if sv is not None:
        try:
            return float(sv) >= 50.0
        except (TypeError, ValueError):
            return None
    return None


def _capture_ticks(snap: dict, env: str) -> int:
    """Append a whole-window observation row for every active market —
    every recorder pass, not just the decision point. This is the raw
    series that lets entry TIMING, spot-vs-quote staleness, and maker
    fill behaviour be studied later (the per-market outcome joins in
    from crypto15m_signals on ticker)."""
    captured = 0
    with db.get_db() as conn:
        for a in snap.get("assets", []):
            if not a.get("hasMarket") or not a.get("ticker"):
                continue
            db.insert_crypto15m_tick(conn, {
                "ticker": a["ticker"],
                "asset": a["asset"],
                "mins_left": a.get("minsLeft"),
                "yes_bid": a.get("yesBid"),
                "yes_ask": a.get("yesAsk"),
                "up_prob": a.get("upProb"),
                "spot": a.get("spotUsd"),
                "open_spot": a.get("open15mUsd"),
                "delta_pct": a.get("deltaPct"),
                "kalshi_env": env,
            })
            captured += 1
    return captured


def _capture(snap: dict, env: str) -> int:
    captured = 0
    for a in snap.get("assets", []):
        if not a.get("hasMarket") or not a.get("ticker"):
            continue
        ml = a.get("minsLeft")
        fav = a.get("favorite")
        if ml is None or ml > CAPTURE_LOOKBACK_MIN or fav not in ("up", "down"):
            continue
        row = {
            "ticker": a["ticker"],
            "asset": a["asset"],
            "series": a.get("series", ""),
            "close_time": a.get("closeTime", ""),
            "mins_left": ml,
            "favorite": fav,
            "favorite_price": a.get("favoritePrice"),
            "entry_cost": a.get("entryCost"),
            "up_prob": a.get("upProb"),
            "delta_pct": a.get("deltaPct"),
            "open_spot": a.get("open15mUsd"),
            "obs_spot": a.get("spotUsd"),
            "kalshi_env": env,
        }
        with db.get_db() as conn:
            if db.insert_crypto15m_signal(conn, row):
                captured += 1
    return captured


async def _resolve(now_epoch: float) -> int:
    with db.get_db() as conn:
        pending = db.unresolved_crypto15m_signals(conn, limit=200)
    resolved = 0
    for s in pending:
        if resolved >= _RESOLVE_PER_TICK:
            break
        ce = crypto15m._parse_close_epoch(s.get("close_time") or "")
        if ce is not None and ce > now_epoch:
            continue
        try:
            m = await kalshi_api.fetch_market(s["ticker"])
        except Exception:
            continue
        up_won = _settled_up_won(m or {})
        if up_won is None:
            continue
        with db.get_db() as conn:
            db.resolve_crypto15m_signal(conn, s["ticker"], 1 if up_won else 0)
        resolved += 1
    return resolved


async def record_tick(cfg: dict) -> dict:
    """One pass: log a tick for every active market, capture new decision
    points, resolve settled ones. Resilient — never raises into the loop."""
    env = kalshi_auth.get_env()
    now_epoch = datetime.now(timezone.utc).timestamp()
    captured = 0
    resolved = 0
    ticks = 0
    try:
        snap = await crypto15m.snapshot(cfg)
    except Exception as e:
        logger.debug(f"crypto15m snapshot failed: {e}")
        snap = None
    if snap:
        try:
            ticks = _capture_ticks(snap, env)
        except Exception as e:
            logger.debug(f"crypto15m tick capture failed: {e}")
        try:
            captured = _capture(snap, env)
        except Exception as e:
            logger.debug(f"crypto15m capture failed: {e}")
    try:
        resolved = await _resolve(now_epoch)
    except Exception as e:
        logger.debug(f"crypto15m resolve failed: {e}")
    if captured or resolved:
        logger.debug(f"crypto15m signals: +{captured} captured, {resolved} resolved")
    return {"captured": captured, "resolved": resolved, "ticks": ticks}
