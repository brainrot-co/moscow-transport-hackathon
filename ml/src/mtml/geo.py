import json

import numpy as np
import pandas as pd

from mtml.data import ALL_ROUTES, ROOT

SPRAVOCHNIK_PATH = ROOT / "dataset" / "spravochniki" / "10_routes.xlsx"
# маршрутов 17, 25, 26, 28, 50 нет в справочнике, их остановки выгружены из OSM
OSM_ROUTES_PATH = ROOT / "dataset" / "external" / "osm_missing_routes.geojson"
EARTH_RADIUS_M = 6_371_000
# грубая рамка Москвы: точка за её пределами — ошибка в координатах
MOSCOW_BBOX = (55.1, 36.8, 56.1, 38.0)


def load_stop_sequences():
    """Справочник организаторов в приоритете, OSM — только для маршрутов, которых в нём нет."""
    order = pd.read_excel(SPRAVOCHNIK_PATH, sheet_name="Порядок_с_координатами")
    order = order[order["route_short_name"].isin(ALL_ROUTES)]
    sprav = pd.DataFrame(
        {
            "route": order["route_short_name"].astype(int),
            "direction_id": order["direction_id"].astype(int),
            "stop_sequence": order["stop_sequence"].astype(int),
            "stop_id": "sprav:" + order["stop_id"].astype(str),
            "stop_name": order["stop_name"],
            "lat": order["stop_lat"],
            "lon": order["stop_lon"],
            "source": "справочник",
            "source_date": pd.to_datetime(order["start_date"]).dt.strftime("%Y-%m-%d"),
        }
    )

    collection = json.loads(OSM_ROUTES_PATH.read_text())
    snapshot = collection["metadata"]["snapshot"][:10]
    osm = pd.DataFrame(
        [
            {
                "route": f["properties"]["route"],
                "direction_id": f["properties"]["direction_id"],
                "stop_sequence": f["properties"]["stop_sequence"],
                "stop_id": f"osm:{f['properties']['osm_node_id']}",
                "stop_name": f["properties"]["stop_name"],
                "lat": f["geometry"]["coordinates"][1],
                "lon": f["geometry"]["coordinates"][0],
                "source": "OSM",
                "source_date": snapshot,
            }
            for f in collection["features"]
            if f["properties"]["kind"] == "stop"
        ]
    )
    osm = osm[~osm["route"].isin(sprav["route"])]

    stops = pd.concat([sprav, osm], ignore_index=True)
    stops = stops.sort_values(["route", "direction_id", "stop_sequence"], ignore_index=True)
    _check_stops(stops)

    trips = stops.groupby(["route", "direction_id"])["stop_name"]
    stops["direction_name"] = trips.transform("first") + " — " + trips.transform("last")
    return stops


def _check_stops(stops: pd.DataFrame):
    missing = set(ALL_ROUTES) - set(stops["route"])
    if missing:
        raise ValueError(f"Нет остановок маршрутов {sorted(missing)}")
    south, west, north, east = MOSCOW_BBOX
    outside = stops[~stops["lat"].between(south, north) | ~stops["lon"].between(west, east)]
    if not outside.empty:
        raise ValueError(f"Остановки вне Москвы:\n{outside[['route', 'stop_name', 'lat', 'lon']]}")
    short = stops.groupby(["route", "direction_id"]).size().loc[lambda s: s < 2]
    if not short.empty:
        raise ValueError(f"Меньше двух остановок в направлении: {short.to_dict()}")


def distance_to_route_m(lat: np.ndarray, lon: np.ndarray, stops: pd.DataFrame):
    """Матрица [точка × маршрут]: расстояние в метрах до ближайшей остановки маршрута."""
    lat1, lon1 = np.radians(lat)[:, None], np.radians(lon)[:, None]
    lat2, lon2 = (
        np.radians(stops["lat"].to_numpy())[None],
        np.radians(stops["lon"].to_numpy())[None],
    )
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    dist = pd.DataFrame(
        2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)), columns=stops["route"].to_numpy()
    )
    return dist.T.groupby(level=0).min().T
