"""Public + signed Kalshi API client.

Public reads (markets, trades, orderbook, series) hit the production
data endpoint regardless of the user's chosen demo/production env —
demo doesn't have a usable trade feed for whale scanning, so we read
public data from prod and only sign trade-API calls against the
configured environment.

Signed writes (orders, positions, balance) hit
`https://demo-api.kalshi.co` or `https://api.elections.kalshi.com`
based on `kalshi_auth.set_env()`.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional
import uuid

import httpx

from kalshi_auth import sign_headers, get_env

logger = logging.getLogger(__name__)

PUBLIC_BASE = "https://api.elections.kalshi.com/trade-api/v2"

_TRADE_BASES = {
    "demo": "https://demo-api.kalshi.co",
    "production": "https://api.elections.kalshi.com",
}

PATH_PREFIX = "/trade-api/v2"
REQUEST_TIMEOUT = 25.0
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5

_pub_client: Optional[httpx.AsyncClient] = None
_signed_client: Optional[httpx.AsyncClient] = None
_signed_env: str = ""


async def _get_pub_client() -> httpx.AsyncClient:
    global _pub_client
    if _pub_client is None or _pub_client.is_closed:
        _pub_client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={
                "Accept": "application/json",
                "User-Agent": "KryptTrader/1.0",
            },
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
        )
    return _pub_client


async def _get_signed_client() -> httpx.AsyncClient:
    global _signed_client, _signed_env
    env = get_env()
    if (
        _signed_client is None
        or _signed_client.is_closed
        or _signed_env != env
    ):
        if _signed_client is not None and not _signed_client.is_closed:
            try:
                await _signed_client.aclose()
            except Exception:
                pass
        _signed_client = httpx.AsyncClient(
            base_url=_TRADE_BASES[env],
            timeout=REQUEST_TIMEOUT,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "KryptTrader/1.0",
            },
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        _signed_env = env
    return _signed_client


async def close_clients() -> None:
    global _pub_client, _signed_client
    for c in (_pub_client, _signed_client):
        if c and not c.is_closed:
            try:
                await c.aclose()
            except Exception:
                pass
    _pub_client = None
    _signed_client = None


class KalshiAPIError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")




async def _pub_get(url: str, params: dict | None = None) -> Any:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = await _get_pub_client()
            resp = await client.get(url, params=params)
            if resp.status_code == 429:
                wait = float(resp.headers.get("retry-after", 5))
                await asyncio.sleep(min(wait, 10))
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF * attempt)
                continue
            try:
                return resp.json() if resp.status_code < 400 else None
            except Exception:
                return None
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF * attempt)
                continue
            logger.warning(f"public GET failed {url}: {e}")
            return None
    return None


async def fetch_markets(
    status: str = "open",
    limit: int = 1000,
    cursor: str = "",
    series_ticker: str = "",
) -> tuple[list, str]:
    params: dict = {"limit": min(limit, 1000)}
    if status:
        params["status"] = status
    if cursor:
        params["cursor"] = cursor
    if series_ticker:
        params["series_ticker"] = series_ticker
    data = await _pub_get(f"{PUBLIC_BASE}/markets", params=params)
    if not isinstance(data, dict):
        return [], ""
    return data.get("markets", []) or [], data.get("cursor", "")


async def fetch_market(ticker: str) -> dict | None:
    data = await _pub_get(f"{PUBLIC_BASE}/markets/{ticker}")
    if not isinstance(data, dict):
        return None
    return data.get("market", data)


async def fetch_all_open_markets(max_pages: int = 10) -> list:
    out: list = []
    cursor = ""
    for _ in range(max_pages):
        m, cursor = await fetch_markets(status="open", limit=1000, cursor=cursor)
        if not m:
            break
        out.extend(m)
        if not cursor:
            break
        await asyncio.sleep(0.25)
    return out


async def fetch_recent_trades(limit: int = 1000) -> list:
    data = await _pub_get(f"{PUBLIC_BASE}/markets/trades", params={"limit": limit})
    if not isinstance(data, dict):
        return []
    return data.get("trades", []) or []


async def fetch_events(
    status: str = "open", limit: int = 200, cursor: str = ""
) -> tuple[list, str]:
    params: dict = {"limit": min(limit, 200)}
    if status:
        params["status"] = status
    if cursor:
        params["cursor"] = cursor
    data = await _pub_get(f"{PUBLIC_BASE}/events", params=params)
    if not isinstance(data, dict):
        return [], ""
    return data.get("events", []) or [], data.get("cursor", "")


_series_cache: dict[str, dict] = {}


async def fetch_series(series_ticker: str) -> dict | None:
    if series_ticker in _series_cache:
        return _series_cache[series_ticker]
    data = await _pub_get(f"{PUBLIC_BASE}/series/{series_ticker}")
    if not isinstance(data, dict):
        return None
    s = data.get("series", data)
    if len(_series_cache) < 5000:
        _series_cache[series_ticker] = s
    return s



_WEB_HOSTS = {
    "production": "kalshi.com",
    "demo": "demo.kalshi.co",
}


def _slugify(text: str) -> str:
    """Reproduce Kalshi's series-title → URL-slug transform.

    Verified against a live URL: the series title "Bitcoin price Above/below"
    becomes "bitcoin-price-abovebelow" — lowercase, spaces collapse to '-',
    every other non-alphanumeric is dropped (so "Above/below" → "abovebelow").
    """
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def _event_from_ticker(ticker: str) -> str:
    """Market ticker → event ticker (drop the trailing strike segment).

    Kalshi markets are `{EVENT}-{STRIKE}` and events are `{SERIES}-{REST}`,
    so the event is everything up to the last hyphen *iff* there are at
    least three segments. A two-segment ticker is already an event ticker.
    """
    parts = (ticker or "").split("-")
    if len(parts) >= 3:
        return "-".join(parts[:-1])
    return ticker or ""


async def web_market_url(
    *, event_ticker: str = "", ticker: str = "", env: str = "production",
) -> str:
    """Build the kalshi.com (or demo.kalshi.co) browser URL for a market.

    Deep-links straight to the event when the series' URL slug resolves
    (`/markets/{series}/{slug}/{event}`); otherwise it degrades to the
    series page (`/markets/{series}`), which Kalshi redirects to its
    canonical slug. Returns "" only when there's no ticker to work from.

    Series metadata is read from the public (production) data API, so the
    slug is identical regardless of env — only the host differs.
    """
    event = (event_ticker or "").strip() or _event_from_ticker(ticker)
    base = event or (ticker or "").strip()
    if not base:
        return ""
    series_l = base.split("-")[0].lower()
    host = _WEB_HOSTS.get(env, "kalshi.com")

    slug = ""
    try:
        s = await fetch_series(base.split("-")[0])
        if s:
            slug = _slugify(str(s.get("title", "")))
    except Exception:
        slug = ""

    if slug and event:
        return f"https://{host}/markets/{series_l}/{slug}/{event.lower()}"
    if slug:
        return f"https://{host}/markets/{series_l}/{slug}"
    return f"https://{host}/markets/{series_l}"




async def _signed_request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
) -> Any:
    assert path.startswith("/")
    signed_path = f"{PATH_PREFIX}{path}"
    method = method.upper()
    last_exc: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        headers = sign_headers(method, signed_path)
        client = await _get_signed_client()
        try:
            resp = await client.request(
                method, signed_path, headers=headers, json=json, params=params
            )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF * attempt)
                continue
            raise

        if resp.status_code == 429:
            wait = float(resp.headers.get("retry-after", 2.0))
            await asyncio.sleep(min(wait, 10))
            continue

        if 500 <= resp.status_code < 600 and attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF * attempt)
            continue

        try:
            body = resp.json()
        except Exception:
            body = resp.text

        if resp.status_code >= 400:
            raise KalshiAPIError(resp.status_code, body)
        return body

    if last_exc:
        raise last_exc
    raise RuntimeError("exhausted retries without response")


async def get_balance() -> dict:
    return await _signed_request("GET", "/portfolio/balance")


async def get_positions(
    limit: int = 200, *, settlement_status: str | None = None,
    paginate: bool = True,
) -> list[dict]:
    """Fetch the user's market_positions from Kalshi.

    Defaults to NO `settlement_status` filter so we get every position
    Kalshi knows about (the API's default is "all"). The reconciler
    then filters by non-zero qty client-side. If the user has more
    than `limit` positions, we follow the response's `cursor` until
    Kalshi stops sending one.
    """
    out: list[dict] = []
    cursor: Optional[str] = None
    pages = 0
    while True:
        params: dict = {"limit": int(limit)}
        if settlement_status:
            params["settlement_status"] = settlement_status
        if cursor:
            params["cursor"] = cursor
        data = await _signed_request(
            "GET", "/portfolio/positions", params=params,
        )
        if isinstance(data, dict):
            out.extend(data.get("market_positions", []) or [])
            cursor = data.get("cursor") or None
        else:
            out.extend(data or [])
            cursor = None
        pages += 1
        if not paginate or not cursor or pages >= 25:
            break
    return out


async def get_settled_positions(limit: int = 200) -> list[dict]:
    """Settled positions — used by the resolution reconciler to detect
    markets that closed in our favour without a tracker DB hit."""
    try:
        data = await _signed_request(
            "GET",
            "/portfolio/positions",
            params={"limit": limit, "settlement_status": "settled"},
        )
    except KalshiAPIError:
        return []
    if isinstance(data, dict):
        return data.get("market_positions", []) or []
    return data or []


async def get_order(order_id: str) -> dict:
    return await _signed_request("GET", f"/portfolio/orders/{order_id}")


async def get_fills_for_order(order_id: str, limit: int = 200) -> list[dict]:
    """List all fills for a single order — authoritative per-order count
    and cost. Use this to recover from any over/under-counting in the
    order/positions endpoints."""
    out: list[dict] = []
    cursor: Optional[str] = None
    pages = 0
    while True:
        params: dict = {"order_id": order_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        try:
            data = await _signed_request("GET", "/portfolio/fills", params=params)
        except KalshiAPIError as e:
            if e.status == 404:
                return []
            raise
        chunk = (data.get("fills") if isinstance(data, dict) else data) or []
        out.extend(chunk)
        cursor = data.get("cursor") if isinstance(data, dict) else None
        pages += 1
        if not cursor or pages >= 5:
            break
    return out


async def get_fills_since(after_ts_unix: int, limit: int = 200) -> list[dict]:
    """All fills since a unix timestamp (paginated, max 5 pages)."""
    out: list[dict] = []
    cursor: Optional[str] = None
    pages = 0
    while True:
        params: dict = {
            "min_ts": int(after_ts_unix),
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor
        try:
            data = await _signed_request("GET", "/portfolio/fills", params=params)
        except KalshiAPIError:
            return out
        chunk = (data.get("fills") if isinstance(data, dict) else data) or []
        out.extend(chunk)
        cursor = data.get("cursor") if isinstance(data, dict) else None
        pages += 1
        if not cursor or pages >= 5:
            break
    return out


def _normalize_orderbook(raw: Any) -> dict:
    """Normalize any Kalshi orderbook shape into integer-cents levels:
        {'yes': [[cents:int, size:float], ...], 'no': [...]}

    Kalshi's elections API returns the book under `orderbook_fp` with keys
    `yes_dollars`/`no_dollars` and DOLLAR-string prices (e.g. "0.3800"),
    while the legacy `orderbook` uses `yes`/`no` with integer cents. The
    rest of the bot (`_best_cross_price_cents`) expects cents `yes`/`no`,
    so normalize here — otherwise limit-cross pricing silently no-ops."""
    if not isinstance(raw, dict):
        return {"yes": [], "no": []}
    book = raw.get("orderbook") or raw.get("orderbook_fp") or raw
    out: dict = {"yes": [], "no": []}
    for side in ("yes", "no"):
        levels = book.get(side)
        is_dollars = levels is None
        if is_dollars:
            levels = book.get(f"{side}_dollars") or []
        for lvl in levels or []:
            try:
                price = int(round(float(lvl[0]) * 100)) if is_dollars else int(lvl[0])
                size = float(lvl[1]) if len(lvl) > 1 else 0.0
                out[side].append([price, size])
            except (TypeError, ValueError, IndexError):
                continue
    return out


async def get_orderbook(ticker: str) -> dict:
    """Authenticated orderbook (best-effort; falls back to public),
    normalized to {'yes': [[cents, size], ...], 'no': [...]}."""
    try:
        book = _normalize_orderbook(await _signed_request("GET", f"/markets/{ticker}/orderbook"))
        if book["yes"] or book["no"]:
            return book
    except Exception:
        pass
    return _normalize_orderbook(await _pub_get(f"{PUBLIC_BASE}/markets/{ticker}/orderbook"))


async def place_limit_order(
    *,
    ticker: str,
    side: str,
    action: str,
    count: int,
    price_cents: int,
    client_order_id: Optional[str] = None,
) -> dict:
    side = side.lower()
    action = action.lower()
    if side not in ("yes", "no"):
        raise ValueError(f"side must be yes|no, got {side}")
    if action not in ("buy", "sell"):
        raise ValueError(f"action must be buy|sell, got {action}")
    if not (1 <= price_cents <= 99):
        raise ValueError(f"price_cents must be 1..99, got {price_cents}")
    if count <= 0:
        raise ValueError(f"count must be positive, got {count}")

    body: dict = {
        "ticker": ticker,
        "client_order_id": client_order_id or str(uuid.uuid4()),
        "side": side,
        "action": action,
        "type": "limit",
        "count": int(count),
    }
    if side == "yes":
        body["yes_price"] = int(price_cents)
    else:
        body["no_price"] = int(price_cents)
    return await _signed_request("POST", "/portfolio/orders", json=body)


async def cancel_order(order_id: str) -> dict:
    return await _signed_request("DELETE", f"/portfolio/orders/{order_id}")
