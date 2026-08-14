# Media Transcript Pipeline

A deployable, auditable pipeline for Persian transcription from video or audio.
The Python core is independent of GitHub Actions and can be called from the CLI,
the existing API/worker, or a future UI.

It also provides an independent Video to Audio delivery exporter for local files
and video URLs. Delivery audio is never routed through ASR normalization.

## Supported inputs

- Video file or upload
- Video URL
- Video staged as a GitHub Release asset
- Audio file or upload (`mp3`, `wav`, `m4a`, `aac`, `flac`, `ogg`, `opus`, and
  other formats decodable by the installed FFmpeg)
- Audio URL
- Audio staged as a public or private GitHub Release asset

Extensions are discovery hints only. The worker rejects empty, corrupt, missing,
or undecodable media by probing the real streams with FFprobe.

## Architecture

```text
File / URL / GitHub Release
→ discovery and ingest
→ media validation
→ shared 16 kHz mono WAV normalization
→ ASR and timestamps
→ optional diarization
→ content-preserving normalization
→ base transcript and quality checks
→ optional explicit semantic/human review
→ final artifacts
```

Video and audio have different ingestion paths, but both enter the same shared
normalization, ASR, diarization, validation, review, and rendering code. GitHub
Actions only orchestrates this core.

## Install and run locally

Python 3.10+, FFmpeg, and FFprobe are required for worker execution.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'

# Video URL
vid-pipeline run-url 'https://example.com/video.mp4' --no-editorial

# Audio file
vid-pipeline run-file './speech.m4a' --audio-profile safe --no-editorial
```

## Video to audio delivery export

Export a local video or URL to `mp3`, `wav`, `m4a`, `flac`, or `opus`:

```bash
vid-pipeline extract-audio './interview.mp4' --format mp3 --bitrate 192k
vid-pipeline extract-audio 'https://example.com/video' \
  --format m4a --output './interview.m4a'
```

The exporter validates the video and selected audio stream with FFprobe,
preserves stereo and normal sample rates by default, stream-copies compatible
codecs, validates duration and decodability, and refuses to overwrite unless
`--overwrite` is supplied. This is separate from the 16 kHz mono WAV created for
transcription. See [Video to audio export](docs/video-to-audio.md).

`run-folder` discovers mixed audio/video directories. Stable job IDs and atomic
state writes make reruns resumable. Existing normalized media is validated before
reuse; `--force` explicitly rebuilds requested stages.

## GitHub Actions and Release inputs

The lightweight client can upload one local audio/video file to a private draft
Release, dispatch the manual worker, validate the result, and remove the temporary
asset after success:

```bash
pip install -e '.[client]'
export VID_PIPELINE_GITHUB_TOKEN='...'
export VID_PIPELINE_GITHUB_REPO='owner/repository'

vid-pipeline github-submit-file './speech.mp3' \
  --wait --download --delete-remote-after-success

vid-pipeline github-run-url 'https://example.com/audio.ogg' --wait --download
```

The token is read from the environment and never written to provenance or logs.
GitHub workflows are manual-only for expensive media processing, use bounded
timeouts, upload short-lived artifacts, and do not run paid semantic models.

## Output contract

Each run is written below `outputs/<job-id>/`. The canonical base delivery is:

```text
delivery/transcript.md
delivery/transcript.txt
delivery/transcript.timestamped.md
```

Auditable internal files include the original source metadata, normalized audio,
raw ASR segments, machine text, provenance, quality reports, review package, and
`result.json`. Runtime output is ignored by Git and must be stored as an artifact
or in external storage.

If a reviewed transcript is imported, the canonical reviewed source is
`review/timestamped/<id>.md`; Markdown and plain-text derivatives must be rendered
from it. The reviewed timestamp sequence must equal the base timestamp sequence.

## Review boundary

Base transcription is not semantic review. Regex cleanup or deterministic text
normalization is never labelled as AI review or a final reviewed transcript.
Semantic/human review is explicit and controlled. No OpenAI API, GitHub Models,
Copilot, or other paid LLM is invoked automatically.

See:

- [Audio input and normalization](docs/audio-input.md)
- [Video to audio export](docs/video-to-audio.md)
- [Deployment](docs/deployment.md)
- [Online API and worker](docs/online-execution.md)
- [Human review](docs/human-review.md)
- [Accuracy review](docs/accuracy-review.md)

## Docker

The API image is a lightweight control plane; the worker image contains FFmpeg
and worker dependencies. Models are cached at runtime rather than baked into the
image.

```bash
cp .env.example .env
docker compose up --build
```

## Development checks

```bash
pytest -q
ruff check .
python -m compileall -q src tests scripts
docker build -t vid-pipeline:local .
```

The repository intentionally contains no historical production transcripts,
collection manifests, raw media, or semantic-review staging payloads.
