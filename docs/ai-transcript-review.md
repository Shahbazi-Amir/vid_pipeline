# AI transcript review

The numbered collection workflow supports an optional, validated LLM review stage after the three base transcript files have been materialized locally.

## Output layout

For result `N`:

```text
<collection-root>/
├── md/N.md
├── timestamped/N.md
├── txt/N.txt
└── review/
    ├── md/N.md
    ├── timestamped/N.md
    └── txt/N.txt
```

The base files remain unchanged and are the source of truth. The reviewed timestamped file is the canonical reviewed representation. The reviewed Markdown and TXT files are rendered mechanically from it, so the three review outputs cannot drift independently.

Consecutive blocks with the same speaker are collapsed only in `review/md` and `review/txt`; timestamps remain one-for-one in `review/timestamped`.

## Automatic execution

When `github-submit-file` is used with `--collection-output-root`, successful collection materialization automatically attempts AI review if all three review environment variables are configured:

```text
VID_PIPELINE_REVIEW_API_KEY
VID_PIPELINE_REVIEW_BASE_URL
VID_PIPELINE_REVIEW_MODEL
```

If none are configured, review is skipped without breaking normal transcript processing. A partially configured review environment is treated as an error instead of silently making an unauthenticated or misrouted request.

A review can also be resumed or run independently:

```bash
vid-review ai-collection ./outputs/uni_tehran 7
```

Use `--force` only when the canonical reviewed timestamped file must be regenerated through the API:

```bash
vid-review ai-collection ./outputs/uni_tehran 7 --force
```

If `review/timestamped/N.md` already exists and validates but one of the derived files is missing, the command rebuilds `review/md/N.md` and `review/txt/N.txt` without paying for another API request.

## Safety and validation

The production prompt is generic: it does not assume a particular person, phrase, subject, role name, or number of speakers. It asks the model to repair likely ASR errors from phonetic, semantic, grammatical, and discourse context while staying conservative when wording is uncertain.

Every model response is validated before promotion. The review must preserve:

- timestamp count;
- timestamp values and ordering;
- block count;
- speaker labels and their ordering;
- non-empty content for every previously non-empty block;
- conservative overall transcript length bounds.

The final timestamped review is then rendered canonically from the validated blocks, so model commentary or unrelated wrapper text is never promoted into the review output.

## Long transcripts

Long transcripts are divided only at timestamp block boundaries. Each chunk is reviewed and validated independently, then the validated blocks are reassembled in their original order. This avoids relying on one very large API response and reduces the risk of output truncation.

The default approximate chunk size is 24,000 characters and can be changed with:

```text
VID_PIPELINE_REVIEW_CHUNK_CHARS=24000
```

The chunk size must be at least 1,000 characters when loaded from the environment.

## Retry and timeout

Transient HTTP/network failures are retried with bounded exponential backoff. Configuration:

```text
VID_PIPELINE_REVIEW_TIMEOUT_SECONDS=900
VID_PIPELINE_REVIEW_MAX_ATTEMPTS=4
```

API credentials are read only from environment variables. They are not stored in output files or written into request-state JSON.
