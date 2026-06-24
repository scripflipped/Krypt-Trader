from __future__ import annotations
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "kalshi_env": "demo",
    "enable_trading": False,

    "trade_whales": True,
    "trade_momentum": True,
    "trade_convergence": False,

    "min_edge_pts_whale": 5.0,
    "min_edge_pts_momentum": 5.0,
    "min_confidence_whale": 55.0,
    "min_confidence_momentum": 55.0,
    "min_entry_price_cents": 15,
    "max_entry_price_cents": 85,
    "allowed_momentum_signal_types": ["trade_cluster"],
    "allowed_categories": None,
    "allowed_whale_categories": None,
    "allowed_momentum_categories": None,
    "contrarian_only": True,

    # "Secret Strategy" — pure-gambling mode. Ignores every gate and gives each
    # fresh signal a flat random chance to trade. For fun only.
    "gambling_mode": False,
    "gambling_trade_probability": 0.10,

    # "percent" = edge-scaled % of balance (below). "fixed" = a flat dollar
    # amount per trade (fixed_trade_usd), ignoring the fractions.
    "sizing_mode": "percent",
    "fixed_trade_usd": 5.0,

    "base_size_fraction": 0.03,
    "min_size_fraction": 0.02,
    "max_size_fraction": 0.06,
    "sizing_base_edge": 5.0,
    "sizing_max_edge": 20.0,
    "hard_max_position_usd": 50.0,
    "min_cash_reserve_fraction": 0.05,

    "order_style": "limit_cross",
    "cross_spread_fallback_offset": 2,
    "order_expiration_sec": 90,

    "max_open_positions": 25,
    "max_positions_per_event": 1,
    "max_daily_new_positions": 40,
    "unlimited_daily_new_positions": False,
    "max_total_exposure_fraction": 0.75,

    "trade_scan_interval": 20,
    "position_poll_interval": 30,
    "balance_poll_interval": 60,
    "resolution_check_interval": 300,
    "whale_scan_interval": 120,
    "momentum_scan_interval": 90,
    "market_refresh_interval": 300,
    "db_cleanup_interval": 3600,

    "max_signal_age_sec": 120,

    "start_bankroll_usd": 0.0,
    "stop_loss_on_day": -50.0,
    "take_profit_on_day": 0.0,

    "trading_hours_enabled": False,
    "trading_hours_start": "00:00",
    "trading_hours_end": "23:59",
    "trading_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    "trading_timezone_offset_min": 0,

    "min_whale_usd": 2500.0,
    "min_whale_confidence": 30.0,
    "min_whale_edge": 2.0,
    "min_momentum_confidence": 0.0,
    "min_momentum_edge": 5.0,
    "min_entry_price_frac": 0.50,

    "crypto15m_time_delay_min": 8.0,
    "crypto15m_entry_threshold": 0.70,
    "crypto15m_entry_max": 0.98,
    "crypto15m_exit_threshold": 0.40,
    "crypto15m_min_delta_pct": 0.0,
    "crypto15m_entry_diff": 0.02,
    "crypto15m_entry_style": "maker",
    "crypto15m_maker_cancel_min": 1.0,
    "crypto15m_hours_start_utc": 0,
    "crypto15m_hours_end_utc": 24,
    "crypto15m_enabled": False,
    "crypto15m_live": False,
    "crypto15m_sizing_mode": "fixed",
    "crypto15m_order_size": 1,
    "crypto15m_balance_pct": 0.02,
    "crypto15m_max_loss_pct": 0.0,
    "crypto15m_max_concurrent": 7,
    "crypto15m_poll_sec": 4,
    "crypto15m_direction_mode": "favorite",
    "crypto15m_record_signals": True,

    "event_webhook_url": "",
    "stats_webhook_url": "",
    "whale_webhook_url": "",
    "momentum_webhook_url": "",
    "stats_push_interval": 3600,
    "stats_chart_window_hours": 168,
    "enable_discord": True,
}



STRATEGY_PRESETS: list[dict[str, Any]] = [
    {
        "id": "krypt-balanced",
        "name": "Krypt Balanced",
        "tagline": "Whales + momentum, both gates active.",
        "description": (
            "Our default everyday strategy. Trades both whale signals and "
            "trade-cluster momentum signals with edge ≥ 5pts and "
            "confidence ≥ 55%. 2-6% sizing, $50 hard cap. Best fit for "
            "most users — let it run a few weeks and check the stats."
        ),
        "riskLabel": "balanced",
        "badge": "recommended",
        "config": {},
    },
    {
        "id": "krypt-conservative",
        "name": "Krypt Conservative",
        "tagline": "Tight sizing, high-edge only, capital-preservation mode.",
        "description": (
            "Only trades signals with edge ≥ 8pts and confidence ≥ 65%. "
            "Smaller sizing (1-3% of bankroll), $25 hard cap. Daily "
            "stop-loss at -$25. Designed to ride out variance with "
            "minimum drawdown."
        ),
        "riskLabel": "safe",
        "config": {
            "min_edge_pts_whale": 8.0,
            "min_edge_pts_momentum": 8.0,
            "min_confidence_whale": 65.0,
            "min_confidence_momentum": 65.0,
            "base_size_fraction": 0.015,
            "min_size_fraction": 0.01,
            "max_size_fraction": 0.03,
            "hard_max_position_usd": 25.0,
            "max_open_positions": 10,
            "max_daily_new_positions": 15,
            "stop_loss_on_day": -25.0,
            "max_total_exposure_fraction": 0.50,
        },
    },
    {
        "id": "krypt-aggressive",
        "name": "Krypt Aggressive",
        "tagline": "More signals, larger sizing, higher variance.",
        "description": (
            "Loosens edge gates to 3pts and confidence to 50%. Sizing "
            "scales 4-10% of bankroll, $100 cap. Higher max-open count. "
            "Use only with a bankroll you can stand to drop 30% on a "
            "bad day."
        ),
        "riskLabel": "aggressive",
        "config": {
            "min_edge_pts_whale": 3.0,
            "min_edge_pts_momentum": 3.0,
            "min_confidence_whale": 50.0,
            "min_confidence_momentum": 50.0,
            "base_size_fraction": 0.06,
            "min_size_fraction": 0.04,
            "max_size_fraction": 0.10,
            "hard_max_position_usd": 100.0,
            "max_open_positions": 40,
            "max_daily_new_positions": 80,
            "max_total_exposure_fraction": 0.85,
            "stop_loss_on_day": -100.0,
        },
    },
    {
        "id": "krypt-whale-only",
        "name": "Whale Hunter",
        "tagline": "Follows large taker orders. No momentum signals.",
        "description": (
            "Pure whale-following. Disables momentum entirely and only "
            "trades when a $2.5k+ taker order hits a market with a "
            "scored edge ≥ 5pts. Best when you trust 'smart money' "
            "patterns more than crowd contrarian setups."
        ),
        "riskLabel": "balanced",
        "config": {
            "trade_whales": True,
            "trade_momentum": False,
            "min_edge_pts_whale": 5.0,
            "min_confidence_whale": 55.0,
        },
    },
    {
        "id": "krypt-momentum-only",
        "name": "Crowd Contrarian",
        "tagline": "Mean-reversion on trade clusters. No whale signals.",
        "description": (
            "Only fades clusters of trades against the underdog. "
            "Empirically the highest-edge zone in the data: NO clusters "
            "when YES is heavy favourite, YES clusters when YES is deep "
            "underdog. Disables whale-following entirely."
        ),
        "riskLabel": "balanced",
        "config": {
            "trade_whales": False,
            "trade_momentum": True,
            "contrarian_only": True,
            "min_edge_pts_momentum": 7.0,
            "min_confidence_momentum": 50.0,
            "allowed_momentum_signal_types": ["trade_cluster"],
        },
    },
    {
        "id": "krypt-edge-hunter",
        "name": "Edge Hunter",
        "tagline": "Top-decile edge only. Few but high-quality trades.",
        "description": (
            "Only fires on signals with edge ≥ 12pts. Sizes more "
            "aggressively on high-edge picks (4-8% scaled). Expect "
            "long quiet periods between trades, but a higher hit rate "
            "when they happen."
        ),
        "riskLabel": "balanced",
        "config": {
            "min_edge_pts_whale": 12.0,
            "min_edge_pts_momentum": 12.0,
            "min_confidence_whale": 60.0,
            "min_confidence_momentum": 55.0,
            "base_size_fraction": 0.04,
            "min_size_fraction": 0.04,
            "max_size_fraction": 0.08,
            "sizing_base_edge": 12.0,
            "sizing_max_edge": 25.0,
            "max_open_positions": 15,
        },
    },
    {
        "id": "krypt-crypto-whale",
        "name": "Crypto Whale",
        "tagline": "Whale-following, crypto markets only.",
        "description": (
            "Most reliable edge (highest t-stat, 97% win). Whale signals in "
            "CRYPTO backtested strongly positive net-of-fee while sports "
            "whales lost. Entry cap raised to 98c because crypto whales follow "
            "high-price favorites (the old 85c cap threw away most of the "
            "edge). In-sample +9.3c/contract (t=3.5, n=36). EXPERIMENTAL / "
            "in-sample on a small sample — paper-trade to confirm."
        ),
        "riskLabel": "experimental",
        "badge": "new",
        "config": {
            "trade_whales": True,
            "trade_momentum": False,
            "allowed_categories": ["crypto"],
            "min_confidence_whale": 55.0,
            "min_edge_pts_whale": 5.0,
            "min_entry_price_cents": 15,
            "max_entry_price_cents": 98,
        },
    },
    {
        "id": "krypt-sports-momentum",
        "name": "Sports Momentum",
        "tagline": "Contrarian trade-clusters, sports only.",
        "description": (
            "Highest raw edge, but noisier (single category, smaller sample). "
            "Contrarian momentum in SPORTS backtested strongly positive "
            "net-of-fee while news/world momentum lost. Fixed: confidence >= 40 "
            "(the old 50 gate cut the edge to noise — momentum scores top out "
            "near 60) and a wider 15-70c band. In-sample +18.2c/contract "
            "(t=2.2, n=37). EXPERIMENTAL / in-sample — paper-trade to confirm."
        ),
        "riskLabel": "experimental",
        "badge": "new",
        "config": {
            "trade_whales": False,
            "trade_momentum": True,
            "contrarian_only": True,
            "allowed_categories": ["sports"],
            "allowed_momentum_signal_types": ["trade_cluster"],
            "min_confidence_momentum": 40.0,
            "min_entry_price_cents": 15,
            "max_entry_price_cents": 70,
        },
    },
    {
        "id": "krypt-edge",
        "name": "Edge Stack",
        "tagline": "Both backtested edges at once — crypto whales + sports momentum.",
        "description": (
            "Our recommended pick — the best risk-adjusted edge. Runs the two "
            "signal sources that backtested net-POSITIVE after fees, each "
            "restricted to where it has an edge — whales in CRYPTO / EXOTICS / "
            "ENTERTAINMENT and contrarian momentum in SPORTS (confidence >= 40) "
            "— with an 85c cap that drops the loss-making high-price favorites. "
            "Sports Momentum has a higher raw edge, but this diversifies across "
            "two independent sources, so it's the most reliable. In-sample "
            "+15.6c/contract (t=3.2, n=81) vs the unfiltered default's "
            "net-NEGATIVE edge. EXPERIMENTAL / in-sample — test on Demo "
            "first to confirm it holds forward."
        ),
        "riskLabel": "experimental",
        "badge": "recommended",
        "config": {
            "trade_whales": True,
            "trade_momentum": True,
            "contrarian_only": True,
            "allowed_categories": None,
            "allowed_whale_categories": ["crypto", "exotics", "entertainment"],
            "allowed_momentum_categories": ["sports"],
            "allowed_momentum_signal_types": ["trade_cluster"],
            "min_confidence_whale": 55.0,
            "min_edge_pts_whale": 5.0,
            "min_confidence_momentum": 40.0,
            "min_entry_price_cents": 15,
            "max_entry_price_cents": 85,
        },
    },
    {
        "id": "krypt-experimental",
        "name": "Convergence Hunter",
        "tagline": "Trades only when 3+ whales agree on the same side.",
        "description": (
            "Experimental. Only trades when convergence is detected — "
            "3+ whales taking the same side of the same market within 2 "
            "hours. Rare but high-conviction setups."
        ),
        "riskLabel": "experimental",
        "badge": "new",
        "config": {
            "trade_whales": False,
            "trade_momentum": False,
            "trade_convergence": True,
            "min_edge_pts_whale": 6.0,
            "min_confidence_whale": 60.0,
            "max_open_positions": 12,
        },
    },
]


CRYPTO15M_PRESETS: list[dict[str, Any]] = [
    {
        "id": "c15-favorite",
        "name": "Deep Favorite",
        "tagline": "Only the deepest favorites: buy at 95-98c.",
        "description": (
            "Buy the favorite only when it is already >=95c — the single "
            "price band that did not lose money in this app's replay of "
            "531 settled 15-minute markets (+2.8c/contract net of fees, "
            "16/16 wins). CAUTION: that sample is far too small to prove "
            "an edge; one loss at 97c wipes out ~35 wins. Paper-trade "
            "first."
        ),
        "config": {
            "crypto15m_direction_mode": "favorite",
            "crypto15m_entry_threshold": 0.95,
            "crypto15m_entry_max": 0.98,
            "crypto15m_exit_threshold": 0.40,
            "crypto15m_entry_style": "maker",
        },
    },
    {
        "id": "c15-contrarian",
        "name": "Contrarian Fade",
        "tagline": "Fade extreme favorites — buy the cheap underdog.",
        "description": (
            "When a side is an extreme favorite (>=90c), buy the CHEAP "
            "opposite side, betting the 15-minute move reverts before "
            "close. Low win rate, high payoff (longshot); holds to "
            "settlement, no stop. Measured roughly break-even (+1.0c/"
            "contract, t=0.3, n=64) on the recorded data — no proven "
            "edge. Paper-trade hard."
        ),
        "config": {
            "crypto15m_direction_mode": "contrarian",
            "crypto15m_entry_threshold": 0.90,
            "crypto15m_entry_max": 0.98,
            "crypto15m_exit_threshold": 0.0,
            "crypto15m_entry_style": "maker",
        },
    },
]


def crypto15m_preset_config(preset_id: str) -> dict[str, Any] | None:
    for p in CRYPTO15M_PRESETS:
        if p["id"] == preset_id:
            return dict(p["config"])
    return None


def _camel_to_snake(name: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch.lower() if ch.isupper() else ch)
    return "".join(out)


def _clampf(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:
        return default
    return max(lo, min(hi, f))


def _clampi(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


_FRACTION_KEYS = [
    "base_size_fraction", "min_size_fraction", "max_size_fraction",
    "min_cash_reserve_fraction", "max_total_exposure_fraction",
]
_UNIT_KEYS = [
    "crypto15m_entry_threshold", "crypto15m_entry_max", "crypto15m_exit_threshold",
    "crypto15m_min_delta_pct", "crypto15m_entry_diff", "min_entry_price_frac",
    "gambling_trade_probability",
]


def _validate_config(cfg: dict[str, Any]) -> dict[str, Any]:
    d = DEFAULT_CONFIG
    for k in _FRACTION_KEYS:
        cfg[k] = _clampf(cfg.get(k), 0.0, 1.0, d[k])
    for k in _UNIT_KEYS:
        cfg[k] = _clampf(cfg.get(k), 0.0, 1.0, d[k])
    if cfg["min_size_fraction"] > cfg["max_size_fraction"]:
        cfg["min_size_fraction"] = cfg["max_size_fraction"]

    if cfg.get("sizing_mode") not in ("percent", "fixed"):
        cfg["sizing_mode"] = d["sizing_mode"]
    cfg["fixed_trade_usd"] = _clampf(cfg.get("fixed_trade_usd"), 0.0, 1e9, d["fixed_trade_usd"])
    cfg["hard_max_position_usd"] = _clampf(cfg.get("hard_max_position_usd"), 0.0, 1e9, d["hard_max_position_usd"])
    cfg["min_entry_price_cents"] = _clampi(cfg.get("min_entry_price_cents"), 1, 99, d["min_entry_price_cents"])
    cfg["max_entry_price_cents"] = _clampi(cfg.get("max_entry_price_cents"), 1, 99, d["max_entry_price_cents"])
    if cfg["min_entry_price_cents"] > cfg["max_entry_price_cents"]:
        cfg["min_entry_price_cents"], cfg["max_entry_price_cents"] = (
            cfg["max_entry_price_cents"], cfg["min_entry_price_cents"],
        )
    cfg["max_open_positions"] = _clampi(cfg.get("max_open_positions"), 0, 100_000, d["max_open_positions"])
    cfg["max_daily_new_positions"] = _clampi(cfg.get("max_daily_new_positions"), 0, 100_000, d["max_daily_new_positions"])
    cfg["max_positions_per_event"] = _clampi(cfg.get("max_positions_per_event"), 1, 100_000, d["max_positions_per_event"])
    cfg["stop_loss_on_day"] = _clampf(cfg.get("stop_loss_on_day"), -1e9, 0.0, d["stop_loss_on_day"])
    cfg["take_profit_on_day"] = _clampf(cfg.get("take_profit_on_day"), 0.0, 1e9, d["take_profit_on_day"])
    cfg["gambling_mode"] = bool(cfg.get("gambling_mode", False))
    cfg["crypto15m_live"] = bool(cfg.get("crypto15m_live", False))
    cfg["crypto15m_order_size"] = _clampi(cfg.get("crypto15m_order_size"), 1, 10_000, d["crypto15m_order_size"])
    cfg["crypto15m_max_concurrent"] = _clampi(cfg.get("crypto15m_max_concurrent"), 1, 50, d["crypto15m_max_concurrent"])
    if cfg.get("crypto15m_sizing_mode") not in ("fixed", "balance_pct"):
        cfg["crypto15m_sizing_mode"] = d["crypto15m_sizing_mode"]
    cfg["crypto15m_balance_pct"] = _clampf(cfg.get("crypto15m_balance_pct"), 0.0, 1.0, d["crypto15m_balance_pct"])
    cfg["crypto15m_max_loss_pct"] = _clampf(cfg.get("crypto15m_max_loss_pct"), 0.0, 1.0, d["crypto15m_max_loss_pct"])
    cfg["crypto15m_time_delay_min"] = _clampf(cfg.get("crypto15m_time_delay_min"), 0.0, 15.0, d["crypto15m_time_delay_min"])
    if cfg.get("crypto15m_direction_mode") not in ("favorite", "contrarian"):
        cfg["crypto15m_direction_mode"] = d["crypto15m_direction_mode"]
    if cfg.get("crypto15m_entry_style") not in ("maker", "taker"):
        cfg["crypto15m_entry_style"] = d["crypto15m_entry_style"]
    cfg["crypto15m_maker_cancel_min"] = _clampf(cfg.get("crypto15m_maker_cancel_min"), 0.0, 15.0, d["crypto15m_maker_cancel_min"])
    cfg["crypto15m_hours_start_utc"] = _clampi(cfg.get("crypto15m_hours_start_utc"), 0, 24, d["crypto15m_hours_start_utc"])
    cfg["crypto15m_hours_end_utc"] = _clampi(cfg.get("crypto15m_hours_end_utc"), 0, 24, d["crypto15m_hours_end_utc"])
    return cfg


def merge_with_defaults(user: dict[str, Any]) -> dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    for k, v in (user or {}).items():
        if k in out:
            out[k] = v
            continue
        sk = _camel_to_snake(k)
        out[sk] = v
    return _validate_config(out)


def strategy_full_config(strategy_id: str) -> dict[str, Any] | None:
    for s in STRATEGY_PRESETS:
        if s["id"] == strategy_id:
            return merge_with_defaults(s["config"])
    return None
