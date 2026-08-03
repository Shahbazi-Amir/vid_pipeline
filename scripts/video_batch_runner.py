# v1.0.0 — Resumable sequential GitHub video transcription with retries, reports, and source-named output folders.

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from vid_pipeline.github_client import (
    GitHubClient,
    GitHubRequest,
    GitHubState,
    discover_media,
)

TRANSIENT_ERRORS = (
    "LocalProtocolError",
    "RemoteProtocolError",
    "ReadTimeout",
    "WriteTimeout",
    "ConnectTimeout",
    "ConnectError",
    "PoolTimeout",
    "NetworkError",
)

FAILED_STATUSES = {
    "failed",
    "workflow_failed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Process videos sequentially with GitHub Actions, resume interrupted "
            "requests, skip completed videos, and rename output folders."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("input_videos"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs"),
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=Path(".vid_pipeline/github"),
    )
    parser.add_argument(
        "--repo",
        default="Shahbazi-Amir/vid_pipeline",
    )
    parser.add_argument(
        "--ref",
        default="main",
    )
    parser.add_argument(
        "--profile",
        choices=("fast", "balanced", "accurate"),
        default="balanced",
    )
    parser.add_argument(
        "--model",
        default="small",
    )
    parser.add_argument(
        "--language",
        default="fa",
    )
    parser.add_argument(
        "--editorial",
        action="store_true",
        help="Enable editorial processing. Disabled by default.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include media files inside subfolders.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=4,
        help="Maximum attempts for each video.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=10.0,
        help="Initial retry delay in seconds.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="GitHub HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--keep-remote",
        action="store_true",
        help="Keep temporary uploaded assets after successful processing.",
    )
    parser.add_argument(
        "--delete-result-artifact",
        action="store_true",
        help="Delete the GitHub result artifact after local download.",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only create a status report without processing videos.",
    )

    return parser.parse_args()


def shown(path: Path) -> str:
    path = path.resolve()

    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def resolve_saved(value: str) -> Path:
    path = Path(value)

    if not path.is_absolute():
        path = Path.cwd() / path

    return path.resolve()


def output_name(filename: str) -> str:
    stem = Path(filename).stem.strip()

    stem = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]+',
        "-",
        stem,
    )

    stem = re.sub(
        r"\s+",
        " ",
        stem,
    ).strip(" .-")

    return stem or "media"


def transcript_path(folder: Path) -> Path:
    return folder / "final" / "transcript.final.txt"


def valid_output(folder: Path) -> bool:
    transcript = transcript_path(folder)

    return (
        transcript.is_file()
        and transcript.stat().st_size > 0
    )


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def same_transcript(
    first: Path,
    second: Path,
) -> bool:
    first_transcript = transcript_path(first)
    second_transcript = transcript_path(second)

    return (
        first_transcript.is_file()
        and second_transcript.is_file()
        and first_transcript.stat().st_size
        == second_transcript.stat().st_size
        and file_hash(first_transcript)
        == file_hash(second_transcript)
    )


def load_states(
    state_root: Path,
) -> list[GitHubRequest]:
    requests: list[GitHubRequest] = []

    for state_file in sorted(
        state_root.glob("*.json")
    ):
        try:
            data = json.loads(
                state_file.read_text(
                    encoding="utf-8"
                )
            )

            requests.append(
                GitHubRequest(**data)
            )

        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"WARNING: ignored invalid state "
                f"{state_file}: {exc}"
            )

    return requests


def normalize_output(
    request: GitHubRequest,
    output_root: Path,
    state: GitHubState,
) -> Path:
    """
    Rename a completed output directory from a long job ID to the
    original source filename, such as outputs/session-15.
    """

    if request.status != "completed":
        raise ValueError(
            "Only completed requests can be renamed."
        )

    if not request.original_name:
        raise ValueError(
            f"Missing original_name for "
            f"{request.request_id}"
        )

    target = (
        output_root
        / output_name(request.original_name)
    ).resolve()

    source = (
        resolve_saved(request.output_path)
        if request.output_path
        else target
    )

    if (
        source == target
        or (
            not source.exists()
            and valid_output(target)
        )
    ):
        if not valid_output(target):
            raise FileNotFoundError(
                f"Transcript not found: {target}"
            )

        request.output_path = shown(target)
        state.save(request)

        return target

    if not valid_output(source):
        raise FileNotFoundError(
            f"Completed output is invalid: {source}"
        )

    if target.exists():
        if (
            not valid_output(target)
            or not same_transcript(
                source,
                target,
            )
        ):
            raise FileExistsError(
                f"Refusing to overwrite: {target}"
            )

        output_root_resolved = (
            output_root.resolve()
        )

        if (
            source != target
            and output_root_resolved
            in source.parents
        ):
            shutil.rmtree(source)

    else:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(target),
        )

    if not valid_output(target):
        raise RuntimeError(
            "Transcript validation failed "
            f"after rename: {target}"
        )

    request.output_path = shown(target)
    state.save(request)

    return target


def normalize_existing_outputs(
    output_root: Path,
    state_root: Path,
) -> None:
    """
    Rename all previously completed outputs, including the first
    video and the eleven videos already processed.
    """

    state = GitHubState(state_root)

    for request in load_states(state_root):
        if (
            request.status != "completed"
            or not request.output_path
        ):
            continue

        try:
            previous_path = request.output_path

            target = normalize_output(
                request,
                output_root,
                state,
            )

            if previous_path != request.output_path:
                print(
                    f"RENAMED: "
                    f"{request.original_name} -> "
                    f"{shown(target)}"
                )

        except Exception as exc:
            print(
                f"WARNING: could not rename "
                f"{request.original_name}: {exc}"
            )


def get_token() -> str:
    token = os.getenv(
        "VID_PIPELINE_GITHUB_TOKEN",
        "",
    ).strip()

    if not token:
        token = getpass.getpass(
            "GitHub token: "
        ).strip()

    if not token:
        raise RuntimeError(
            "GitHub token is missing."
        )

    return token


def new_client(
    args: argparse.Namespace,
    token: str,
) -> GitHubClient:
    # Retries are handled by this script with a fresh HTTP client and file handle.

    return GitHubClient(
        token,
        args.repo,
        ref=args.ref,
        output_root=args.output,
        state_root=args.state_root,
        timeout=args.timeout,
        retries=0,
    )


def transient(
    exc: Exception,
) -> bool:
    text = (
        f"{type(exc).__name__}: {exc}"
    )

    return any(
        name in text
        for name in TRANSIENT_ERRORS
    )


def report_row(
    index: int,
    media: Path,
    category: str,
    request: GitHubRequest | None = None,
    attempts: int = 0,
    error: str = "",
) -> dict[str, Any]:
    output_path = (
        request.output_path
        if request
        else ""
    )

    transcript = ""

    if output_path:
        transcript = shown(
            transcript_path(
                resolve_saved(output_path)
            )
        )

    return {
        "index": index,
        "file": media.name,
        "local_path": shown(media),
        "category": category,
        "status": (
            request.status
            if request
            else "not_started"
        ),
        "request_id": (
            request.request_id
            if request
            else ""
        ),
        "workflow_run_id": (
            request.workflow_run_id
            if request
            else 0
        ),
        "workflow_run_url": (
            request.workflow_run_url
            if request
            else ""
        ),
        "output_path": output_path,
        "transcript": transcript,
        "attempts": attempts,
        "error": (
            error
            or (
                request.last_error
                if request
                else ""
            )
        ),
    }


def initial_rows(
    files: list[Path],
    state_root: Path,
) -> list[dict[str, Any]]:
    states_by_path = {
        str(
            resolve_saved(
                request.local_path
            )
        ): request
        for request in load_states(
            state_root
        )
        if request.local_path
    }

    rows: list[dict[str, Any]] = []

    for index, media in enumerate(
        files,
        1,
    ):
        request = states_by_path.get(
            str(media.resolve())
        )

        if request is None:
            category = "not_started"

        elif request.status == "completed":
            output_folder = (
                resolve_saved(
                    request.output_path
                )
                if request.output_path
                else Path(
                    "__missing_output__"
                )
            )

            category = (
                "successful"
                if valid_output(output_folder)
                else "partial"
            )

        elif request.status in FAILED_STATUSES:
            category = "failed"

        else:
            category = "partial"

        rows.append(
            report_row(
                index,
                media,
                category,
                request,
            )
        )

    return rows


def write_reports(
    rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    counts = Counter(
        item["category"]
        for item in rows
    )

    payload = {
        "summary": {
            "total": len(rows),
            "successful": counts["successful"],
            "failed": counts["failed"],
            "partial": counts["partial"],
            "not_started": counts["not_started"],
        },
        "files": rows,
    }

    json_temp = (
        output_root
        / ".batch_report.json.tmp"
    )

    json_temp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    json_temp.replace(
        output_root
        / "batch_report.json"
    )

    fields = (
        list(rows[0].keys())
        if rows
        else []
    )

    csv_temp = (
        output_root
        / ".batch_report.csv.tmp"
    )

    with csv_temp.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(rows)

    csv_temp.replace(
        output_root
        / "batch_report.csv"
    )


def print_summary(
    rows: list[dict[str, Any]],
) -> None:
    counts = Counter(
        item["category"]
        for item in rows
    )

    print("\n" + "=" * 58)
    print(f"Total:       {len(rows)}")
    print(
        f"Successful:  "
        f"{counts['successful']}"
    )
    print(
        f"Failed:      "
        f"{counts['failed']}"
    )
    print(
        f"Partial:     "
        f"{counts['partial']}"
    )
    print(
        f"Not started: "
        f"{counts['not_started']}"
    )
    print(
        "Reports: "
        "outputs/batch_report.json, "
        "outputs/batch_report.csv"
    )
    print("=" * 58)


def process_one(
    args: argparse.Namespace,
    token: str,
    media: Path,
    index: int,
    total: int,
) -> dict[str, Any]:
    last_request: GitHubRequest | None = None
    last_error = ""

    for attempt in range(
        1,
        args.max_attempts + 1,
    ):
        client = new_client(
            args,
            token,
        )

        try:
            request = (
                client.create_file_request(
                    media
                )
            )

            last_request = request

            # Never re-upload a completed request because its temporary asset
            # has already been deleted after successful validation.

            if request.status == "completed":
                target = normalize_output(
                    request,
                    args.output,
                    client.state,
                )

                print(
                    f"[{index}/{total}] "
                    f"SKIP completed: "
                    f"{media.name} -> "
                    f"{shown(target)}"
                )

                return report_row(
                    index,
                    media,
                    "successful",
                    request,
                    attempt - 1,
                )

            print(
                f"\n[{index}/{total}] "
                f"PROCESS {media.name} | "
                f"attempt "
                f"{attempt}/"
                f"{args.max_attempts}"
            )

            request = client.process_file(
                media,
                wait=True,
                download=True,
                delete_remote_after_success=(
                    not args.keep_remote
                ),
                delete_result_artifact_after_download=(
                    args.delete_result_artifact
                ),
                profile=args.profile,
                model=args.model,
                language=args.language,
                no_editorial=(
                    not args.editorial
                ),
            )

            last_request = request

            if request.status == "completed":
                target = normalize_output(
                    request,
                    args.output,
                    client.state,
                )

                print(
                    f"SUCCESS: {media.name}"
                )

                print(
                    f"TEXT: "
                    f"{shown(transcript_path(target))}"
                )

                return report_row(
                    index,
                    media,
                    "successful",
                    request,
                    attempt,
                )

            if request.status in FAILED_STATUSES:
                print(
                    f"FAILED: {media.name} | "
                    f"{request.last_error}"
                )

                return report_row(
                    index,
                    media,
                    "failed",
                    request,
                    attempt,
                )

            if attempt < args.max_attempts:
                delay = (
                    args.retry_delay
                    * (
                        2
                        ** (attempt - 1)
                    )
                )

                print(
                    f"PARTIAL: "
                    f"status="
                    f"{request.status}; "
                    f"resume in "
                    f"{delay:.0f}s"
                )

                time.sleep(delay)
                continue

            return report_row(
                index,
                media,
                "partial",
                request,
                attempt,
                request.last_error
                or "Request did not finish.",
            )

        except Exception as exc:
            last_error = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            print(
                f"ERROR: {media.name} | "
                f"{last_error}"
            )

            if (
                transient(exc)
                and attempt
                < args.max_attempts
            ):
                delay = (
                    args.retry_delay
                    * (
                        2
                        ** (attempt - 1)
                    )
                )

                print(
                    "TEMPORARY NETWORK ERROR: "
                    f"retry in {delay:.0f}s"
                )

                time.sleep(delay)
                continue

            return report_row(
                index,
                media,
                "failed",
                last_request,
                attempt,
                last_error,
            )

        finally:
            client.close()

    return report_row(
        index,
        media,
        "failed",
        last_request,
        args.max_attempts,
        last_error
        or "Maximum attempts exceeded.",
    )


def main() -> int:
    args = parse_args()

    if not args.input.is_dir():
        print(
            f"Input folder not found: "
            f"{args.input}",
            file=sys.stderr,
        )

        return 2

    if args.max_attempts < 1:
        print(
            "--max-attempts must be "
            "at least 1.",
            file=sys.stderr,
        )

        return 2

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.state_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    normalize_existing_outputs(
        args.output,
        args.state_root,
    )

    files = discover_media(
        args.input,
        args.recursive,
    )

    if not files:
        print(
            f"No media files found in "
            f"{args.input}"
        )

        return 0

    print(
        f"{len(files)} media files:"
    )

    for index, media in enumerate(
        files,
        1,
    ):
        print(
            f"{index:02d}. "
            f"{media.name}"
        )

    rows = initial_rows(
        files,
        args.state_root,
    )

    write_reports(
        rows,
        args.output,
    )

    print_summary(rows)

    if args.status_only:
        return (
            1
            if any(
                item["category"]
                == "failed"
                for item in rows
            )
            else 0
        )

    try:
        token = get_token()

    except RuntimeError as exc:
        print(
            str(exc),
            file=sys.stderr,
        )

        return 2

    try:
        for index, media in enumerate(
            files,
            1,
        ):
            rows[index - 1] = process_one(
                args,
                token,
                media,
                index,
                len(files),
            )

            write_reports(
                rows,
                args.output,
            )

            print_summary(rows)

    except KeyboardInterrupt:
        print(
            "\nStopped by user; "
            "State and reports were preserved."
        )

        write_reports(
            rows,
            args.output,
        )

        return 130

    write_reports(
        rows,
        args.output,
    )

    print_summary(rows)

    return (
        1
        if any(
            item["category"]
            in {
                "failed",
                "partial",
            }
            for item in rows
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())