#!/usr/bin/env bash
set -euo pipefail
workers="${VID_PIPELINE_WORKER_REPLICAS:-2}"
if ! [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
  echo "VID_PIPELINE_WORKER_REPLICAS must be a positive integer" >&2
  exit 2
fi
exec docker compose up --build --scale worker="$workers"
