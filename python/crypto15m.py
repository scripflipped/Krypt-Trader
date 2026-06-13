from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

import kalshi_api

logger = logging.getLogger(__name__)


SERIES: list[dict[str, str]] = [
    {"asset": "BTC",  "series": "KXBTC15M",  "cg": "bitcoin"},
    {"asset": "ETH",  "series": "KXETH15M",  "cg": "ethereum"},
    {"asset": "SOL",  "series": "KXSOL15M",  "cg": "solana"},
    {"asset": "XRP",  "series": "KXXRP15M",  "cg": "ripple"},
    {"asset": "DOGE", "series": "KXDOGE15M", "cg": "dogecoin"},
    {"asset": "HYPE", "series": "KXHYPE15M", "cg": "hyperliquid"},
    {"asset": "BNB",  "series": "KXBNB15M",  "cg": "binancecoin"},
]

_DEFAULTS: dict[str, float] = {
    "time_delay_min": 8.0,
    "entry_threshold": 0.95,
    "exit_threshold": 0.40,
    "entry_max": 0.98,
    "min_delta_pct": 0.0,
    "entry_diff": 0.02,
}

_CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data/pricemulti"
_COINBASE_URL = "https://api.coinbase.com/v2/prices/{sym}-USD/spot"
_COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
_SPOT_CACHE_TTL = 10.0
_QUARTER_SEC = 15 * 60

_spot_client: Optional[httpx.AsyncClient] = None

_spot_cache: dict = {"at": 0.0, "spots": {}, "source": "none"}

_window_open: dict[tuple[str, int], float] = {}


def _get_spot_client() -> httpx.AsyncClient:
    global _spot_client
    if _spot_client is None or _spot_client.is_closed:
        _spot_client = httpx.AsyncClient(
            timeout=8.0,
            headers={"Accept": "application/json", "User-Agent": "KryptTrader/1.0"},
        )
    return _spot_client


async def close_clients() -> None:
    global _spot_client
    if _spot_client and not _spot_client.is_closed:
        try:
            await _spot_client.aclose()
        except Exception:
            pass
    _spot_client = None


def _const(cfg: dict, key: str) -> float:
    try:
        return float(cfg.get(f"crypto15m_{key}", _DEFAULTS[key]))
    except (TypeError, ValueError):
        return _DEFAULTS[key]


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _price_dollars(m: dict, key: str) -> float:
    d = m.get(f"{key}_dollars")
    if d is not None:
        return _to_float(d)
    return _to_float(m.get(key)) / 100.0


def _parse_close_epoch(close_time: str) -> Optional[float]:
    if not close_time:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            ct = datetime.strptime(close_time, fmt)
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
            return ct.timestamp()
        except ValueError:
            continue
    return None


async def _spots_cryptocompare(client: httpx.AsyncClient) -> dict[str, float]:
    syms = ",".join(s["asset"] for s in SERIES)
    resp = await client.get(_CRYPTOCOMPARE_URL, params={"fsyms": syms, "tsyms": "USD"})
    resp.raise_for_status()
    data = resp.json() or {}
    if isinstance(data, dict) and data.get("Response") == "Error":
        raise RuntimeError(str(data.get("Message") or "cryptocompare error"))
    out: dict[str, float] = {}
    for s in SERIES:
        px = (data.get(s["asset"]) or {}).get("USD")
        if px is not None:
            out[s["asset"]] = float(px)
    return out


async def _spots_coinbase(client: httpx.AsyncClient) -> dict[str, float]:
    async def one(s: dict) -> tuple[str, Optional[float]]:
        try:
            r = await client.get(_COINBASE_URL.format(sym=s["asset"]))
            r.raise_for_status()
            amt = ((r.json() or {}).get("data") or {}).get("amount")
            return s["asset"], (float(amt) if amt is not None else None)
        except Exception:
            return s["asset"], None

    results = await asyncio.gather(*[one(s) for s in SERIES])
    return {a: px for a, px in results if px is not None}


async def _spots_coingecko(client: httpx.AsyncClient) -> dict[str, float]:
    ids = ",".join(s["cg"] for s in SERIES)
    resp = await client.get(_COINGECKO_URL, params={"ids": ids, "vs_currencies": "usd"})
    resp.raise_for_status()
    data = resp.json()
    out: dict[str, float] = {}
    for s in SERIES:
        px = (data.get(s["cg"]) or {}).get("usd")
        if px is not None:
            out[s["asset"]] = float(px)
    return out


_SPOT_SOURCES = [
    ("cryptocompare", _spots_cryptocompare),
    ("coinbase", _spots_coinbase),
    ("coingecko", _spots_coingecko),
]


async def fetch_spots() -> tuple[dict[str, float], str]:
    loop = asyncio.get_event_loop()
    now = loop.time()
    if _spot_cache["spots"] and (now - _spot_cache["at"]) < _SPOT_CACHE_TTL:
        return dict(_spot_cache["spots"]), _spot_cache["source"]

    client = _get_spot_client()
    for name, fn in _SPOT_SOURCES:
        try:
            spots = await fn(client)
        except Exception as e:
            logger.debug(f"crypto15m spot source {name} failed: {e}")
            continue
        if spots:
            _spot_cache.update(at=now, spots=dict(spots), source=name)
            return spots, name

    if _spot_cache["spots"]:
        return dict(_spot_cache["spots"]), f"{_spot_cache['source']} (stale)"
    return {}, "unavailable"


def _blank_asset(entry: dict, spot: Optional[float], error: Optional[str] = None) -> dict:
    return {
        "asset": entry["asset"], "series": entry["series"],
        "spotUsd": spot, "open15mUsd": None, "deltaUsd": None, "deltaPct": None,
        "hasMarket": False, "ticker": None, "closeTime": None, "minsLeft": None,
        "upProb": None, "downProb": None, "favorite": None,
        "favoritePrice": None, "entryCost": None, "yesBid": None, "yesAsk": None,
        "inWindow": False, "signal": False, "openMarketCount": 0, "error": error,
    }


def hours_ok(cfg: dict, hour: Optional[int] = None) -> bool:
    try:
        start = int(cfg.get("crypto15m_hours_start_utc", 0) or 0)
        end = int(cfg.get("crypto15m_hours_end_utc", 24) or 24)
    except (TypeError, ValueError):
        return True
    start, end = start % 24, (end % 24 if end != 24 else 24)
    if start == end or (start == 0 and end == 24):
        return True
    if hour is None:
        hour = datetime.now(timezone.utc).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _track_window_open(asset: str, window_start: int, spot: Optional[float]) -> Optional[float]:
    if spot is None:
        return None
    key = (asset, window_start)
    if key not in _window_open:
        _window_open[key] = spot
        if len(_window_open) > 200:
            for old in sorted(_window_open, key=lambda k: k[1])[:50]:
                _window_open.pop(old, None)
    return _window_open[key]


async def _asset_snapshot(entry: dict, spot: Optional[float], cfg: dict, now_epoch: float) -> dict:
    asset, series = entry["asset"], entry["series"]
    try:
        markets, _ = await kalshi_api.fetch_markets(
            status="open", series_ticker=series, limit=200,
        )
    except Exception as e:
        return _blank_asset(entry, spot, f"market fetch failed: {e}")

    candidates: list[tuple[float, dict]] = []
    for m in markets:
        ce = _parse_close_epoch(m.get("close_time", ""))
        if ce is None or ce <= now_epoch:
            continue
        candidates.append((ce, m))

    out = _blank_asset(entry, spot)
    out["openMarketCount"] = len(candidates)
    if not candidates:
        return out

    candidates.sort(key=lambda x: x[0])
    close_epoch, m = candidates[0]

    window_start = int(close_epoch - _QUARTER_SEC)
    open15m = _track_window_open(asset, window_start, spot)
    delta = abs(open15m - spot) if (open15m is not None and spot is not None) else None
    delta_pct = (delta / open15m) if (delta is not None and open15m) else None

    yes_bid = _price_dollars(m, "yes_bid")
    yes_ask = _price_dollars(m, "yes_ask")
    up = (yes_bid + yes_ask) / 2 if (yes_bid or yes_ask) else _price_dollars(m, "last_price")
    up = max(0.0, min(1.0, up))
    down = 1.0 - up
    favorite = "up" if up >= down else "down"
    fav_price = up if favorite == "up" else down

    no_ask = _price_dollars(m, "no_ask")
    entry_cost = yes_ask if favorite == "up" else (no_ask if no_ask else 1.0 - yes_bid)
    entry_cost = max(0.0, min(1.0, entry_cost))

    mins_left = (close_epoch - now_epoch) / 60.0
    in_window = mins_left <= _const(cfg, "time_delay_min")
    signal = (
        in_window
        and hours_ok(cfg)
        and fav_price >= _const(cfg, "entry_threshold")
        and entry_cost <= _const(cfg, "entry_max")
        and (delta_pct is None or delta_pct >= _const(cfg, "min_delta_pct"))
    )

    out.update({
        "open15mUsd": open15m, "deltaUsd": delta, "deltaPct": delta_pct,
        "hasMarket": True, "ticker": m.get("ticker"),
        "closeTime": m.get("close_time"), "minsLeft": round(mins_left, 2),
        "upProb": round(up, 4), "downProb": round(down, 4),
        "favorite": favorite, "favoritePrice": round(fav_price, 4),
        "entryCost": round(entry_cost, 4),
        "yesBid": round(yes_bid, 4) if yes_bid else None,
        "yesAsk": round(yes_ask, 4) if yes_ask else None,
        "inWindow": in_window, "signal": signal,
    })
    return out


async def snapshot(cfg: dict) -> dict:
    now_epoch = datetime.now(timezone.utc).timestamp()
    try:
        spots, spot_source = await fetch_spots()
    except Exception as e:
        logger.debug(f"crypto15m spot fetch failed: {e}")
        spots, spot_source = {}, "unavailable"
    spot_ok = bool(spots)

    results = await asyncio.gather(
        *[_asset_snapshot(s, spots.get(s["asset"]), cfg, now_epoch) for s in SERIES],
        return_exceptions=True,
    )
    assets: list[dict] = []
    for s, r in zip(SERIES, results):
        assets.append(
            r if not isinstance(r, Exception)
            else _blank_asset(s, spots.get(s["asset"]), str(r))
        )

    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "spotOk": spot_ok,
        "spotSource": spot_source,
        "hoursOk": hours_ok(cfg),
        "constants": {
            "timeDelayMin": _const(cfg, "time_delay_min"),
            "entryThreshold": _const(cfg, "entry_threshold"),
            "exitThreshold": _const(cfg, "exit_threshold"),
            "entryMax": _const(cfg, "entry_max"),
            "minDeltaPct": _const(cfg, "min_delta_pct"),
            "entryDiff": _const(cfg, "entry_diff"),
            "directionMode": str(cfg.get("crypto15m_direction_mode", "favorite")),
            "entryStyle": str(cfg.get("crypto15m_entry_style", "maker")),
            "hoursStartUtc": int(cfg.get("crypto15m_hours_start_utc", 0) or 0),
            "hoursEndUtc": int(cfg.get("crypto15m_hours_end_utc", 24) or 24),
        },
        "assets": assets,
    }
