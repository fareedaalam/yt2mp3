"""Lightweight Flask web UI over the existing yt2mp3 core logic.

This module is a thin interface layer, exactly like cli.py: it validates
requests, calls the same downloader/audio/timestamps/filenames functions
the CLI uses, and returns results to the browser. No download/convert
business logic lives here.
"""

from __future__ import annotations

import argparse
import shutil
import webbrowser
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_file

from .audio import check_dependencies, convert
from .downloader import download_best_audio, fetch_info, make_temp_dir
from .exceptions import Yt2Mp3Error
from .filenames import build_filename, resolve_unique_path
from .timestamps import format_timestamp, parse_timestamp, validate_range

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_OUTPUT_DIR = "./downloads"

# Friendly quality presets -> the existing 0-10 libmp3lame VBR scale
# (0 = highest quality). Kept out of the browser UI on purpose.
_QUALITY_PRESETS = {"best": 0, "high": 3, "medium": 6}
_BITRATES = {"128k", "192k", "256k", "320k"}

_ERROR_STATUS = {
    "DependencyError": 500,
    "VideoUnavailableError": 404,
    "AgeRestrictedError": 403,
}


def create_app(output_dir: Optional[str] = None) -> Flask:
    app = Flask(__name__)
    app.config["OUTPUT_DIR"] = Path(output_dir or DEFAULT_OUTPUT_DIR).resolve()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/info")
    def api_info():
        url = (request.get_json(silent=True) or {}).get("url", "")
        try:
            info = fetch_info(url)
        except Yt2Mp3Error as exc:
            return _error_response(exc)

        return jsonify(
            {
                "title": info.title,
                "uploader": info.uploader or "Unknown",
                "duration": info.duration,
                "duration_formatted": (
                    format_timestamp(info.duration) if info.duration is not None else None
                ),
                "thumbnail_url": info.thumbnail_url,
            }
        )

    @app.post("/api/download")
    def api_download():
        payload = request.get_json(silent=True) or {}
        url = payload.get("url", "")
        output_format = (payload.get("format") or "mp3").lower()
        quality_preset = (payload.get("quality") or "best").lower()
        bitrate = (payload.get("bitrate") or "auto").lower()
        start_raw = payload.get("start") or None
        end_raw = payload.get("end") or None

        try:
            if output_format not in ("mp3", "wav"):
                raise Yt2Mp3Error(f"Unsupported format: '{output_format}'.")

            start = parse_timestamp(start_raw) if start_raw else None
            end = parse_timestamp(end_raw) if end_raw else None
            validate_range(start, end)

            quality = _QUALITY_PRESETS.get(quality_preset, _QUALITY_PRESETS["best"])
            resolved_bitrate = bitrate if bitrate in _BITRATES else None
            if resolved_bitrate:
                resolved_bitrate = resolved_bitrate.upper()

            check_dependencies()

            temp_dir = make_temp_dir()
            try:
                source_path, info = download_best_audio(url, temp_dir)

                output_dir: Path = app.config["OUTPUT_DIR"]
                filename = build_filename(info.title, output_format, start, end)
                output_path = resolve_unique_path(output_dir, filename)

                convert(
                    source_path,
                    output_path,
                    output_format=output_format,
                    video_info=info,
                    start=start,
                    end=end,
                    quality=quality,
                    bitrate=resolved_bitrate if output_format == "mp3" else None,
                )
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Yt2Mp3Error as exc:
            return _error_response(exc)
        except Exception as exc:  # noqa: BLE001 - keep tracebacks out of the browser
            app.logger.exception("Unexpected error handling download request")
            return jsonify({"error": "An unexpected error occurred. Check server logs."}), 500

        mimetype = "audio/mpeg" if output_format == "mp3" else "audio/wav"
        return send_file(
            output_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=output_path.name,
        )

    return app


def _error_response(exc: Yt2Mp3Error):
    status = _ERROR_STATUS.get(type(exc).__name__, 400)
    return jsonify({"error": str(exc)}), status


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt2mp3-web", description="Run the yt2mp3 web UI.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT_DIR, metavar="DIR",
        help=f"Directory to save downloaded files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser window automatically.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    app = create_app(output_dir=args.output)

    url = f"http://{args.host}:{args.port}"
    print("yt2mp3 web server running at:")
    print(f"  {url}")

    if not args.no_browser:
        webbrowser.open(url)

    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
