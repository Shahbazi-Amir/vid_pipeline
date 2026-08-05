from pathlib import Path

import pytest

from vid_pipeline import llm_review
from vid_pipeline.llm_review import (
    AIReviewError,
    ReviewAPIConfig,
    render_review_markdown,
    render_review_text,
    review_collection_output,
    review_collection_output_if_configured,
    validate_review,
)
from vid_pipeline.review_cli import build_parser

SOURCE = """# media

[00:00:00 → 00:00:03] **SPEAKER_00**

این یک دقدقه مهم است.

[00:00:03 → 00:00:06] **SPEAKER_00**

و ادامه همان صحبت است.

[00:00:06 → 00:00:09] **Guest A**

بله، درست است.
"""

REVIEWED = """# media

[00:00:00 → 00:00:03] **SPEAKER_00**

این یک دغدغه مهم است.

[00:00:03 → 00:00:06] **SPEAKER_00**

و ادامه همان صحبت است.

[00:00:06 → 00:00:09] **Guest A**

بله، درست است.
"""


def test_validate_review_preserves_generic_structure():
    blocks = validate_review(SOURCE, REVIEWED)

    assert [block.speaker for block in blocks] == ["SPEAKER_00", "SPEAKER_00", "Guest A"]
    assert blocks[0].text == "این یک دغدغه مهم است."


def test_validate_review_rejects_timestamp_or_speaker_changes():
    with pytest.raises(AIReviewError, match="timestamp"):
        validate_review(SOURCE, REVIEWED.replace("00:00:09", "00:00:10"))

    with pytest.raises(AIReviewError, match="speaker"):
        validate_review(SOURCE, REVIEWED.replace("**Guest A**", "**Guest B**"))


def test_rendered_review_collapses_only_consecutive_same_speaker_labels():
    blocks = validate_review(SOURCE, REVIEWED)
    markdown = render_review_markdown(blocks)
    text = render_review_text(blocks)

    assert markdown.count("**SPEAKER_00**") == 1
    assert markdown.count("**Guest A**") == 1
    assert text.count("SPEAKER_00:") == 1
    assert text.count("Guest A:") == 1
    assert "این یک دغدغه مهم است." in markdown
    assert "و ادامه همان صحبت است." in markdown


def test_review_collection_output_writes_three_review_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "outputs" / "collection"
    source = root / "timestamped" / "7.md"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE, encoding="utf-8")

    monkeypatch.setattr(llm_review, "_call_review_api", lambda text, config: REVIEWED)
    config = ReviewAPIConfig(
        api_key="secret",
        base_url="https://example.invalid/v1",
        model="model",
    )

    result = review_collection_output(root, 7, config=config)

    assert result["status"] == "completed"
    assert result["api_used"] is True
    reviewed_timed = root / "review" / "timestamped" / "7.md"
    reviewed_md = root / "review" / "md" / "7.md"
    reviewed_txt = root / "review" / "txt" / "7.txt"
    assert reviewed_timed.read_text(encoding="utf-8") == REVIEWED
    assert reviewed_md.exists()
    assert reviewed_txt.exists()
    assert reviewed_md.read_text(encoding="utf-8").count("**SPEAKER_00**") == 1

    skipped = review_collection_output(root, 7, config=config)
    assert skipped["status"] == "skipped"


def test_review_is_optional_when_no_review_environment_is_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    for name in (
        "VID_PIPELINE_REVIEW_API_KEY",
        "VID_PIPELINE_REVIEW_BASE_URL",
        "VID_PIPELINE_REVIEW_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    result = review_collection_output_if_configured(tmp_path, 3)

    assert result["status"] == "skipped"
    assert result["reason"] == "review API is not configured"


def test_review_cli_exposes_ai_collection_command():
    args = build_parser().parse_args(["ai-collection", "outputs/uni_tehran", "3"])

    assert args.command == "ai-collection"
    assert args.collection_root == Path("outputs/uni_tehran")
    assert args.result_number == 3
