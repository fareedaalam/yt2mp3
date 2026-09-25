"""yt-dlp integration: URL validation, metadata retrieval, and downloading.

Uses the official yt-dlp Python API (rather than shelling out to the
`yt-dlp` executable) for URL handling, info extraction, and downloading
the best available audio stream.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .exceptions import (
    AgeRestrictedError,
    DownloadError,
    InvalidURLError,
    NetworkError,
    VideoUnavailableError,
)

_YOUTUBE_URL_RE = re.compile(
    r"^https?://(www\.|m\.|music\.)?(youtube\.com/(watch\?.*v=|shorts/|live/)|youtu\.be/)",
    re.IGNORECASE,
)

ProgressCallback = Callable[[dict], None]


@dataclass
class VideoInfo:
    """Subset of yt-dlp metadata relevant to yt2mp3."""

    id: str
    title: str
    uploader: Optional[str]
    duration: Optional[float]  # seconds
    album: Optional[str]
    track: Optional[int]
    thumbnail_url: Optional[str]
    webpage_url: str


def validate_url(url: str) -> None:
    """Raise InvalidURLError if `url` is not a recognizable YouTube URL."""
    if not url or not isinstance(url, str):
        raise InvalidURLError("No URL provided.")
    if not _YOUTUBE_URL_RE.match(url.strip()):
        raise InvalidURLError(
            f"'{url}' does not look like a valid YouTube URL. "
            "Expected something like https://www.youtube.com/watch?v=... "
            "or https://youtu.be/..."
        )


def _translate_download_error(exc: Exception) -> Exception:
    """Map a yt-dlp exception to one of our domain-specific exceptions."""
    message = str(exc)
    lower = message.lower()

    if "private video" in lower:
        return VideoUnavailableError("This video is private and cannot be downloaded.")
    if "video unavailable" in lower or "has been removed" in lower:
        return VideoUnavailableError("This video is unavailable (it may have been removed).")
    if "sign in to confirm your age" in lower or "age-restricted" in lower or "age restricted" in lower:
        return AgeRestrictedError(
            "This video is age-restricted and requires authentication that "
            "yt2mp3 does not attempt to bypass."
        )
    if "unable to download webpage" in lower or "urlopen error" in lower or "timed out" in lower:
        return NetworkError(f"Network error while contacting YouTube: {message}")
    if "unsupported url" in lower:
        return InvalidURLError(f"Unsupported URL: {message}")

    return DownloadError(f"Download failed: {message}")


def fetch_info(url: str, verbose: bool = False) -> VideoInfo:
    """Retrieve video metadata without downloading any media."""
    validate_url(url)

    ydl_opts = {
        "quiet": not verbose,
        "no_warnings": not verbose,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise _translate_download_error(exc) from exc

    if info is None:
        raise VideoUnavailableError("Could not retrieve information for this video.")

    return _video_info_from_dict(info)


def _video_info_from_dict(info: dict) -> VideoInfo:
    thumbnails = info.get("thumbnails") or []
    thumbnail_url = info.get("thumbnail")
    if not thumbnail_url and thumbnails:
        thumbnail_url = thumbnails[-1].get("url")

    return VideoInfo(
        id=info.get("id", ""),
        title=info.get("title") or "Untitled",
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        album=info.get("album"),
        track=info.get("track_number"),
        thumbnail_url=thumbnail_url,
        webpage_url=info.get("webpage_url") or info.get("original_url") or "",
    )


_NO_END_TRIM_SENTINEL = 1e9  # "to the end of the video"


def download_best_audio(
    url: str,
    dest_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
    verbose: bool = False,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> tuple[Path, VideoInfo]:
    """Download the best available audio-only stream for `url` into
    `dest_dir`, without any further post-processing/re-encoding.

    When `start`/`end` are given, only that time range is fetched (via
    yt-dlp's section-download support) instead of the full audio stream,
    which avoids downloading the whole video just to keep a short clip
    of it. yt-dlp performs the cut with ffmpeg to within a few
    milliseconds of the requested boundaries, which is accurate enough
    for audio trimming; the caller should treat the returned file as
    already trimmed and not trim it again.

    Returns the path to the downloaded file and the parsed VideoInfo.
    """
    validate_url(url)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(dest_dir / "%(id)s.source.%(ext)s")

    hooks = [progress_callback] if progress_callback else []

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "progress_hooks": hooks,
        "retries": 3,
        "fragment_retries": 3,
    }

    if start is not None or end is not None:
        range_start = start if start is not None else 0.0
        range_end = end if end is not None else _NO_END_TRIM_SENTINEL
        ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
            None, [(range_start, range_end)]
        )
        ydl_opts["force_keyframes_at_cuts"] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))
    except yt_dlp.utils.DownloadError as exc:
        raise _translate_download_error(exc) from exc
    except KeyboardInterrupt:
        raise
    except OSError as exc:
        raise DownloadError(f"Failed to write downloaded audio: {exc}") from exc

    if not downloaded_path.exists():
        raise DownloadError("Download reported success but no output file was found.")

    return downloaded_path, _video_info_from_dict(info)


def make_temp_dir() -> Path:
    """Create a fresh temporary directory for intermediate downloads."""
    return Path(tempfile.mkdtemp(prefix="yt2mp3-"))
