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

Folder discovery recognizes `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.ogg`,
`.opus`, `.webm`, `.wma`, `.aiff`, `.aif`, `.alac`, `.caf`, `.ac3`, and `.amr`,
as well as supported video extensions. Extensions only select candidates;
FFprobe validates actual streams on the processing worker. Wrong or absent
extensions are accepted by direct file processing when the content is decodable.

Supports common audio formats decodable by the installed FFmpeg build.

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
applied filters, and warnings. It does not claim an exact SNR.

## Uploads, artifacts, and review

The lightweight clients use a shared extension registry and do not require
FFmpeg or Whisper. The worker performs real FFprobe validation, rejecting empty,
corrupt, unsupported, or no-audio media with a clear error. Existing upload-size,
resume, hash verification, cleanup, and token-redaction behavior is preserved.

Original uploaded media is temporary and excluded from result artifacts. The
normalized WAV is also excluded from GitHub artifacts by default. Local jobs keep
their original media outside the output tree and retain normalized audio for
review clips. Machine output is not a substitute for listening: use the generated
review package and human audio verification for important transcripts.

## Limitations

- Exact codec availability depends on the installed FFmpeg build; AMR and some
  proprietary codecs are commonly unavailable.
- URL support depends on direct HTTP access or a compatible yt-dlp extractor.
- Password-protected, DRM-protected, truncated, or undecodable media is rejected.
- Noise and silence metrics are estimates and do not guarantee ASR accuracy.
