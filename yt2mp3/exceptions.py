"""Custom exceptions for yt2mp3.

Each exception maps to a distinct, user-facing failure mode so the CLI
layer can print a clear message and return a meaningful exit code
instead of leaking a Python traceback.
"""


class Yt2Mp3Error(Exception):
    """Base class for all yt2mp3 errors."""

    exit_code = 1


class DependencyError(Yt2Mp3Error):
    """A required external dependency (ffmpeg, ffprobe) is missing or broken."""

    exit_code = 2


class InvalidURLError(Yt2Mp3Error):
    """The supplied URL is not a supported/valid YouTube URL."""

    exit_code = 3


class VideoUnavailableError(Yt2Mp3Error):
    """The video is private, deleted, region-locked, or otherwise unavailable."""

    exit_code = 4


class AgeRestrictedError(Yt2Mp3Error):
    """The video requires authentication (age-restricted / members-only)."""

    exit_code = 5


class NetworkError(Yt2Mp3Error):
    """A network failure occurred while talking to YouTube."""

    exit_code = 6


class TimestampError(Yt2Mp3Error):
    """A start/end timestamp is malformed or logically invalid."""

    exit_code = 7


class DownloadError(Yt2Mp3Error):
    """The audio download failed or was interrupted."""

    exit_code = 8


class ConversionError(Yt2Mp3Error):
    """FFmpeg failed to convert/trim the audio."""

    exit_code = 9


class OutputError(Yt2Mp3Error):
    """The destination path could not be written to (disk full, permissions, etc.)."""

    exit_code = 10


class UnsupportedFormatError(Yt2Mp3Error):
    """The requested output format is not supported."""

    exit_code = 11


class InterruptedByUserError(Yt2Mp3Error):
    """The user cancelled the operation (Ctrl+C)."""

    exit_code = 130
