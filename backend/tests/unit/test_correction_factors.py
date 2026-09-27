import shutil
from pathlib import Path

import pytest

from app.ml.store import ForecastStore
from app.schemas.correction_factors import CorrectionFactorsRead

REFERENCE = Path(__file__).parents[3] / "dataset/external/correction_factors.json"


@pytest.fixture
def reference() -> CorrectionFactorsRead:
    return CorrectionFactorsRead.model_validate_json(
        REFERENCE.read_text(encoding="utf-8")
    )


def test_repository_reference_matches_schema(reference: CorrectionFactorsRead):
    types = {item.type: item for item in reference.scenario_types}

    assert types["heavy_rain"].scope == "city"
    assert types["route_closed"].default_multiplier == 0.0
    for item in reference.scenario_types:
        assert item.min <= item.default_multiplier <= item.max


@pytest.mark.parametrize(
    ("kind", "factor", "value", "routes", "expected"),
    [
        ("scenario", "heavy_rain", 0.96, None, None),
        ("scenario", "heavy_rain", 0.96, [7], "city_scenario_cannot_target_routes"),
        ("scenario", "route_shortened", 0.45, None, "route_scenario_requires_routes"),
        ("scenario", "route_shortened", 0.45, [7], None),
        ("scenario", "route_closed", 0.9, [7], "value_out_of_reference_range"),
        ("scenario", "tornado", 0.5, None, "unknown_scenario_type"),
        ("model_factor", "holiday", 1.5, None, None),
        ("model_factor", "weather", 1.0, None, "unknown_model_factor"),
    ],
)
def test_scenario_is_checked_against_reference(
    reference: CorrectionFactorsRead,
    kind: str,
    factor: str,
    value: float,
    routes: list[int] | None,
    expected: str | None,
):
    assert reference.validate_scenario(kind, factor, value, routes) == expected


def test_patch_of_legacy_scenario_skips_scope_but_keeps_range(
    reference: CorrectionFactorsRead,
):
    assert (
        reference.validate_scenario(
            "scenario", "heavy_rain", 0.9, [7], check_scope=False
        )
        is None
    )
    assert (
        reference.validate_scenario(
            "scenario", "heavy_rain", 1.9, [7], check_scope=False
        )
        == "value_out_of_reference_range"
    )


async def test_store_reads_reference_without_forecast(tmp_path: Path):
    (tmp_path / "reference").mkdir()
    shutil.copy(REFERENCE, tmp_path / "reference/correction_factors.json")
    store = ForecastStore(tmp_path)

    assert await store.load() is False
    assert store.snapshot is None
    assert store.correction_factors is not None
    assert store.correction_factors.scenario_types[0].type == "heavy_rain"
