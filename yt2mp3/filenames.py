"""YouTube title -> safe, unique output filenames."""

from __future__ import annotations

import re
from pathlib import Path

# Characters illegal (or awkward) on Windows, macOS, and Linux filesystems.
_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_DOTS_SPACES_RE = re.compile(r"[.\s]+$")

# Reserved device names on Windows (case-insensitive).
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_MAX_STEM_LENGTH = 150  # keep well under filesystem limits even with suffixes


def sanitize_filename(name: str, fallback: str = "untitled") -> str:
    """Turn an arbitrary string into a safe filename stem (no extension)."""
    if not name:
        name = fallback

    cleaned = _ILLEGAL_CHARS_RE.sub("", name)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    cleaned = _TRAILING_DOTS_SPACES_RE.sub("", cleaned)

    if not cleaned:
        cleaned = fallback

    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"

    if len(cleaned) > _MAX_STEM_LENGTH:
        cleaned = cleaned[:_MAX_STEM_LENGTH].rstrip()

    return cleaned


def build_filename(
    title: str,
    extension: str,
    start: float | None = None,
    end: float | None = None,
) -> str:
    """Build a sanitized filename (with extension) from a video title and
    optional time range."""
    from .timestamps import format_timestamp_for_filename  # local import: avoid cycle

    stem = sanitize_filename(title)

    if start is not None and end is not None:
        range_part = (
            f" [{format_timestamp_for_filename(start)} to "
            f"{format_timestamp_for_filename(end)}]"
        )
        # Re-truncate so stem + range tag stays within limits.
        max_stem = _MAX_STEM_LENGTH - len(range_part)
        if max_stem > 0 and len(stem) > max_stem:
            stem = stem[:max_stem].rstrip()
        stem = f"{stem}{range_part}"

    ext = extension.lstrip(".")
    return f"{stem}.{ext}"


def resolve_unique_path(directory: Path, filename: str) -> Path:
    """Return a path in `directory` that does not already exist.

    If `filename` is taken, append " (1)", " (2)", etc. before the
    extension until a free name is found.
    """
    directory = Path(directory)
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix

    counter = 1
    while True:
        candidate = directory / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
