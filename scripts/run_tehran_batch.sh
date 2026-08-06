#!/usr/bin/env bash
set -u

REPO="${VID_PIPELINE_BATCH_REPO:-Shahbazi-Amir/vid_pipeline}"
INPUT="${VID_PIPELINE_BATCH_INPUT:-./input_videos/tehran_}"
OUT="${VID_PIPELINE_BATCH_OUTPUT:-./outputs/uni_tehran}"
START="${VID_PIPELINE_BATCH_START:-1}"
END="${VID_PIPELINE_BATCH_END:-38}"
PARALLEL="${VID_PIPELINE_BATCH_PARALLEL:-3}"
MAX_PROCESS_ATTEMPTS="${VID_PIPELINE_BATCH_PROCESS_ATTEMPTS:-1}"
MAX_REVIEW_ATTEMPTS="${VID_PIPELINE_BATCH_REVIEW_ATTEMPTS:-3}"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ -z "${VID_PIPELINE_GITHUB_TOKEN:-}" ]]; then
  read -r -s -p "GitHub PAT: " VID_PIPELINE_GITHUB_TOKEN
  export VID_PIPELINE_GITHUB_TOKEN
  echo
fi

if [[ -z "${VID_PIPELINE_GITHUB_TOKEN:-}" ]]; then
  echo "ERROR: GitHub token is missing." >&2
  exit 2
fi

is_positive_integer() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

if ! is_positive_integer "$START" || ! is_positive_integer "$END" || (( START > END )); then
  echo "ERROR: invalid batch range: START=$START END=$END" >&2
  exit 2
fi
if ! is_positive_integer "$PARALLEL"; then
  echo "ERROR: VID_PIPELINE_BATCH_PARALLEL must be a positive integer." >&2
  exit 2
fi
if ! is_positive_integer "$MAX_PROCESS_ATTEMPTS" || ! is_positive_integer "$MAX_REVIEW_ATTEMPTS"; then
  echo "ERROR: retry counts must be positive integers." >&2
  exit 2
fi

mkdir -p \
  "$OUT/md" "$OUT/timestamped" "$OUT/txt" \
  "$OUT/review/md" "$OUT/review/timestamped" "$OUT/review/txt"

RUN_ID="$(date +%Y%m%d-%H%M%S)-$$"
STATUS_DIR=".vid_pipeline/tehran-batch/$RUN_ID"
LOG_DIR=".vid_pipeline/tehran-batch-logs/$RUN_ID"
mkdir -p "$STATUS_DIR" "$LOG_DIR"

base_complete() {
  local n="$1"
  [[ -s "$OUT/md/$n.md" && -s "$OUT/timestamped/$n.md" && -s "$OUT/txt/$n.txt" ]]
}

review_complete() {
  local n="$1"
  [[ -s "$OUT/review/md/$n.md" && -s "$OUT/review/timestamped/$n.md" && -s "$OUT/review/txt/$n.txt" ]]
}

find_video() {
  local n="$1"
  local candidates=("$INPUT/$n."*)
  if (( ${#candidates[@]} == 1 )) && [[ -f "${candidates[0]}" ]]; then
    printf '%s\n' "${candidates[0]}"
    return 0
  fi
  if (( ${#candidates[@]} > 1 )); then
    printf 'ERROR: multiple input files start with %s.:\n' "$n" >&2
    printf '  %s\n' "${candidates[@]}" >&2
  fi
  return 1
}

mark_status() {
  local kind="$1"
  local n="$2"
  : > "$STATUS_DIR/$kind.$n"
}

CURRENT_CHILD=""

stop_worker() {
  if [[ -n "${CURRENT_CHILD:-}" ]]; then
    kill "$CURRENT_CHILD" 2>/dev/null || true
    wait "$CURRENT_CHILD" 2>/dev/null || true
  fi
  exit 130
}

run_review() {
  local n="$1"
  local attempt rc
  if review_complete "$n"; then
    return 0
  fi
  for ((attempt=1; attempt<=MAX_REVIEW_ATTEMPTS; attempt++)); do
    echo "→ Review $n (attempt $attempt/$MAX_REVIEW_ATTEMPTS)"
    vid-review ai-collection "$OUT" "$n" &
    CURRENT_CHILD=$!
    rc=0
    wait "$CURRENT_CHILD" || rc=$?
    CURRENT_CHILD=""
    if (( rc == 0 )) && review_complete "$n"; then
      echo "✓ Review $n complete"
      return 0
    fi
    if (( attempt < MAX_REVIEW_ATTEMPTS )); then
      echo "⚠ Review $n failed; retrying in 30 seconds..."
      sleep 30
    fi
  done
  echo "✗ Review $n failed after $MAX_REVIEW_ATTEMPTS attempts."
  return 1
}

process_one() {
  local n="$1"
  local file="${2:-}"
  local attempt
  local success=false

  echo "========== VIDEO $n / $END =========="

  if base_complete "$n"; then
    if review_complete "$n"; then
      echo "✓ Video $n + review already complete — skipping"
      printf 'complete\n' > "$STATUS_DIR/done.$n"
      return 0
    fi
    echo "✓ Transcript $n exists; only review is missing"
    if run_review "$n"; then
      printf 'complete\n' > "$STATUS_DIR/done.$n"
      return 0
    fi
    mark_status review_failure "$n"
    printf 'review_failed\n' > "$STATUS_DIR/done.$n"
    return 0
  fi

  echo "Input: $file"
  for ((attempt=1; attempt<=MAX_PROCESS_ATTEMPTS; attempt++)); do
    echo "→ Processing video $n (attempt $attempt/$MAX_PROCESS_ATTEMPTS)"
    vid-pipeline github-submit-file \
      "$file" \
      --repo "$REPO" \
      --ref main \
      --profile balanced \
      --language fa \
      --no-editorial \
      --diarize \
      --diarization-required \
      --num-speakers 2 \
      --speaker-role-mode host-teacher \
      --keep-debug-artifacts \
      --yes \
      --collection-output-root "$OUT" \
      --result-number "$n" \
      --delete-remote-after-success \
      --delete-result-artifact-after-save &
    CURRENT_CHILD=$!
    wait "$CURRENT_CHILD" || true
    CURRENT_CHILD=""

    if base_complete "$n"; then
      success=true
      break
    fi
  done

  if [[ "$success" != true ]]; then
    echo "✗ Video $n processing failed; NOT retrying indefinitely."
    mark_status processing_failure "$n"
    printf 'processing_failed\n' > "$STATUS_DIR/done.$n"
    return 0
  fi

  echo "✓ Transcript $n complete"
  if run_review "$n"; then
    printf 'complete\n' > "$STATUS_DIR/done.$n"
  else
    mark_status review_failure "$n"
    printf 'review_failed\n' > "$STATUS_DIR/done.$n"
  fi
}

running_jobs() {
  local count
  count="$(jobs -pr | wc -l | tr -d ' ')"
  printf '%s\n' "${count:-0}"
}

announce_finished() {
  local marker n status symbol
  for marker in "$STATUS_DIR"/done.*; do
    [[ -e "$marker" ]] || continue
    n="${marker##*.}"
    status="$(cat "$marker")"
    case "$status" in
      complete) symbol="✓" ;;
      *) symbol="✗" ;;
    esac
    echo "$symbol Worker video $n finished: $status"
    mv "$marker" "$STATUS_DIR/announced.$n"
  done
}

wait_for_slot() {
  while (( $(running_jobs) >= PARALLEL )); do
    announce_finished
    sleep 2
  done
  announce_finished
}

stop_children() {
  local pids
  echo
  echo "Stopping active batch workers..."
  pids="$(jobs -pr)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    wait $pids 2>/dev/null || true
  fi
  echo "Stopped. Completed outputs are preserved and the next run will resume from them."
  exit 130
}
trap stop_children INT TERM

collect_numbers() {
  local kind="$1"
  local marker n result=""
  for marker in "$STATUS_DIR"/"$kind".*; do
    [[ -e "$marker" ]] || continue
    n="${marker##*.}"
    result="$result $n"
  done
  if [[ -z "$result" ]]; then
    printf 'none\n'
  else
    printf '%s\n' "${result# }"
  fi
}

echo "===================================="
echo "TEHRAN PARALLEL BATCH"
echo "Range: $START..$END"
echo "Parallel workers: $PARALLEL"
echo "Logs: $LOG_DIR"
echo "===================================="

for ((n=START; n<=END; n++)); do
  if base_complete "$n" && review_complete "$n"; then
    echo "✓ Video $n + review already complete — skipping"
    continue
  fi

  FILE=""
  if ! base_complete "$n"; then
    FILE="$(find_video "$n" || true)"
    if [[ -z "$FILE" ]]; then
      echo "⚠ Video $n input not found — continuing"
      mark_status missing_input "$n"
      continue
    fi
  fi

  wait_for_slot
  (
    trap stop_worker INT TERM
    process_one "$n" "$FILE" > "$LOG_DIR/$n.log" 2>&1
  ) &
  echo "→ Started video $n in parallel (PID $!); log: $LOG_DIR/$n.log"
done

while (( $(running_jobs) > 0 )); do
  announce_finished
  sleep 2
done
wait || true
announce_finished

echo
echo "===================================="
echo "BATCH FINISHED"
echo "===================================="
echo "Processing failures: $(collect_numbers processing_failure)"
echo "Review failures:     $(collect_numbers review_failure)"
echo "Missing inputs:      $(collect_numbers missing_input)"
echo "Per-video logs:      $LOG_DIR"
echo "No git commit or push was performed by this script."
