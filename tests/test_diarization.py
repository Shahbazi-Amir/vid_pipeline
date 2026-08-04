import hashlib
import io
import os
import subprocess
import tarfile
import wave
from pathlib import Path

import pytest

from vid_pipeline.diarization import (
    DiarizationConfig,
    DiarizationError,
    DiarizationModelManager,
    ModelArtifact,
    SherpaOnnxDiarizationBackend,
    SpeakerTurn,
    align_segments,
    join_word_tokens,
    map_roles,
    normalize_turns,
    run_diarization,
)
from vid_pipeline.final_export import export_final_outputs


class FakeBackend:
    name = "fake"

    def diarize(self, audio: Path, *, num_speakers: int | None):
        assert num_speakers == 2
        return [SpeakerTurn(0, 1, "alice"), SpeakerTurn(1, 2, "bob")]


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def artifact(data: bytes, *, archive: bool = False, required_file: str = "model.onnx"):
    return ModelArtifact(
        name="test-model", url="https://example.invalid/model",
        sha256=hashlib.sha256(data).hexdigest(), required_file=required_file,
        file_sha256=hashlib.sha256(b"model").hexdigest(), archive=archive,
    )


def test_model_manager_download_and_cache_hit(tmp_path: Path):
    calls = []
    manager = DiarizationModelManager(tmp_path, opener=lambda *args, **kwargs: (
        calls.append(args[0].full_url) or Response(b"model")
    ))
    spec = artifact(b"model")
    assert manager.provision(spec).read_bytes() == b"model"
    assert manager.provision(spec).read_bytes() == b"model"
    assert len(calls) == 1


def test_model_manager_recovers_from_corrupt_cached_model(tmp_path: Path):
    calls = []
    spec = artifact(b"model")
    cached = tmp_path / spec.name / spec.required_file
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"partial")
    manager = DiarizationModelManager(tmp_path, opener=lambda *args, **kwargs: (
        calls.append(1) or Response(b"model")
    ))
    assert manager.provision(spec).read_bytes() == b"model"
    assert calls == [1]


def test_model_manager_cleans_partial_file_after_checksum_mismatch(tmp_path: Path):
    manager = DiarizationModelManager(tmp_path, opener=lambda *args, **kwargs: Response(b"bad"))
    with pytest.raises(DiarizationError, match="checksum mismatch"):
        manager.provision(artifact(b"good"))
    assert not list(tmp_path.glob("*.part"))


def test_model_manager_extracts_archive_and_rejects_corruption(tmp_path: Path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:bz2") as bundle:
        info = tarfile.TarInfo("bundle/model.onnx")
        info.size = 5
        bundle.addfile(info, io.BytesIO(b"model"))
    data = stream.getvalue()
    manager = DiarizationModelManager(tmp_path, opener=lambda *args, **kwargs: Response(data))
    assert manager.provision(artifact(data, archive=True)).read_bytes() == b"model"

    corrupt = b"not an archive"
    broken = DiarizationModelManager(tmp_path / "broken", opener=lambda *args, **kwargs: Response(corrupt))
    with pytest.raises(DiarizationError, match="extract"):
        broken.provision(artifact(corrupt, archive=True))


def test_model_manager_rejects_missing_model_file(tmp_path: Path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:bz2") as bundle:
        info = tarfile.TarInfo("bundle/other.txt")
        info.size = 1
        bundle.addfile(info, io.BytesIO(b"x"))
    data = stream.getvalue()
    manager = DiarizationModelManager(tmp_path, opener=lambda *args, **kwargs: Response(data))
    with pytest.raises(DiarizationError, match="missing model file"):
        manager.provision(artifact(data, archive=True))


class FakeSherpa:
    class Config:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def validate(self):
            return True

    OfflineSpeakerDiarizationConfig = Config
    OfflineSpeakerSegmentationModelConfig = Config
    OfflineSpeakerSegmentationPyannoteModelConfig = Config
    SpeakerEmbeddingExtractorConfig = Config
    FastClusteringConfig = Config


@pytest.mark.parametrize("requested", [1, 2, 3])
def test_sherpa_config_passes_requested_cluster_count(tmp_path: Path, requested: int):
    sf = pytest.importorskip("soundfile")
    audio = tmp_path / "audio.wav"
    sf.write(audio, [0.0] * 1600, 16000)
    captured = {}

    class Segment:
        start, end, speaker = 0.0, 0.1, 0

    class Result(list):
        def sort_by_start_time(self):
            return self

    class Diarizer:
        sample_rate = 16000

        def __init__(self, config):
            captured["clusters"] = config.clustering.num_clusters

        def process(self, samples):
            return Result([Segment()])

    FakeSherpa.OfflineSpeakerDiarization = Diarizer
    backend = object.__new__(SherpaOnnxDiarizationBackend)
    backend.sherpa = FakeSherpa
    backend.segmentation = tmp_path / "seg.onnx"
    backend.embedding = tmp_path / "emb.onnx"
    assert backend.diarize(audio, num_speakers=requested)[0].speaker == "speaker_00"
    assert captured["clusters"] == requested


def test_sherpa_backend_reports_initialization_failure(tmp_path: Path):
    sf = pytest.importorskip("soundfile")
    audio = tmp_path / "audio.wav"
    sf.write(audio, [0.0] * 1600, 16000)
    FakeSherpa.OfflineSpeakerDiarization = lambda config: (_ for _ in ()).throw(RuntimeError())
    backend = object.__new__(SherpaOnnxDiarizationBackend)
    backend.sherpa = FakeSherpa
    backend.segmentation = tmp_path / "seg.onnx"
    backend.embedding = tmp_path / "emb.onnx"
    with pytest.raises(DiarizationError, match="inference failed"):
        backend.diarize(audio, num_speakers=2)


def test_run_diarization_rejects_zero_turns(tmp_path: Path):
    class EmptyBackend:
        name = "empty"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return []

    with pytest.raises(DiarizationError, match="zero speakers"):
        run_diarization(
            tmp_path / "audio.wav", [], DiarizationConfig(enabled=True), backend=EmptyBackend()
        )


@pytest.mark.skipif(
    os.getenv("RUN_SHERPA_DIARIZATION_INTEGRATION") != "1",
    reason="real public-model integration is opt-in",
)
def test_real_sherpa_two_voice_integration(tmp_path: Path):
    if subprocess.run(["sh", "-c", "command -v espeak-ng || command -v espeak"], capture_output=True).returncode:
        pytest.skip("espeak is not installed")
    executable = "espeak-ng" if subprocess.run(["sh", "-c", "command -v espeak-ng"], capture_output=True).returncode == 0 else "espeak"
    clips = []
    for index, (voice, text) in enumerate((("en-us", "The first speaker begins."), ("en-sc", "The second speaker replies.")) * 3):
        clip = tmp_path / f"voice-{index}.wav"
        subprocess.run([executable, "-v", voice, "-s", "135", "-w", str(clip), text], check=True)
        clips.append(clip)
    output = tmp_path / "two-speakers.wav"
    with wave.open(str(output), "wb") as target:
        target.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        for clip in clips:
            with wave.open(str(clip), "rb") as source:
                frames = source.readframes(source.getnframes())
            target.writeframes(frames)
            target.writeframes(b"\0\0" * 8000)
    turns = SherpaOnnxDiarizationBackend().diarize(output, num_speakers=2)
    assert len({turn.speaker for turn in turns}) == 2
    normalized = normalize_turns(turns)
    assert len({turn.speaker for turn in normalized}) == 2
    segments = [{
        "start": turn.start,
        "end": turn.end,
        "text": f"word {index}",
        "words": [{"start": turn.start, "end": turn.end, "word": f" word{index}"}],
    } for index, turn in enumerate(normalized)]
    aligned, _ = align_segments(segments, normalized)
    assert len({row["speaker"] for row in aligned}) == 2


def test_normalization_word_split_and_short_interjection():
    turns = normalize_turns([SpeakerTurn(1, 2, "b"), SpeakerTurn(0, 1, "a")])
    segments = [{"start": 0, "end": 2, "text": "سلام بله", "words": [
        {"start": 0.1, "end": 0.8, "word": "سلام"},
        {"start": 1.1, "end": 1.3, "word": "بله"},
    ]}]
    aligned, ambiguous = align_segments(segments, turns)
    assert [row["speaker"] for row in aligned] == ["SPEAKER_00", "SPEAKER_01"]
    assert [row["text"] for row in aligned] == ["سلام", "بله"]
    assert ambiguous == 0


@pytest.mark.parametrize(("tokens", "expected"), [
    (["سلام", " به", " همه"], "سلام به همه"),
    (["این", " یک", " تست", " است"], "این یک تست است"),
    (["سلام", "،", " دنیا"], "سلام، دنیا"),
    (["آیا", " خوب", " است", "؟"], "آیا خوب است؟"),
    (["می\u200cشود"], "می\u200cشود"),
    (["برنامه\u200cریزی", " و", " سرمایه\u200cگذاری"], "برنامه\u200cریزی و سرمایه\u200cگذاری"),
])
def test_join_word_tokens_preserves_persian_spacing(tokens, expected):
    assert join_word_tokens(tokens) == expected


def test_alignment_preserves_persian_spacing_and_speaker_timeline():
    turns = normalize_turns([
        SpeakerTurn(0, 5, "speaker_00"),
        SpeakerTurn(5, 10, "speaker_01"),
        SpeakerTurn(10, 15, "speaker_00"),
    ])
    segments = [{"start": 0, "end": 15, "text": "سلام به همه بله دوباره", "words": [
        {"start": 1, "end": 2, "word": "سلام"},
        {"start": 2, "end": 3, "word": " به"},
        {"start": 3, "end": 4, "word": " همه"},
        {"start": 6, "end": 7, "word": " بله"},
        {"start": 11, "end": 12, "word": " دوباره"},
    ]}]
    aligned, ambiguous = align_segments(segments, turns)
    assert [row["speaker"] for row in aligned] == [
        "SPEAKER_00", "SPEAKER_01", "SPEAKER_00"
    ]
    assert [row["text"] for row in aligned] == ["سلام به همه", "بله", "دوباره"]
    assert " ".join(row["text"] for row in aligned) == segments[0]["text"]
    assert ambiguous == 0


def test_normalization_never_collapses_distinct_raw_labels():
    turns = normalize_turns([
        SpeakerTurn(0, 1, "speaker_00"), SpeakerTurn(1, 2, "speaker_01")
    ])
    assert [turn.speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01"]


def test_overlap_is_deterministic_and_three_speakers_are_generic():
    turns = [SpeakerTurn(0, 1, "SPEAKER_00"), SpeakerTurn(0, 1, "SPEAKER_01")]
    aligned, ambiguous = align_segments([{"start": 0, "end": 1, "text": "x"}], turns)
    assert aligned[0]["speaker"] == "SPEAKER_00"
    assert ambiguous == 1
    mapping = map_roles([
        {"speaker": "SPEAKER_00", "text": "چه می‌شود؟"},
        {"speaker": "SPEAKER_01", "text": "پاسخ طولانی"},
        {"speaker": "SPEAKER_02", "text": "سوم"},
    ], "host-teacher")
    assert all(not value["role"] for value in mapping.values())


def test_nested_sherpa_turn_wins_equal_overlap_by_temporal_specificity():
    turns = [
        SpeakerTurn(0, 100, "SPEAKER_00"),
        SpeakerTurn(20, 22, "SPEAKER_01"),
    ]
    aligned, ambiguous = align_segments([{
        "start": 20, "end": 22, "text": "پاسخ کوتاه",
        "words": [
            {"start": 20.1, "end": 20.8, "word": " پاسخ"},
            {"start": 20.8, "end": 21.5, "word": " کوتاه"},
        ],
    }], turns)
    assert {row["speaker"] for row in aligned} == {"SPEAKER_01"}
    assert ambiguous == 2


def test_changed_consensus_text_is_never_overwritten_by_stale_words():
    aligned, _ = align_segments([{
        "start": 0, "end": 2, "text": "متن بهتر انسانی",
        "words": [{"start": 0, "end": 1, "word": "متن خام"}],
    }], [SpeakerTurn(0, 2, "SPEAKER_00")])
    assert aligned[0]["text"] == "متن بهتر انسانی"


def test_manual_roles_and_fake_backend(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake")
    segments, report = run_diarization(audio, [{"start": 0, "end": 2, "text": "متن"}], DiarizationConfig(
        enabled=True, num_speakers=2, role_overrides={"SPEAKER_00": "host"}
    ), backend=FakeBackend())
    assert report["detected_speaker_count"] == 2
    assert segments[0]["speaker_role"] == "مجری"


def test_diagnostics_and_required_quality_gate_after_alignment(tmp_path: Path):
    class CollapsedBackend:
        name = "sherpa-onnx"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            assert num_speakers == 2
            return [SpeakerTurn(0, 90, "speaker_00"), SpeakerTurn(90, 100, "speaker_01")]

    output = tmp_path / "diarization.json"
    config = DiarizationConfig(enabled=True, required=True, num_speakers=2)
    with pytest.raises(
        DiarizationError,
        match=r"requested=2 raw_effective=2 aligned_effective=1",
    ):
        run_diarization(
            tmp_path / "audio.wav",
            [{
                "start": 0, "end": 90, "text": "یک متن معنی دار",
                "words": [
                    {"start": 1, "end": 2, "word": " یک"},
                    {"start": 2, "end": 3, "word": " متن"},
                    {"start": 3, "end": 4, "word": " معنی"},
                    {"start": 4, "end": 5, "word": " دار"},
                ],
            }],
            config,
            backend=CollapsedBackend(),
            output=output,
        )
    report = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert report["raw_speakers"] == ["speaker_00", "speaker_01"]
    assert report["normalized_speakers"] == ["SPEAKER_00", "SPEAKER_01"]
    assert report["raw_effective_speaker_count"] == 2
    assert report["aligned_effective_speaker_count"] == 1
    assert report["speakers"]["SPEAKER_01"]["word_overlap_duration"] == 0
    assert report["speakers"]["SPEAKER_01"]["aligned_words"] == 0
    assert report["quality_gate_passed"] is False


def test_optional_mode_records_quality_warning_instead_of_failing(tmp_path: Path):
    class OneBackend:
        name = "sherpa-onnx"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [SpeakerTurn(0, 10, "speaker_00")]

    _, report = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 10, "text": "متن"}],
        DiarizationConfig(enabled=True, required=False, num_speakers=2),
        backend=OneBackend(),
    )
    assert report["effective_speaker_count"] == 1
    assert "requested=2 raw_effective=1 aligned_effective=0" in report["quality_warning"]


def test_meaningful_second_speaker_passes_effective_gate(tmp_path: Path):
    class HealthyBackend:
        name = "sherpa-onnx"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [SpeakerTurn(0, 400, "speaker_00"), SpeakerTurn(400, 480, "speaker_01")]

    words = [
        {"start": start, "end": start + 1, "word": f" واژه{index}"}
        for index, start in enumerate((1, 3, 5, 401, 403, 405))
    ]
    aligned, report = run_diarization(
        tmp_path / "audio.wav",
        [{
            "start": 0, "end": 480,
            "text": " ".join(word["word"].strip() for word in words),
            "words": words,
        }],
        DiarizationConfig(enabled=True, required=True, num_speakers=2),
        backend=HealthyBackend(),
    )
    assert report["effective_speaker_count"] == 2
    assert report["aligned_effective_speaker_count"] == 2
    assert {row["speaker"] for row in aligned} == {"SPEAKER_00", "SPEAKER_01"}


def test_two_speakers_survive_raw_normalized_aligned_and_export(tmp_path: Path):
    class ThreePeriodBackend:
        name = "sherpa-onnx"

        def diarize(self, audio: Path, *, num_speakers: int | None):
            return [
                SpeakerTurn(0, 5, "speaker_00"),
                SpeakerTurn(5, 10, "speaker_01"),
                SpeakerTurn(10, 15, "speaker_00"),
            ]

    words = [
        {"start": second, "end": second + 0.8, "word": f" واژه{index}"}
        for index, second in enumerate((1, 2, 3, 6, 7, 8, 11, 12, 13))
    ]
    text = " ".join(word["word"].strip() for word in words)
    aligned, report = run_diarization(
        tmp_path / "audio.wav",
        [{"start": 0, "end": 15, "text": text, "words": words}],
        DiarizationConfig(enabled=True, required=True, num_speakers=2),
        backend=ThreePeriodBackend(),
        output=tmp_path / "diarization" / "diarization.json",
    )
    assert len(report["raw_speakers"]) == 2
    assert len(report["normalized_speakers"]) == 2
    assert len({row["speaker"] for row in aligned}) == 2
    assert report["aligned_effective_speaker_count"] == 2

    root = tmp_path
    (root / "final").mkdir()
    (root / "accuracy").mkdir()
    (root / "final/transcript.final.md").write_text(text, encoding="utf-8")
    (root / "final/transcript.final.txt").write_text(text, encoding="utf-8")
    (root / "accuracy/transcript.consensus.json").write_text(
        __import__("json").dumps({"segments": aligned}, ensure_ascii=False),
        encoding="utf-8",
    )
    result = export_final_outputs(root)
    assert result["exported_effective_speaker_count"] == 2
    assert "گوینده ۲" in (root / "delivery/transcript.timestamped.md").read_text(
        encoding="utf-8"
    )


def test_speaker_aware_three_file_export(tmp_path: Path):
    root = tmp_path / "job"
    for directory in ("final", "accuracy"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "final/transcript.final.md").write_text("fallback", encoding="utf-8")
    (root / "final/transcript.final.txt").write_text("fallback", encoding="utf-8")
    (root / "accuracy/transcript.consensus.json").write_text(
        '{"segments":[{"start":0,"end":1,"text":"سلام","speaker":"SPEAKER_00"},'
        '{"start":1,"end":2,"text":"بله","speaker":"SPEAKER_01"}]}', encoding="utf-8"
    )
    export_final_outputs(root)
    assert {p.name for p in (root / "delivery").iterdir()} == {
        "transcript.md", "transcript.txt", "transcript.timestamped.md"
    }
    assert "گوینده ۱" in (root / "delivery/transcript.txt").read_text(encoding="utf-8")
    assert "گوینده ۲" in (root / "delivery/transcript.timestamped.md").read_text(encoding="utf-8")
