from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt2mp3.cli import build_parser, run
from yt2mp3.downloader import VideoInfo
from yt2mp3.exceptions import InvalidURLError, TimestampError


def make_video_info(**overrides) -> VideoInfo:
    defaults = dict(
        id="abc123",
        title="My Test Video",
        uploader="Test Channel",
        duration=300.0,
        album=None,
        track=None,
        thumbnail_url=None,
        webpage_url="https://www.youtube.com/watch?v=abc123",
    )
    defaults.update(overrides)
    return VideoInfo(**defaults)


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["https://www.youtube.com/watch?v=abc123"])
    assert args.format == "mp3"
    assert args.quality is None
    assert args.output == "./downloads"
    assert args.start is None
    assert args.end is None


def test_parser_rejects_missing_url():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_rejects_invalid_format():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["https://youtu.be/abc123", "--format", "flac"])


def test_run_invalid_url_returns_error_code(capsys):
    code = run(["not-a-url"])
    assert code == InvalidURLError.exit_code
    captured = capsys.readouterr()
    assert "Error" in captured.out


def test_run_invalid_timestamp_returns_error_code(capsys):
    code = run(["https://youtu.be/abc123", "--start", "not-a-time"])
    assert code == TimestampError.exit_code


def test_run_end_before_start_returns_error_code(capsys):
    code = run(["https://youtu.be/abc123", "--start", "01:00", "--end", "00:30"])
    assert code == TimestampError.exit_code


@patch("yt2mp3.cli.check_dependencies")
@patch("yt2mp3.cli.fetch_info")
def test_run_info_does_not_download(mock_fetch_info, mock_check_deps, capsys):
    mock_fetch_info.return_value = make_video_info()

    code = run(["https://youtu.be/abc123", "--info"])

    assert code == 0
    mock_check_deps.assert_not_called()
    captured = capsys.readouterr()
    assert "My Test Video" in captured.out
    assert "Test Channel" in captured.out


@patch("yt2mp3.cli._cleanup_dir")
@patch("yt2mp3.cli.convert")
@patch("yt2mp3.cli.download_best_audio")
@patch("yt2mp3.cli.make_temp_dir")
@patch("yt2mp3.cli.fetch_info")
@patch("yt2mp3.cli.check_dependencies")
def test_run_full_pipeline_success(
    mock_check_deps,
    mock_fetch_info,
    mock_make_temp_dir,
    mock_download,
    mock_convert,
    mock_cleanup,
    tmp_path: Path,
    capsys,
):
    info = make_video_info()
    mock_fetch_info.return_value = info
    mock_make_temp_dir.return_value = tmp_path / "tmp"
    (tmp_path / "tmp").mkdir()
    source_file = tmp_path / "tmp" / "abc123.source.webm"
    source_file.write_bytes(b"fake-audio")
    mock_download.return_value = (source_file, info)

    output_dir = tmp_path / "downloads"

    def fake_convert(source_path, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mp3-data")
        return output_path

    mock_convert.side_effect = fake_convert

    code = run(
        [
            "https://youtu.be/abc123",
            "--format",
            "mp3",
            "--output",
            str(output_dir),
        ]
    )

    assert code == 0
    mock_check_deps.assert_called_once()
    mock_convert.assert_called_once()
    captured = capsys.readouterr()
    assert "Done:" in captured.out
    assert (output_dir / "My Test Video.mp3").exists()


@patch("yt2mp3.cli.check_dependencies")
def test_run_dependency_error_reports_cleanly(mock_check_deps, capsys):
    from yt2mp3.exceptions import DependencyError

    mock_check_deps.side_effect = DependencyError("ffmpeg not found")

    code = run(["https://youtu.be/abc123"])

    assert code == DependencyError.exit_code
    captured = capsys.readouterr()
    assert "ffmpeg not found" in captured.out
