import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mtml import clock as clock_module
from mtml.clock import load_clock


def test_frozen_virtual_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLOCK_START", "2025-11-01T03:00:00")
    clock = load_clock(tmp_path / "clock.json")

    assert clock.now() == datetime(2025, 11, 1, 3, 0)


def test_all_services_share_first_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    real = datetime(2026, 9, 27, 12, 0)
    monkeypatch.setattr(clock_module, "real_now", lambda: real)
    monkeypatch.setenv("CLOCK_START", "2025-09-01T03:00:00")
    monkeypatch.setenv("CLOCK_SPEED", "1440")
    monkeypatch.setenv("CLOCK_END", "2025-11-01T03:00:00")
    load_clock(tmp_path / "clock.json")

    real = datetime(2026, 9, 27, 12, 1)
    monkeypatch.setenv("CLOCK_START", "2030-01-01T00:00:00")
    other = load_clock(tmp_path / "clock.json")
    assert other.now() == datetime(2025, 9, 2, 3, 0)

    real = datetime(2026, 9, 28, 12, 0)
    assert other.now() == datetime(2025, 11, 1, 3, 0)
    assert json.loads((tmp_path / "clock.json").read_text())["speed"] == 1440


def test_without_clock_start_time_is_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CLOCK_START", raising=False)
    clock = load_clock(tmp_path / "clock.json")

    assert abs(clock.now() - clock_module.real_now()) < timedelta(seconds=2)
