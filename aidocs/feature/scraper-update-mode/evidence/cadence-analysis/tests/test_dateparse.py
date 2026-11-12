import datetime

from dateparse import parse_iso_date


def test_date_only():
    assert parse_iso_date("2024-01-15") == datetime.date(2024, 1, 15)


def test_datetime_with_offset():
    assert parse_iso_date("2024-01-15T10:30:00+00:00") == datetime.date(2024, 1, 15)


def test_datetime_with_z():
    assert parse_iso_date("2024-01-15T10:30:00Z") == datetime.date(2024, 1, 15)


def test_microseconds_and_offset():
    assert parse_iso_date("2026-06-27T17:18:14.598236+00:00") == datetime.date(2026, 6, 27)


def test_none_and_empty():
    assert parse_iso_date(None) is None
    assert parse_iso_date("") is None
    assert parse_iso_date("   ") is None


def test_garbage():
    assert parse_iso_date("not-a-date") is None
