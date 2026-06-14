"""Tests for service._iso_utc — the SQLite-naive-UTC -> ISO 8601 fixer.

Regression guard for the "every Started/Resolved time shows up 7 hours
off in PT" bug: SQLite writes naive "YYYY-MM-DD HH:MM:SS" which JS parses
as LOCAL time. _iso_utc must tag a real Z onto naive strings while leaving
already-zoned strings untouched.
"""
from __future__ import annotations

import service


def test_naive_sqlite_string_gets_t_and_z():
    assert service._iso_utc("2024-01-02 03:04:05") == "2024-01-02T03:04:05Z"


def test_already_zulu_is_left_alone():
    assert service._iso_utc("2024-01-02T03:04:05Z") == "2024-01-02T03:04:05Z"


def test_offset_timestamp_is_not_double_tagged():
    s = "2024-01-02T03:04:05+00:00"
    assert service._iso_utc(s) == s


def test_empty_and_none_pass_through():
    assert service._iso_utc("") == ""
    assert service._iso_utc(None) is None
