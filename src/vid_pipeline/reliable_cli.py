"""Reliable command-line entry point with CPU-safe local editorial limits.

The public CLI used to pass very large chunk/output limits to Ollama. On CPU,
that could keep an 8B model generating long enough to hit the HTTP timeout even
after Whisper had successfully transcribed the complete audio. This entry point
keeps the existing CLI surface while applying conservative editorial limits.
"""

from __future__ import annotations

from argparse import Namespace

from vid_pipeline import cli as base_cli
from vid_pipeline.editorial import EditorialConfig

_MAX_EDITORIAL_CHARS = 3500
_MAX_OUTPUT_TOKENS = 4500
_CONTEXT_WINDOW = 8192
_TIMEOUT_SECONDS = 900
_RETRIES = 2


def reliable_editorial_config(args: Namespace) -> EditorialConfig:
    """Build a CPU-safe Ollama configuration without changing CLI arguments."""

    chunk_chars = max(2000, min(int(args.editorial_chunk_chars), _MAX_EDITORIAL_CHARS))
    max_output_tokens = max(1024, min(int(args.editorial_max_output_tokens), _MAX_OUTPUT_TOKENS))
    return EditorialConfig(
        model=args.editorial_model,
        base_url=args.editorial_base_url,
        chunk_chars=chunk_chars,
        max_output_tokens=max_output_tokens,
        context_window=_CONTEXT_WINDOW,
        timeout_seconds=_TIMEOUT_SECONDS,
        retries=_RETRIES,
        second_pass=False,
    )


def main() -> int:
    """Run the original CLI with reliable local-editorial defaults."""

    base_cli._editorial_config = reliable_editorial_config
    return base_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
