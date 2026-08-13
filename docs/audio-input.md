# Audio input

The canonical pipeline accepts audio-only and video media through local files,
folders, URLs, the online upload API, and GitHub Actions. Audio is not a separate
pipeline: all inputs pass through the same validation, ASR, cleaning, accuracy,
review, and final-output stages.

## Inputs

- Local: `vid-pipeline run-file speech.m4a --audio-profile safe`
- Mixed folders: `vid-pipeline run-folder media --recursive --audio-profile safe`
- Direct audio or supported podcast page: `vid-pipeline run-url URL --audio-profile safe`
- Online upload: `vid-pipeline submit-file speech.wav --audio-profile safe`
- GitHub upload: `vid-pipeline github-submit-file speech.mp3 --audio-profile safe --wait --download`
- GitHub URL: `vid-pipeline github-run-url URL --audio-profile safe --wait --download`
- Existing GitHub Release: `vid-pipeline run-github-release owner/repo TAG --asset-name speech.flac --no-editorial`

Release selection is exact and deterministic by asset name or numeric asset ID.
Public assets need no token. Private assets read `VID_PIPELINE_RELEASE_TOKEN`
(falling back to `GITHUB_TOKEN`/`GH_TOKEN`) from the environment. Repository,
tag, release ID, asset ID, size, and GitHub digest are written to source
provenance; the credential is never serialized.

All sources converge before processing:

```text
URL / local file / GitHub upload / GitHub Release
→ source resolution and provenance
→ FFprobe validation and audio/video classification
→ one canonical normalization, quality, ASR, accuracy, review, and export path
```

`source.json` identifies URL sources with `source=url` and retains the source URL
and extractor metadata. Local sources use `source=local_file` and record the
original filename, byte size, and SHA-256. Release sources use
`source=github_release` and record the exact repository, tag, release/asset IDs,
asset name, size, digest, and public download URL. Tokens and authorization
headers are not part of provenance.

For a digest-less GitHub asset, a same-size local file is not trusted by itself.
The download cache is reused only when a sidecar matches the complete repository,
release, and asset identity and its saved SHA-256 matches the current file.
Otherwise the asset is downloaded again atomically.

Folder discovery recognizes `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.ogg`,
`.opus`, `.webm`, `.wma`, `.aiff`, `.aif`, `.alac`, `.caf`, `.ac3`, and `.amr`,
as well as supported video extensions. Extensions only select candidates;
FFprobe validates actual streams on the processing worker. Wrong or absent
extensions are accepted by direct file processing when the content is decodable.
Attached album/cover artwork is treated as audio metadata rather than as a real
video stream, so covered MP3/M4A-style audio remains classified as audio.

Supports common audio formats decodable by the installed FFmpeg build.

## Local control plane and GitHub worker

Local `run-file` and `run-url` require FFmpeg/FFprobe and the selected ASR worker
dependencies. The GitHub commands intentionally keep the client lightweight:
the user's Mac uploads or dispatches, polls status, downloads the result, and can
clean temporary media; FFmpeg, FFprobe, model loading, normalization, and ASR run
on the GitHub Actions runner. Homebrew, Whisper, and FFmpeg are therefore not
requirements on the Mac when GitHub processing is used.

The existing URL workflow accepts all processing options, including language,
ASR profile/model, audio profile, editorial boundary, and optional diarization.
The Release workflow is manual-only and requires exactly one of `asset_name` or
`asset_id`. It has bounded runtime, non-cancelling source-specific concurrency,
and supports an optional exact ASR model override.

## Normalization and profiles

All decodable inputs with an audio stream become
`audio/audio-16k-mono.wav`: WAV, `pcm_s16le`, 16 kHz, mono. The write is atomic,
the result is probed, and codec, sample rate, channels, and duration are checked.
The original input is never modified or deleted by the local pipeline.

- `none`: decode, downmix, resample, and PCM conversion only.
- `safe` (default): mild high/low-pass filtering, conservative loudness
  normalization, and peak protection suitable for ordinary speech.
- `noisy`: stronger speech-band filtering and FFmpeg FFT denoising before
  conservative loudness normalization.

Profiles preserve natural pauses and internal silence; they do not aggressively
trim recordings. Denoising can reduce intelligibility on unusual recordings, so
compare `safe` and `none` when speech is already clean.

## Quality report

Each job writes `audio/audio-quality.json` with duration, codec, sample rate,
channels, peak and mean volume, possible clipping, silence ratio, very-low-volume
status, an explicitly estimated `noise_probability`, the selected profile,
applied filters, and warnings. Noise estimation is independent from silence and
uses FFmpeg `astats` sample entropy plus zero-crossing rate; those source metrics
are also included in the report for transparency. A `likely_noise` warning is
added only when the heuristic crosses its conservative threshold. It does not
claim an exact SNR.

## Uploads, artifacts, and review

The lightweight clients use a shared extension registry and do not require
FFmpeg or Whisper. The worker performs real FFprobe validation, rejecting empty,
corrupt, unsupported, or no-audio media with a clear error. Existing upload-size,
resume, hash verification, cleanup, and token-redaction behavior is preserved.

Original uploaded media is temporary and excluded from normal success artifacts.
The normalized WAV and `audio-quality.json` stay in the internal/debug output tree;
GitHub success artifacts remain lean and contain only the three delivery transcript
files unless a separate debug artifact is explicitly requested. Local jobs keep
their original media outside the output tree and retain normalized audio for
review clips. Machine output is not a substitute for listening: use the generated
review package and human audio verification for important transcripts.

GitHub processing defaults to `--no-editorial`. This is intentional: the runner
produces a machine transcript and review material without calling a paid LLM.
It must not be described as human-reviewed merely because it appears under the
canonical final filenames.

Each successful full pipeline run creates `review/chatgpt/` containing source
metadata, raw and machine transcripts, available quality/accuracy/diarization
data, `chatgpt-review-prompt.md`, `review-manifest.json`, and lossless ordered
`chunks/*.txt` for long transcripts. The prompt requires evidence-based,
content-preserving correction and explicit uncertainty. Building this package
invokes no OpenAI API or other paid model.

## Resume and failure behavior

Pipeline stages are checkpointed with output paths and SHA-256 values. A complete
stage is reused only while its recorded outputs still exist and match saved
hashes. GitHub client requests are correlated by request/dispatch identity, and a
new execution with changed options must create a new request rather than select a
terminal result from an older run. Interrupted downloads retain no finalized
`.part` file. Failures remain explicit in `state.json`/`result.json`.

Uploaded media cleanup is opt-in for single-file submission with
`--delete-remote-after-success`. Release source assets are user-owned inputs and
are never deleted by `run-github-release`.

## Diarization, ASR, and security

ASR profiles remain `fast`, `balanced`, and `accurate`; language and model are
overridable. Diarization remains optional through `--diarize`; Pyannote is not a
dependency when it is disabled.

- Keep GitHub tokens in environment variables or Actions secrets, never CLI text.
- Private cross-repository Releases need a credential able to read that repo.
- Credentials stay in request headers and are excluded from provenance and artifacts.
- Success artifacts contain only the three delivery files; internals are confined
  to the opt-in debug package and bounded failure diagnostics.

## Limitations

- Exact codec availability depends on the installed FFmpeg build; AMR and some
  proprietary codecs are commonly unavailable.
- URL support depends on direct HTTP access or a compatible yt-dlp extractor.
- Password-protected, DRM-protected, truncated, or undecodable media is rejected.
- Noise and silence metrics are estimates and do not guarantee ASR accuracy.
- A private cross-repository Release is `NOT RUN` when no suitable existing
  credential is available to the runner.
- Long recordings remain bounded by the Actions timeout, model cache, and artifact
  limits; completed stage checkpoints are reusable, but an interrupted ASR call
  cannot resume internally before it writes output.
