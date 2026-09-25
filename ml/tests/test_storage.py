from pathlib import Path

import pytest

from mtml.storage import write_atomic, write_json_atomic


def test_failed_write_keeps_previous_file(tmp_path: Path):
    target = tmp_path / "file.txt"
    target.write_text("старое")

    def broken(tmp: Path):
        tmp.write_text("половина")
        raise OSError("диск кончился")

    with pytest.raises(OSError):
        write_atomic(target, broken)
    assert target.read_text() == "старое"
    assert list(tmp_path.iterdir()) == [target]


def test_unserializable_json_does_not_touch_file(tmp_path: Path):
    target = tmp_path / "state.json"
    target.write_text('{"watermark": "2025-10-31"}')
    payload: dict[str, object] = {}
    payload["self"] = payload

    with pytest.raises(ValueError):
        write_json_atomic(target, payload)
    assert target.read_text() == '{"watermark": "2025-10-31"}'
