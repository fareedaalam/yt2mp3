# yt2mp3

A cross-platform tool that downloads a YouTube video's audio and converts
it to MP3 or WAV, with optional time-range trimming. Use it from your
browser via a lightweight local web UI, or from the command line.

> **Use responsibly.** Only download content you own, that is licensed for
> download, or that you otherwise have the right to download (e.g. under
> YouTube's terms, Creative Commons content, or your own uploads). This
> tool does not implement, and will not implement, any authentication
> bypass, DRM circumvention, CAPTCHA bypass, or other mechanism to get
> around YouTube's access restrictions.

## What it does

- Downloads the best available audio stream via [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Converts it to **MP3** (VBR quality or explicit bitrate) or **WAV** (PCM) using FFmpeg
- Trims to a precise `--start`/`--end` time range, or downloads the full audio
- Names the output file after the video title (sanitized, collision-safe)
- Embeds metadata (title/artist/album/track) and cover art on MP3 output
- Shows progress and clear, non-crashy error messages
- Works on macOS, Linux, and Windows

## Requirements

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (`ffmpeg` and `ffprobe` on your `PATH`)
- `yt-dlp` (installed automatically as a dependency)

## Installation

```bash
git clone <this-repo-url> yt2mp3
cd yt2mp3
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

This installs the `yt2mp3` and `yt2mp3-web` commands into your environment.

### FFmpeg installation

**macOS (Homebrew):**

```bash
brew install ffmpeg
```

**Ubuntu / Debian:**

```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows (winget):**

```bash
winget install ffmpeg
```

**Windows (Chocolatey):**

```bash
choco install ffmpeg
```

After installing, verify FFmpeg is on your `PATH`:

```bash
ffmpeg -version
ffprobe -version
```

`yt2mp3` checks for `ffmpeg`/`ffprobe` at startup and prints these exact
instructions if either is missing, instead of crashing.

## Usage (Web UI)

Start the web server:

```bash
yt2mp3-web
```

```text
yt2mp3 web server running at:
  http://127.0.0.1:8000
```

Your browser opens automatically (pass `--no-browser` to skip that). From
there:

1. Paste a YouTube URL — the title, channel, duration, and thumbnail are
   fetched and shown automatically.
2. Choose **Format** (MP3/WAV), **Quality** (Best/High/Medium), **Bitrate**
   (Auto or a fixed MP3 bitrate), and an optional **Start**/**End** time
   range.
3. Click **Download Audio**. The converted file is saved to the server's
   downloads directory and offered to your browser as a direct download.

### Options

| Flag              | Meaning                                                  |
| ----------------- | --------------------------------------------------------- |
| `--host`          | Host to bind (default `127.0.0.1`)                        |
| `--port`          | Port to bind (default `8000`)                              |
| `--output`        | Directory to save downloaded files (default `./downloads`) |
| `--no-browser`    | Don't open a browser window automatically                  |

```bash
yt2mp3-web --port 5000 --output ~/Music/yt2mp3
```

Equivalent to `python -m yt2mp3.web`.

## Usage (CLI, advanced)

The command-line interface remains available and uses the exact same
downloader/converter logic as the web UI.

```bash
yt2mp3 <youtube-url> [options]
```

Run `yt2mp3 --help` at any time for the full option list.

### Basic (MP3, full audio, default quality)

```bash
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID"
```

### MP3 examples

```bash
# Default MP3
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3

# Highest quality MP3 (VBR quality 0)
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3 --quality 0

# Explicit constant bitrate
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format mp3 --bitrate 320K
```

> Note: choosing `--bitrate 320K` re-encodes the best available source
> audio at 320 kbps. It does **not** add information that wasn't in the
> source — it just avoids further lossy quality loss from a lower bitrate.

### WAV examples

```bash
# Default WAV (lossless PCM, source sample rate/channels)
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format wav

# Specific sample rate and channel count
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --format wav --sample-rate 48000 --channels 2
```

### Time-range examples

```bash
# Trim to a specific range
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --start 01:30 --end 04:45

# From a start time to the end of the video
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --start 02:00

# From the beginning up to a given time
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --end 03:00
```

Accepted time formats: `90` (seconds), `01:30` (MM:SS), `01:02:30` (HH:MM:SS).

### Output directory

```bash
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --output ./downloads
```

### Combined options

```bash
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" \
  --format mp3 \
  --quality 0 \
  --start 01:20 \
  --end 05:40 \
  --output ./downloads
```

### Info / dry run

Fetch and display video metadata without downloading anything:

```bash
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --info
```

### Verbose / debugging

```bash
yt2mp3 "https://www.youtube.com/watch?v=VIDEO_ID" --verbose
```

Shows detailed yt-dlp/FFmpeg output and full tracebacks on failure, and
preserves temporary files if conversion fails.

## Quality options

| Flag                | Meaning                                                              |
| -------------------- | --------------------------------------------------------------------- |
| `--quality 0`–`10`   | MP3 VBR quality (libmp3lame `-q:a`), `0` = highest, `10` = lowest. Default `0`. |
| `--bitrate 320K`     | Explicit constant MP3 bitrate; overrides `--quality` when set.       |
| `--sample-rate 48000`| Output sample rate in Hz (MP3 or WAV). Source rate kept if omitted.   |
| `--channels 2`       | Output channel count. Source channel count kept if omitted.          |

`yt2mp3` always downloads the best available source audio stream first,
then converts/trims from that source — it never re-encodes an
already-lossy download a second time unnecessarily.

## Output naming

Files are named after the video title, sanitized for cross-platform
filesystems:

```text
downloads/
    My Video Title.mp3
```

With a time range:

```text
downloads/
    My Video Title [01-30 to 04-45].mp3
```

If a file with the same name already exists, `yt2mp3` automatically adds
a numeric suffix rather than overwriting it:

```text
My Video Title (1).mp3
My Video Title (2).mp3
```

## Troubleshooting

**`Required dependency not found on PATH: ffmpeg and ffprobe`**
Install FFmpeg (see above) and make sure it's on your `PATH`.

**`This video is private and cannot be downloaded.` / `...is unavailable`**
The video isn't accessible to download; there's no bypass for this.

**`This video is age-restricted and requires authentication...`**
`yt2mp3` intentionally does not attempt to authenticate as you or bypass
age gates.

**`Network error while contacting YouTube: ...`**
Check your internet connection and try again; transient YouTube-side
issues can also cause this.

**`Invalid timestamp` / `End time must be after start time`**
Double check your `--start`/`--end` values use `SS`, `MM:SS`, or
`HH:MM:SS` format, and that the end time is after the start time.

**Conversion fails partway through**
Re-run with `--verbose` to see the full FFmpeg output and to keep the
temporary source file for inspection.

## Project structure

```text
yt2mp3/
├── yt2mp3/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py             # CLI interface: argument parsing, orchestration, progress, exit codes
│   ├── web.py              # Web UI interface: Flask app, routes, orchestration
│   ├── downloader.py       # core: yt-dlp integration (URL validation, info, download)
│   ├── audio.py             # core: FFmpeg conversion, trimming, metadata, dependency checks
│   ├── timestamps.py        # core: timestamp parsing/validation/formatting
│   ├── filenames.py         # core: title -> safe, unique filename
│   ├── exceptions.py        # typed errors -> exit codes / HTTP status
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── style.css
│       └── app.js
│
├── tests/
│   ├── test_timestamps.py
│   ├── test_filenames.py
│   ├── test_cli.py
│   └── test_web.py
│
├── downloads/
├── requirements.txt
├── pyproject.toml
├── README.md
└── .gitignore
```

Both `cli.py` and `web.py` are thin interfaces over the same core modules
(`downloader.py`, `audio.py`, `timestamps.py`, `filenames.py`) — neither
contains its own download/conversion logic.

## Development / testing

```bash
pip install -e ".[dev]"
pytest
```

Tests mock `yt-dlp` and FFmpeg calls — no network access or real
downloads are required to run the test suite.

## Legal / copyright note

This tool is provided for downloading audio from content you are
authorized to download (your own uploads, explicitly licensed content,
public-domain content, etc.). You are responsible for complying with
YouTube's Terms of Service and applicable copyright law in your
jurisdiction. Do not use this tool to infringe on others' copyrights.
