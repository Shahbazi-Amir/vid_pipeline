from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from vid_pipeline import accuracy
from vid_pipeline.accuracy import AccuracyConfig, build_accuracy_package
from vid_pipeline.asre_shirin import AsreShirinCheckpoints

ROOT = Path(__file__).resolve().parents[1]


def test_production_worker_hands_verified_media_to_run_file() -> None:
    script = (ROOT / "scripts/process_asre_shirin_url.py").read_text(encoding="utf-8")
    assert '"run-file"' in script
    assert '"run-url"' not in script
    assert "ensure_verified_aparat_media" in script


def test_diarization_retry_reuses_completed_targeted_asr(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "job"
    audio = root / "audio" / "audio-16k-mono.wav"
    raw = root / "raw" / "transcript.raw.json"
    audio.parent.mkdir(parents=True)
    raw.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    raw.write_text(
        json.dumps(
            {
                "model": "large-v3-turbo",
                "language": "fa",
                "duration": 10,
                "segments": [
                    {
                        "id": 0,
                        "start": 0,
                        "end": 10,
                        "text": "سلام این یک متن آزمایشی است",
                        "avg_logprob": -2.0,
                        "compression_ratio": 1.0,
                        "no_speech_prob": 0.0,
                        "words": [],
                        "review_flags": ["low_log_probability"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = 0

    def runner(_path, _spec, _hotwords):
        nonlocal calls
        calls += 1
        return {
            "model": "large-v3-turbo",
            "segments": [
                {
                    "id": 0,
                    "start": 0,
                    "end": 10,
                    "text": "سلام این یک متن آزمایشی است",
                    "avg_logprob": -0.1,
                    "compression_ratio": 1.0,
                    "no_speech_prob": 0.0,
                    "words": [],
                }
            ],
        }

    def fake_extract(_audio, output, _start, _end):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"same-clip")
        return ""

    attempts = 0

    def enrichment(_audio, segments, _config):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("forced diarization failure")
        return segments, []

    monkeypatch.setattr(accuracy, "extract_clip", fake_extract)
    monkeypatch.setattr(accuracy, "optional_enrichment", enrichment)
    config = AccuracyConfig(mode="fast", max_targeted_segments=1, diarization=True)
    with pytest.raises(RuntimeError, match="forced diarization failure"):
        build_accuracy_package(root, config=config, pass_runner=runner)
    build_accuracy_package(root, config=config, pass_runner=runner)
    assert calls == 1
    manifest = json.loads((root / "accuracy" / "manifest.json").read_text(encoding="utf-8"))
    assert "targeted_0_reused_from_checkpoint" in manifest["warnings"]


def test_stage_checkpoint_rejects_corrupt_output(tmp_path: Path) -> None:
    output = tmp_path / "raw.json"
    output.write_text("first", encoding="utf-8")
    state = AsreShirinCheckpoints(tmp_path / "checkpoints.json")
    state.mark_complete("raw_asr_complete", [output])
    assert state.is_complete("raw_asr_complete")
    output.write_text("corrupt", encoding="utf-8")
    assert not state.is_complete("raw_asr_complete")


def test_role_labeling_does_not_name_doctor_from_dominance(tmp_path: Path) -> None:
    root = tmp_path / "collection"
    for directory, suffix in (("timestamped", ".md"), ("md", ".md"), ("txt", ".txt")):
        path = root / directory / f"2{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "[00:00:00 → 00:00:08] **گوینده ۱**\n\nسلام و خوش آمدید\n\n"
            "[00:00:08 → 00:10:00] **گوینده ۲**\n\nتوضیح طولانی مهمان\n\n"
            "[00:10:00 → 00:10:30] **گوینده ۳**\n\nپاسخ کوتاه\n"
        )
        path.write_text(content, encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/label_asre_shirin_roles.py"), str(root), "2"],
        check=True,
        cwd=ROOT,
    )
    roles = json.loads((root / "roles" / "2.json").read_text(encoding="utf-8"))
    assert "دکتر کمیل رودی" not in roles["mapping"].values()
    assert roles["doctor_selection"]["dominance_not_used_for_identity"] is True
    assert len(roles["unresolved_raw_labels"]) == 2


def test_asre_workflow_contract() -> None:
    workflow = (ROOT / ".github/workflows/private-asre-shirin-transcription.yml").read_text(
        encoding="utf-8"
    )
    process_block = workflow.split("  process:", 1)[1].split("\n  publish:", 1)[0]
    assert "max-parallel: 6" in process_block
    assert "git push" not in process_block
    assert "AI_REVIEW_ENABLED: \"false\"" in workflow
    assert "run-url" not in workflow
    assert "timings/$RESULT_NUMBER.json" in workflow
    assert "--skip-existing-complete-base" in workflow
    assert workflow.count("git push") == 1
    assert workflow.count("  publish:") == 1
    assert "sleep $((attempt * 15))" in workflow
    assert "if (( attempt < 2 ))" in workflow

    manifest = json.loads(
        (ROOT / "sources/asre_shirin/aparat_manifest.json").read_text(encoding="utf-8")
    )
    assert [int(row["result_number"]) for row in manifest["videos"]] == list(range(1, 27))


def test_cpu_dependency_contract_excludes_unused_execution_paths() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    extra = project.split("asre-shirin-cpu = [", 1)[1].split("]", 1)[0]
    assert "faster-whisper==1.2.1" in extra
    assert "pyannote.audio==4.0.4" in extra
    assert "whisperx" not in extra
    assert "yt-dlp" not in extra
    workflow = (ROOT / ".github/workflows/private-asre-shirin-transcription.yml").read_text(
        encoding="utf-8"
    )
    assert "https://download.pytorch.org/whl/cpu" in workflow
    assert "constraints/asre-shirin-cpu.txt" in workflow
    assert "hashFiles('pyproject.toml', 'constraints/asre-shirin-cpu.txt')" in workflow
