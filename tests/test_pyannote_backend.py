import os
from pathlib import Path

import pytest

from vid_pipeline.diarization import DiarizationError
from vid_pipeline.pyannote_diarization import (
    PYANNOTE_MODEL_ID,
    PyannoteDiarizationBackend,
    annotation_to_speaker_turns,
)


class Segment:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class Annotation:
    def __init__(self, rows):
        self.rows = rows

    def itertracks(self, yield_label=False):
        assert yield_label is True
        for index, (start, end, speaker) in enumerate(self.rows):
            yield Segment(start, end), index, speaker


class Output:
    def __init__(self, regular, exclusive=None):
        self.speaker_diarization = regular
        self.exclusive_speaker_diarization = exclusive


def fake_waveform(_audio):
    return {"waveform": "preloaded-pcm", "sample_rate": 16_000}


def test_annotation_adapter_sorts_turns():
    turns = annotation_to_speaker_turns(
        Annotation([(2.0, 3.0, "B"), (0.0, 1.0, "A")])
    )
    assert [(t.start, t.end, t.speaker) for t in turns] == [
        (0.0, 1.0, "A"),
        (2.0, 3.0, "B"),
    ]


def test_exclusive_timeline_is_preferred_and_num_speakers_is_passed():
    captured = {}

    class Pipeline:
        def __call__(self, audio, **kwargs):
            captured["call"] = (audio, kwargs)
            return Output(
                Annotation([(0.0, 10.0, "regular")]),
                Annotation([(0.0, 4.0, "host"), (4.0, 10.0, "teacher")]),
            )

    def loader(model_id, **kwargs):
        captured["load"] = (model_id, kwargs)
        return Pipeline()

    backend = PyannoteDiarizationBackend(
        token="hf_test_secret",
        pipeline_loader=loader,
        waveform_loader=fake_waveform,
    )
    turns = backend.diarize(Path("/tmp/audio.wav"), num_speakers=2)

    assert captured["load"][0] == PYANNOTE_MODEL_ID
    assert captured["load"][1]["token"] == "hf_test_secret"
    assert captured["call"][0] == {
        "waveform": "preloaded-pcm",
        "sample_rate": 16_000,
    }
    assert captured["call"][1] == {"num_speakers": 2}
    assert [t.speaker for t in turns] == ["host", "teacher"]
    assert backend.last_used_exclusive is True


def test_regular_timeline_is_fallback():
    class Pipeline:
        def __call__(self, audio, **kwargs):
            return Output(Annotation([(0.0, 2.0, "A")]), None)

    backend = PyannoteDiarizationBackend(
        token="hf_test_secret",
        pipeline_loader=lambda *args, **kwargs: Pipeline(),
        waveform_loader=fake_waveform,
    )
    turns = backend.diarize(Path("/tmp/audio.wav"), num_speakers=2)
    assert [t.speaker for t in turns] == ["A"]
    assert backend.last_used_exclusive is False


def test_preloaded_waveform_is_reused_across_diarization_attempts():
    loads = 0

    class Pipeline:
        def __call__(self, audio, **kwargs):
            return Output(Annotation([(0.0, 2.0, "A")]), None)

    def loader(_audio):
        nonlocal loads
        loads += 1
        return fake_waveform(_audio)

    backend = PyannoteDiarizationBackend(
        token="hf_test_secret",
        pipeline_loader=lambda *args, **kwargs: Pipeline(),
        waveform_loader=loader,
    )
    path = Path("/tmp/audio.wav")
    backend.diarize(path, num_speakers=None)
    backend.diarize(path, num_speakers=None)
    assert loads == 1


def test_missing_hf_token_fails_cleanly(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("VID_PIPELINE_PYANNOTE_TOKEN", raising=False)
    with pytest.raises(
        DiarizationError,
        match="HF_TOKEN is required for pyannote Community-1 model download",
    ):
        PyannoteDiarizationBackend(pipeline_loader=lambda *args, **kwargs: object())


def test_loader_exception_does_not_leak_token():
    secret = "hf_super_secret_value"

    def loader(*args, **kwargs):
        raise RuntimeError(f"upstream accidentally echoed {kwargs['token']}")

    with pytest.raises(DiarizationError) as error:
        PyannoteDiarizationBackend(token=secret, pipeline_loader=loader)
    assert secret not in str(error.value)


def test_dedicated_env_token_works_when_standard_hf_token_is_empty(monkeypatch):
    monkeypatch.setenv("VID_PIPELINE_PYANNOTE_TOKEN", "hf_dedicated_test")
    monkeypatch.setenv("HF_TOKEN", "")
    captured = {}

    class Pipeline:
        def __call__(self, audio, **kwargs):
            return Output(Annotation([(0.0, 1.0, "A")]), None)

    def loader(model_id, **kwargs):
        captured.update(kwargs)
        return Pipeline()

    backend = PyannoteDiarizationBackend(
        pipeline_loader=loader,
        waveform_loader=fake_waveform,
    )
    backend.diarize(Path("/tmp/audio.wav"), num_speakers=1)
    assert captured["token"] == "hf_dedicated_test"
    assert os.environ["HF_TOKEN"] == "hf_dedicated_test"


def test_existing_standard_hf_token_is_not_overwritten(monkeypatch):
    monkeypatch.setenv("VID_PIPELINE_PYANNOTE_TOKEN", "hf_dedicated_test")
    monkeypatch.setenv("HF_TOKEN", "hf_standard_test")

    backend = PyannoteDiarizationBackend(
        pipeline_loader=lambda *args, **kwargs: object(),
        waveform_loader=fake_waveform,
    )
    assert backend is not None
    assert os.environ["HF_TOKEN"] == "hf_standard_test"


def test_waveform_loader_failure_is_sanitized():
    secret = "signed-media-query-secret"

    class Pipeline:
        def __call__(self, audio, **kwargs):
            raise AssertionError("pipeline must not run")

    def broken_loader(_audio):
        raise RuntimeError(secret)

    backend = PyannoteDiarizationBackend(
        token="hf_test_secret",
        pipeline_loader=lambda *args, **kwargs: Pipeline(),
        waveform_loader=broken_loader,
    )
    with pytest.raises(DiarizationError, match="waveform load failed: RuntimeError") as error:
        backend.diarize(Path("/tmp/audio.wav"), num_speakers=None)
    assert secret not in str(error.value)
