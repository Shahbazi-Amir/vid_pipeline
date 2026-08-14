# Video to audio export

`extract-audio` creates a user-facing audio file from a local video or an
HTTP(S) video URL. It is independent from transcription preprocessing:

- delivery export preserves the selected stream's channel count and, where the
  target codec permits it, its sample rate;
- transcription continues to use the separate 16 kHz mono PCM WAV normalizer
  documented in [audio-input.md](audio-input.md).

## Usage

FFmpeg and FFprobe must be available in `PATH`. URL input also requires the
download extra (`pip install -e '.[download]'`).

```bash
# Default output: ./interview.mp3
vid-pipeline extract-audio ./interview.mp4 --format mp3

# Explicit output and MP3 bitrate
vid-pipeline extract-audio ./interview.mp4 \
  --format mp3 --bitrate 320k --output ./delivery/interview.mp3

# URL input; the existing yt-dlp source resolver downloads to an isolated temp directory
vid-pipeline extract-audio 'https://example.com/video' --format m4a

# Select the second audio stream (zero-based audio-stream ordinal)
vid-pipeline extract-audio ./multilingual.mkv \
  --format flac --audio-stream 1
```

Supported outputs are `mp3`, `wav`, `m4a`, `flac`, and `opus`. MP3 accepts
`128k`, `192k`, `256k`, or `320k`; transcoded MP3 defaults to `192k`. A bitrate
option is intentionally not exposed for the other formats in this version.

For a local input, the default output is beside the source with the requested
extension. For a URL, it is written in the current directory using the
downloaded title. `--output` overrides this. Existing output is rejected unless
`--overwrite` is present, and the output extension must match `--format`.

## Stream and codec behavior

FFprobe must find a real motion-video stream and at least one audio stream. The
marked default audio stream is selected; if none is marked, the first audio
stream is used. `--audio-stream` provides explicit zero-based selection.

Compatible audio is copied without re-encoding when no transformation was
requested: MP3 to MP3, AAC/ALAC to M4A, FLAC to FLAC, Opus to Opus, and
compatible PCM to WAV. Other combinations transcode directly from the source:

| Output | Encoder | Default bitrate when transcoding |
|---|---|---:|
| MP3 | `libmp3lame` | `192k` |
| WAV | `pcm_s16le` | lossless PCM |
| M4A | `aac` | `192k` |
| FLAC | `flac` | lossless |
| Opus | `libopus` | `128k` |

There is no lossy intermediate file. Stereo is not downmixed and 16 kHz is not
forced. Codec constraints may still determine the encoded sample rate (for
example, Opus is represented at 48 kHz).

## Validation and failures

Exports are written to a unique temporary file and atomically moved into place
only after validation. Validation requires a non-empty file, exactly one audio
stream, a codec compatible with the requested format, preserved channel count,
successful full decode, and a plausible duration. Duration tolerance is the
greater of two seconds or five percent to allow encoder delay and container
rounding.

Missing tools, missing/corrupt/non-video input, video without audio, invalid
format or bitrate, bad stream selection, download failure, output collision,
transcode failure, and output-validation failure produce actionable errors.
Temporary URL downloads and failed export files are cleaned automatically.

Deterministic CI generates small local video fixtures with FFmpeg. Third-party
live URLs are deliberately not part of required CI because extractor and site
changes would make the suite flaky; URL source resolution is covered through a
controlled downloader integration test.
