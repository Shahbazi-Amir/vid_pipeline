from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vid_pipeline.asr_model import AsrModelManager, ProvisionedAsrModel


def test_parallel_cold_provision_installs_once(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    manifest = {
        "name": "large-v3-turbo",
        "artifact_version": "v1",
        "asset_sha256": "x" * 64,
    }
    installs = 0

    monkeypatch.setattr(AsrModelManager, "_manifest", lambda self: manifest)
    monkeypatch.setattr(
        AsrModelManager,
        "_validate_cached_model",
        classmethod(lambda cls, path, _manifest: Path(path).is_dir()),
    )

    def install(self, _manifest, version_dir, model_dir):
        nonlocal installs
        installs += 1
        time.sleep(0.05)
        model_dir.mkdir(parents=True)
        return ProvisionedAsrModel(model_dir, manifest, False)

    monkeypatch.setattr(AsrModelManager, "_install_missing_model", install)
    managers = [AsrModelManager(cache_root=cache), AsrModelManager(cache_root=cache)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda manager: manager.provision("large-v3-turbo"), managers))

    assert installs == 1
    assert sorted(result.cache_hit for result in results) == [False, True]
    assert (cache / ".provision.lock").is_file()
