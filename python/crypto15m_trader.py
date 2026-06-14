"""15-minute crypto LIVE executor.

A self-contained execution engine for the 15-min crypto strategy,
DELIBERATELY ISOLATED from the scanner trader (trader.py): it uses its
own `crypto15m_positions` table and never touches `bot_positions`, so it
cannot destabilise the tested whale/momentum engine.

Lifecycle (at most one open position per asset):
  ENTRY   in the last `time_delay` minutes, when one side is a strong
          favorite (>= entry threshold) and the delta filter passes
          (i.e. the monitor's `signal` is true), BUY `order_size`
          contracts of the favorite at ask + entryDiff.
  STOP    if the held side's price falls below `exit_threshold`, SELL to
          flatten — this is the capability the scanner engine lacks.
  SETTLE  otherwise hold to the 15-min settlement and book pnl from the
          binary outcome.

The executor is fully INDEPENDENT of the main bot's enable_trading /
dry_run switches. Two gates must be on for REAL orders:
    crypto15m_enabled  AND  crypto15m_live   (+ Kalshi auth)
Otherwise the engine PAPER-TRADES: identical decisions, fills simulated
against real market prices, no orders placed.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import crypto15m
import db
import kalshi_api
import trader

logger = logging.getLogger("crypto15m")




def direction_for_favorite(favorite: str) -> str:
    """Map the displayed favorite side to the Kalshi contract side."""
    return "yes" if favorite == "up" else "no"


def entry_limit_cents(entry_cost: float, entry_diff: float) -> int:
    """Favorite ask in [0,1] crossed up by `entry_diff`, clamped 1..99¢."""
    cents = round((float(entry_cost) + float(entry_diff)) * 100)
    return max(1, min(99, int(cents)))


def maker_limit_cents(side: str, yes_bid, yes_ask, entry_cost: float) -> int:
    """Resting (maker) entry price: join the best bid on the side we're
    buying, so the order adds liquidity instead of crossing the spread.

    up/yes  -> yes best bid;  down/no -> no best bid = 1 - yes best ask.
    Falls back to 1¢ under the side's ask when the book is unknown."""
    bid = None
    if side == "up":
        bid = yes_bid
    elif side == "down" and yes_ask:
        bid = 1.0 - float(yes_ask)
    if not bid or bid <= 0:
        bid = max(0.01, float(entry_cost) - 0.01)
    return max(1, min(99, int(round(float(bid) * 100))))


def side_prob_from_market(market: Optional[dict], direction: str) -> Optional[float]:
    """Current probability (0..1) of the side we hold, from a market dict."""
    if not market:
        return None
    yes_bid = crypto15m._price_dollars(market, "yes_bid")
    yes_ask = crypto15m._price_dollars(market, "yes_ask")
    up = (yes_bid + yes_ask) / 2 if (yes_bid or yes_ask) else crypto15m._price_dollars(market, "last_price")
    up = max(0.0, min(1.0, up))
    return up if direction == "yes" else (1.0 - up)


def should_enter(asset: dict, cfg: dict, *, has_open: bool, open_count: int) -> tuple[bool, str]:
    if not cfg.get("crypto15m_enabled"):
        return False, "disabled"
    if has_open:
        return False, "already open"
    max_conc = int(cfg.get("crypto15m_max_concurrent", len(crypto15m.SERIES)))
    if open_count >= max_conc:
        return False, "max concurrent"
    if not asset.get("hasMarket"):
        return False, "no market"
    if asset.get("favorite") not in ("up", "down"):
        return False, "no favorite"
    if not asset.get("signal"):
        return False, "no signal"
    return True, "ok"


def should_stop_loss(position: dict, side_prob: Optional[float], cfg: dict) -> bool:
    """A filled position trips the stop-loss when the side we hold falls
    below `exit_threshold`. Only `filled` rows are eligible (not ones
    already submitting/exiting/exited)."""
    if side_prob is None:
        return False
    if position.get("status") != "filled":
        return False
    if int(position.get("filled_contracts") or 0) <= 0:
        return False
    return side_prob < crypto15m._const(cfg, "exit_threshold")


def _clamp01(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if f != f:
        return 0.0
    return max(0.0, min(1.0, f))


def compute_entry_contracts(
    cfg: dict, *, entry_limit_cents: int, balance_usd: float, order_size: int
) -> int:
    """Contracts to buy for one entry.

    fixed mode      -> `order_size` contracts.
    balance_pct mode-> spend `crypto15m_balance_pct` of balance at the
                       entry price (floored to whole contracts).
    Either way, if `crypto15m_max_loss_pct` > 0 the capital at risk
    (contracts x price — the most a buy-only binary can lose) is held to
    that fraction of balance. Returns 0 when the risk budget can't fund a
    single contract, so the caller skips the entry rather than overspend.
    A balance of 0 (no account / paper before a bankroll is known) falls
    back to the fixed `order_size` and ignores the % cap."""
    price = max(0.01, int(entry_limit_cents) / 100.0)
    bal = max(0.0, float(balance_usd or 0.0))
    mode = (cfg.get("crypto15m_sizing_mode") or "fixed").lower()

    if mode == "balance_pct" and bal > 0:
        pct = _clamp01(cfg.get("crypto15m_balance_pct", 0.02))
        contracts = int((bal * pct) // price)
    else:
        contracts = max(1, int(order_size))

    max_loss = _clamp01(cfg.get("crypto15m_max_loss_pct", 0.0))
    if max_loss > 0 and bal > 0:
        contracts = min(contracts, int((bal * max_loss) // price))

    return max(0, contracts)


async def _bankroll_usd(cfg: dict, authed: bool) -> float:
    """Balance to size against. Uses live cash when connected (cached by
    `refresh_balance`), else the user's pinned start bankroll so paper
    mode can still size by % before an account is linked."""
    if authed:
        try:
            cents, _port = await trader.refresh_balance(cfg, force=False)
            if cents > 0:
                return cents / 100.0
        except Exception:
            pass
    return max(0.0, float(cfg.get("start_bankroll_usd", 0.0) or 0.0))




def _iso(s):
    if not s or not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return s
    if s.endswith("Z") or "+" in s[10:]:
        return s.replace(" ", "T")
    return s.replace(" ", "T") + "Z"


def _pos_to_js(r: dict) -> dict:
    def _f(k):
        return float(r[k]) if r.get(k) is not None else None
    return {
        "id": int(r["id"]),
        "asset": r["asset"], "series": r.get("series") or "",
        "ticker": r.get("ticker") or "",
        "side": r.get("side") or "", "direction": r.get("direction") or "",
        "targetContracts": int(r.get("target_contracts") or 0),
        "filledContracts": int(r.get("filled_contracts") or 0),
        "entryLimitCents": int(r.get("entry_limit_cents") or 0),
        "avgEntryCents": _f("avg_entry_cents"),
        "costUsd": float(r.get("cost_usd") or 0.0),
        "status": r.get("status") or "",
        "exitReason": r.get("exit_reason"),
        "exitLimitCents": int(r["exit_limit_cents"]) if r.get("exit_limit_cents") is not None else None,
        "proceedsUsd": _f("proceeds_usd"),
        "confidence": float(r.get("confidence") or 0.0),
        "entryDeltaUsd": _f("entry_delta_usd"),
        "outcomeCorrect": int(r["outcome_correct"]) if r.get("outcome_correct") is not None else None,
        "settlementUsd": _f("settlement_usd"),
        "pnlUsd": _f("pnl_usd"),
        "resolved": bool(r.get("resolved") or 0),
        "dryRun": bool(r.get("dry_run") or 0),
        "closeTime": _iso(r.get("close_time")) or "",
        "kalshiEnv": r.get("kalshi_env") or "demo",
        "createdAt": _iso(r.get("created_at")) or "",
        "resolvedAt": _iso(r.get("resolved_at")),
        "error": r.get("error"),
    }




async def _open_entry(a: dict, cfg: dict, env: str, live: bool, balance_usd: float) -> Optional[dict]:
    mode = (cfg.get("crypto15m_direction_mode") or "favorite").lower()
    favorite = a.get("favorite")
    fav_price = float(a.get("favoritePrice") or 0.0)
    if mode == "contrarian":
        side = "down" if favorite == "up" else "up"
        entry_cost = max(0.01, 1.0 - fav_price)
        conf = entry_cost * 100.0
    else:
        side = favorite
        entry_cost = float(a.get("entryCost") or fav_price)
        conf = fav_price * 100.0
    direction = direction_for_favorite(side)
    style = (cfg.get("crypto15m_entry_style") or "maker").lower()
    if style == "maker":
        limit_cents = maker_limit_cents(side, a.get("yesBid"), a.get("yesAsk"), entry_cost)
    else:
        limit_cents = entry_limit_cents(entry_cost, crypto15m._const(cfg, "entry_diff"))
    order_size = compute_entry_contracts(
        cfg,
        entry_limit_cents=limit_cents,
        balance_usd=balance_usd,
        order_size=max(1, int(cfg.get("crypto15m_order_size", 1))),
    )
    if order_size < 1:
        logger.info(
            f"[crypto15m] skip {a.get('asset')}: sizing yielded 0 contracts "
            f"(risk budget too small at {limit_cents}c)"
        )
        return None
    ticker = a.get("ticker")
    coid = f"krypt-c15-{a['asset']}-{uuid.uuid4().hex[:8]}"
    row = {
        "asset": a["asset"], "series": a["series"], "ticker": ticker,
        "side": side, "direction": direction,
        "target_contracts": order_size, "entry_limit_cents": limit_cents,
        "client_order_id": coid, "close_time": a.get("closeTime") or "",
        "confidence": conf,
        "entry_delta_usd": a.get("deltaUsd"), "kalshi_env": env,
    }

    if not live:
        if style == "maker":
            row.update({"status": "submitted", "dry_run": True})
            with db.get_db() as conn:
                pid = db.insert_crypto15m_position(conn, row)
                logger.info(f"[paper] maker entry resting {a['asset']} {direction} x{order_size} @ {limit_cents}c")
                return db.fetch_crypto15m_by_id(conn, pid)
        row.update({
            "status": "filled", "filled_contracts": order_size,
            "avg_entry_cents": float(limit_cents),
            "cost_usd": order_size * limit_cents / 100.0, "dry_run": True,
        })
        with db.get_db() as conn:
            pid = db.insert_crypto15m_position(conn, row)
            logger.info(f"[paper] entry {a['asset']} {direction} x{order_size} @ {limit_cents}c")
            return db.fetch_crypto15m_by_id(conn, pid)

    try:
        resp = await kalshi_api.place_limit_order(
            ticker=ticker, side=direction, action="buy",
            count=order_size, price_cents=limit_cents, client_order_id=coid,
        )
    except Exception as e:
        row.update({"status": "error", "error": str(e)[:200], "dry_run": False})
        with db.get_db() as conn:
            pid = db.insert_crypto15m_position(conn, row)
            _mark_resolved(conn, pid, status="error")
            logger.error(f"[crypto15m] entry order failed {a['asset']}: {e}")
            return db.fetch_crypto15m_by_id(conn, pid)

    order = (resp.get("order") if isinstance(resp, dict) else None) or resp or {}
    row.update({
        "status": "submitted",
        "kalshi_order_id": order.get("order_id") if isinstance(order, dict) else None,
        "dry_run": False,
    })
    with db.get_db() as conn:
        pid = db.insert_crypto15m_position(conn, row)
        logger.info(f"[live] entry {a['asset']} {direction} x{order_size} @ {limit_cents}c")
        return db.fetch_crypto15m_by_id(conn, pid)




def _mark_resolved(conn, pid: int, **fields) -> None:
    db.update_crypto15m_position(conn, pid, resolved=1, **fields)
    conn.execute(
        "UPDATE crypto15m_positions SET resolved_at=datetime('now') WHERE id=?", (pid,)
    )


async def _poll_entry(pos: dict, cfg: dict) -> Optional[dict]:
    pid, kid = pos["id"], pos.get("kalshi_order_id")
    if not kid:
        return None
    parsed = None
    try:
        resp = await kalshi_api.get_order(kid)
        order = (resp.get("order") if isinstance(resp, dict) else resp) or {}
        parsed = trader._parse_kalshi_order(order)
    except Exception as e:
        logger.debug(f"[crypto15m] entry poll {kid}: {e}")

    filled = int(parsed.get("filled") or 0) if parsed else 0
    remaining = int(parsed.get("remaining") or 0) if parsed else 0

    if filled > 0 and remaining <= 0:
        with db.get_db() as conn:
            db.update_crypto15m_position(
                conn, pid, status="filled",
                filled_contracts=filled,
                cost_usd=parsed["cost_cents"] / 100.0,
                avg_entry_cents=parsed["avg_cents"],
            )
            return db.fetch_crypto15m_by_id(conn, pid)

    if filled > 0 and filled != int(pos.get("filled_contracts") or 0):
        with db.get_db() as conn:
            db.update_crypto15m_position(
                conn, pid,
                filled_contracts=filled,
                cost_usd=parsed["cost_cents"] / 100.0,
                avg_entry_cents=parsed["avg_cents"],
            )

    if _entry_expired(pos, cfg):
        try:
            await kalshi_api.cancel_order(kid)
        except Exception:
            pass
        final_filled, final_cost, final_avg = filled, None, None
        try:
            resp2 = await kalshi_api.get_order(kid)
            order2 = (resp2.get("order") if isinstance(resp2, dict) else resp2) or {}
            p2 = trader._parse_kalshi_order(order2)
            if int(p2.get("filled") or 0) >= final_filled:
                final_filled = int(p2["filled"])
                final_cost = p2["cost_cents"] / 100.0
                final_avg = p2["avg_cents"]
        except Exception:
            pass
        with db.get_db() as conn:
            if final_filled > 0:
                upd = {"status": "filled", "filled_contracts": final_filled}
                if final_cost is not None:
                    upd["cost_usd"] = final_cost
                    upd["avg_entry_cents"] = final_avg
                db.update_crypto15m_position(conn, pid, **upd)
            else:
                _mark_resolved(conn, pid, status="canceled", exit_reason="unfilled_expired")
            return db.fetch_crypto15m_by_id(conn, pid)
    return None


def _entry_expired(pos: dict, cfg: dict) -> bool:
    """An unfilled entry is abandoned within `crypto15m_maker_cancel_min`
    minutes of its market's close (0 = only once the market has closed)."""
    close_epoch = crypto15m._parse_close_epoch(pos.get("close_time") or "")
    if close_epoch is None:
        return False
    lead = max(0.0, float(cfg.get("crypto15m_maker_cancel_min", 0.0) or 0.0)) * 60.0
    return datetime.now(timezone.utc).timestamp() >= close_epoch - lead


async def _paper_poll_entry(pos: dict, cfg: dict) -> Optional[dict]:
    """Simulate a RESTING paper maker entry honestly: it only fills when
    the market actually trades down to our limit (the side's ask reaches
    it) — the same condition under which a real resting bid is hit. An
    instant simulated fill would hide maker mode's true cost: sometimes
    you don't get filled and miss the trade."""
    pid = pos["id"]
    limit_cents = int(pos.get("entry_limit_cents") or 0)
    direction = pos.get("direction")
    target = int(pos.get("target_contracts") or 0)
    try:
        m = await kalshi_api.fetch_market(pos["ticker"])
    except Exception:
        m = None

    if m and trader._market_yes_payout(m) is None and target > 0:
        yes_bid = crypto15m._price_dollars(m, "yes_bid")
        yes_ask = crypto15m._price_dollars(m, "yes_ask")
        if direction == "yes":
            side_ask = yes_ask
        else:
            side_ask = crypto15m._price_dollars(m, "no_ask") or (1.0 - yes_bid if yes_bid else 0.0)
        if side_ask and side_ask * 100.0 <= limit_cents + 1e-9:
            with db.get_db() as conn:
                db.update_crypto15m_position(
                    conn, pid, status="filled", filled_contracts=target,
                    avg_entry_cents=float(limit_cents),
                    cost_usd=target * limit_cents / 100.0,
                )
                logger.info(f"[paper] maker entry filled {pos['asset']} x{target} @ {limit_cents}c")
                return db.fetch_crypto15m_by_id(conn, pid)

    if _entry_expired(pos, cfg) or (m and trader._market_yes_payout(m) is not None):
        with db.get_db() as conn:
            _mark_resolved(conn, pid, status="canceled", exit_reason="unfilled_expired")
            return db.fetch_crypto15m_by_id(conn, pid)
    return None


async def _place_stop_loss(pos: dict, market: Optional[dict], cfg: dict) -> Optional[dict]:
    pid, ticker, direction = pos["id"], pos["ticker"], pos["direction"]
    filled = int(pos.get("filled_contracts") or 0)
    exit_cents: Optional[int] = None
    try:
        book = await kalshi_api.get_orderbook(ticker)
        bids = book.get(direction) or []
        if bids:
            exit_cents = max(int(b[0]) for b in bids if b and b[0] is not None)
    except Exception:
        exit_cents = None
    if exit_cents is None:
        sp = side_prob_from_market(market, direction) or 0.0
        exit_cents = int(round(sp * 100)) - 2
    exit_cents = max(1, min(99, exit_cents))

    coid = f"krypt-c15x-{pos['asset']}-{uuid.uuid4().hex[:8]}"
    try:
        resp = await kalshi_api.place_limit_order(
            ticker=ticker, side=direction, action="sell",
            count=filled, price_cents=exit_cents, client_order_id=coid,
        )
    except Exception as e:
        with db.get_db() as conn:
            db.update_crypto15m_position(conn, pid, error=f"stop-loss sell failed: {str(e)[:160]}")
            return db.fetch_crypto15m_by_id(conn, pid)

    order = (resp.get("order") if isinstance(resp, dict) else None) or resp or {}
    with db.get_db() as conn:
        db.update_crypto15m_position(
            conn, pid, status="exiting", exit_reason="stop_loss",
            exit_client_order_id=coid,
            exit_kalshi_order_id=order.get("order_id") if isinstance(order, dict) else None,
            exit_limit_cents=exit_cents,
        )
        logger.info(f"[live] STOP-LOSS sell {pos['asset']} x{filled} @ {exit_cents}c")
        return db.fetch_crypto15m_by_id(conn, pid)


async def _poll_exit(pos: dict) -> Optional[dict]:
    pid, kid = pos["id"], pos.get("exit_kalshi_order_id")
    if not kid:
        return None
    try:
        resp = await kalshi_api.get_order(kid)
        order = (resp.get("order") if isinstance(resp, dict) else resp) or {}
        parsed = trader._parse_kalshi_order(order)
    except Exception:
        return None
    sold = int(parsed.get("filled") or 0)
    remaining = int(parsed.get("remaining") or 0)
    proceeds = parsed["cost_cents"] / 100.0

    if sold > 0 and remaining <= 0:
        pnl = proceeds - float(pos.get("cost_usd") or 0.0)
        with db.get_db() as conn:
            _mark_resolved(
                conn, pid, status="exited",
                exit_filled_contracts=sold, proceeds_usd=proceeds,
                pnl_usd=pnl, outcome_correct=1 if pnl > 0 else 0,
            )
            return db.fetch_crypto15m_by_id(conn, pid)

    if sold > 0 and sold != int(pos.get("exit_filled_contracts") or 0):
        with db.get_db() as conn:
            db.update_crypto15m_position(
                conn, pid, exit_filled_contracts=sold, proceeds_usd=proceeds,
            )
    return None


async def _settle_if_closed(pos: dict) -> Optional[dict]:
    """An 'exiting' position whose market settled while the stop-loss sell
    sat UNFILLED (thin/empty books — routine on demo) still holds its
    contracts: Kalshi cancels resting orders at close and the binary
    settles. Book that settlement, or the row stays 'exiting' forever and
    pins an executor slot (live bug: 5 such rows froze the engine)."""
    try:
        market = await kalshi_api.fetch_market(pos["ticker"])
    except Exception:
        return None
    payout = trader._market_yes_payout(market) if market else None
    if payout is None:
        return None

    kid = pos.get("exit_kalshi_order_id")
    if kid:
        try:
            await kalshi_api.cancel_order(kid)
        except Exception:
            pass

    filled = int(pos.get("filled_contracts") or 0)
    cost_usd = float(pos.get("cost_usd") or 0.0)
    sold = int(pos.get("exit_filled_contracts") or 0)
    partial_proceeds = float(pos.get("proceeds_usd") or 0.0)
    residual = max(0, filled - sold)
    our = payout if pos["direction"] == "yes" else (1.0 - payout)
    settlement = residual * our
    pnl = partial_proceeds + settlement - cost_usd
    correct = 1 if our >= 0.99 else (0 if our <= 0.01 else (1 if pnl > 0.01 else 0))
    with db.get_db() as conn:
        _mark_resolved(
            conn, pos["id"], status="settled",
            exit_reason=pos.get("exit_reason") or "settlement",
            outcome_correct=correct, settlement_usd=settlement, pnl_usd=pnl,
        )
        logger.info(f"[crypto15m] exiting->settled {pos['asset']} pnl=${pnl:+.2f} (sell never filled)")
        return db.fetch_crypto15m_by_id(conn, pos["id"])


async def _manage_position(pos: dict, cfg: dict, env: str, live: bool) -> Optional[dict]:
    status = pos.get("status")

    if status == "submitted":
        if pos.get("dry_run"):
            return await _paper_poll_entry(pos, cfg)
        return await _poll_entry(pos, cfg)
    if status == "exiting":
        row = await _poll_exit(pos)
        if row:
            return row
        return await _settle_if_closed(pos)
    if status == "error" and int(pos.get("filled_contracts") or 0) <= 0:
        with db.get_db() as conn:
            _mark_resolved(conn, pos["id"], status="error")
            return db.fetch_crypto15m_by_id(conn, pos["id"])
    if status != "filled":
        return None

    pid = pos["id"]
    direction = pos["direction"]
    filled = int(pos.get("filled_contracts") or 0)
    cost_usd = float(pos.get("cost_usd") or 0.0)
    is_dry = bool(pos.get("dry_run"))

    try:
        market = await kalshi_api.fetch_market(pos["ticker"])
    except Exception:
        market = None

    payout = trader._market_yes_payout(market) if market else None
    if payout is not None:
        our = payout if direction == "yes" else (1.0 - payout)
        settlement = filled * our
        pnl = settlement - cost_usd
        correct = 1 if our >= 0.99 else (0 if our <= 0.01 else (1 if pnl > 0.01 else 0))
        with db.get_db() as conn:
            _mark_resolved(
                conn, pid, status="settled",
                exit_reason=(pos.get("exit_reason") or "settlement"),
                outcome_correct=correct, settlement_usd=settlement, pnl_usd=pnl,
            )
            return db.fetch_crypto15m_by_id(conn, pid)

    side_prob = side_prob_from_market(market, direction)
    if should_stop_loss(pos, side_prob, cfg):
        if not live or is_dry:
            proceeds = filled * float(side_prob)
            pnl = proceeds - cost_usd
            with db.get_db() as conn:
                _mark_resolved(
                    conn, pid, status="exited", exit_reason="stop_loss",
                    proceeds_usd=proceeds, exit_filled_contracts=filled,
                    exit_limit_cents=int(round(side_prob * 100)),
                    pnl_usd=pnl, outcome_correct=1 if pnl > 0 else 0,
                )
                logger.info(f"[paper] STOP-LOSS {pos['asset']} pnl=${pnl:+.2f}")
                return db.fetch_crypto15m_by_id(conn, pid)
        return await _place_stop_loss(pos, market, cfg)

    return None




async def run_tick(cfg: dict, *, authed: bool) -> list[dict]:
    """One execution pass: manage open positions, then consider entries.
    Returns the list of changed position rows."""
    if not cfg.get("crypto15m_enabled"):
        return []
    env = trader.get_env()
    live = bool(authed) and bool(cfg.get("crypto15m_live"))

    snap = await crypto15m.snapshot(cfg)
    assets = {a["asset"]: a for a in snap.get("assets", [])}

    with db.get_db() as conn:
        open_positions = db.get_open_crypto15m(conn, env)
        errored_tickers = db.crypto15m_errored_tickers(conn, env)
    open_by_asset = {p["asset"]: p for p in open_positions}
    open_count = len(open_positions)

    updated: list[dict] = []

    for pos in open_positions:
        try:
            row = await _manage_position(pos, cfg, env, live)
            if row:
                updated.append(row)
        except Exception as e:
            logger.warning(f"[crypto15m] manage {pos.get('asset')} failed: {e}")

    need_balance = (
        (cfg.get("crypto15m_sizing_mode") or "fixed").lower() == "balance_pct"
        or float(cfg.get("crypto15m_max_loss_pct") or 0.0) > 0.0
    )
    balance_usd = await _bankroll_usd(cfg, bool(authed)) if need_balance else 0.0

    for sym, a in assets.items():
        if sym in open_by_asset:
            continue
        if a.get("ticker") in errored_tickers:
            continue
        ok, _why = should_enter(a, cfg, has_open=False, open_count=open_count)
        if not ok:
            continue
        try:
            row = await _open_entry(a, cfg, env, live, balance_usd)
            if row:
                updated.append(row)
                open_count += 1
        except Exception as e:
            logger.warning(f"[crypto15m] entry {sym} failed: {e}")

    return updated


async def _sizing_preview(cfg: dict, authed: bool) -> dict:
    """A worked example of the current sizing settings for the UI, so the
    user can see roughly how much each bet costs before placing one."""
    mode = (cfg.get("crypto15m_sizing_mode") or "fixed").lower()
    balance_pct = _clamp01(cfg.get("crypto15m_balance_pct", 0.02))
    max_loss_pct = _clamp01(cfg.get("crypto15m_max_loss_pct", 0.0))
    order_size = max(1, int(cfg.get("crypto15m_order_size", 1)))
    bal = await _bankroll_usd(cfg, bool(authed))

    thr = crypto15m._const(cfg, "entry_threshold")
    base = (1.0 - thr) if (cfg.get("crypto15m_direction_mode") == "contrarian") else thr
    if (cfg.get("crypto15m_entry_style") or "maker") == "maker":
        est_price_cents = max(1, min(99, int(round(base * 100)) - 1))
    else:
        est_price_cents = entry_limit_cents(base, crypto15m._const(cfg, "entry_diff"))
    est_contracts = compute_entry_contracts(
        cfg, entry_limit_cents=est_price_cents, balance_usd=bal, order_size=order_size,
    )
    est_cost = est_contracts * est_price_cents / 100.0

    note = ""
    if mode == "balance_pct" and bal <= 0:
        note = "No balance yet — using fixed order size. Connect Kalshi or set a start bankroll to size by %."
    elif max_loss_pct > 0 and bal > 0 and est_contracts < 1:
        note = f"Max-loss budget too small to fund a contract at ~{est_price_cents}c."

    return {
        "mode": mode,
        "balancePct": balance_pct,
        "maxLossPct": max_loss_pct,
        "balanceUsd": bal,
        "estPriceCents": est_price_cents,
        "estContracts": est_contracts,
        "estCostUsd": est_cost,
        "note": note,
    }


async def status(cfg: dict, *, authed: bool = False) -> dict:
    """Snapshot of the executor's positions + stats for the UI."""
    env = trader.get_env()
    with db.get_db() as conn:
        open_rows = db.get_open_crypto15m(conn, env)
        recent = db.recent_crypto15m(conn, env, limit=40)
        stats = db.crypto15m_stats(conn, env)
    live_armed = bool(cfg.get("crypto15m_live"))
    return {
        "enabled": bool(cfg.get("crypto15m_enabled")),
        "live": bool(cfg.get("crypto15m_enabled")) and live_armed and bool(authed),
        "liveArmed": live_armed,
        "authed": bool(authed),
        "orderSize": int(cfg.get("crypto15m_order_size", 1)),
        "maxConcurrent": int(cfg.get("crypto15m_max_concurrent", len(crypto15m.SERIES))),
        "sizing": await _sizing_preview(cfg, authed),
        "env": env,
        "stats": stats,
        "open": [_pos_to_js(r) for r in open_rows],
        "recent": [_pos_to_js(r) for r in recent],
    }
