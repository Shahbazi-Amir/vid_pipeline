# Media Transcript Pipeline

A deployable, auditable pipeline for Persian transcription from video or audio.
The Python core is independent of GitHub Actions and can be called from the CLI,
the existing API/worker, or a future UI.

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

# Existing public/private Release asset (exact tag + exact asset name)
export VID_PIPELINE_RELEASE_TOKEN='...'  # omit for public assets
vid-pipeline run-github-release owner/media audio-v1 \
  --asset-name speech.flac --no-editorial
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

Every full run also builds an API-free `review/chatgpt/` handoff with source,
raw/machine transcripts, available quality/speaker data, a reusable preservation
prompt, and a lossless chunk manifest. It remains outside the lean success artifact.

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
