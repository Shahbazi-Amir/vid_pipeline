from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "assemble_reviewed_chunks.py"
SPEC = spec_from_file_location("assemble_reviewed_chunks", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def reviewed(body: str) -> str:
    return (
        "# عنوان\n\n"
        "منبع: https://example.com  \n\n"
        "> این متن فقط از روی صوت استخراج شده است. توضیح.\n\n"
        f"{body}\n"
    )


def test_extract_body_removes_generated_header() -> None:
    assert MODULE.extract_body(reviewed("پاراگراف اصلی.")) == "پاراگراف اصلی."


def test_assemble_keeps_chunk_order_and_single_header(tmp_path: Path) -> None:
    (tmp_path / "chunk-001.md").write_text(reviewed("بخش دوم."), encoding="utf-8")
    (tmp_path / "chunk-000.md").write_text(reviewed("بخش اول."), encoding="utf-8")

    result = MODULE.assemble(tmp_path, "عنوان نهایی", "https://source.example")

    assert result.count("# عنوان نهایی") == 1
    assert result.index("بخش اول.") < result.index("بخش دوم.")
    assert "https://source.example" in result


def test_missing_preservation_notice_is_rejected() -> None:
    try:
        MODULE.extract_body("# عنوان\n\nمتن")
    except ValueError as exc:
        assert "preservation notice" in str(exc)
    else:
        raise AssertionError("invalid reviewed chunk was accepted")
