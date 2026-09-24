"""Parsing, validation, and formatting of user-supplied timestamps.

Accepted input forms:
    "90"          -> 90 seconds
    "01:30"       -> 90 seconds  (MM:SS)
    "01:02:30"    -> 3750 seconds (HH:MM:SS)
"""

from __future__ import annotations

import re

from .exceptions import TimestampError

_PLAIN_SECONDS_RE = re.compile(r"^\d+(\.\d+)?$")
_TIME_PARTS_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?(\.\d+)?$")


def parse_timestamp(value: str) -> float:
    """Parse a timestamp string into seconds (float).

    Supports plain seconds ("90"), MM:SS ("01:30"), and HH:MM:SS
    ("01:02:30"). Raises TimestampError on anything else.
    """
    if value is None:
        raise TimestampError("Timestamp is missing.")

    text = value.strip()
    if not text:
        raise TimestampError("Timestamp cannot be empty.")

    if _PLAIN_SECONDS_RE.match(text):
        seconds = float(text)
    elif _TIME_PARTS_RE.match(text):
        parts = text.split(":")
        try:
            parts_f = [float(p) for p in parts]
        except ValueError as exc:
            raise TimestampError(f"Invalid timestamp: '{value}'.") from exc

        if len(parts_f) == 2:
            minutes, secs = parts_f
            hours = 0.0
        elif len(parts_f) == 3:
            hours, minutes, secs = parts_f
        else:  # pragma: no cover - regex prevents this
            raise TimestampError(f"Invalid timestamp: '{value}'.")

        if minutes >= 60 or secs >= 60:
            raise TimestampError(
                f"Invalid timestamp: '{value}'. Minutes and seconds must be < 60."
            )

        seconds = hours * 3600 + minutes * 60 + secs
    else:
        raise TimestampError(
            f"Invalid timestamp: '{value}'. Expected formats: SS, MM:SS, or HH:MM:SS."
        )

    if seconds < 0:
        raise TimestampError(f"Timestamp cannot be negative: '{value}'.")

    return seconds


def validate_range(start: float | None, end: float | None) -> None:
    """Validate a (start, end) pair of already-parsed seconds."""
    if start is not None and start < 0:
        raise TimestampError("Start time must be >= 0.")
    if end is not None and end < 0:
        raise TimestampError("End time must be >= 0.")
    if start is not None and end is not None and end <= start:
        raise TimestampError(
            f"End time ({format_timestamp(end)}) must be after "
            f"start time ({format_timestamp(start)})."
        )


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS (or MM:SS if under an hour)."""
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp_for_filename(seconds: float) -> str:
    """Format seconds as HH-MM-SS / MM-SS for safe use in filenames."""
    return format_timestamp(seconds).replace(":", "-")
