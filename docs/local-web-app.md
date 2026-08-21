# Local Web App

The local operations console is a Streamlit front end over the existing FastAPI + Redis/RQ + Worker pipeline. It does not bypass the production processing core.

## What the UI supports

- Upload one or many audio/video files.
- Submit one or many public HTTP/HTTPS media URLs.
- Submit one or many GitHub Release assets using `owner/repo | tag | asset` rows.
- Queue many jobs and execute them concurrently when more than one RQ worker is running.
- Live job table with status, progress, current stage, input-media duration and execution time.
- Detailed stage timeline: ingest, audio normalization, primary ASR, targeted retry, cleanup, quality scoring, quality gate and rendering.
- In-page transcript preview.
- Browser download of text/Markdown/timecoded/JSON artifacts.
- `review_required` jobs show the machine draft instead of pretending a low-quality transcript is final.
- Cancel active jobs and retry failed/cancelled/review-required jobs.

## Start locally

```bash
cp .env.example .env
# Optional: set VID_PIPELINE_API_TOKEN and VID_PIPELINE_GITHUB_TOKEN in .env
VID_PIPELINE_WORKER_REPLICAS=2 bash scripts/local_web.sh
```

Open:

- Web app: `http://localhost:8501`
- API: `http://localhost:8000`

The first worker run provisions the integrity-pinned `large-v3-turbo` model into the shared `model-cache` Docker volume. Model installation is protected by a cross-process file lock so parallel cold workers do not download/extract the same artifact simultaneously.

## Parallelism

Each RQ `SimpleWorker` handles one transcription at a time and keeps its Whisper model resident between jobs. Real parallel execution therefore comes from multiple worker containers:

```bash
docker compose up --build --scale worker=3
```

or set `VID_PIPELINE_WORKER_REPLICAS=3` before running `scripts/local_web.sh`.

Each worker loads its own in-memory Whisper model. Increase worker count only when CPU/GPU and RAM/VRAM are sufficient. All workers share Redis, PostgreSQL, media storage and the on-disk model artifact cache.

## URL and GitHub Release inputs

URL jobs are materialized by the worker through the existing SSRF-protected source adapter. The worker image includes `yt-dlp` so supported web media can be fetched in Docker.

For private GitHub Release assets, set:

```bash
VID_PIPELINE_GITHUB_TOKEN=...
```

The token is passed only to workers and is not written to transcript provenance.

## Timing fields

Jobs expose:

- `created_at`: accepted by API
- `started_at`: worker began materialization
- `completed_at`: terminal time
- queue wait / execution / total duration (derived by UI)
- `input_duration_seconds`: media/audio duration after normalization
- `output_duration_seconds`: last transcript segment timestamp
- `stage_timings`: normalization, primary ASR, targeted retry and cleanup measurements
- `stage_history`: timestamped coarse-grained stage transitions

These fields are operational telemetry, not transcript confidence.

## Review boundary

This UI intentionally stops at a trustworthy base transcript. A passing transcript is downloadable; a failing quality gate remains `review_required` and exposes the machine draft plus evidence. Deep AI/human review should be added as a separate auditable phase rather than silently rewriting base ASR output.
