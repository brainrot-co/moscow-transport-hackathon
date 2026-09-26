import argparse
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# в справочнике организаторов нет геометрии этих маршрутов, dataset/README.md:84-86
MISSING_ROUTES = (17, 25, 26, 28, 50)
MOSCOW_BBOX = (55.49, 37.30, 55.96, 37.97)
# основной сервер часто перегружен, зеркало Mail.ru тоже отвечает на запросы на дату:
# на 25.12.2025 у маршрута 17 конечная «Останкино», как в срезе марта 2025, а сейчас
# «Усадьба Останкино»
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
ROUNDS = 4
ROUND_PAUSE_SECONDS = 30
USER_AGENT = "moscow-transport-hackathon/0.1 (tram routes snapshot)"
STOP_ROLES = ("stop", "stop_entry_only", "stop_exit_only")


def fetch_route(route: int, snapshot: str):
    south, west, north, east = MOSCOW_BBOX
    query = (
        f'[out:json][timeout:180][date:"{snapshot}"];'
        f'rel["type"="route"]["route"="tram"]["ref"="{route}"]({south},{west},{north},{east})->.r;'
        ".r out geom;node(r.r);out body;"
    )
    body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for round_no in range(ROUNDS):
        for endpoint in ENDPOINTS:
            request = urllib.request.Request(
                endpoint, data=body, headers={"User-Agent": USER_AGENT}
            )
            try:
                with urllib.request.urlopen(request, timeout=200) as response:
                    payload = json.load(response)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                errors.append(f"{endpoint}: {error}")
                continue
            # при перегрузке Overpass может ответить 200 и описать ошибку в remark
            if "remark" in payload:
                errors.append(f"{endpoint}: {payload['remark']}")
                continue
            return payload["elements"], endpoint
        if round_no < ROUNDS - 1:
            time.sleep(ROUND_PAUSE_SECONDS * (round_no + 1))
    raise RuntimeError(f"Overpass не ответил по маршруту {route}: {errors[-1]}")


def route_features(route: int, elements: list[dict[str, Any]]):
    names = {e["id"]: e.get("tags", {}).get("name") for e in elements if e["type"] == "node"}
    relations = sorted((e for e in elements if e["type"] == "relation"), key=lambda e: e["id"])
    if not relations:
        raise ValueError(f"Маршрута {route} нет в OSM на эту дату")

    features = []
    for direction_id, relation in enumerate(relations):
        tags = relation["tags"]
        common = {
            "route": route,
            "direction_id": direction_id,
            "from": tags.get("from"),
            "to": tags.get("to"),
            "osm_relation_id": relation["id"],
        }
        tracks = [
            [[point["lon"], point["lat"]] for point in member["geometry"]]
            for member in relation["members"]
            if member["type"] == "way" and member.get("role", "") == ""
        ]
        stops = [
            member
            for member in relation["members"]
            if member["type"] == "node" and member.get("role") in STOP_ROLES
        ]
        if not tracks or len(stops) < 2:
            raise ValueError(
                f"Маршрут {route}, relation {relation['id']}: "
                f"рельсов {len(tracks)}, остановок {len(stops)} — разметка неполная"
            )

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "MultiLineString", "coordinates": tracks},
                "properties": {"kind": "track", **common},
            }
        )
        for sequence, stop in enumerate(stops, start=1):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [stop["lon"], stop["lat"]]},
                    "properties": {
                        "kind": "stop",
                        **common,
                        "stop_sequence": sequence,
                        "stop_name": names.get(stop["ref"]),
                        "osm_node_id": stop["ref"],
                    },
                }
            )
    return features


def main():
    parser = argparse.ArgumentParser(
        description="Трамвайные маршруты без геометрии в справочнике -> GeoJSON из OpenStreetMap"
    )
    parser.add_argument(
        "--date",
        type=dt.date.fromisoformat,
        default=dt.date(2025, 12, 25),
        help="дата среза OSM (по умолчанию 2025-12-25, внутри прогнозного периода)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("dataset/external/osm_missing_routes.geojson"),
        help="куда сохранить GeoJSON",
    )
    args = parser.parse_args()
    snapshot = f"{args.date.isoformat()}T00:00:00Z"

    features = []
    endpoints = {}
    for route in MISSING_ROUTES:
        elements, endpoint = fetch_route(route, snapshot)
        route_part = route_features(route, elements)
        features.extend(route_part)
        endpoints[route] = endpoint
        stops = sum(f["properties"]["kind"] == "stop" for f in route_part)
        directions = sum(f["properties"]["kind"] == "track" for f in route_part)
        print(
            f"Маршрут {route}: направлений {directions}, остановок {stops} ({endpoint})",
            flush=True,
        )

    collection = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "OpenStreetMap, Overpass API",
            "license": "ODbL, © участники OpenStreetMap",
            "snapshot": snapshot,
            "endpoints": endpoints,
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        },
        "features": features,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(collection, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Записано {len(features)} объектов -> {args.out}")


if __name__ == "__main__":
    main()
