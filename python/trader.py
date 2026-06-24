from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import db
from kalshi_api import (
    KalshiAPIError, cancel_order, fetch_market, get_balance,
    get_fills_for_order, get_order, get_orderbook, get_positions,
    place_limit_order,
)
from kalshi_auth import ENV_LOCK, get_env

logger = logging.getLogger(__name__)



_balance_cache: dict[str, dict] = {}


async def refresh_balance(cfg: dict, force: bool = False) -> tuple[int, int]:
    interval = float(cfg.get("balance_poll_interval", 60))
    loop = asyncio.get_event_loop()
    now = loop.time()
    # Hold the env lock across read-env → fetch → cache so a concurrent
    # credential test (which briefly flips the global env) can't make us fetch
    # the other account's balance and cache it under this env. Without this the
    # displayed balance flickers between demo and production.
    async with ENV_LOCK:
        env = get_env()
        cached = _balance_cache.get(env)
        if not force and cached and (now - cached["at"]) < interval:
            return cached["cents"], cached["portfolio_cents"]
        try:
            data = await get_balance()
            cents = int(data.get("balance", 0))
            port = int(data.get("portfolio_value", 0))
            _balance_cache[env] = {"cents": cents, "portfolio_cents": port, "at": now}
            return cents, port
        except Exception as e:
            logger.warning(f"balance fetch failed: {e}")
            cached = _balance_cache.get(env)
            return (cached["cents"], cached["portfolio_cents"]) if cached else (0, 0)




def _compute_position_usd(balance_usd: float, edge_pts: float, cfg: dict) -> float:
    if cfg.get("sizing_mode") == "fixed":
        return min(
            float(cfg.get("fixed_trade_usd", 5.0) or 0.0),
            float(cfg["hard_max_position_usd"]),
        )
    lo_e = float(cfg["sizing_base_edge"])
    hi_e = float(cfg["sizing_max_edge"])
    lo_f = float(cfg["min_size_fraction"])
    hi_f = float(cfg["max_size_fraction"])
    if edge_pts <= lo_e:
        frac = lo_f
    elif edge_pts >= hi_e:
        frac = hi_f
    else:
        t = (edge_pts - lo_e) / (hi_e - lo_e)
        frac = lo_f + t * (hi_f - lo_f)
    return min(balance_usd * frac, float(cfg["hard_max_position_usd"]))




def _best_cross_price_cents(orderbook: dict, side: str) -> Optional[int]:
    side = side.lower()
    opposing_bids = orderbook.get("no" if side == "yes" else "yes") or []
    if not opposing_bids:
        return None
    try:
        best = max(int(b[0]) for b in opposing_bids if b and b[0] is not None)
    except (ValueError, TypeError):
        return None
    cross = 100 - best
    return cross if 1 <= cross <= 99 else None


async def _compute_limit_price_cents(
    ticker: str, direction: str, signal_price_cents: int, cfg: dict
) -> int:
    direction = direction.lower()
    style = cfg.get("order_style", "limit_cross")
    if style == "market":
        return 99 if direction == "yes" else 99
    try:
        book = await get_orderbook(ticker)
        cross = _best_cross_price_cents(book, direction)
        if cross is not None:
            if style == "limit_mid":
                our_bids = book.get(direction) or []
                if our_bids:
                    best_ours = max(
                        int(b[0]) for b in our_bids if b and b[0] is not None
                    )
                    return max(1, min(99, (cross + best_ours) // 2))
            return cross
    except Exception as e:
        logger.warning(f"orderbook fetch failed for {ticker}: {e}")
    fallback = signal_price_cents + int(cfg.get("cross_spread_fallback_offset", 2))
    return max(1, min(99, fallback))




def _signal_cost_cents(signal: dict, source: str) -> tuple[str, int]:
    if source == "whale":
        direction = (signal.get("taker_side") or "yes").lower()
        price_frac = float(signal.get("price") or 0.0)
        cents = max(1, min(99, int(round(price_frac * 100))))
        return direction, cents
    if source == "convergence":
        direction = (signal.get("direction") or "yes").lower()
        price_frac = float(signal.get("price") or 0.5)
        cents = max(1, min(99, int(round(price_frac * 100))))
        return direction, cents
    direction = (signal.get("direction") or "yes").lower()
    yes_frac = float(signal.get("price") or 0.0)
    yes_cents = max(1, min(99, int(round(yes_frac * 100))))
    if direction == "yes":
        return direction, yes_cents
    return direction, max(1, min(99, 100 - yes_cents))


def _compute_edge(signal: dict, source: str) -> float:
    conf = float(signal.get("confidence") or 0.0)
    if source == "whale":
        implied = float(signal.get("price") or 0.0) * 100
    elif source == "convergence":
        implied = float(signal.get("price") or 0.5) * 100
    else:
        direction = (signal.get("direction") or "yes").lower()
        yes = float(signal.get("price") or 0.0)
        implied = (yes if direction == "yes" else (1.0 - yes)) * 100
    return conf - implied


def should_trade(signal: dict, source: str, cfg: dict) -> tuple[bool, str]:
    # "Secret Strategy" — pure gambling. Ignore every gate (confidence, edge,
    # category, price); each fresh signal just gets a flat random roll.
    if cfg.get("gambling_mode"):
        prob = float(cfg.get("gambling_trade_probability", 0.10) or 0.0)
        pct = int(round(prob * 100))
        if random.random() < prob:
            return True, f"\U0001F3B0 gambling: HIT ({pct}%)"
        return False, f"\U0001F3B0 gambling: no hit ({pct}%)"

    conf = float(signal.get("confidence") or 0.0)
    edge = _compute_edge(signal, source)

    if source == "whale":
        if not cfg.get("trade_whales", False):
            return False, "whales disabled"
        if conf < cfg["min_confidence_whale"]:
            return False, f"conf {conf:.1f} < {cfg['min_confidence_whale']}"
        if edge < cfg["min_edge_pts_whale"]:
            return False, f"edge {edge:.1f} < {cfg['min_edge_pts_whale']}"
    elif source == "momentum":
        if not cfg.get("trade_momentum", False):
            return False, "momentum disabled"
        if conf < cfg["min_confidence_momentum"]:
            return False, f"conf {conf:.1f} < {cfg['min_confidence_momentum']}"
        if edge < cfg["min_edge_pts_momentum"]:
            return False, f"edge {edge:.1f} < {cfg['min_edge_pts_momentum']}"
        sig_type = (signal.get("signal_type") or "")
        allowed = set(cfg.get("allowed_momentum_signal_types", []))
        if sig_type not in allowed:
            return False, f"signal_type {sig_type!r} not allowed"
    elif source == "convergence":
        if not cfg.get("trade_convergence", False):
            return False, "convergence disabled"
        if conf < cfg["min_confidence_whale"]:
            return False, f"conf {conf:.1f} < {cfg['min_confidence_whale']}"

    cat = (signal.get("category") or "").lower()
    allowed_cats = cfg.get("allowed_categories")
    if allowed_cats is not None:
        if not allowed_cats:
            return False, "no categories enabled"
        if cat not in {c.lower() for c in allowed_cats}:
            return False, f"category {cat!r} not in allowed set"

    src_key = {
        "whale": "allowed_whale_categories",
        "convergence": "allowed_whale_categories",
        "momentum": "allowed_momentum_categories",
    }.get(source)
    src_cats = cfg.get(src_key) if src_key else None
    if src_cats is not None:
        if not src_cats:
            return False, f"no {source} categories enabled"
        if cat not in {c.lower() for c in src_cats}:
            return False, f"category {cat!r} not in {source} set"

    _, cost_cents = _signal_cost_cents(signal, source)
    if cost_cents < cfg["min_entry_price_cents"]:
        return False, f"entry {cost_cents}c < {cfg['min_entry_price_cents']}c"
    if cost_cents > cfg["max_entry_price_cents"]:
        return False, f"entry {cost_cents}c > {cfg['max_entry_price_cents']}c"
    return True, "ok"




def _today_pnl_balance_delta(env: str) -> float | None:
    with db.get_db() as conn:
        first_today = db.first_snapshot_of_today(conn, env)
        if not first_today:
            return None
        latest = db.latest_snapshot(conn, env)
    if not latest:
        return None
    today_baseline = float(first_today["total_usd"] or 0.0)
    today_total = float(latest["total_usd"] or 0.0)
    return today_total - today_baseline


def _is_blocked_by_daily_risk(cfg: dict, env: str) -> tuple[bool, str]:
    pnl = _today_pnl_balance_delta(env)
    if pnl is None:
        return False, ""
    sl = float(cfg.get("stop_loss_on_day", 0))
    tp = float(cfg.get("take_profit_on_day", 0))
    if sl < 0 and pnl <= sl:
        return True, f"daily stop-loss hit (today pnl=${pnl:+.2f}, limit=${sl:+.2f})"
    if tp > 0 and pnl >= tp:
        return True, f"daily take-profit hit (today pnl=${pnl:+.2f}, target=${tp:+.2f})"
    return False, ""


_DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _is_blocked_by_trading_hours(cfg: dict) -> tuple[bool, str]:
    if not cfg.get("trading_hours_enabled"):
        return False, ""
    from datetime import datetime, timedelta, timezone
    offset_min = int(cfg.get("trading_timezone_offset_min", 0) or 0)
    local_now = datetime.now(timezone.utc) + timedelta(minutes=offset_min)
    days = [d.lower() for d in (cfg.get("trading_days") or [])]
    weekday_short = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][local_now.weekday()]
    if weekday_short not in days:
        return True, f"trading-hours: {weekday_short} not in active days"
    try:
        s_h, s_m = (int(x) for x in str(cfg.get("trading_hours_start", "00:00")).split(":"))
        e_h, e_m = (int(x) for x in str(cfg.get("trading_hours_end", "23:59")).split(":"))
    except (ValueError, AttributeError):
        return False, ""
    cur_min = local_now.hour * 60 + local_now.minute
    start_min = s_h * 60 + s_m
    end_min = e_h * 60 + e_m
    in_window = (
        (start_min <= end_min and start_min <= cur_min <= end_min)
        or (start_min > end_min and (cur_min >= start_min or cur_min <= end_min))
    )
    if not in_window:
        return True, (
            f"trading-hours: outside window "
            f"({local_now.strftime('%H:%M')} not in "
            f"{s_h:02d}:{s_m:02d}-{e_h:02d}:{e_m:02d})"
        )
    return False, ""




async def execute_signal(
    signal: dict, source: str, cfg: dict, balance_usd: float
) -> dict | None:
    direction, signal_cost_cents = _signal_cost_cents(signal, source)
    edge_pts = _compute_edge(signal, source)
    env = get_env()

    with db.get_db() as conn:
        open_count = db.count_open_bot_positions(conn, env)
        if open_count >= cfg["max_open_positions"]:
            logger.info(
                f"[skip] {signal['ticker']}: MAX_OPEN_POSITIONS "
                f"({open_count}/{cfg['max_open_positions']} open)"
            )
            return None
        if not cfg.get("unlimited_daily_new_positions"):
            today_count = db.count_new_positions_today(conn, env)
            daily_cap = int(cfg["max_daily_new_positions"])
            if today_count >= daily_cap:
                logger.info(
                    f"[skip] {signal['ticker']}: MAX_DAILY_NEW_POSITIONS "
                    f"({today_count}/{daily_cap} today). "
                    f"Toggle 'Unlimited daily new positions' in Settings → "
                    f"Concurrency to disable this cap."
                )
                return None
        if cfg["max_positions_per_event"] == 1 and db.exists_position_in_event(
            conn, signal.get("event_ticker") or "", env
        ):
            logger.info(f"[skip] {signal['ticker']}: event already has a position")
            return None
        if db.exists_position_in_market(conn, signal["ticker"], direction, env):
            logger.info(f"[skip] {signal['ticker']}: market/side already open")
            return None
        exposure = db.current_total_exposure_usd(conn, env)

    target_usd = _compute_position_usd(balance_usd, edge_pts, cfg)
    max_exposure = balance_usd * float(cfg["max_total_exposure_fraction"])
    target_usd = min(target_usd, max(0.0, max_exposure - exposure))
    reserve = balance_usd * float(cfg["min_cash_reserve_fraction"])
    target_usd = min(target_usd, max(0.0, balance_usd - reserve - exposure))

    if target_usd < 1.0:
        logger.info(f"[skip] {signal['ticker']}: size ${target_usd:.2f} < $1")
        return None

    limit_cents = await _compute_limit_price_cents(
        signal["ticker"], direction, signal_cost_cents, cfg
    )
    if not (cfg["min_entry_price_cents"] <= limit_cents <= cfg["max_entry_price_cents"]):
        logger.info(
            f"[skip] {signal['ticker']}: order price {limit_cents}c outside band "
            f"[{cfg['min_entry_price_cents']},{cfg['max_entry_price_cents']}]c "
            f"(book moved since signal)"
        )
        return None
    contracts = max(1, int(target_usd * 100 // limit_cents))
    expected_cost_usd = contracts * limit_cents / 100.0
    client_order_id = f"krypt-{source}-{signal['id']}-{uuid.uuid4().hex[:8]}"

    logger.info(
        f"[{source}] {signal['ticker']} {direction} x{contracts} @ {limit_cents}c "
        f"= ${expected_cost_usd:.2f} conf={signal.get('confidence',0):.1f} edge={edge_pts:.1f}"
    )

    row = {
        "signal_source": source,
        "signal_id": signal["id"],
        "ticker": signal["ticker"],
        "event_ticker": signal.get("event_ticker", ""),
        "title": signal.get("title", ""),
        "category": signal.get("category", ""),
        "direction": direction,
        "action": "buy",
        "target_contracts": contracts,
        "limit_price_cents": limit_cents,
        "filled_contracts": 0,
        "cost_usd": 0.0,
        "client_order_id": client_order_id,
        "kalshi_order_id": None,
        "status": "submitted",
        "confidence": signal.get("confidence", 0.0),
        "edge_pts": edge_pts,
        "signal_price": (signal.get("price") or 0.0) * 100,
        "balance_before_usd": balance_usd,
        "kalshi_env": env,
    }

    if not cfg.get("enable_trading"):
        logger.info(f"[skip] {signal['ticker']}: trading disabled (enable_trading off)")
        return None

    try:
        resp = await place_limit_order(
            ticker=signal["ticker"],
            side=direction,
            action="buy",
            count=contracts,
            price_cents=limit_cents,
            client_order_id=client_order_id,
        )
    except KalshiAPIError as e:
        row["status"] = "error"
        row["error"] = f"HTTP {e.status}: {str(e.body)[:200]}"
        logger.error(f"[ORDER-FAIL] {signal['ticker']}: {row['error']}")
        with db.get_db() as conn:
            pid = db.insert_bot_position(conn, row)
            db.log_event(conn, pid, "error", note=row["error"])
            return db.fetch_position_by_id(conn, pid)
    except Exception as e:
        row["status"] = "error"
        row["error"] = f"{type(e).__name__}: {e}"
        logger.error(f"[ORDER-EXC] {signal['ticker']}: {row['error']}")
        with db.get_db() as conn:
            pid = db.insert_bot_position(conn, row)
            db.log_event(conn, pid, "error", note=row["error"])
            return db.fetch_position_by_id(conn, pid)

    order = (resp.get("order") if isinstance(resp, dict) else None) or resp or {}
    order_id = order.get("order_id") if isinstance(order, dict) else None
    row["kalshi_order_id"] = order_id

    with db.get_db() as conn:
        pid = db.insert_bot_position(conn, row)
        db.log_event(
            conn, pid, "placed", kalshi_status=order.get("status"),
            note=f"order_id={order_id}",
        )
        return db.fetch_position_by_id(conn, pid)




async def scan_for_trades(cfg: dict) -> list[dict]:
    global _last_scan_skip_log
    now_ts = time.time()

    def _skip_log(reason: str) -> None:
        last = _last_scan_skip_log.get(reason, 0)
        if now_ts - last < 60:
            return
        _last_scan_skip_log[reason] = now_ts
        logger.info(f"[skip-cycle] {reason}")

    if not cfg.get("enable_trading"):
        _skip_log("enable_trading=false (master kill-switch off in Settings)")
        return []

    env = get_env()
    blocked, reason = _is_blocked_by_daily_risk(cfg, env)
    if blocked:
        _skip_log(reason)
        return []
    blocked, reason = _is_blocked_by_trading_hours(cfg)
    if blocked:
        _skip_log(reason)
        return []

    cents, _ = await refresh_balance(cfg)
    balance_usd = cents / 100.0
    if balance_usd < 5.0:
        _skip_log(f"balance ${balance_usd:.2f} too low")
        return []

    candidates: list[tuple[dict, str]] = []
    fetched_w = fetched_m = 0
    with db.get_db() as conn:
        if cfg.get("trade_whales"):
            seen = db.already_traded_signal_ids(conn, "whale", env)
            for sig in db.fetch_tradeable_whale_signals(
                conn,
                min_confidence=float(cfg["min_confidence_whale"]),
                max_age_sec=int(cfg["max_signal_age_sec"]),
                seen_ids=seen,
            ):
                fetched_w += 1
                candidates.append((sig, "whale"))
        if cfg.get("trade_momentum"):
            seen = db.already_traded_signal_ids(conn, "momentum", env)
            for sig in db.fetch_tradeable_momentum_signals(
                conn,
                min_confidence=float(cfg["min_confidence_momentum"]),
                max_age_sec=int(cfg["max_signal_age_sec"]),
                allowed_types=list(cfg.get("allowed_momentum_signal_types", [])),
                seen_ids=seen,
            ):
                fetched_m += 1
                candidates.append((sig, "momentum"))

    if not candidates:
        bits = []
        if not cfg.get("trade_whales"):
            bits.append("whales OFF")
        if not cfg.get("trade_momentum"):
            bits.append("momentum OFF")
        if not bits:
            bits.append(
                f"no fresh signals match thresholds "
                f"(whale min_conf={cfg.get('min_confidence_whale')}, "
                f"momentum min_conf={cfg.get('min_confidence_momentum')}, "
                f"max_age={cfg.get('max_signal_age_sec')}s)"
            )
        _skip_log("no candidates: " + ", ".join(bits))
        return []

    candidates.sort(key=lambda c: _compute_edge(c[0], c[1]), reverse=True)
    inserted: list[dict] = []
    filter_counts: dict[str, int] = {}
    for sig, src in candidates:
        ok, why = should_trade(sig, src, cfg)
        if not ok:
            key = (int(sig.get("id") or 0), src)
            last = _last_filter_log.get(key, 0.0)
            if (now_ts - last) >= float(cfg.get("max_signal_age_sec", 120)):
                logger.info(f"[filter] {sig['ticker']} {src}: {why}")
                _last_filter_log[key] = now_ts
            filter_counts[why] = filter_counts.get(why, 0) + 1
            continue
        try:
            row = await execute_signal(sig, src, cfg, balance_usd)
            if row:
                inserted.append(row)
        except Exception as e:
            logger.error(f"[exec-fail] {sig['ticker']} {src}: {e}", exc_info=True)
        cents, _ = await refresh_balance(cfg, force=True)
        balance_usd = cents / 100.0
        if balance_usd < 5.0:
            logger.info("[halt-cycle] balance now below $5")
            break

    if candidates:
        rejected = sum(filter_counts.values())
        logger.info(
            f"[trade-cycle] candidates={len(candidates)} "
            f"(whale={fetched_w}, momentum={fetched_m}) "
            f"placed={len(inserted)} filtered={rejected}"
        )

    return inserted


_last_scan_skip_log: dict[str, float] = {}

_last_filter_log: dict[tuple[int, str], float] = {}

_last_skip_import_log: dict[tuple[str, str], float] = {}




def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _parse_kalshi_order(order: dict) -> dict:
    if order.get("fill_count_fp") is not None or order.get("taker_fill_cost_dollars") is not None:
        filled = int(round(_f(order.get("fill_count_fp"))))
        cost_cents = int(round(
            (_f(order.get("taker_fill_cost_dollars")) + _f(order.get("maker_fill_cost_dollars"))) * 100
        ))
        place_count = int(round(_f(order.get("initial_count_fp"))))
        remaining = int(round(_f(order.get("remaining_count_fp"))))
    else:
        filled = int(order.get("taker_fill_count") or 0) + int(order.get("maker_fill_count") or 0)
        cost_cents = int(order.get("taker_fill_cost") or 0) + int(order.get("maker_fill_cost") or 0)
        place_count = int(order.get("place_count") or 0)
        remaining = int(order.get("remaining_count") or 0)
    status = (order.get("status") or "").lower()
    avg_cents = (cost_cents / filled) if filled else None
    return {
        "filled": filled,
        "cost_cents": cost_cents,
        "avg_cents": avg_cents,
        "status": status,
        "place_count": place_count,
        "remaining": remaining,
    }


def _parse_kalshi_fill(f: dict, default_side: str = "") -> dict:
    if f.get("count") is not None:
        count = int(_f(f.get("count")))
    else:
        count = int(round(_f(f.get("count_fp"))))
    side = str(f.get("side") or default_side).lower()
    if side == "yes":
        cents = f.get("yes_price")
        if cents in (None, "") and f.get("yes_price_dollars") is not None:
            cents = int(round(_f(f.get("yes_price_dollars")) * 100))
    else:
        cents = f.get("no_price")
        if cents in (None, "") and f.get("no_price_dollars") is not None:
            cents = int(round(_f(f.get("no_price_dollars")) * 100))
    try:
        price_cents: Optional[int] = int(cents) if cents not in (None, "") else None
    except (TypeError, ValueError):
        price_cents = None
    if price_cents is not None and not (1 <= price_cents <= 99):
        price_cents = None
    return {"count": count, "side": side, "price_cents": price_cents}


def _parse_kalshi_position(p: dict) -> dict:
    try:
        qty_signed = float(p.get("position_fp") or 0)
    except (TypeError, ValueError):
        qty_signed = 0.0
    filled = int(abs(round(qty_signed)))
    side = "yes" if qty_signed > 0 else ("no" if qty_signed < 0 else "")
    try:
        exposure_usd = float(p.get("market_exposure_dollars") or 0)
    except (TypeError, ValueError):
        exposure_usd = 0.0
    try:
        fees_usd = float(p.get("fees_paid_dollars") or 0)
    except (TypeError, ValueError):
        fees_usd = 0.0
    cost_cents = int(round(exposure_usd * 100))
    avg_cents = (cost_cents / filled) if filled else None
    return {
        "filled": filled,
        "cost_cents": cost_cents,
        "avg_cents": avg_cents,
        "fees_usd": fees_usd,
        "side": side,
        "status": "executed",
        "place_count": filled,
        "remaining": 0,
    }


def _db_status_from_order(parsed: dict, target: int) -> str:
    s = parsed["status"]
    filled = parsed["filled"]
    if s == "executed" or (filled >= target and target > 0):
        return "filled"
    if s in ("canceled", "cancelled"):
        return "canceled" if filled == 0 else "partial"
    if filled > 0:
        return "partial"
    if s == "resting":
        return "submitted"
    return "submitted"


_poll_failures: dict[int, int] = {}
_POLL_FAILURE_THRESHOLD = 6


async def poll_open_orders(cfg: dict) -> list[dict]:
    with db.get_db() as conn:
        pending = db.get_pending_bot_positions(conn)
    if not pending:
        return []

    pos_by_key: dict[tuple[str, str], dict] = {}
    try:
        live_positions = await get_positions(limit=1000)
        for lp in live_positions:
            qty = 0.0
            for k in ("position_fp", "position"):
                v = lp.get(k)
                if v in (None, "", 0):
                    continue
                try:
                    f = float(v)
                    if f != 0:
                        qty = f
                        break
                except (TypeError, ValueError):
                    pass
            if qty == 0:
                continue
            tkr = lp.get("ticker") or ""
            side = "yes" if qty > 0 else "no"
            pos_by_key[(tkr, side)] = lp
    except Exception as e:
        logger.debug(f"poll: get_positions for rescue failed: {e}")

    updated: list[dict] = []

    def _bump_failure(pid: int) -> int:
        n = _poll_failures.get(pid, 0) + 1
        _poll_failures[pid] = n
        return n

    def _clear_failure(pid: int) -> None:
        _poll_failures.pop(pid, None)

    def _try_rescue_from_position_aggregate(pos: dict) -> dict | None:
        live_p = pos_by_key.get((pos["ticker"], pos["direction"]))
        if not live_p:
            return None
        with db.get_db() as conn:
            siblings = conn.execute(
                """SELECT id FROM bot_positions
                    WHERE ticker = ? AND direction = ?
                      AND kalshi_env = ?
                      AND resolved = 0
                      AND status NOT IN ('gone','canceled','expired','error','dry_run')""",
                (pos["ticker"], pos["direction"], pos["kalshi_env"]),
            ).fetchall()
        if len(siblings) != 1:
            return None
        qty = 0.0
        for k in ("position_fp", "position"):
            v = live_p.get(k)
            if v in (None, "", 0):
                continue
            try:
                f = float(v)
                if f != 0:
                    qty = abs(f)
                    break
            except (TypeError, ValueError):
                pass
        cost_cents = 0.0
        v = live_p.get("market_exposure")
        if v not in (None, "", 0):
            try:
                cost_cents = abs(float(v))
            except (TypeError, ValueError):
                pass
        if cost_cents == 0:
            v = live_p.get("market_exposure_dollars")
            if v not in (None, ""):
                try:
                    cost_cents = abs(float(v) * 100.0)
                except (TypeError, ValueError):
                    pass
        if qty <= 0:
            return None
        local_cost_usd = float(pos.get("cost_usd") or 0.0)
        local_avg_cents = pos.get("avg_fill_price_cents")
        new_cost_usd = (
            cost_cents / 100.0 if cost_cents > 0 else local_cost_usd
        )
        new_avg_cents = (
            (cost_cents / qty) if (qty and cost_cents > 0)
            else local_avg_cents
        )
        new_filled = int(round(qty))

        cur_filled = int(pos.get("filled_contracts") or 0)
        cur_cost_usd = float(pos.get("cost_usd") or 0.0)
        if (
            pos.get("status") == "filled"
            and cur_filled == new_filled
            and abs(cur_cost_usd - new_cost_usd) < 0.005
        ):
            return None

        with db.get_db() as conn:
            db.update_bot_position(
                conn, pos["id"], status="filled",
                filled_contracts=new_filled,
                cost_usd=new_cost_usd,
                avg_fill_price_cents=new_avg_cents,
            )
            db.log_event(
                conn, pos["id"], "poll",
                note="rescued via /portfolio/positions",
            )
            return db.fetch_position_by_id(conn, pos["id"])

    for pos in pending:
        kid = pos.get("kalshi_order_id")
        if pos["status"] == "dry_run":
            continue

        if pos["status"] == "filled":
            row = _try_rescue_from_position_aggregate(pos)
            if row:
                _clear_failure(pos["id"])
                updated.append(row)
            else:
                _clear_failure(pos["id"])
            continue

        if not kid:
            row = _try_rescue_from_position_aggregate(pos)
            if row:
                _clear_failure(pos["id"])
                updated.append(row)
                continue
            n = _bump_failure(pos["id"])
            if n >= _POLL_FAILURE_THRESHOLD:
                with db.get_db() as conn:
                    db.update_bot_position(
                        conn, pos["id"], status="gone",
                        error=f"missing kalshi_order_id ({n} cycles)",
                    )
                    db.log_event(conn, pos["id"], "poll", note=f"no id × {n} -> gone")
                    row = db.fetch_position_by_id(conn, pos["id"])
                if row:
                    updated.append(row)
                _clear_failure(pos["id"])
            continue

        try:
            resp = await get_order(kid)
            order = (resp.get("order") if isinstance(resp, dict) else resp) or {}
            parsed = _parse_kalshi_order(order)
        except KalshiAPIError as e:
            row = _try_rescue_from_position_aggregate(pos)
            if row:
                _clear_failure(pos["id"])
                updated.append(row)
                continue
            n = _bump_failure(pos["id"])
            logger.debug(
                f"order poll {kid}: HTTP {e.status} (failure #{n})"
            )
            if e.status == 404 and n >= _POLL_FAILURE_THRESHOLD:
                with db.get_db() as conn:
                    db.update_bot_position(
                        conn, pos["id"], status="gone",
                        error=f"order 404 × {n}",
                    )
                    db.log_event(conn, pos["id"], "poll", note=f"404 × {n} -> gone")
                    row = db.fetch_position_by_id(conn, pos["id"])
                if row:
                    updated.append(row)
                _clear_failure(pos["id"])
            continue
        except Exception as e:
            _bump_failure(pos["id"])
            logger.warning(f"order poll {kid}: {e}")
            continue

        _clear_failure(pos["id"])

        db_status = _db_status_from_order(parsed, pos["target_contracts"])
        if db_status == "filled" and parsed["filled"] == 0:
            rescued = _try_rescue_from_position_aggregate(pos)
            if rescued:
                updated.append(rescued)
                continue
            db_status = "gone"

        with db.get_db() as conn:
            fields: dict = {
                "status": db_status,
                "filled_contracts": parsed["filled"],
            }
            if parsed["avg_cents"] is not None:
                fields["avg_fill_price_cents"] = parsed["avg_cents"]
            if parsed["cost_cents"]:
                fields["cost_usd"] = parsed["cost_cents"] / 100.0
            if parsed.get("fees_usd"):
                fields["fees_usd"] = parsed["fees_usd"]
            db.update_bot_position(conn, pos["id"], **fields)
            db.log_event(
                conn, pos["id"], "poll",
                kalshi_status=parsed["status"],
                filled_contracts=parsed["filled"],
                fill_cost_cents=parsed["cost_cents"] or None,
            )
            row = db.fetch_position_by_id(conn, pos["id"])
        if row:
            updated.append(row)

        if (
            db_status == "submitted"
            and cfg.get("order_expiration_sec") is not None
            and parsed["filled"] == 0
            and kid
        ):
            with db.get_db() as conn:
                age = conn.execute(
                    "SELECT (julianday('now')-julianday(created_at))*86400 "
                    "FROM bot_positions WHERE id=?", (pos["id"],),
                ).fetchone()
            age_sec = float(age[0]) if age and age[0] is not None else 0.0
            if age_sec > float(cfg["order_expiration_sec"]):
                try:
                    await cancel_order(kid)
                    with db.get_db() as conn:
                        db.update_bot_position(
                            conn, pos["id"], status="canceled",
                            error=f"auto-canceled after {age_sec:.0f}s",
                        )
                        db.log_event(conn, pos["id"], "cancel", note=f"age {age_sec:.0f}s")
                        r = db.fetch_position_by_id(conn, pos["id"])
                    if r:
                        updated.append(r)
                except KalshiAPIError as e:
                    with db.get_db() as conn:
                        db.update_bot_position(
                            conn, pos["id"], status="gone",
                            error=f"cancel 404: {str(e.body)[:100]}",
                        )
                        db.log_event(conn, pos["id"], "cancel", note="404 -> gone")
                        r = db.fetch_position_by_id(conn, pos["id"])
                    if r:
                        updated.append(r)
                except Exception as e:
                    logger.warning(f"cancel exception {kid}: {e}")

    return updated




def _market_yes_payout(market: dict | None) -> Optional[float]:
    if not market:
        return None
    result = (market.get("result") or "").lower()
    if result == "yes":
        return 1.0
    if result == "no":
        return 0.0
    status = (market.get("status") or "").lower()
    if status not in ("settled", "finalized", "determined"):
        return None
    sv = market.get("settlement_value_dollars")
    if sv is None:
        sv = market.get("settlement_value")
        if sv is not None:
            try:
                sv = float(sv) / 100.0
            except (TypeError, ValueError):
                sv = None
    if sv is None:
        return None
    try:
        f = float(sv)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, f))


async def mark_resolved_positions(cfg: dict) -> list[dict]:
    with db.get_db() as conn:
        unresolved = db.get_unresolved_bot_positions(conn)
    if not unresolved:
        return []

    env = get_env()
    by_env = [p for p in unresolved if p["kalshi_env"] == env]
    if not by_env:
        return []

    updated: list[dict] = []
    needs_market: list[dict] = []
    for pos in by_env:
        filled = int(pos["filled_contracts"] or 0)
        if filled <= 0:
            with db.get_db() as conn:
                db.update_bot_position(
                    conn, pos["id"], resolved=1, outcome_correct=None,
                    pnl_usd=0.0, settlement_usd=0.0,
                )
                conn.execute(
                    "UPDATE bot_positions SET resolved_at=datetime('now') WHERE id=?",
                    (pos["id"],),
                )
                db.log_event(conn, pos["id"], "resolve", note="no fill -> closed")
                r = db.fetch_position_by_id(conn, pos["id"])
            if r:
                updated.append(r)
            continue
        needs_market.append(pos)

    if not needs_market:
        return updated

    market_cache: dict[str, dict | None] = {}
    for ticker in {p["ticker"] for p in needs_market}:
        try:
            m = await fetch_market(ticker)
        except Exception as e:
            logger.debug(f"fetch_market({ticker}) failed: {e}")
            m = None
        market_cache[ticker] = m
        if m:
            try:
                with db.get_db() as conn:
                    db.upsert_market(
                        conn,
                        {
                            "ticker": ticker,
                            "event_ticker": m.get("event_ticker", ""),
                            "title": m.get("title", ""),
                            "yes_sub_title": m.get("yes_sub_title", ""),
                            "status": m.get("status", ""),
                            "close_time": m.get("close_time", ""),
                            "volume": m.get("volume_fp", 0),
                            "volume_24h": m.get("volume_24h_fp", 0),
                            "open_interest": m.get("open_interest_fp", 0),
                            "yes_bid": m.get("yes_bid_dollars", 0),
                            "yes_ask": m.get("yes_ask_dollars", 0),
                            "last_price": m.get("last_price_dollars", 0),
                            "result": m.get("result", ""),
                            "settlement_value": m.get("settlement_value_dollars"),
                        },
                    )
            except Exception:
                pass

    for pos in needs_market:
        market = market_cache.get(pos["ticker"])
        yes_payout = _market_yes_payout(market)
        if yes_payout is None:
            continue

        direction = pos["direction"]
        filled = int(pos["filled_contracts"] or 0)
        cost_usd = float(pos["cost_usd"] or 0.0)
        our_payout = yes_payout if direction == "yes" else (1.0 - yes_payout)
        settlement_usd = filled * our_payout
        pnl_usd = settlement_usd - cost_usd

        max_settlement = float(filled)
        max_pnl = max_settlement - cost_usd
        min_pnl = -cost_usd
        if pnl_usd > max_pnl + 0.01 or pnl_usd < min_pnl - 0.01:
            logger.warning(
                f"[resolve-clamp] {pos['ticker']} pnl=${pnl_usd:+.2f} "
                f"outside physical bounds (filled={filled}, cost=${cost_usd:.2f}, "
                f"settlement=${settlement_usd:.2f}); clamping. "
                f"This usually means filled_contracts or cost_usd is corrupt — "
                f"run Reconcile Fills."
            )
            pnl_usd = max(min_pnl, min(max_pnl, pnl_usd))
            settlement_usd = pnl_usd + cost_usd

        if our_payout >= 0.99:
            correct: Optional[int] = 1
        elif our_payout <= 0.01:
            correct = 0
        elif pnl_usd > 0.05:
            correct = 1
        elif pnl_usd < -0.05:
            correct = 0
        else:
            correct = None

        with db.get_db() as conn:
            db.update_bot_position(
                conn, pos["id"], resolved=1, outcome_correct=correct,
                settlement_usd=settlement_usd, pnl_usd=pnl_usd,
            )
            conn.execute(
                "UPDATE bot_positions SET resolved_at=datetime('now') WHERE id=?",
                (pos["id"],),
            )
            label = "WIN" if correct == 1 else ("LOSS" if correct == 0 else "CLOSED")
            db.log_event(
                conn, pos["id"], "resolve",
                note=f"{label} pnl=${pnl_usd:+.2f} ({filled}c @ {our_payout:.2f})",
            )
            r = db.fetch_position_by_id(conn, pos["id"])
        if r:
            updated.append(r)
            logger.info(
                f"[resolve] {pos['ticker']} {direction}: {label} "
                f"pnl=${pnl_usd:+.2f} ({filled}c @ {our_payout:.2f}, "
                f"cost=${cost_usd:.2f})"
            )

    return updated




async def reconcile_fills_from_kalshi() -> dict:
    env = get_env()
    with db.get_db() as conn:
        rows = conn.execute(
            """SELECT id, kalshi_order_id, ticker, direction, status
               FROM bot_positions
               WHERE kalshi_env=? AND kalshi_order_id IS NOT NULL
                 AND status NOT IN ('dry_run','submitted')""",
            (env,),
        ).fetchall()
        targets = [dict(r) for r in rows]

    fills_reconciled = 0
    for pos in targets:
        kid = pos["kalshi_order_id"]
        try:
            fills = await get_fills_for_order(kid)
        except Exception as e:
            logger.debug(f"fills fetch failed for {kid}: {e}")
            continue

        ours = [f for f in fills if str(f.get("order_id") or "") == str(kid)]
        if not ours and fills:
            logger.warning(
                f"[reconcile] /portfolio/fills returned {len(fills)} fills "
                f"but none matched order_id={kid} — Kalshi may have rotated "
                f"old fills out. Skipping this position."
            )
            continue

        ours = [
            f for f in ours
            if str(f.get("action") or "buy").lower() == "buy"
        ]

        total_filled = 0
        total_cost_cents = 0
        for f in ours:
            fp = _parse_kalshi_fill(f, default_side=pos["direction"])
            n = fp["count"]
            if n <= 0:
                continue
            price_cents = fp["price_cents"]
            if price_cents is None:
                logger.warning(
                    f"[reconcile] unreadable price on fill order={kid} "
                    f"side={fp['side']}; skipping fill"
                )
                continue
            total_filled += n
            total_cost_cents += n * price_cents

        if total_filled == 0 and total_cost_cents == 0:
            continue

        avg_cents = (total_cost_cents / total_filled) if total_filled else None
        with db.get_db() as conn:
            db.update_bot_position(
                conn, pos["id"],
                filled_contracts=total_filled,
                cost_usd=total_cost_cents / 100.0,
                avg_fill_price_cents=avg_cents,
            )
            db.log_event(
                conn, pos["id"], "reconcile-fills",
                filled_contracts=total_filled,
                fill_cost_cents=total_cost_cents,
            )
        fills_reconciled += 1

    with db.get_db() as conn:
        cleared = conn.execute(
            """UPDATE bot_positions
               SET resolved=0, outcome_correct=NULL,
                   pnl_usd=NULL, settlement_usd=NULL,
                   resolved_at=NULL
               WHERE kalshi_env=?
                 AND status IN ('filled','partial','expired','canceled','gone','error')
                 AND resolved=1""",
            (env,),
        ).rowcount
    resolved = await mark_resolved_positions({})
    return {
        "fills_reconciled": fills_reconciled,
        "pnl_cleared": int(cleared or 0),
        "pnl_recomputed": len(resolved),
    }


async def audit_pnl(limit: int = 200) -> dict:
    env = get_env()
    with db.get_db() as conn:
        rows = conn.execute(
            """SELECT id, ticker, direction, filled_contracts, cost_usd,
                      pnl_usd, settlement_usd, outcome_correct
               FROM bot_positions
               WHERE kalshi_env=? AND resolved=1
               ORDER BY resolved_at DESC LIMIT ?""",
            (env, int(limit)),
        ).fetchall()
        rows = [dict(r) for r in rows]

    flagged: list[dict] = []
    sum_stored = 0.0
    sum_recompute = 0.0
    for r in rows:
        market = await fetch_market(r["ticker"])
        yes_payout = _market_yes_payout(market)
        if yes_payout is None:
            continue
        direction = r["direction"]
        filled = int(r["filled_contracts"] or 0)
        cost = float(r["cost_usd"] or 0)
        our = yes_payout if direction == "yes" else (1.0 - yes_payout)
        settle = filled * our
        pnl_fresh = settle - cost
        pnl_fresh = max(-cost, min(filled - cost, pnl_fresh))
        pnl_stored = float(r["pnl_usd"] or 0)
        sum_stored += pnl_stored
        sum_recompute += pnl_fresh
        if abs(pnl_stored - pnl_fresh) > 0.05:
            flagged.append({
                "id": r["id"],
                "ticker": r["ticker"],
                "direction": direction,
                "filled": filled,
                "cost": round(cost, 2),
                "settlement_payout": round(our, 2),
                "stored_pnl": round(pnl_stored, 2),
                "fresh_pnl": round(pnl_fresh, 2),
                "delta": round(pnl_fresh - pnl_stored, 2),
            })
    return {
        "checked": len(rows),
        "flagged": len(flagged),
        "sum_stored_pnl": round(sum_stored, 2),
        "sum_recompute_pnl": round(sum_recompute, 2),
        "delta": round(sum_recompute - sum_stored, 2),
        "samples": flagged[:20],
    }


async def recompute_pnl_from_kalshi() -> dict:
    env = get_env()
    with db.get_db() as conn:
        cleared = conn.execute(
            """UPDATE bot_positions
               SET resolved=0, outcome_correct=NULL,
                   pnl_usd=NULL, settlement_usd=NULL,
                   resolved_at=NULL
               WHERE kalshi_env=?
                 AND status IN ('filled','partial','expired','canceled','gone','error')
                 AND resolved=1""",
            (env,),
        ).rowcount
    rows = await mark_resolved_positions({})
    return {"cleared": int(cleared or 0), "recomputed": len(rows)}




async def reconcile_positions_with_kalshi() -> tuple[dict, list[dict]]:
    summary = {
        "closed_orphans": 0,
        "imported_unknowns": 0,
        "rescued": 0,
        "resurrected": 0,
    }
    changed: list[dict] = []
    env = get_env()

    try:
        live = await get_positions(limit=1000)
    except Exception as e:
        logger.warning(f"reconcile: get_positions failed: {e}")
        return summary, changed

    def _signed_qty(p: dict) -> float:
        for k in ("position_fp", "position"):
            v = p.get(k)
            if v in (None, "", 0):
                continue
            try:
                f = float(v)
                if f != 0:
                    return f
            except (TypeError, ValueError):
                pass
        return 0.0

    def _cost_cents(p: dict) -> float:
        v = p.get("market_exposure")
        if v not in (None, "", 0):
            try:
                return abs(float(v))
            except (TypeError, ValueError):
                pass
        v = p.get("market_exposure_dollars")
        if v not in (None, ""):
            try:
                return abs(float(v) * 100.0)
            except (TypeError, ValueError):
                pass
        return 0.0

    nonzero_count = sum(1 for p in live if _signed_qty(p) != 0)
    if live and nonzero_count == 0:
        sample_keys = list(live[0].keys())
        logger.warning(
            f"reconcile: Kalshi returned {len(live)} positions but ZERO "
            f"have non-zero qty — likely a field-name change. "
            f"sample keys = {sample_keys}"
        )
    elif live:
        logger.debug(
            f"reconcile: Kalshi returned {len(live)} positions, "
            f"{nonzero_count} with non-zero qty"
        )

    live_by_key: dict[tuple[str, str], dict] = {}
    for p in live:
        qty = _signed_qty(p)
        if qty == 0:
            continue
        side = "yes" if qty > 0 else "no"
        live_by_key[(p.get("ticker") or "", side)] = p

    with db.get_db() as conn:
        all_local = conn.execute(
            "SELECT * FROM bot_positions WHERE kalshi_env = ?", (env,),
        ).fetchall()
    local_by_key: dict[tuple[str, str], list] = {}
    for r in all_local:
        pos = dict(r)
        if pos.get("resolved"):
            continue
        if pos.get("status") == "dry_run":
            continue
        local_by_key.setdefault(
            (pos["ticker"], pos["direction"]), [],
        ).append(pos)

    for (ticker, side), live_p in live_by_key.items():
        rows = local_by_key.get((ticker, side), [])
        qty = abs(_signed_qty(live_p))
        cost_cents = _cost_cents(live_p)
        if qty <= 0:
            continue

        if rows:
            active = next(
                (r for r in rows if r["status"] in ("submitted", "partial", "filled")),
                None,
            )
            target = active or rows[0]
            was_terminal = target["status"] in (
                "gone", "canceled", "expired", "error",
            )
            local_cost_usd = float(target.get("cost_usd") or 0.0)
            local_avg_cents = target.get("avg_fill_price_cents")
            new_cost_usd = (
                cost_cents / 100.0 if cost_cents > 0 else local_cost_usd
            )
            new_avg_cents = (
                (cost_cents / qty) if (qty and cost_cents > 0)
                else local_avg_cents
            )
            new_filled = int(round(qty))

            cur_filled = int(target.get("filled_contracts") or 0)
            cur_cost_usd = float(target.get("cost_usd") or 0.0)
            if (
                not was_terminal
                and target.get("status") == "filled"
                and cur_filled == new_filled
                and abs(cur_cost_usd - new_cost_usd) < 0.005
            ):
                continue

            with db.get_db() as conn:
                db.update_bot_position(
                    conn, target["id"], status="filled",
                    filled_contracts=new_filled,
                    cost_usd=new_cost_usd,
                    avg_fill_price_cents=new_avg_cents,
                    error=None if was_terminal else target.get("error"),
                )
                db.log_event(
                    conn, target["id"], "reconcile",
                    note=(
                        "resurrected from "
                        f"{target['status']} via /portfolio/positions"
                    ) if was_terminal else "rescued via /portfolio/positions",
                )
                row = db.fetch_position_by_id(conn, target["id"])
            if row:
                changed.append(row)
            if was_terminal:
                summary["resurrected"] += 1
                logger.info(
                    f"[reconcile] RESURRECTED #{target['id']} "
                    f"({ticker} {side}, was {target['status']}) "
                    f"qty={qty:.0f} cost=${cost_cents / 100:.2f}"
                )
            else:
                summary["rescued"] += 1
        else:
            with db.get_db() as conn:
                if db.recent_resolved_position_exists(
                    conn, ticker, side, env,
                ):
                    key = (ticker, side)
                    last = _last_skip_import_log.get(key, 0.0)
                    if (time.time() - last) >= 600:
                        logger.info(
                            f"[reconcile] skip-import {ticker} {side}: "
                            f"already resolved within 24h "
                            f"(Kalshi cash-settlement still pending)"
                        )
                        _last_skip_import_log[key] = time.time()
                    continue
            now_ms = int(time.time() * 1000)
            signal_id = (
                abs(hash((ticker, side, now_ms))) % 2_000_000_000
            )
            client_id = f"ext-{ticker}-{side}-{now_ms}"
            try:
                with db.get_db() as conn:
                    new_id = db.insert_bot_position(conn, {
                        "signal_source": "external",
                        "signal_id": signal_id,
                        "ticker": ticker,
                        "event_ticker": live_p.get("event_ticker") or "",
                        "title": live_p.get("title") or ticker,
                        "category": live_p.get("category") or "",
                        "direction": side,
                        "action": "buy",
                        "target_contracts": int(round(qty)),
                        "limit_price_cents": (
                            int(round(cost_cents / qty)) if qty else 0
                        ),
                        "filled_contracts": int(round(qty)),
                        "avg_fill_price_cents": (
                            (cost_cents / qty) if qty else None
                        ),
                        "cost_usd": cost_cents / 100.0,
                        "client_order_id": client_id,
                        "kalshi_order_id": None,
                        "status": "filled",
                        "confidence": 0.0,
                        "edge_pts": 0.0,
                        "signal_price": 0.0,
                        "kalshi_env": env,
                    })
                    row = db.fetch_position_by_id(conn, new_id)
                if row:
                    changed.append(row)
                summary["imported_unknowns"] += 1
                logger.info(
                    f"[reconcile] imported external #{new_id} "
                    f"{ticker} {side} qty={qty:.0f} "
                    f"cost=${cost_cents / 100:.2f}"
                )
            except Exception as e:
                logger.warning(
                    f"[reconcile] import failed for {ticker} {side}: {e}",
                )

    return summary, changed




async def cancel_all_open() -> int:
    with db.get_db() as conn:
        rows = conn.execute(
            """SELECT id, kalshi_order_id FROM bot_positions
               WHERE status IN ('submitted','partial')
                 AND resolved=0 AND kalshi_env=?""",
            (get_env(),),
        ).fetchall()
    canceled = 0
    for r in rows:
        kid = r["kalshi_order_id"]
        if not kid:
            continue
        try:
            await cancel_order(kid)
            with db.get_db() as conn:
                db.update_bot_position(
                    conn, r["id"], status="canceled",
                    error="user cancel-all",
                )
                db.log_event(
                    conn, r["id"], "cancel", note="user cancel-all"
                )
            canceled += 1
        except Exception as e:
            logger.warning(f"cancel_all: {kid}: {e}")
    return canceled
