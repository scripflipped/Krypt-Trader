from __future__ import annotations

import asyncio
import io
import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



_log_q: asyncio.Queue | None = None


class _StdoutHandler(logging.Handler):

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        source = "backend"
        if record.name.startswith("trader"):
            source = "trader"
        elif record.name.startswith("scanner"):
            source = "whale" if "whale" in msg.lower()[:20] else "momentum"
        elif record.name.startswith("webhook") or record.name.startswith("discord"):
            source = "discord"
        try:
            evt = {
                "type": "log",
                "level": record.levelname,
                "source": source,
                "msg": msg,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            sys.stdout.write(json.dumps(evt) + "\n")
            sys.stdout.flush()
        except Exception:
            pass


def _setup_logging() -> None:
    log_dir_base = os.environ.get("KRYPT_TRADER_USERDATA")
    if log_dir_base:
        log_dir = Path(log_dir_base) / "logs"
    else:
        log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        log_dir / "backend.log", maxBytes=10 * 1024 * 1024,
        backupCount=5, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
    sh = _StdoutHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)




_setup_logging()
logger = logging.getLogger("service")


import db  # noqa: E402
import kalshi_api  # noqa: E402
import kalshi_auth  # noqa: E402
import scanner  # noqa: E402
import crypto15m  # noqa: E402
import trader  # noqa: E402
import crypto15m_trader  # noqa: E402
import crypto15m_record  # noqa: E402
import webhook  # noqa: E402
from config import DEFAULT_CONFIG, merge_with_defaults  # noqa: E402


def _iso_utc(s: Any) -> Any:
    if not s:
        return s
    if not isinstance(s, str):
        return s
    s = s.strip()
    if not s:
        return s
    if s.endswith("Z") or "+" in s[10:] or s.count("-") > 2:
        return s.replace(" ", "T")
    return s.replace(" ", "T") + "Z"




class State:
    cfg: dict[str, Any] = dict(DEFAULT_CONFIG)
    auth_ok: bool = False
    paused: bool = False
    last_whale_scan_at: str | None = None
    last_momentum_scan_at: str | None = None
    last_trade_scan_at: str | None = None
    started_at: str = ""
    active_run_id: int = 0


STATE = State()




_stdout_lock = asyncio.Lock()


async def _send(obj: dict) -> None:
    line = json.dumps(obj, default=str) + "\n"
    async with _stdout_lock:
        sys.stdout.write(line)
        sys.stdout.flush()


async def emit_event(name: str, data: Any = None) -> None:
    await _send({"type": "event", "name": name, "data": data})


async def respond_ok(req_id: str, result: Any = None) -> None:
    await _send({"type": "rpc", "id": req_id, "ok": True, "result": result})


async def respond_err(req_id: str, msg: str) -> None:
    await _send({"type": "rpc", "id": req_id, "ok": False, "error": msg})




async def _build_account_snapshot() -> dict:
    env = kalshi_auth.get_env()
    cash_cents = port_cents = 0
    if STATE.auth_ok:
        try:
            cents, port = await trader.refresh_balance(STATE.cfg, force=False)
            cash_cents = cents
            port_cents = port
        except Exception:
            pass
    cash_usd = cash_cents / 100.0
    port_usd = port_cents / 100.0
    total = cash_usd + port_usd

    user_start = float(STATE.cfg.get("start_bankroll_usd", 0.0) or 0.0)
    if user_start > 0:
        baseline = user_start
        baseline_source = "user"
    else:
        with db.get_db() as conn:
            earliest = db.earliest_pnl_total(conn, env)
        if earliest and earliest > 0:
            baseline = earliest
            baseline_source = "auto"
        else:
            baseline = total if total > 0 else 0.0
            baseline_source = "live"
    roi = ((total - baseline) / baseline * 100.0) if baseline > 0 else 0.0

    with db.get_db() as conn:
        stats_env = db.aggregate_stats(conn, env)
        stats_demo = db.aggregate_stats(conn, "demo")
        stats_prod = db.aggregate_stats(conn, "production")

    wl = stats_env["wins"] + stats_env["losses"]
    wr = (stats_env["wins"] / wl * 100.0) if wl else 0.0
    open_cost = stats_env["open_cost"]
    unrealized = port_usd - open_cost

    with db.get_db() as conn:
        first_today = db.first_snapshot_of_today(conn, env)
        bankroll_baseline_snap = db.earliest_pnl_total(conn, env)
        active_run = db.get_active_run(conn, env) if STATE.active_run_id else None

    today_balance_baseline = (
        float(first_today["total_usd"]) if first_today else None
    )
    today_balance_pnl = (
        total - today_balance_baseline
        if today_balance_baseline is not None else 0.0
    )
    alltime_balance_baseline = (
        float(bankroll_baseline_snap)
        if bankroll_baseline_snap is not None else baseline
    )
    alltime_balance_pnl = total - alltime_balance_baseline

    if active_run:
        session_baseline = float(active_run.get("start_total_usd") or 0.0)
        session_started_at = _iso_utc(
            active_run.get("started_at") or STATE.started_at
        )
        session_run_id = int(active_run.get("id") or 0)
    else:
        session_baseline = total
        session_started_at = STATE.started_at
        session_run_id = 0
    session_pnl = total - session_baseline if session_baseline > 0 else 0.0
    session_roi = (
        (session_pnl / session_baseline * 100.0)
        if session_baseline > 0 else 0.0
    )

    return {
        "cashUsd": cash_usd,
        "portfolioUsd": port_usd,
        "totalUsd": total,
        "startBankrollUsd": baseline,
        "bankrollSource": baseline_source,
        "roiPct": roi,
        "realizedPnlUsd": stats_env["realized_pnl"],
        "todayPnlUsd": today_balance_pnl,
        "alltimePnlUsd": alltime_balance_pnl,
        "todayBaselineUsd": today_balance_baseline,
        "alltimeBaselineUsd": alltime_balance_baseline,
        "sessionPnlUsd": session_pnl,
        "sessionRoiPct": session_roi,
        "sessionBaselineUsd": session_baseline,
        "sessionStartedAt": session_started_at,
        "sessionRunId": session_run_id,
        "todayWins": stats_env["today_wins"],
        "todayLosses": stats_env["today_losses"],
        "unrealizedPnlUsd": unrealized,
        "openCostUsd": open_cost,
        "feesUsd": stats_env["fees"],
        "wins": stats_env["wins"],
        "losses": stats_env["losses"],
        "winRate": wr,
        "pendingCount": stats_env["pending"],
        "openCount": stats_env["open_filled"],
        "resolvedCount": stats_env["resolved_count"],
        "totalOpened": stats_env["total_opened"],
        "byEnv": {
            "demo": {
                "wins": stats_demo["wins"],
                "losses": stats_demo["losses"],
                "realizedPnl": stats_demo["realized_pnl"],
            },
            "production": {
                "wins": stats_prod["wins"],
                "losses": stats_prod["losses"],
                "realizedPnl": stats_prod["realized_pnl"],
            },
        },
    }




def _position_row_to_js(r: dict) -> dict:
    return {
        "id": int(r["id"]),
        "signalSource": r["signal_source"],
        "signalId": int(r["signal_id"]),
        "ticker": r["ticker"],
        "eventTicker": r.get("event_ticker") or "",
        "title": r.get("title") or "",
        "category": r.get("category") or "",
        "direction": r["direction"],
        "action": r.get("action") or "buy",
        "targetContracts": int(r.get("target_contracts") or 0),
        "limitPriceCents": int(r.get("limit_price_cents") or 0),
        "filledContracts": int(r.get("filled_contracts") or 0),
        "avgFillPriceCents": (
            float(r["avg_fill_price_cents"])
            if r.get("avg_fill_price_cents") is not None
            else None
        ),
        "costUsd": float(r.get("cost_usd") or 0),
        "feesUsd": float(r.get("fees_usd") or 0),
        "clientOrderId": r.get("client_order_id") or "",
        "kalshiOrderId": r.get("kalshi_order_id"),
        "status": r["status"],
        "confidence": float(r.get("confidence") or 0),
        "edgePts": float(r.get("edge_pts") or 0),
        "signalPriceCents": float(r.get("signal_price") or 0),
        "resolved": bool(r.get("resolved") or 0),
        "outcomeCorrect": (
            int(r["outcome_correct"])
            if r.get("outcome_correct") is not None
            else None
        ),
        "settlementUsd": (
            float(r["settlement_usd"])
            if r.get("settlement_usd") is not None
            else None
        ),
        "pnlUsd": float(r["pnl_usd"]) if r.get("pnl_usd") is not None else None,
        "balanceBeforeUsd": (
            float(r["balance_before_usd"])
            if r.get("balance_before_usd") is not None
            else None
        ),
        "kalshiEnv": r.get("kalshi_env") or "demo",
        "createdAt": _iso_utc(r.get("created_at")) or "",
        "lastUpdated": _iso_utc(r.get("last_updated")) or "",
        "resolvedAt": _iso_utc(r.get("resolved_at")),
        "error": r.get("error"),
    }


def _signal_row_to_js(r: dict, source: str, traded: bool) -> dict:
    if source == "whale":
        price_frac = float(r.get("price") or 0)
        price_c = int(round(price_frac * 100))
        return {
            "id": int(r["id"]),
            "source": "whale",
            "ticker": r["ticker"],
            "eventTicker": r.get("event_ticker") or "",
            "title": r.get("title") or r.get("ticker", ""),
            "category": r.get("category") or "",
            "direction": (r.get("taker_side") or "yes").lower(),
            "priceCents": price_c,
            "confidence": float(r.get("confidence") or 0),
            "edgePts": float(r.get("confidence") or 0) - price_c,
            "dollarValue": float(r.get("dollar_value") or 0),
            "createdAt": _iso_utc(r.get("created_at")) or "",
            "resolved": bool(r.get("resolved") or 0),
            "outcomeCorrect": (
                int(r["outcome_correct"])
                if r.get("outcome_correct") is not None
                else None
            ),
            "pnlEstimate": (
                float(r["pnl_estimate"])
                if r.get("pnl_estimate") is not None
                else None
            ),
            "traded": traded,
        }
    direction = (r.get("direction") or "yes").lower()
    price_frac = float(r.get("price") or 0)
    yes_c = int(round(price_frac * 100))
    cost_c = yes_c if direction == "yes" else max(0, 100 - yes_c)
    implied = yes_c if direction == "yes" else 100 - yes_c
    return {
        "id": int(r["id"]),
        "source": "momentum",
        "ticker": r["ticker"],
        "eventTicker": r.get("event_ticker") or "",
        "title": r.get("title") or r.get("ticker", ""),
        "category": r.get("category") or "",
        "direction": direction,
        "priceCents": cost_c,
        "confidence": float(r.get("confidence") or 0),
        "edgePts": float(r.get("confidence") or 0) - implied,
        "signalType": r.get("signal_type") or "",
        "createdAt": _iso_utc(r.get("created_at")) or "",
        "resolved": bool(r.get("resolved") or 0),
        "outcomeCorrect": (
            int(r["outcome_correct"])
            if r.get("outcome_correct") is not None
            else None
        ),
        "pnlEstimate": (
            float(r["pnl_estimate"])
            if r.get("pnl_estimate") is not None
            else None
        ),
        "traded": traded,
    }




_loop_task: asyncio.Task | None = None
_loop_stop: asyncio.Event | None = None

_event_webhook_last: dict[int, str] = {}


def _should_fire_event_webhook(pos_id: int, kind: str) -> bool:
    if not pos_id:
        return True
    if _event_webhook_last.get(pos_id) == kind:
        return False
    _event_webhook_last[pos_id] = kind
    return True


async def _scanner_and_trader_loop() -> None:
    last_whale = 0.0
    last_momentum = 0.0
    last_trade = 0.0
    last_poll = 0.0
    last_resolve = 0.0
    last_market_sync = 0.0
    last_event_sync = 0.0
    last_account_emit = 0.0
    last_reconcile = 0.0
    last_crypto15m = 0.0
    last_crypto15m_record = 0.0
    last_cleanup = 0.0
    last_stats_push = asyncio.get_event_loop().time()

    try:
        cnt = await scanner.sync_markets(max_pages=10)
        logger.info(f"Initial market sync: {cnt} markets")
    except Exception as e:
        logger.warning(f"initial market sync failed: {e}")


    while not (_loop_stop and _loop_stop.is_set()):
        now = asyncio.get_event_loop().time()
        cfg = STATE.cfg

        if STATE.paused:
            await asyncio.sleep(1)
            continue

        try:
            if now - last_market_sync >= float(cfg.get("market_refresh_interval", 300)):
                await scanner.sync_markets(max_pages=10)
                last_market_sync = now
            if now - last_event_sync >= 600:
                await scanner.sync_events()
                last_event_sync = now
        except Exception as e:
            logger.warning(f"sync error: {e}")

        try:
            if now - last_whale >= float(cfg.get("whale_scan_interval", 120)):
                cnt, rows = await scanner.scan_whales(cfg)
                last_whale = now
                STATE.last_whale_scan_at = datetime.now(timezone.utc).isoformat()
                if cnt:
                    logger.info(f"whale scan: {cnt} new")
                with db.get_db() as conn:
                    seen = db.already_traded_signal_ids(
                        conn, "whale", kalshi_auth.get_env()
                    )
                for row in rows:
                    js = _signal_row_to_js(row, "whale", int(row["id"]) in seen)
                    await emit_event("signal:new", js)
                    if cfg.get("enable_discord"):
                        try:
                            await webhook.send_whale(
                                cfg.get("whale_webhook_url", ""), row
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"whale scan error: {e}")

        try:
            if now - last_momentum >= float(cfg.get("momentum_scan_interval", 90)):
                cnt, rows = await scanner.scan_momentum(cfg)
                last_momentum = now
                STATE.last_momentum_scan_at = datetime.now(timezone.utc).isoformat()
                if cnt:
                    logger.info(f"momentum scan: {cnt} new")
                with db.get_db() as conn:
                    seen = db.already_traded_signal_ids(
                        conn, "momentum", kalshi_auth.get_env()
                    )
                for row in rows:
                    js = _signal_row_to_js(row, "momentum", int(row["id"]) in seen)
                    await emit_event("signal:new", js)
                    if cfg.get("enable_discord"):
                        try:
                            await webhook.send_momentum(
                                cfg.get("momentum_webhook_url", ""), row
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"momentum scan error: {e}")

        try:
            if (
                STATE.auth_ok
                and now - last_trade >= float(cfg.get("trade_scan_interval", 20))
            ):
                placed = await trader.scan_for_trades(cfg)
                last_trade = now
                STATE.last_trade_scan_at = datetime.now(timezone.utc).isoformat()
                for row in placed:
                    js = _position_row_to_js(row)
                    await emit_event("position:new", js)
                    if (
                        cfg.get("enable_discord")
                        and _should_fire_event_webhook(int(row.get("id") or 0), "placed")
                    ):
                        try:
                            await webhook.send_event(
                                cfg.get("event_webhook_url", ""),
                                "placed", row, kalshi_auth.get_env(),
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.error(f"trade scan error: {e}", exc_info=True)

        try:
            if (
                STATE.auth_ok
                and now - last_poll >= float(cfg.get("position_poll_interval", 30))
            ):
                updated = await trader.poll_open_orders(cfg)
                last_poll = now
                for row in updated:
                    js = _position_row_to_js(row)
                    await emit_event("position:update", js)
                    if cfg.get("enable_discord"):
                        kind = row["status"]
                        if (
                            kind in ("filled", "partial", "canceled", "gone", "error")
                            and _should_fire_event_webhook(
                                int(row.get("id") or 0), kind
                            )
                        ):
                            try:
                                await webhook.send_event(
                                    cfg.get("event_webhook_url", ""),
                                    kind, row, kalshi_auth.get_env(),
                                )
                            except Exception:
                                pass
        except Exception as e:
            logger.error(f"poll error: {e}", exc_info=True)

        try:
            if STATE.auth_ok and now - last_reconcile >= 30:
                summary, changed = await trader.reconcile_positions_with_kalshi()
                last_reconcile = now
                if any(summary.values()):
                    logger.info(f"reconcile: {summary}")
                    await emit_event("backend:reconciled", summary)
                for row in changed:
                    await emit_event(
                        "position:update", _position_row_to_js(row),
                    )
        except Exception as e:
            logger.debug(f"periodic reconcile failed: {e}")

        try:
            if (
                STATE.auth_ok
                and now - last_resolve >= float(cfg.get("resolution_check_interval", 300))
            ):
                resolved_pos = await trader.mark_resolved_positions(cfg)
                await scanner.resolve_alerts_from_markets()
                await scanner.resolve_whales_from_markets()
                last_resolve = now
                for row in resolved_pos:
                    js = _position_row_to_js(row)
                    await emit_event("position:update", js)
                    if cfg.get("enable_discord"):
                        kind = "won" if row.get("outcome_correct") == 1 else (
                            "lost" if row.get("outcome_correct") == 0 else "na"
                        )
                        if _should_fire_event_webhook(
                            int(row.get("id") or 0), kind
                        ):
                            try:
                                await webhook.send_event(
                                    cfg.get("event_webhook_url", ""),
                                    kind, row, kalshi_auth.get_env(),
                                )
                            except Exception:
                                pass
        except Exception as e:
            logger.error(f"resolution error: {e}", exc_info=True)

        try:
            if (
                cfg.get("crypto15m_enabled")
                and now - last_crypto15m >= float(cfg.get("crypto15m_poll_sec", 4))
            ):
                await crypto15m_trader.run_tick(cfg, authed=STATE.auth_ok)
                last_crypto15m = now
        except Exception as e:
            logger.error(f"crypto15m tick error: {e}", exc_info=True)

        try:
            if (
                cfg.get("crypto15m_record_signals", True)
                and now - last_crypto15m_record >= 25
            ):
                await crypto15m_record.record_tick(cfg)
                last_crypto15m_record = now
        except Exception as e:
            logger.debug(f"crypto15m record error: {e}")

        try:
            if now - last_cleanup >= float(cfg.get("db_cleanup_interval", 3600)):
                summary = await asyncio.get_event_loop().run_in_executor(
                    None, db.run_maintenance
                )
                if summary.get("deleted") or summary.get("vacuumed"):
                    logger.info(
                        f"db maintenance: pruned {summary['deleted']} rows, "
                        f"vacuumed={summary['vacuumed']} "
                        f"(reclaimable {summary['reclaimable_mb']}MB)"
                    )
                last_cleanup = now
        except Exception as e:
            logger.warning(f"db maintenance failed: {e}")

        try:
            if now - last_account_emit >= 15:
                snap = await _build_account_snapshot()
                if STATE.auth_ok:
                    with db.get_db() as conn:
                        db.insert_pnl_snapshot(
                            conn,
                            cash_usd=snap["cashUsd"],
                            portfolio_usd=snap["portfolioUsd"],
                            realized_pnl_usd=snap["realizedPnlUsd"],
                            wins=snap["wins"], losses=snap["losses"],
                            open_positions=snap["openCount"] + snap["pendingCount"],
                            env=kalshi_auth.get_env(),
                        )
                        if STATE.active_run_id:
                            db.heartbeat_bot_run(
                                conn, STATE.active_run_id,
                                cash_usd=snap["cashUsd"],
                                portfolio_usd=snap["portfolioUsd"],
                                lifetime_trades=snap["totalOpened"],
                                lifetime_wins=snap["wins"],
                                lifetime_losses=snap["losses"],
                            )
                await emit_event("account:update", snap)
                last_account_emit = now
        except Exception as e:
            logger.debug(f"account snapshot error: {e}")

        try:
            push_iv = float(cfg.get("stats_push_interval", 3600) or 3600)
            if (
                cfg.get("enable_discord")
                and cfg.get("stats_webhook_url")
                and now - last_stats_push >= push_iv
            ):
                snap_for_stats = await _build_account_snapshot()
                try:
                    await webhook.send_stats(
                        cfg.get("stats_webhook_url", ""),
                        snap_for_stats,
                        kalshi_auth.get_env(),
                    )
                    logger.info(
                        f"stats webhook fired (next in "
                        f"{int(push_iv // 60)}m)"
                    )
                except Exception as e:
                    logger.debug(f"stats webhook send failed: {e}")
                last_stats_push = now
        except Exception as e:
            logger.debug(f"stats webhook scheduler error: {e}")

        await asyncio.sleep(1)


async def _start_loop() -> None:
    global _loop_task, _loop_stop
    if _loop_task and not _loop_task.done():
        return
    _loop_stop = asyncio.Event()
    _loop_task = asyncio.create_task(_scanner_and_trader_loop())


async def _stop_loop() -> None:
    global _loop_task, _loop_stop
    if _loop_stop:
        _loop_stop.set()
    if _loop_task:
        try:
            await asyncio.wait_for(_loop_task, timeout=5)
        except Exception:
            pass




async def _h_ping(_p: dict) -> dict:
    return {"pong": True, "ts": datetime.now(timezone.utc).isoformat()}


async def _h_setConfig(p: dict) -> dict:
    cfg = merge_with_defaults(p.get("config") or {})
    STATE.cfg = cfg
    logger.info(
        f"setConfig applied: enable_trading={cfg.get('enable_trading')} "
        f"trade_whales={cfg.get('trade_whales')} "
        f"trade_momentum={cfg.get('trade_momentum')} "
        f"max_open={cfg.get('max_open_positions')} "
        f"max_daily="
        f"{'∞' if cfg.get('unlimited_daily_new_positions') else cfg.get('max_daily_new_positions')} "
        f"stop_loss={cfg.get('stop_loss_on_day')} "
        f"env={cfg.get('kalshi_env')}"
    )
    new_env = cfg.get("kalshi_env", "demo")
    prev_env = kalshi_auth.get_env()
    kalshi_auth.set_env(new_env)

    if new_env != prev_env:
        kalshi_auth.reset_credential_cache()
        if kalshi_auth.credentials_present(new_env):
            try:
                kalshi_auth.prime_credentials(sync_time=True)
                bal = await kalshi_api.get_balance()
                int(bal.get("balance", 0))
                STATE.auth_ok = True
            except Exception as e:
                logger.warning(f"env-switch auth failed: {e}")
                STATE.auth_ok = False
        else:
            STATE.auth_ok = False
        await emit_event("backend:authChanged", {"authOk": STATE.auth_ok})

        try:
            if STATE.active_run_id:
                with db.get_db() as conn:
                    db.end_bot_run(conn, STATE.active_run_id)
                STATE.active_run_id = 0
            if STATE.auth_ok:
                cents, port = await trader.refresh_balance(STATE.cfg, force=True)
                with db.get_db() as conn:
                    stats = db.aggregate_stats(conn, new_env)
                    STATE.active_run_id = db.start_bot_run(
                        conn, env=new_env,
                        cash_usd=cents / 100.0,
                        portfolio_usd=port / 100.0,
                        lifetime_trades=int(stats.get("total_opened") or 0),
                        lifetime_wins=int(stats.get("wins") or 0),
                        lifetime_losses=int(stats.get("losses") or 0),
                    )
                logger.info(
                    f"Bot run #{STATE.active_run_id} started after env switch "
                    f"(env={new_env})"
                )
        except Exception as e:
            logger.warning(f"could not roll bot_run on env switch: {e}")
    return {"ok": True}


async def _h_setCredentials(p: dict) -> dict:
    p = p or {}
    api_key = p.get("apiKey", "")
    rsa_pem = p.get("rsaPem", "")
    env = p.get("env")
    kalshi_auth.save_credentials(api_key, rsa_pem, env)
    status = kalshi_auth.credentials_status_all()
    await emit_event("credentials:changed", status)
    return status


async def _h_clearCredentials(p: dict) -> dict:
    p = p or {}
    env = p.get("env")
    kalshi_auth.clear_credentials(env)
    if env in (None, kalshi_auth.get_env()):
        STATE.auth_ok = False
        await emit_event("backend:authChanged", {"authOk": False})
    status = kalshi_auth.credentials_status_all()
    await emit_event("credentials:changed", status)
    return status


async def _h_credentialStatus(_p: dict) -> dict:
    return kalshi_auth.credentials_status_all()


async def _h_testCredentials(p: dict) -> dict:
    p = p or {}
    target_env = p.get("env") or kalshi_auth.get_env()
    if not kalshi_auth.credentials_present(target_env):
        raise RuntimeError(f"credentials not set for {target_env}")

    saved_env = kalshi_auth.get_env()
    # Hold the env lock so the account poller / trade loop can't fetch a balance
    # while we've temporarily flipped the global env to the other account.
    async with kalshi_auth.ENV_LOCK:
        if target_env != saved_env:
            kalshi_auth.set_env(target_env)
        kalshi_auth.reset_credential_cache()
        try:
            kalshi_auth.prime_credentials(sync_time=True)
            bal = await kalshi_api.get_balance()
        finally:
            if target_env != saved_env:
                kalshi_auth.set_env(saved_env)
                kalshi_auth.reset_credential_cache()
                try:
                    kalshi_auth.prime_credentials(sync_time=False)
                except Exception:
                    pass
    cents = int(bal.get("balance", 0))
    if target_env == saved_env:
        STATE.auth_ok = True
        await emit_event("backend:authChanged", {"authOk": True})
    return {"env": target_env, "balanceUsd": cents / 100.0}


async def _h_account(_p: dict) -> dict:
    return await _build_account_snapshot()


async def _h_pnlSeries(p: dict) -> list:
    hours = int((p or {}).get("sinceHours", 168))
    env = kalshi_auth.get_env()
    with db.get_db() as conn:
        rows = db.get_pnl_snapshots(conn, since_hours=hours, env=env)
    return [
        {
            "at": _iso_utc(r["at"]),
            "cashUsd": float(r["cash_usd"] or 0),
            "portfolioUsd": float(r["portfolio_usd"] or 0),
            "totalUsd": float(r["total_usd"] or 0),
            "realizedPnlUsd": float(r["realized_pnl_usd"] or 0),
            "openPositions": int(r["open_positions"] or 0),
        }
        for r in rows
    ]


async def _h_positions(p: dict) -> list:
    f = p or {}
    status = f.get("status")
    resolved = f.get("resolved")
    src = f.get("signalSource")
    limit = int(f.get("limit") or 500)

    sql = "SELECT * FROM bot_positions WHERE 1=1"
    args: list = []
    if status:
        placeholders = ",".join("?" for _ in status)
        sql += f" AND status IN ({placeholders})"
        args.extend(status)
    if resolved is not None:
        sql += " AND resolved = ?"
        args.append(1 if resolved else 0)
    if src:
        sql += " AND signal_source = ?"
        args.append(src)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)

    with db.get_db() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_position_row_to_js(dict(r)) for r in rows]


async def _h_signals(p: dict) -> list:
    f = p or {}
    src = f.get("source")
    min_conf = float(f.get("minConfidence") or 0)
    limit = int(f.get("limit") or 200)

    out: list[dict] = []
    env = kalshi_auth.get_env()
    with db.get_db() as conn:
        if src in (None, "whale"):
            rows = conn.execute(
                """SELECT * FROM whale_trades
                   WHERE confidence >= ?
                   ORDER BY created_at DESC LIMIT ?""",
                (min_conf, limit),
            ).fetchall()
            seen = db.already_traded_signal_ids(conn, "whale", env)
            for r in rows:
                d = dict(r)
                out.append(_signal_row_to_js(d, "whale", int(d["id"]) in seen))
        if src in (None, "momentum"):
            rows = conn.execute(
                """SELECT * FROM alerts
                   WHERE confidence >= ?
                   ORDER BY created_at DESC LIMIT ?""",
                (min_conf, limit),
            ).fetchall()
            seen = db.already_traded_signal_ids(conn, "momentum", env)
            for r in rows:
                d = dict(r)
                out.append(_signal_row_to_js(d, "momentum", int(d["id"]) in seen))
    out.sort(key=lambda s: s["createdAt"], reverse=True)
    return out[:limit]


async def _h_scannerStats(_p: dict) -> dict:
    with db.get_db() as conn:
        markets = conn.execute(
            "SELECT COUNT(*) FROM markets WHERE status IN ('active','open')"
        ).fetchone()[0]
        wt = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN discord_sent=1 THEN 1 ELSE 0 END) AS sent,
                      SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) AS resolved,
                      SUM(CASE WHEN outcome_correct=1 THEN 1 ELSE 0 END) AS wins
               FROM whale_trades"""
        ).fetchone()
        al = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN discord_sent=1 THEN 1 ELSE 0 END) AS sent,
                      SUM(CASE WHEN resolved=1 THEN 1 ELSE 0 END) AS resolved,
                      SUM(CASE WHEN outcome_correct=1 THEN 1 ELSE 0 END) AS wins
               FROM alerts"""
        ).fetchone()

    def wr(d) -> dict:
        total = int(d["total"] or 0)
        resolved = int(d["resolved"] or 0)
        wins = int(d["wins"] or 0)
        return {
            "total": total,
            "sent": int(d["sent"] or 0),
            "resolved": resolved,
            "winRate": (wins / resolved * 100.0) if resolved else 0.0,
        }

    return {
        "whales": wr(wt),
        "momentum": wr(al),
        "marketsTracked": int(markets or 0),
        "lastWhaleScanAt": STATE.last_whale_scan_at,
        "lastMomentumScanAt": STATE.last_momentum_scan_at,
        "lastTradeScanAt": STATE.last_trade_scan_at,
    }


async def _h_cancelAllOpen(_p: dict) -> dict:
    if not STATE.auth_ok:
        raise RuntimeError("not authenticated")
    n = await trader.cancel_all_open()
    return {"canceled": n}


async def _h_flatten(_p: dict) -> dict:
    if not STATE.auth_ok:
        raise RuntimeError("not authenticated")
    canceled = await trader.cancel_all_open()
    return {"closed": canceled}


async def _h_runOnce(p: dict) -> dict:
    action = (p or {}).get("action")
    if action == "syncMarkets":
        cnt = await scanner.sync_markets(max_pages=10)
        return {"summary": f"Synced {cnt} markets"}
    if action == "pollOrders":
        upd = await trader.poll_open_orders(STATE.cfg)
        return {"summary": f"Polled, {len(upd)} updates"}
    if action == "resolveAll":
        rp = await trader.mark_resolved_positions(STATE.cfg)
        ra = await scanner.resolve_alerts_from_markets()
        rw = await scanner.resolve_whales_from_markets()
        return {"summary": f"Positions:{len(rp)} alerts:{ra} whales:{rw}"}
    if action == "reconcilePositions":
        s, changed = await trader.reconcile_positions_with_kalshi()
        for row in changed:
            await emit_event("position:update", _position_row_to_js(row))
        return {
            "summary": (
                f"Reconciled — rescued {s.get('rescued', 0)}, "
                f"resurrected {s.get('resurrected', 0)}, "
                f"imported {s.get('imported_unknowns', 0)}"
            ),
        }
    if action == "recomputePnl":
        s = await trader.recompute_pnl_from_kalshi()
        return {
            "summary": f"Re-resolved {s['recomputed']} of {s['cleared']} positions from Kalshi",
        }
    if action == "reconcileFills":
        s = await trader.reconcile_fills_from_kalshi()
        return {
            "summary": (
                f"Reconciled {s['fills_reconciled']} orders from Kalshi fills, "
                f"re-resolved {s['pnl_recomputed']} of {s['pnl_cleared']}"
            ),
        }
    if action == "auditPnl":
        s = await trader.audit_pnl(200)
        worst_lines = []
        for x in s.get("samples", [])[:8]:
            worst_lines.append(
                f"  {x['ticker']} {x['direction']}: stored ${x['stored_pnl']:+.2f} → fresh ${x['fresh_pnl']:+.2f} (Δ ${x['delta']:+.2f})"
            )
        msg = (
            f"Audited {s['checked']} resolved positions: {s['flagged']} flagged. "
            f"Sum stored=${s['sum_stored_pnl']:+.2f} vs fresh=${s['sum_recompute_pnl']:+.2f} "
            f"(Δ ${s['delta']:+.2f})"
        )
        if worst_lines:
            msg += "\n" + "\n".join(worst_lines)
        return {"summary": msg, "audit": s}
    raise ValueError(f"unknown action: {action}")


async def _h_pause(p: dict) -> dict:
    STATE.paused = bool((p or {}).get("paused", False))
    return {"paused": STATE.paused}


def _run_row_to_js(r: dict) -> dict:
    return {
        "id": int(r["id"]),
        "kalshiEnv": r.get("kalshi_env") or "demo",
        "startedAt": _iso_utc(r.get("started_at")) or "",
        "endedAt": _iso_utc(r.get("ended_at")),
        "startCashUsd": float(r.get("start_cash_usd") or 0),
        "startPortfolioUsd": float(r.get("start_portfolio_usd") or 0),
        "startTotalUsd": float(r.get("start_total_usd") or 0),
        "endCashUsd": (
            float(r["end_cash_usd"])
            if r.get("end_cash_usd") is not None else None
        ),
        "endPortfolioUsd": (
            float(r["end_portfolio_usd"])
            if r.get("end_portfolio_usd") is not None else None
        ),
        "endTotalUsd": (
            float(r["end_total_usd"])
            if r.get("end_total_usd") is not None else None
        ),
        "pnlUsd": float(r.get("pnl_usd") or 0),
        "tradesOpened": int(r.get("trades_opened") or 0),
        "tradesWon": int(r.get("trades_won") or 0),
        "tradesLost": int(r.get("trades_lost") or 0),
        "isActive": r.get("ended_at") is None,
    }


async def _h_botRuns(p: dict) -> dict:
    env = (p or {}).get("env")
    limit = int((p or {}).get("limit") or 100)
    with db.get_db() as conn:
        rows = db.get_recent_runs(conn, env=env, limit=limit)
        active = (
            db.get_active_run(conn, kalshi_auth.get_env())
            if STATE.active_run_id else None
        )
    return {
        "runs": [_run_row_to_js(r) for r in rows],
        "activeRunId": STATE.active_run_id,
        "activeRun": _run_row_to_js(active) if active else None,
    }


async def _h_shutdown(_p: dict) -> dict:
    asyncio.create_task(_shutdown())
    return {"shutting_down": True}


async def _h_factoryReset(_p: dict) -> dict:
    logger.warning("factory reset: STARTING — pausing trader loop")
    await _stop_loop()

    if STATE.active_run_id:
        try:
            with db.get_db() as conn:
                db.end_bot_run(conn, STATE.active_run_id)
        except Exception as e:
            logger.warning(f"factoryReset: end_bot_run: {e}")
        STATE.active_run_id = 0

    summary = await asyncio.to_thread(db.factory_reset)
    deleted_total = sum(
        v for k, v in summary.items()
        if not k.startswith("_") and isinstance(v, int) and v > 0
    )
    if summary.get("_errors"):
        logger.error(
            f"factory reset: PARTIAL — deleted {deleted_total} rows, "
            f"errors={summary['_errors']}"
        )
    else:
        logger.warning(
            f"factory reset: COMPLETE — deleted {deleted_total} rows "
            f"({summary})"
        )

    STATE.last_whale_scan_at = ""
    STATE.last_momentum_scan_at = ""
    STATE.last_trade_scan_at = ""

    if STATE.auth_ok:
        try:
            cents, port = await trader.refresh_balance(STATE.cfg, force=True)
            env = kalshi_auth.get_env()
            with db.get_db() as conn:
                stats = db.aggregate_stats(conn, env)
                STATE.active_run_id = db.start_bot_run(
                    conn, env=env,
                    cash_usd=cents / 100.0,
                    portfolio_usd=port / 100.0,
                    lifetime_trades=int(stats.get("total_opened") or 0),
                    lifetime_wins=int(stats.get("wins") or 0),
                    lifetime_losses=int(stats.get("losses") or 0),
                )
            logger.info(
                f"Bot run #{STATE.active_run_id} started after factory reset "
                f"(env={env}, "
                f"start_total=${(cents + port) / 100:.2f})"
            )
        except Exception as e:
            logger.warning(f"factoryReset: post-reset run start: {e}")

    await emit_event("data:reset", {"summary": summary})
    snap = await _build_account_snapshot()
    await emit_event("account:update", snap)

    await _start_loop()
    logger.info("factory reset: trader loop resumed")

    return {"ok": True, "deleted": summary}


async def _h_crypto15m(_p: dict) -> dict:
    return await crypto15m.snapshot(STATE.cfg)


async def _h_crypto15mStatus(_p: dict) -> dict:
    return await crypto15m_trader.status(STATE.cfg, authed=STATE.auth_ok)


async def _h_kalshiMarketUrl(p: dict) -> dict:
    url = await kalshi_api.web_market_url(
        event_ticker=str(p.get("eventTicker") or ""),
        ticker=str(p.get("ticker") or ""),
        env=str(p.get("env") or "production"),
    )
    return {"url": url}


_HANDLERS = {
    "ping": _h_ping,
    "crypto15m": _h_crypto15m,
    "crypto15mStatus": _h_crypto15mStatus,
    "kalshiMarketUrl": _h_kalshiMarketUrl,
    "setConfig": _h_setConfig,
    "setCredentials": _h_setCredentials,
    "clearCredentials": _h_clearCredentials,
    "credentialStatus": _h_credentialStatus,
    "testCredentials": _h_testCredentials,
    "account": _h_account,
    "pnlSeries": _h_pnlSeries,
    "positions": _h_positions,
    "signals": _h_signals,
    "scannerStats": _h_scannerStats,
    "cancelAllOpen": _h_cancelAllOpen,
    "flatten": _h_flatten,
    "runOnce": _h_runOnce,
    "pause": _h_pause,
    "shutdown": _h_shutdown,
    "botRuns": _h_botRuns,
    "factoryReset": _h_factoryReset,
}


async def _dispatch_request(req: dict) -> None:
    rid = req.get("id", "")
    method = req.get("method", "")
    params = req.get("params") or {}
    h = _HANDLERS.get(method)
    if not h:
        await respond_err(rid, f"unknown method: {method}")
        return
    try:
        result = await h(params)
        await respond_ok(rid, result)
    except Exception as e:
        logger.debug(
            f"RPC {method} failed: {e}\n{traceback.format_exc(limit=3)}"
        )
        await respond_err(rid, f"{type(e).__name__}: {e}")




async def _stdin_reader() -> None:
    loop = asyncio.get_event_loop()

    def _readline() -> str:
        return sys.stdin.readline()

    while True:
        line = await loop.run_in_executor(None, _readline)
        if not line:
            await asyncio.sleep(0.1)
            await _shutdown()
            return
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        if not isinstance(req, dict):
            continue
        if req.get("type") != "rpc":
            continue
        asyncio.create_task(_dispatch_request(req))


_shutting_down = False


async def _shutdown() -> None:
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    try:
        await _stop_loop()
    except Exception:
        pass
    try:
        if STATE.active_run_id:
            with db.get_db() as conn:
                db.end_bot_run(conn, STATE.active_run_id)
            STATE.active_run_id = 0
    except Exception:
        pass
    try:
        await kalshi_api.close_clients()
    except Exception:
        pass
    try:
        await crypto15m.close_clients()
    except Exception:
        pass
    await emit_event("backend:shutdown", {})
    sys.stdout.flush()
    await asyncio.sleep(0.1)
    os._exit(0)




async def _main() -> None:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    STATE.started_at = datetime.now(timezone.utc).isoformat()
    db.init_db()
    logger.info("Krypt Trader backend starting")

    active_env = STATE.cfg.get("kalshi_env", "demo")
    try:
        kalshi_auth.set_env(active_env)
    except Exception:
        pass
    try:
        if kalshi_auth.migrate_legacy_credentials(active_env):
            logger.info(f"Migrated legacy credentials → {active_env}")
    except Exception as e:
        logger.warning(f"legacy credential migration failed: {e}")

    if kalshi_auth.credentials_present(active_env):
        try:
            kalshi_auth.prime_credentials(sync_time=True)
            bal = await kalshi_api.get_balance()
            int(bal.get("balance", 0))
            STATE.auth_ok = True
            logger.info("Saved credentials verified")
        except Exception as e:
            logger.warning(f"saved-credential verify failed: {e}")
            STATE.auth_ok = False

    await emit_event("backend:ready", {"startedAt": STATE.started_at})
    await emit_event("backend:authChanged", {"authOk": STATE.auth_ok})
    try:
        await emit_event(
            "credentials:changed", kalshi_auth.credentials_status_all(),
        )
    except Exception:
        pass

    if STATE.auth_ok:
        try:
            summary, changed = await trader.reconcile_positions_with_kalshi()
            if any(summary.values()):
                logger.info(f"Eager startup reconcile: {summary}")
            await emit_event("backend:reconciled", summary)
            for row in changed:
                await emit_event("position:update", _position_row_to_js(row))
        except Exception as e:
            logger.warning(f"eager startup reconcile failed: {e}")

    if STATE.auth_ok:
        try:
            cents, port = await trader.refresh_balance(STATE.cfg, force=True)
            env_now = kalshi_auth.get_env()
            with db.get_db() as conn:
                stats = db.aggregate_stats(conn, env_now)
                STATE.active_run_id = db.start_bot_run(
                    conn,
                    env=env_now,
                    cash_usd=cents / 100.0,
                    portfolio_usd=port / 100.0,
                    lifetime_trades=int(stats.get("total_opened") or 0),
                    lifetime_wins=int(stats.get("wins") or 0),
                    lifetime_losses=int(stats.get("losses") or 0),
                )
            logger.info(
                f"Bot run #{STATE.active_run_id} started "
                f"(env={env_now}, "
                f"start_total=${(cents + port) / 100.0:.2f})"
            )
        except Exception as e:
            logger.warning(f"could not open bot_run: {e}")

    await _start_loop()
    try:
        await _stdin_reader()
    except Exception as e:
        logger.error(f"reader crashed: {e}")
    finally:
        await _shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
