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


def download_best_audio(
    url: str,
    dest_dir: Path,
    progress_callback: Optional[ProgressCallback] = None,
    verbose: bool = False,
) -> tuple[Path, VideoInfo]:
    """Download the best available audio-only stream for `url` into
    `dest_dir`, without any post-processing/re-encoding.

    Returns the path to the downloaded file and the parsed VideoInfo.
    Trimming and format conversion are handled separately (see audio.py)
    so that we always start from the highest quality source stream and
    perform exact, ffmpeg-driven trimming rather than relying solely on
    yt-dlp's keyframe-based section seeking.
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
