# Online execution architecture

## Boundaries

The lightweight client only discovers files, computes SHA-256, streams
multipart chunks, resumes interrupted transfers, creates jobs, polls status and
downloads artifacts. It never imports the worker, audio or ASR implementation.

The FastAPI control plane authenticates requests, validates metadata, persists
uploads and jobs, and enqueues work. SQLite is the development default;
`VID_PIPELINE_DATABASE_URL` accepts PostgreSQL URLs for deployment.

The Redis/RQ adapter transports only a job ID. Worker orchestration remains
queue-neutral and can be tested through `InlineJobQueue`. The worker runs
FFmpeg/FFprobe and faster-whisper, renders final files and stores progress in
the database rather than process memory.

## API

```text
GET  /health
POST /v1/uploads
PUT  /v1/uploads/{upload_id}/parts/{part_number}
POST /v1/uploads/{upload_id}/complete
GET  /v1/uploads/{upload_id}
POST /v1/jobs
GET  /v1/jobs
GET  /v1/jobs/{job_id}
POST /v1/jobs/{job_id}/cancel
POST /v1/jobs/{job_id}/retry
GET  /v1/jobs/{job_id}/artifacts
GET  /v1/jobs/{job_id}/artifacts/{artifact_name}
```

Local development receives streaming request bodies and persists numbered
parts. Completion concatenates parts without loading the file into RAM and
checks declared size and SHA-256. S3 deployments use `S3ArtifactStore`
multipart uploads and presigned part URLs.

## Security and lifecycle

The API supports bearer authentication, configurable file-size limits, safe
generated names, media extension and MIME checks, hash verification, bounded
client retries and storage path containment. Tokens are held only in request
headers and are never logged by the client.

Set upload, job and artifact expiration/retention in the deployment scheduler.
The persisted timestamps make cleanup idempotent. Reverse-proxy rate limits and
request timeouts should be enabled in production. URL ingestion is outside the
online upload API; the existing direct `run-url` path validates HTTP(S) schemes.

## Environment variables

All supported settings are listed in `.env.example`. Secrets must be injected
by the deployment platform and must not be committed.
