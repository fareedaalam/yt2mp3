"""FFmpeg-driven audio conversion: trimming, format conversion, metadata.

All FFmpeg/ffprobe invocations use subprocess with explicit argument
lists (never shell strings), so nothing derived from video titles or
URLs is ever interpreted by a shell.
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .downloader import VideoInfo
from .exceptions import ConversionError, DependencyError

# yt-dlp/FFmpeg-style quality scale: 0 = best, 9/10 = worst.
# Maps to libmp3lame's -q:a VBR scale (also 0 = best .. 9 = worst).
_MP3_QUALITY_MIN = 0
_MP3_QUALITY_MAX = 10


def check_dependencies() -> None:
    """Verify ffmpeg and ffprobe are installed and runnable.

    Raises DependencyError with an actionable install message if not.
    """
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise DependencyError(_missing_deps_message(missing))

    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run(
                [tool, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=15,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise DependencyError(
                f"'{tool}' was found but could not be executed: {exc}\n\n"
                + _install_instructions()
            ) from exc


def _missing_deps_message(missing: list[str]) -> str:
    names = " and ".join(missing)
    return f"Required dependency not found on PATH: {names}.\n\n" + _install_instructions()


def _install_instructions() -> str:
    return (
        "Install FFmpeg (provides ffmpeg and ffprobe):\n"
        "  macOS (Homebrew):       brew install ffmpeg\n"
        "  Ubuntu/Debian:          sudo apt update && sudo apt install ffmpeg\n"
        "  Windows (winget):       winget install ffmpeg\n"
        "  Windows (Chocolatey):   choco install ffmpeg\n"
        "After installing, make sure 'ffmpeg' and 'ffprobe' are on your PATH."
    )


def get_duration_seconds(path: Path) -> Optional[float]:
    """Return the duration of a media file in seconds, via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
        return float(result.stdout.decode().strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def _mp3_quality_to_ffmpeg_qscale(quality: int) -> str:
    if not (_MP3_QUALITY_MIN <= quality <= _MP3_QUALITY_MAX):
        raise ConversionError(
            f"--quality must be between {_MP3_QUALITY_MIN} and {_MP3_QUALITY_MAX} "
            f"(0 = highest quality), got {quality}."
        )
    return str(quality)


def _download_thumbnail(url: str, dest: Path, timeout: int = 15) -> Optional[Path]:
    """Best-effort thumbnail download. Never raises; returns None on failure."""
    if not url:
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "yt2mp3/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = response.read()
        dest.write_bytes(data)
        return dest
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def convert(
    source_path: Path,
    output_path: Path,
    *,
    output_format: str,
    video_info: VideoInfo,
    start: Optional[float] = None,
    end: Optional[float] = None,
    quality: Optional[int] = None,
    bitrate: Optional[str] = None,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
    embed_thumbnail: bool = True,
    verbose: bool = False,
) -> Path:
    """Convert `source_path` to `output_path` in one FFmpeg pass, applying
    trimming, quality/bitrate, sample rate/channels, and metadata as
    requested. Returns the final output path.
    """
    output_format = output_format.lower()
    if output_format not in ("mp3", "wav"):
        raise ConversionError(f"Unsupported output format: '{output_format}'.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    thumbnail_path: Optional[Path] = None
    cmd: list[str] = ["ffmpeg", "-y", "-hide_banner"]
    if not verbose:
        cmd += ["-loglevel", "error"]

    # Accurate trim: seek input as close as possible, then apply a precise
    # output-side trim so the result matches the requested range exactly
    # rather than snapping to the nearest keyframe.
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(source_path)]

    if end is not None:
        duration = end - (start or 0.0)
        cmd += ["-t", f"{duration:.3f}"]

    map_args = ["-map", "0:a"]

    if output_format == "mp3" and embed_thumbnail and video_info.thumbnail_url:
        thumbnail_path = source_path.parent / f"{video_info.id}.thumb.jpg"
        thumbnail_path = _download_thumbnail(video_info.thumbnail_url, thumbnail_path)
        if thumbnail_path is not None:
            cmd += ["-i", str(thumbnail_path)]
            map_args += ["-map", "1:v"]

    cmd += map_args

    if output_format == "mp3":
        cmd += ["-c:a", "libmp3lame"]
        if bitrate:
            cmd += ["-b:a", bitrate]
        else:
            q = _mp3_quality_to_ffmpeg_qscale(quality if quality is not None else 0)
            cmd += ["-q:a", q]
        if thumbnail_path is not None:
            cmd += ["-c:v", "mjpeg", "-id3v2_version", "3", "-disposition:v", "attached_pic"]
    else:  # wav
        cmd += ["-c:a", "pcm_s16le"]

    if sample_rate:
        cmd += ["-ar", str(sample_rate)]
    if channels:
        cmd += ["-ac", str(channels)]

    if output_format == "mp3":
        cmd += _metadata_args(video_info)

    cmd += [str(output_path)]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=3600,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise ConversionError(f"FFmpeg conversion failed:\n{stderr.strip()}") from exc
    except (subprocess.SubprocessError, OSError) as exc:
        raise ConversionError(f"FFmpeg conversion failed: {exc}") from exc
    finally:
        if thumbnail_path is not None and thumbnail_path.exists():
            thumbnail_path.unlink(missing_ok=True)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ConversionError("FFmpeg reported success but produced no output.")

    return output_path


def _metadata_args(video_info: VideoInfo) -> list[str]:
    args = ["-metadata", f"title={video_info.title}"]
    if video_info.uploader:
        args += ["-metadata", f"artist={video_info.uploader}"]
    if video_info.album:
        args += ["-metadata", f"album={video_info.album}"]
    if video_info.track:
        args += ["-metadata", f"track={video_info.track}"]
    return args
