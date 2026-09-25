from pathlib import Path
from unittest.mock import patch

import pytest

from yt2mp3.downloader import VideoInfo
from yt2mp3.web import create_app


def make_video_info(**overrides) -> VideoInfo:
    defaults = dict(
        id="abc123",
        title="My Test Video",
        uploader="Test Channel",
        duration=300.0,
        album=None,
        track=None,
        thumbnail_url="https://example.com/thumb.jpg",
        webpage_url="https://www.youtube.com/watch?v=abc123",
    )
    defaults.update(overrides)
    return VideoInfo(**defaults)


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=str(tmp_path / "downloads"))
    app.testing = True
    return app.test_client()


def test_index_page_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"yt2mp3" in res.data


def test_api_info_invalid_url(client):
    res = client.post("/api/info", json={"url": "not-a-url"})
    assert res.status_code == 400
    assert "error" in res.get_json()


@patch("yt2mp3.web.fetch_info")
def test_api_info_success(mock_fetch_info, client):
    mock_fetch_info.return_value = make_video_info()

    res = client.post("/api/info", json={"url": "https://youtu.be/abc123"})

    assert res.status_code == 200
    data = res.get_json()
    assert data["title"] == "My Test Video"
    assert data["uploader"] == "Test Channel"
    assert data["duration_formatted"] == "05:00"


def test_api_download_invalid_timestamp(client):
    res = client.post(
        "/api/download",
        json={"url": "https://youtu.be/abc123", "start": "not-a-time"},
    )
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_api_download_end_before_start(client):
    res = client.post(
        "/api/download",
        json={"url": "https://youtu.be/abc123", "start": "01:00", "end": "00:30"},
    )
    assert res.status_code == 400


@patch("yt2mp3.web.check_dependencies")
def test_api_download_dependency_error(mock_check_deps, client):
    from yt2mp3.exceptions import DependencyError

    mock_check_deps.side_effect = DependencyError("ffmpeg not found")

    res = client.post("/api/download", json={"url": "https://youtu.be/abc123"})

    assert res.status_code == 500
    assert "ffmpeg not found" in res.get_json()["error"]


@patch("yt2mp3.web.convert")
@patch("yt2mp3.web.download_best_audio")
@patch("yt2mp3.web.make_temp_dir")
@patch("yt2mp3.web.check_dependencies")
def test_api_download_full_pipeline_success(
    mock_check_deps, mock_make_temp_dir, mock_download, mock_convert, client, tmp_path
):
    info = make_video_info()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    mock_make_temp_dir.return_value = tmp_dir

    source_file = tmp_dir / "abc123.source.webm"
    source_file.write_bytes(b"fake-audio")
    mock_download.return_value = (source_file, info)

    def fake_convert(source_path, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-mp3-data")
        return output_path

    mock_convert.side_effect = fake_convert

    res = client.post(
        "/api/download",
        json={"url": "https://youtu.be/abc123", "format": "mp3"},
    )

    assert res.status_code == 200
    assert res.mimetype == "audio/mpeg"
    assert "My Test Video.mp3" in res.headers["Content-Disposition"]
    mock_convert.assert_called_once()
