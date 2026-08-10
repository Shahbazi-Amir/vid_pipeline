from pathlib import Path


def test_url_dispatch_option_contract():
    repository = Path(__file__).resolve().parents[1]
    workflow = (repository / ".github/workflows/process-video.yml").read_text(encoding="utf-8")
    client = (repository / "src/vid_pipeline/github_compat.py").read_text(encoding="utf-8")

    assert "language:" in workflow
    assert "no_editorial:" in workflow
    assert "LANGUAGE: ${{ inputs.language || 'fa' }}" in workflow
    assert "NO_EDITORIAL: ${{ inputs.no_editorial || 'false' }}" in workflow
    assert "if: env.NO_EDITORIAL != 'true'" in workflow
    assert '--language "$LANGUAGE"' in workflow
    assert "args+=(--no-editorial)" in workflow
    assert '"language": options.get("language", "fa")' in client
    assert '"no_editorial": str(options.get("no_editorial", True)).lower()' in client
