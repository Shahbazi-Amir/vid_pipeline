#!/usr/bin/env bash
set -u

REPO="${VID_PIPELINE_BATCH_REPO:-Shahbazi-Amir/vid_pipeline}"
INPUT="${VID_PIPELINE_BATCH_INPUT:-./input_videos/tehran_}"
OUT="${VID_PIPELINE_BATCH_OUTPUT:-./outputs/uni_tehran}"
START="${VID_PIPELINE_BATCH_START:-1}"
END="${VID_PIPELINE_BATCH_END:-38}"
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

mkdir -p \
  "$OUT/md" "$OUT/timestamped" "$OUT/txt" \
  "$OUT/review/md" "$OUT/review/timestamped" "$OUT/review/txt"

failed_processing=()
failed_review=()
missing_input=()

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

run_review() {
  local n="$1"
  local attempt
  if review_complete "$n"; then
    return 0
  fi
  for ((attempt=1; attempt<=MAX_REVIEW_ATTEMPTS; attempt++)); do
    echo "→ Review $n (attempt $attempt/$MAX_REVIEW_ATTEMPTS)"
    if vid-review ai-collection "$OUT" "$n" && review_complete "$n"; then
      echo "✓ Review $n complete"
      return 0
    fi
    if (( attempt < MAX_REVIEW_ATTEMPTS )); then
      echo "⚠ Review $n failed; retrying in 30 seconds..."
      sleep 30
    fi
  done
  echo "✗ Review $n failed after $MAX_REVIEW_ATTEMPTS attempts; continuing batch."
  failed_review+=("$n")
  return 1
}

for ((n=START; n<=END; n++)); do
  echo
  echo "========== VIDEO $n / $END =========="

  if base_complete "$n"; then
    if review_complete "$n"; then
      echo "✓ Video $n + review already complete — skipping"
    else
      echo "✓ Transcript $n exists; only review is missing"
      run_review "$n" || true
    fi
    continue
  fi

  FILE="$(find_video "$n" || true)"
  if [[ -z "$FILE" ]]; then
    echo "⚠ Video $n input not found — continuing"
    missing_input+=("$n")
    continue
  fi

  echo "Input: $FILE"
  success=false
  for ((attempt=1; attempt<=MAX_PROCESS_ATTEMPTS; attempt++)); do
    echo "→ Processing video $n (attempt $attempt/$MAX_PROCESS_ATTEMPTS)"
    vid-pipeline github-submit-file \
      "$FILE" \
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
      --delete-result-artifact-after-save || true

    if base_complete "$n"; then
      success=true
      break
    fi
  done

  if [[ "$success" != true ]]; then
    echo "✗ Video $n processing failed; NOT retrying indefinitely. Continuing to next video."
    failed_processing+=("$n")
    continue
  fi

  echo "✓ Transcript $n complete"
  run_review "$n" || true
done

echo
echo "===================================="
echo "BATCH FINISHED"
echo "===================================="
echo "Processing failures: ${failed_processing[*]:-none}"
echo "Review failures:     ${failed_review[*]:-none}"
echo "Missing inputs:      ${missing_input[*]:-none}"
echo "No git commit or push was performed by this script."
