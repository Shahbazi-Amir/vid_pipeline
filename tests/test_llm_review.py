from pathlib import Path

import pytest

from vid_pipeline import llm_review
from vid_pipeline.llm_review import (
    AIReviewError,
    ReviewAPIConfig,
    render_review_markdown,
    render_review_text,
    render_review_timestamped,
    review_collection_output,
    review_collection_output_if_configured,
    validate_review,
)
from vid_pipeline.review_cli import build_parser
from vid_pipeline.review_prompt import PERSIAN_TRANSCRIPT_REVIEW_PROMPT

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


def test_production_prompt_is_generic_not_transcript_specific():
    forbidden_examples = (
        "دویتر جان",
        "دکتر جان",
        "ثواد مالی",
        "تلاتوم",
        "مرفع",
    )

    assert all(item not in PERSIAN_TRANSCRIPT_REVIEW_PROMPT for item in forbidden_examples)
    assert "any number of speakers" in PERSIAN_TRANSCRIPT_REVIEW_PROMPT
    assert "Never assume specific speaker names" in PERSIAN_TRANSCRIPT_REVIEW_PROMPT


def test_validate_review_preserves_generic_structure():
    blocks = validate_review(SOURCE, REVIEWED)

    assert [block.speaker for block in blocks] == ["SPEAKER_00", "SPEAKER_00", "Guest A"]
    assert blocks[0].text == "این یک دغدغه مهم است."
    assert render_review_timestamped(blocks) == REVIEWED


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
    assert result["chunks"] == 1
    reviewed_timed = root / "review" / "timestamped" / "7.md"
    reviewed_md = root / "review" / "md" / "7.md"
    reviewed_txt = root / "review" / "txt" / "7.txt"
    assert reviewed_timed.read_text(encoding="utf-8") == REVIEWED
    assert reviewed_md.exists()
    assert reviewed_txt.exists()
    assert reviewed_md.read_text(encoding="utf-8").count("**SPEAKER_00**") == 1

    skipped = review_collection_output(root, 7, config=config)
    assert skipped["status"] == "skipped"


def test_review_chunks_long_input_and_canonicalizes_each_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "outputs" / "collection"
    source = root / "timestamped" / "8.md"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE, encoding="utf-8")
    calls: list[str] = []

    def fake_review(text: str, config: ReviewAPIConfig) -> str:
        calls.append(text)
        return "extra model commentary\n\n" + text.replace("دقدقه", "دغدغه")

    monkeypatch.setattr(llm_review, "_call_review_api", fake_review)
    config = ReviewAPIConfig(
        api_key="secret",
        base_url="https://example.invalid/v1",
        model="model",
        chunk_chars=90,
    )

    result = review_collection_output(root, 8, config=config)

    assert result["status"] == "completed"
    assert result["chunks"] == len(calls)
    assert result["chunks"] > 1
    reviewed = (root / "review" / "timestamped" / "8.md").read_text(encoding="utf-8")
    assert reviewed == REVIEWED
    assert "extra model commentary" not in reviewed


def test_existing_reviewed_timestamped_file_rebuilds_derived_outputs_without_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "outputs" / "collection"
    source = root / "timestamped" / "9.md"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE, encoding="utf-8")
    reviewed_timed = root / "review" / "timestamped" / "9.md"
    reviewed_timed.parent.mkdir(parents=True)
    reviewed_timed.write_text(REVIEWED, encoding="utf-8")

    def fail_if_called(text: str, config: ReviewAPIConfig) -> str:
        raise AssertionError("API must not be called when validated timestamped review exists")

    monkeypatch.setattr(llm_review, "_call_review_api", fail_if_called)
    result = review_collection_output(root, 9)

    assert result["status"] == "completed"
    assert result["api_used"] is False
    assert result["chunks"] == 0
    assert (root / "review" / "md" / "9.md").exists()
    assert (root / "review" / "txt" / "9.txt").exists()


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
    args = build_parser().parse_args(["ai-collection", "outputs/sample_collection", "3"])

    assert args.command == "ai-collection"
    assert args.collection_root == Path("outputs/sample_collection")
    assert args.result_number == 3
