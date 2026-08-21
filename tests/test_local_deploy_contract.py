from __future__ import annotations

from pathlib import Path

import yaml


def test_compose_exposes_web_and_scalable_worker() -> None:
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"web", "api", "worker", "redis", "database"} <= set(services)
    assert "8501:8501" in services["web"]["ports"]
    assert services["web"]["environment"]["VID_PIPELINE_SERVER_URL"] == "http://api:8000"
    assert "pipeline-storage:/data/storage" in services["worker"]["volumes"]
    assert "model-cache:/models" in services["worker"]["volumes"]


def test_worker_image_contains_url_downloader_and_model_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (root / "docker" / "Dockerfile.worker").read_text(encoding="utf-8")
    assert 'worker = [' in pyproject and '"yt-dlp"' in pyproject
    assert "COPY models/asr ./models/asr" in dockerfile
    assert "VID_PIPELINE_ASR_MANIFEST=/app/models/asr/large-v3-turbo-ct2-v1.json" in dockerfile


def test_local_web_launcher_scales_workers() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "scripts" / "local_web.sh").read_text(encoding="utf-8")
    assert 'VID_PIPELINE_WORKER_REPLICAS:-2' in launcher
    assert '--scale worker="$workers"' in launcher
