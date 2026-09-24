from pathlib import Path

from yt2mp3.filenames import build_filename, resolve_unique_path, sanitize_filename


def test_sanitize_removes_illegal_characters():
    assert sanitize_filename('My "Video": <Title>?*|') == "My Video Title"


def test_sanitize_removes_path_separators():
    assert sanitize_filename("a/b\\c") == "abc"


def test_sanitize_collapses_whitespace():
    assert sanitize_filename("My    Video   Title") == "My Video Title"


def test_sanitize_strips_trailing_dots_and_spaces():
    assert sanitize_filename("Title...   ") == "Title"


def test_sanitize_empty_uses_fallback():
    assert sanitize_filename("") == "untitled"
    assert sanitize_filename("???") == "untitled"


def test_sanitize_windows_reserved_name():
    assert sanitize_filename("CON") == "_CON"


def test_build_filename_no_range():
    assert build_filename("My Video Title", "mp3") == "My Video Title.mp3"


def test_build_filename_with_range():
    name = build_filename("My Video Title", "mp3", start=90.0, end=285.0)
    assert name == "My Video Title [01-30 to 04-45].mp3"


def test_resolve_unique_path_no_conflict(tmp_path: Path):
    result = resolve_unique_path(tmp_path, "song.mp3")
    assert result == tmp_path / "song.mp3"


def test_resolve_unique_path_with_conflict(tmp_path: Path):
    (tmp_path / "song.mp3").write_bytes(b"x")
    result = resolve_unique_path(tmp_path, "song.mp3")
    assert result == tmp_path / "song (1).mp3"


def test_resolve_unique_path_multiple_conflicts(tmp_path: Path):
    (tmp_path / "song.mp3").write_bytes(b"x")
    (tmp_path / "song (1).mp3").write_bytes(b"x")
    result = resolve_unique_path(tmp_path, "song.mp3")
    assert result == tmp_path / "song (2).mp3"
