# Deployment and worker usage

The Python package is the execution core. CLI arguments override environment
variables, which override configuration-file values when a caller supplies
one. No platform-specific backend is required.

## Local

```bash
python -m pip install -e '.[all]'
vid-pipeline run-url "https://example.com/video"
vid-pipeline run-file "/data/input/talk.mp4" --no-editorial
vid-pipeline run-folder "/data/input" --recursive --no-editorial
```

## Docker

```bash
docker build -t vid-pipeline .
docker run --rm \
  -v "$PWD/input:/data/input:ro" \
  -v "$PWD/outputs:/data/outputs" \
  -v "$PWD/model-cache:/home/pipeline/.cache" \
  vid-pipeline run-file /data/input/talk.mp4 \
  --output-root /data/outputs --no-editorial
```

## Worker

A queue worker should deserialize `JobRequest`, select URL or file acquisition,
and call `VideoPipeline` or `LocalMediaPipeline`. State is written after every
stage, so a retry can resume completed stages. A worker must keep its ASR and
local-review model alive across jobs where its backend supports reuse.

`TranscriptReviewProvider` is the provider-neutral review boundary.
`OpenAIReviewProvider` is deliberately not implemented; no OpenAI credential,
request, model selection, token calculation, or billing logic exists here.

## Profiles

`balanced` is the default. `fast` is intended for lower beam sizes and limited
retry work; `accurate` is intended for stricter validation and larger models.
Model, device, compute type, language, and worker count remain overridable.

macOS acceleration and Ollama are optional. Linux CPU and Docker are supported
without Homebrew, Metal, CoreML, or Apple Silicon.
