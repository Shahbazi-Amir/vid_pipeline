"""Command-line entry point for the video processing pipeline."""

from __future__ import annotations

import argparse

from vid_pipeline import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="vid-pipeline",
        description="Process Persian financial education videos for transcript review and RAG.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main() -> int:
    """Run the command-line application."""
    parser = build_parser()
    parser.parse_args()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
