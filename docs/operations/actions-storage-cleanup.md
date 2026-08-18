# Actions Storage Cleanup Policy

This repository automatically manages GitHub Actions storage so transcription and review jobs do not fill available Actions storage.

## Scope

The cleanup workflow is `.github/workflows/actions-retention.yml`.

It manages only GitHub Actions execution history, Actions artifacts, and Actions caches. It does **not** delete GitHub Release assets or final transcript/review outputs committed under `outputs/`.

## Schedule and triggers

- Scheduled every 6 hours.
- Can be started manually with `workflow_dispatch`.
- Changes to the cleanup workflow itself trigger an immediate cleanup run.

## Retention rules

### Workflow runs

- Active/queued/in-progress runs are always preserved.
- The 30 most recent completed runs are preserved.
- Older completed runs become eligible after 2 hours.
- At most 300 run records are deleted per cleanup execution.

### Actions artifacts

- Artifacts attached to active runs are always preserved.
- The 10 newest live artifacts are preserved.
- Other artifacts become eligible after 6 hours.
- At most 300 artifacts are deleted per cleanup execution.
- GitHub Release assets are outside this cleanup and are never touched.

### Actions caches

- The 8 most recently used caches are preserved.
- Other caches are deleted only after at least 7 days without use.
- At most 50 caches are deleted per cleanup execution.
- This protects frequently reused ASR/model/dependency caches during active transcription batches.

## Protected project data

The cleanup must never remove:

- `outputs/chehelstoun/**`
- `outputs/mizan/**`
- `outputs/ketab-baz/**`
- transcript, accuracy, review, provenance, and delivery files committed to Git
- GitHub Release media archives and manifests
- active workflow runs or their artifacts

## Operational status

Each cleanup execution updates `ops/actions-cleanup/latest-status.json` with the most recent cleanup metrics, including runs/artifacts/caches deleted and bytes freed. This file is operational metadata only and does not contain media or transcript content.

## Failure behavior

Cleanup failures must not cancel or delete active transcription/review work. Failed deletion attempts are recorded in the workflow summary/status so the next scheduled cleanup can retry safely.
