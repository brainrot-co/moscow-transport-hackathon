import argparse
import json

from mtml.data import ROOT
from mtml.geo import OSM_ROUTES_PATH, SPRAVOCHNIK_PATH, load_stop_sequences

OUT_DIR = ROOT / "dataset" / "external"
CSV_PATH = OUT_DIR / "route_stops.csv"
GEOJSON_PATH = OUT_DIR / "route_stops.geojson"


def main():
    argparse.ArgumentParser(
        description="Остановки 10 маршрутов: справочник + OSM -> dataset/external/"
    ).parse_args()
    if not OSM_ROUTES_PATH.exists():
        raise FileNotFoundError(
            f"Нет {OSM_ROUTES_PATH}: запустите uv run python ml/scripts/fetch_osm_routes.py"
        )

    stops = load_stop_sequences()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stops.to_csv(CSV_PATH, index=False)

    properties = [c for c in stops.columns if c not in ("lat", "lon")]
    collection = {
        "type": "FeatureCollection",
        "metadata": {
            "sources": {
                "справочник": SPRAVOCHNIK_PATH.relative_to(ROOT).as_posix(),
                "OSM": OSM_ROUTES_PATH.relative_to(ROOT).as_posix(),
            },
            "license_osm": "ODbL, © участники OpenStreetMap",
        },
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.lon, row.lat]},
                "properties": {name: getattr(row, name) for name in properties},
            }
            for row in stops.itertuples()
        ],
    }
    GEOJSON_PATH.write_text(
        json.dumps(collection, ensure_ascii=False, indent=1, default=int), encoding="utf-8"
    )

    summary = stops.groupby(["route", "source"]).agg(
        directions=("direction_id", "nunique"), stops=("stop_id", "size")
    )
    print(summary.to_string())
    print(f"Всего {len(stops)} остановок -> {CSV_PATH}, {GEOJSON_PATH}")


if __name__ == "__main__":
    main()
