# v1.0.0 — Delete unusable GitHub draft assets and reset failed requests for a clean re-upload and retry.

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

from vid_pipeline.github_client import (
    GitHubClient,
    GitHubRequest,
)

REPOSITORY = "Shahbazi-Amir/vid_pipeline"
REF = "main"
STATE_ROOT = Path(".vid_pipeline/github")
OUTPUT_ROOT = Path("outputs")

TARGET_ERROR = "Download authenticated draft release asset"


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


def reset_request(
    client: GitHubClient,
    request: GitHubRequest,
) -> bool:
    print(
        f"\nRepairing: {request.original_name}"
    )
    print(
        f"Request ID: {request.request_id}"
    )
    print(
        f"Old asset ID: {request.asset_id}"
    )

    if request.asset_id:
        try:
            client.delete_asset(
                request.asset_id
            )

            print(
                "Old remote asset deleted."
            )

        except Exception as delete_error:
            print(
                "Direct asset deletion failed; "
                "checking the temporary release."
            )

            try:
                release = (
                    client.temporary_release()
                )

                assets = client.list_assets(
                    int(release["id"])
                )

                matches = [
                    asset
                    for asset in assets
                    if (
                        int(asset["id"])
                        == request.asset_id
                        or asset["name"]
                        == request.safe_asset_name
                    )
                ]

                for asset in matches:
                    client.delete_asset(
                        int(asset["id"])
                    )

                if matches:
                    print(
                        "Matching remote asset deleted."
                    )
                else:
                    print(
                        "Old asset was already absent."
                    )

            except Exception as verify_error:
                print(
                    "Repair failed; the request "
                    "was not modified."
                )
                print(
                    f"Delete error: {delete_error}"
                )
                print(
                    f"Verification error: "
                    f"{verify_error}"
                )

                return False

    request.release_id = 0
    request.asset_id = 0

    request.dispatch_id = ""
    request.dispatch_started_at = ""
    request.dispatch_server_at = ""

    request.workflow_run_id = 0
    request.workflow_run_url = ""
    request.workflow_started_at = ""
    request.workflow_completed_at = ""

    request.artifact_id = 0
    request.artifact_name = ""
    request.job_id = ""
    request.output_path = ""

    request.upload_started_at = ""
    request.upload_completed_at = ""
    request.download_completed_at = ""
    request.remote_deleted_at = ""

    request.status = "discovered"
    request.last_error = ""
    request.retry_count = 0

    client.state.save(request)

    print(
        "Request reset successfully."
    )

    return True


def main() -> int:
    if not STATE_ROOT.is_dir():
        print(
            f"State folder not found: "
            f"{STATE_ROOT}"
        )
        return 2

    token = get_token()

    client = GitHubClient(
        token,
        REPOSITORY,
        ref=REF,
        output_root=OUTPUT_ROOT,
        state_root=STATE_ROOT,
        timeout=180,
        retries=2,
    )

    repaired = 0
    matched = 0

    try:
        for state_file in sorted(
            STATE_ROOT.glob("*.json")
        ):
            try:
                data = json.loads(
                    state_file.read_text(
                        encoding="utf-8"
                    )
                )

                request = GitHubRequest(
                    **data
                )

            except Exception as exc:
                print(
                    f"Invalid state ignored: "
                    f"{state_file}: {exc}"
                )
                continue

            if (
                request.status
                != "workflow_failed"
                or TARGET_ERROR
                not in request.last_error
            ):
                continue

            matched += 1

            if reset_request(
                client,
                request,
            ):
                repaired += 1

    finally:
        client.close()

    print("\nRepair summary")
    print(f"Matched:  {matched}")
    print(f"Repaired: {repaired}")

    return 0 if repaired == matched else 1


if __name__ == "__main__":
    raise SystemExit(main())