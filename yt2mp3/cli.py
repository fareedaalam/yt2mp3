"""Command-line interface for yt2mp3."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn, Optional

from . import __version__
from .audio import check_dependencies, convert, get_duration_seconds
from .downloader import download_best_audio, fetch_info, make_temp_dir, validate_url
from .exceptions import InterruptedByUserError, TimestampError, Yt2Mp3Error
from .filenames import build_filename, resolve_unique_path
from .timestamps import format_timestamp, parse_timestamp, validate_range

DEFAULT_FORMAT = "mp3"
DEFAULT_QUALITY = 0
DEFAULT_OUTPUT_DIR = "./downloads"

_EPILOG = """\
Examples:
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID"
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format wav
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3 --quality 0
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --start 01:30 --end 04:45
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3 --bitrate 320K
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --output ./downloads
  yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --info

Time formats accepted for --start/--end: SS, MM:SS, HH:MM:SS (e.g. 90, 01:30, 01:02:30)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt2mp3",
        description="Download and convert a YouTube video's audio to MP3 or WAV.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--format",
        choices=["mp3", "wav"],
        default=DEFAULT_FORMAT,
        help=f"Output audio format (default: {DEFAULT_FORMAT})",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=None,
        metavar="0-10",
        help="MP3 VBR quality, 0 = highest, 10 = lowest (default: 0). Ignored for WAV.",
    )
    parser.add_argument(
        "--bitrate",
        default=None,
        metavar="RATE",
        help="Explicit MP3 bitrate, e.g. 320K. Overrides --quality.",
    )
    parser.add_argument(
        "--start",
        default=None,
        metavar="TIME",
        help="Start time (SS, MM:SS, or HH:MM:SS)",
    )
    parser.add_argument(
        "--end",
        default=None,
        metavar="TIME",
        help="End time (SS, MM:SS, or HH:MM:SS)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        metavar="HZ",
        help="Output sample rate in Hz (e.g. 48000). WAV/MP3; source rate kept if omitted.",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=None,
        metavar="N",
        help="Number of output audio channels (e.g. 2). Source channel count kept if omitted.",
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="Skip embedding cover art in MP3 output.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show video info (title, uploader, duration) without downloading.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress and full error output for debugging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"yt2mp3 {__version__}",
    )
    return parser


class ProgressBar:
    """A minimal, dependency-free terminal progress bar."""

    def __init__(self, label: str, width: int = 30, stream=sys.stdout):
        self.label = label
        self.width = width
        self.stream = stream
        self._last_pct = -1
        self.stream.write(f"{label}\n")

    def update(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        pct = int(fraction * 100)
        if pct == self._last_pct:
            return
        self._last_pct = pct
        filled = int(self.width * fraction)
        bar = "█" * filled + " " * (self.width - filled)
        self.stream.write(f"\r[{bar}] {pct:3d}%")
        self.stream.flush()

    def finish(self) -> None:
        self.update(1.0)
        self.stream.write("\n")
        self.stream.flush()


def _print(message: str = "") -> None:
    print(message)


def _make_download_progress_hook(bar: ProgressBar):
    def hook(status: dict) -> None:
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = status.get("downloaded_bytes", 0)
            if total:
                bar.update(downloaded / total)
        elif status.get("status") == "finished":
            bar.finish()

    return hook


def _resolve_times(args: argparse.Namespace) -> tuple[Optional[float], Optional[float]]:
    start = parse_timestamp(args.start) if args.start is not None else None
    end = parse_timestamp(args.end) if args.end is not None else None
    validate_range(start, end)
    return start, end


def _print_info(url: str, verbose: bool) -> int:
    info = fetch_info(url, verbose=verbose)
    _print(f"Title:    {info.title}")
    _print(f"Uploader: {info.uploader or 'Unknown'}")
    if info.duration is not None:
        _print(f"Duration: {format_timestamp(info.duration)}")
    else:
        _print("Duration: Unknown")
    _print(f"URL:      {info.webpage_url}")
    return 0


def run(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_url(args.url)
        start, end = _resolve_times(args)

        if args.bitrate is None and args.quality is None:
            args.quality = DEFAULT_QUALITY

        if args.info:
            check_dependencies_soft(verbose=args.verbose)
            return _print_info(args.url, args.verbose)

        check_dependencies()

        _print("Fetching video information...")
        info = fetch_info(args.url, verbose=args.verbose)
        _print(f"Title: {info.title}")
        if info.duration is not None:
            _print(f"Duration: {format_timestamp(info.duration)}")
        _print()

        if start is not None or end is not None:
            range_start = start if start is not None else 0.0
            range_end_display = format_timestamp(end) if end is not None else "end"
            _print(f"Requested range: {format_timestamp(range_start)} -> {range_end_display}")

        temp_dir = make_temp_dir()
        cleanup_temp = not args.verbose
        try:
            _print("Downloading audio...")
            bar = ProgressBar("")
            hook = _make_download_progress_hook(bar)
            source_path, info = download_best_audio(
                args.url, temp_dir, progress_callback=hook, verbose=args.verbose
            )
            _print()

            output_dir = Path(args.output)
            filename = build_filename(info.title, args.format, start, end)
            output_path = resolve_unique_path(output_dir, filename)

            _print(f"Converting to {args.format.upper()}...")
            convert(
                source_path,
                output_path,
                output_format=args.format,
                video_info=info,
                start=start,
                end=end,
                quality=args.quality,
                bitrate=args.bitrate,
                sample_rate=args.sample_rate,
                channels=args.channels,
                embed_thumbnail=not args.no_thumbnail,
                verbose=args.verbose,
            )
            _print()

            if start is not None or end is not None:
                out_duration = get_duration_seconds(output_path)
                if out_duration is not None:
                    _print(f"Output duration: {format_timestamp(out_duration)}")

            _print("Done:")
            _print(str(output_path))
            return 0
        finally:
            if cleanup_temp:
                _cleanup_dir(temp_dir)
            elif args.verbose:
                _print(f"(verbose) Temporary files preserved at: {temp_dir}")

    except KeyboardInterrupt:
        _print("\nCancelled by user.")
        return InterruptedByUserError.exit_code
    except Yt2Mp3Error as exc:
        _print(f"\nError: {exc}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 - last-resort safety net
        _print(f"\nUnexpected error: {exc}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        else:
            _print("Run with --verbose for full details.")
        return 1


def check_dependencies_soft(verbose: bool) -> None:
    """--info only needs yt-dlp, not ffmpeg, but we still validate ffmpeg
    lazily elsewhere; kept as a named hook for clarity/extensibility."""
    return None


def _cleanup_dir(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def main() -> NoReturn:
    sys.exit(run())


if __name__ == "__main__":
    main()
