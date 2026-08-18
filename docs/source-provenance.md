# Source provenance for transcript outputs

Every transcript delivery should preserve where the media actually came from.

The pipeline distinguishes three links:

- `original_download_url`: the direct audio/video URL that was actually used to download the original media before archiving.
- `source_page_url`: the public episode/video/page URL, when one exists.
- `archive_url`: an internal or later archive copy such as a GitHub Release asset.

`original_download_url` is preferred for provenance. An archive URL must never replace a known original URL.

## Storage

Provenance is stored in `source.json` under `provenance` and mirrored as resolved top-level fields for compatibility.

```json
{
  "provenance": {
    "original_download_url": "https://cdn.example.org/original.mp3",
    "source_page_url": "https://example.org/episode",
    "archive_url": "https://github.com/owner/repo/releases/download/tag/copy.mp3"
  }
}
```

## Delivery files

During final export, provenance is automatically added to all three user-facing files:

- `delivery/transcript.md`
- `delivery/transcript.txt`
- `delivery/transcript.timestamped.md`

The transcript content itself is not changed; a small source block is prepended.

## Recording provenance for an existing/local-media job

When media was downloaded outside `vid-pipeline` and then passed to `run-file`, record the URLs after the job exists:

```bash
python -m vid_pipeline.provenance outputs/<job-id> \
  --original-download-url 'https://cdn.example.org/original.mp3' \
  --source-page-url 'https://example.org/episode' \
  --archive-url 'https://github.com/owner/repo/releases/download/tag/copy.mp3'
```

The command is idempotent and can be re-run if a better provenance link becomes available later.

## Archive-before-transcription rule

For workflows that first download media and later upload a copy to GitHub Releases:

1. capture the exact URL used by the downloader before or during download;
2. save it in a manifest or provenance file;
3. upload the media copy to the archive;
4. transcribe the archived copy if convenient;
5. restore `original_download_url` from the manifest into the transcript job;
6. store the Release asset only as `archive_url`;
7. final export exposes the original URL first.

If an old manually uploaded file has no recorded pre-upload URL, the pipeline does not invent one. The archive URL remains available until the original URL is recovered.
