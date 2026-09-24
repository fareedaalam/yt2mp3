import pytest

from yt2mp3.exceptions import TimestampError
from yt2mp3.timestamps import (
    format_timestamp,
    format_timestamp_for_filename,
    parse_timestamp,
    validate_range,
)


def test_plain_seconds():
    assert parse_timestamp("90") == 90.0


def test_mm_ss():
    assert parse_timestamp("01:30") == 90.0


def test_hh_mm_ss():
    assert parse_timestamp("01:02:30") == 3750.0


def test_zero_seconds():
    assert parse_timestamp("0") == 0.0


@pytest.mark.parametrize(
    "value",
    ["", "abc", "1:2:3:4", "-5", "01:99", "99:99:99:99", "1:2:x"],
)
def test_invalid_timestamp_raises(value):
    with pytest.raises(TimestampError):
        parse_timestamp(value)


def test_invalid_minutes_or_seconds_over_59():
    with pytest.raises(TimestampError):
        parse_timestamp("01:75")


def test_validate_range_end_before_start():
    with pytest.raises(TimestampError):
        validate_range(90.0, 30.0)


def test_validate_range_end_equal_start():
    with pytest.raises(TimestampError):
        validate_range(90.0, 90.0)


def test_validate_range_negative_start():
    with pytest.raises(TimestampError):
        validate_range(-1.0, 10.0)


def test_validate_range_ok():
    validate_range(30.0, 90.0)  # should not raise


def test_validate_range_only_start():
    validate_range(30.0, None)  # should not raise


def test_validate_range_only_end():
    validate_range(None, 90.0)  # should not raise


def test_validate_range_none():
    validate_range(None, None)  # should not raise


def test_format_timestamp_under_hour():
    assert format_timestamp(90) == "01:30"


def test_format_timestamp_over_hour():
    assert format_timestamp(3750) == "01:02:30"


def test_format_timestamp_for_filename():
    assert format_timestamp_for_filename(90) == "01-30"
