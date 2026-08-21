# Media Transcript Pipeline

A deployable, auditable pipeline for Persian transcription from video or audio.
The Python core is independent of GitHub Actions and is used by the CLI, FastAPI/RQ worker stack, and the local Streamlit web app.

## Supported inputs

- Video/audio file upload
- Public HTTP/HTTPS media URL
- Public or private GitHub Release asset
- Mixed common audio/video formats decodable by the installed FFmpeg

Extensions are discovery hints only. The worker rejects empty, corrupt, missing, or undecodable media by probing the real streams with FFprobe.

## Architecture

```text
Streamlit Web / API / CLI
        ↓
File / URL / GitHub Release
        ↓
FastAPI control plane → PostgreSQL + Redis/RQ
        ↓
One or more Workers
        ↓
source materialization
→ media validation
→ shared 16 kHz mono WAV normalization
→ primary ASR + timestamps
→ targeted retry for suspicious segments only
→ content-preserving cleanup
→ deterministic quality gate
→ completed delivery OR review_required evidence
```

The online Worker and deployable core use the same canonical processing service. GitHub Actions are not required for runtime processing.

## Local Web App

The easiest local end-to-end path is the Streamlit console:

```bash
cp .env.example .env
VID_PIPELINE_WORKER_REPLICAS=2 bash scripts/local_web.sh
```

Then open `http://localhost:8501`.

The UI can:

- upload one or many audio/video files;
- submit multiple URLs;
- submit GitHub Release assets;
- keep multiple jobs queued/running;
- show status, percent, exact processing stage and timestamps;
- show input media duration, queue wait, execution time and total time;
- preview transcript text in the browser;
- download TXT/Markdown/timecoded/JSON outputs;
- show `review_required` machine drafts without falsely marking them final;
- cancel and retry jobs.

Real parallel processing is provided by multiple RQ worker containers:

```bash
docker compose up --build --scale worker=3
```

Each worker keeps its own Whisper model resident in memory, while all workers share the integrity-checked on-disk model cache. Cold model provisioning is cross-process locked so scaled workers do not download/extract the model concurrently.

See [Local Web App](docs/local-web-app.md) for the complete local operations guide.

## Install and run core locally

Python 3.10+, FFmpeg, and FFprobe are required for direct worker/core execution.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'

vid-pipeline run-url 'https://example.com/video.mp4' --no-editorial
vid-pipeline run-file './speech.m4a' --audio-profile safe --no-editorial
```

`run-folder` discovers mixed audio/video directories. Stable job IDs and atomic state writes make reruns resumable. Existing normalized media is validated before reuse; `--force` explicitly rebuilds requested stages.

## Output contract

A successful online run exposes the canonical base delivery:

```text
delivery/transcript.md
delivery/transcript.txt
delivery/transcript.timestamped.md
```

A job that fails the quality gate does **not** create a final delivery. It remains `review_required` and exposes raw/machine transcript evidence, normalized review audio and quality diagnostics.

Auditable internal files include source metadata, normalized audio, raw ASR segments, machine text, quality reports, targeted retry diagnostics and `result.json`.

## Review boundary

Base transcription is not semantic review. Regex cleanup or deterministic text normalization is never labelled as AI review or human verification. AI review and evidence-backed human audio review are separate explicit phases; an AI/LLM cannot produce `human_verified` status.

## Docker services

`compose.yml` includes:

- `web` — Streamlit local UI (`8501`)
- `api` — FastAPI control plane (`8000`)
- `worker` — scalable RQ transcription workers
- `redis` — queue
- `database` — PostgreSQL state

The worker image includes FFmpeg, faster-whisper and `yt-dlp`, so File, URL and GitHub Release jobs use the same Docker processing path.

## Development checks

```bash
pytest -q
ruff check .
python -m compileall -q src tests scripts
```

The repository intentionally contains no historical production transcripts, raw media, or semantic-review staging payloads.
