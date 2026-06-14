"""Tests for orderbook normalization (kalshi_api._normalize_orderbook).

Regression for a real bug found via the live demo account: Kalshi's
elections API returns the book under `orderbook_fp` with dollar-string
prices, which `_best_cross_price_cents` (expecting cents `yes`/`no`)
couldn't read — so limit-cross order pricing silently fell back.
"""
from __future__ import annotations

import kalshi_api
import trader


def test_normalize_fp_dollars_to_cents():
    raw = {"orderbook_fp": {"no_dollars": [["0.3800", "12.00"]], "yes_dollars": []}}
    assert kalshi_api._normalize_orderbook(raw) == {"yes": [], "no": [[38, 12.0]]}


def test_normalize_legacy_cents():
    raw = {"orderbook": {"yes": [[30, 10]], "no": [[45, 5], [40, 3]]}}
    book = kalshi_api._normalize_orderbook(raw)
    assert book["yes"] == [[30, 10.0]]
    assert book["no"] == [[45, 5.0], [40, 3.0]]


def test_normalize_garbage_is_empty():
    assert kalshi_api._normalize_orderbook(None) == {"yes": [], "no": []}
    assert kalshi_api._normalize_orderbook({}) == {"yes": [], "no": []}


def test_fp_orderbook_restores_cross_pricing():
    raw = {"orderbook_fp": {"no_dollars": [["0.38", "12"]], "yes_dollars": []}}
    book = kalshi_api._normalize_orderbook(raw)
    assert trader._best_cross_price_cents(book, "yes") == 62
