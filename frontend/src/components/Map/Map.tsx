import { useEffect, useMemo, useRef, useState } from 'react';
import {
    LngLatBounds,
    Map as MapLibreMap,
    setWorkerUrl,
    type FilterSpecification,
    type GeoJSONSource,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

import styles from './Map.module.scss';
import { routeColors } from '../../data/routeColors';
import RouteDetailsModal from '../RouteDetailsModal/RouteDetailsModal';
import type { ForecastMeta, ForecastRow } from '../../api/forecast';
import {
    findRoute,
    tramRoutes,
} from './routes';
import {
    fallbackRouteStops,
    getUniqueStopOptions,
    isRawStopsGeoJson,
    normaliseRouteStops,
    routesFromStops,
    routeStopsToGeoJson,
    type RouteStop,
    type RoutesMapGeoJson,
    type StopsMapGeoJson,
} from './transitData';

setWorkerUrl(workerUrl);

const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark';
const ALL_ROUTES = 'all';
const INITIAL_ROUTES_GEOJSON = routesFromStops(fallbackRouteStops);
const INITIAL_STOPS_GEOJSON = routeStopsToGeoJson(fallbackRouteStops);
const DATA_LAYER_IDS = new Set([
    'route-glow',
    'route-inner-glow',
    'route-lines',
    'route-focus',
    'route-hit-area',
    'stop-glow',
    'tram-stops',
    'selected-stop',
]);

type MapTheme = 'dark' | 'light';

interface MapProps {
    theme?: MapTheme;
    rows?: ForecastRow[];
    meta?: ForecastMeta | null;
}

const networkBounds = new LngLatBounds();

tramRoutes.forEach((route) => {
    route.coordinates.forEach((coordinate) => networkBounds.extend(coordinate));
});

const getRouteBounds = (routeId: string, stops: RouteStop[]) => {
    const bounds = new LngLatBounds();
    const routeStops = stops.filter((tramStop) => tramStop.routeId === routeId);

    if (routeStops.length > 0) {
        routeStops.forEach((tramStop) => bounds.extend(tramStop.coordinates));
    } else {
        findRoute(routeId).coordinates.forEach((coordinate) => bounds.extend(coordinate));
    }

    return bounds;
};

const getNetworkBounds = (stops: RouteStop[]) => {
    if (stops.length === 0) {
        return networkBounds;
    }

    const bounds = new LngLatBounds();
    stops.forEach((tramStop) => bounds.extend(tramStop.coordinates));

    return bounds;
};

const applyMapTheme = (map: MapLibreMap, theme: MapTheme) => {
    const styleLayers = map.getStyle().layers ?? [];
    const isLight = theme === 'light';

    styleLayers.forEach((layer) => {
        const layerId = layer.id.toLowerCase();

        if (DATA_LAYER_IDS.has(layer.id)) {
            return;
        }

        if (layer.type === 'background') {
            map.setPaintProperty(layer.id, 'background-color', isLight ? '#edf3f7' : '#061321');
            return;
        }

        if (layer.type === 'fill') {
            const fillColor = layerId.includes('water')
                ? (isLight ? '#d9eaf3' : '#071a2c')
                : layerId.includes('building')
                    ? (isLight ? '#e1e6eb' : '#10243a')
                    : layerId.includes('park')
                        || layerId.includes('wood')
                        || layerId.includes('grass')
                        || layerId.includes('landcover')
                        ? (isLight ? '#dcebdd' : '#0a1d2d')
                        : (isLight ? '#edf1f4' : '#081827');

            map.setPaintProperty(layer.id, 'fill-color', fillColor);
            map.setPaintProperty(layer.id, 'fill-outline-color', isLight ? '#d1d8df' : '#10283d');
            return;
        }

        if (layer.type === 'line') {
            const lineColor = layerId.includes('motorway') || layerId.includes('trunk')
                ? (isLight ? '#aebdcb' : '#254563')
                : layerId.includes('road')
                    || layerId.includes('street')
                    || layerId.includes('bridge')
                    || layerId.includes('tunnel')
                    ? (isLight ? '#c3ced9' : '#193550')
                    : layerId.includes('boundary')
                        ? (isLight ? '#91a2b5' : '#27435f')
                        : layerId.includes('water')
                            ? (isLight ? '#b8d5e4' : '#12314b')
                            : (isLight ? '#cbd5df' : '#122b43');

            map.setPaintProperty(layer.id, 'line-color', lineColor);
            return;
        }

        if (layer.type === 'symbol') {
            map.setPaintProperty(layer.id, 'text-color', isLight ? '#5f7083' : '#6f87a3');
            map.setPaintProperty(layer.id, 'text-halo-color', isLight ? '#f8fafc' : '#061321');
            map.setPaintProperty(layer.id, 'text-halo-width', 1.1);
            map.setPaintProperty(layer.id, 'icon-opacity', 0.55);
            return;
        }

        if (layer.type === 'circle') {
            map.setPaintProperty(layer.id, 'circle-color', isLight ? '#bccbda' : '#193750');
            map.setPaintProperty(layer.id, 'circle-stroke-color', isLight ? '#f8fafc' : '#071421');
        }
    });
};

const TramIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3h10M9 3V1m6 2V1M6 6.5h12v10H6zM8.5 19 7 21m8.5-2 1.5 2M8.5 13h.01m7-.01h.01M8 8h8v3H8z" />
    </svg>
);

const PinIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11Z" />
        <circle cx="12" cy="10" r="2.2" />
    </svg>
);

const RecenterIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m4 11 16-7-7 16-2-7-7-2Z" />
    </svg>
);

export default function Map({ theme = 'dark', rows = [], meta = null }: MapProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<MapLibreMap | null>(null);
    const [mapReady, setMapReady] = useState(false);
    const [routeFilter, setRouteFilter] = useState(ALL_ROUTES);
    const [selectedStop, setSelectedStop] = useState(ALL_ROUTES);
    const [focusedRouteId, setFocusedRouteId] = useState<string | null>(null);
    const [detailsRouteId, setDetailsRouteId] = useState<string | null>(null);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [routeStops, setRouteStops] = useState<RouteStop[]>(fallbackRouteStops);
    const [mapRoutes, setMapRoutes] = useState<RoutesMapGeoJson>(INITIAL_ROUTES_GEOJSON);
    const [mapStops, setMapStops] = useState<StopsMapGeoJson>(INITIAL_STOPS_GEOJSON);
    const routeLoads = useMemo(() => {
        const totals = new globalThis.Map<string, number>();
        rows.forEach((row) => {
            if (row.availability === 'cold_start' || row.availability === 'unavailable') return;
            const amount = row.source === 'mixed'
                ? (row.value ?? 0) + (row.yhat ?? 0)
                : row.value ?? row.yhat;
            if (amount !== null) {
                const routeId = String(row.route);
                totals.set(routeId, (totals.get(routeId) ?? 0) + amount);
            }
        });
        const maximum = Math.max(0, ...totals.values());
        return new globalThis.Map([...totals].map(([routeId, amount]) => [
            routeId,
            maximum > 0 ? Math.max(1, Math.round((amount / maximum) * 100)) : 0,
        ]));
    }, [rows]);

    const focusedRoute = focusedRouteId ? findRoute(focusedRouteId) : null;
    const detailsRoute = detailsRouteId ? findRoute(detailsRouteId) : null;
    const focusedLoad = focusedRoute ? routeLoads.get(focusedRoute.id) ?? null : null;
    const stopOptions = useMemo(() => {
        const matchingStops = routeFilter === ALL_ROUTES
            ? routeStops
            : routeStops.filter((tramStop) => tramStop.routeId === routeFilter);

        return getUniqueStopOptions(matchingStops);
    }, [routeFilter, routeStops]);

    useEffect(() => {
        let cancelled = false;

        fetch('/data/route_stops.geojson')
            .then((response) => response.json() as Promise<unknown>)
            .then((stopsData) => {
                if (cancelled || !isRawStopsGeoJson(stopsData)) {
                    return;
                }

                const nextStops = normaliseRouteStops(stopsData);

                setRouteStops(nextStops);
                setMapStops(routeStopsToGeoJson(nextStops));
                setMapRoutes(routesFromStops(nextStops));
            }).catch(() => {
                // The embedded prototype data remains available if the static files cannot be loaded.
            });

        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!containerRef.current || mapRef.current) {
            return;
        }

        const map = new MapLibreMap({
            container: containerRef.current,
            style: MAP_STYLE_URL,
            bounds: networkBounds,
            fitBoundsOptions: {
                padding: { top: 54, right: 58, bottom: 54, left: 58 },
            },
            minZoom: 8,
            maxZoom: 17,
            renderWorldCopies: false,
            attributionControl: { compact: true },
        });

        mapRef.current = map;

        map.on('styleimagemissing', (event) => {
            if (!map.hasImage(event.id)) {
                map.addImage(event.id, {
                    width: 1,
                    height: 1,
                    data: new Uint8Array([0, 0, 0, 0]),
                });
            }
        });

        map.on('load', () => {
            map.addSource('tram-routes', {
                type: 'geojson',
                data: INITIAL_ROUTES_GEOJSON,
            });
            map.addSource('tram-stops', {
                type: 'geojson',
                data: INITIAL_STOPS_GEOJSON,
            });

            map.addLayer({
                id: 'route-glow',
                type: 'line',
                source: 'tram-routes',
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': ['interpolate', ['linear'], ['zoom'], 9, 9, 13, 20],
                    'line-opacity': 0.28,
                    'line-blur': 8,
                },
            });
            map.addLayer({
                id: 'route-inner-glow',
                type: 'line',
                source: 'tram-routes',
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': ['interpolate', ['linear'], ['zoom'], 9, 5, 13, 11],
                    'line-opacity': 0.52,
                    'line-blur': 3.5,
                },
            });
            map.addLayer({
                id: 'route-lines',
                type: 'line',
                source: 'tram-routes',
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2.4, 13, 4.4],
                    'line-opacity': 1,
                },
            });
            map.addLayer({
                id: 'route-focus',
                type: 'line',
                source: 'tram-routes',
                filter: ['==', ['get', 'id'], ''],
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
                paint: {
                    'line-color': ['get', 'color'],
                    'line-width': ['interpolate', ['linear'], ['zoom'], 9, 3.5, 13, 6],
                    'line-opacity': 1,
                },
            });
            map.addLayer({
                id: 'route-hit-area',
                type: 'line',
                source: 'tram-routes',
                layout: {
                    'line-cap': 'round',
                    'line-join': 'round',
                },
                paint: {
                    'line-color': '#ffffff',
                    'line-width': 18,
                    'line-opacity': 0,
                },
            });
            map.addLayer({
                id: 'stop-glow',
                type: 'circle',
                source: 'tram-stops',
                paint: {
                    'circle-color': ['get', 'color'],
                    'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 5, 13, 9],
                    'circle-opacity': 0.24,
                    'circle-blur': 0.6,
                },
            });
            map.addLayer({
                id: 'tram-stops',
                type: 'circle',
                source: 'tram-stops',
                paint: {
                    'circle-color': '#f3f7fd',
                    'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 2.2, 13, 3.6],
                    'circle-stroke-color': ['get', 'color'],
                    'circle-stroke-width': 2,
                    'circle-opacity': 0.96,
                },
            });
            map.addLayer({
                id: 'selected-stop',
                type: 'circle',
                source: 'tram-stops',
                filter: ['==', ['get', 'id'], ''],
                paint: {
                    'circle-color': '#ffffff',
                    'circle-radius': 7,
                    'circle-stroke-color': ['get', 'color'],
                    'circle-stroke-width': 4,
                },
            });

            setMapReady(true);
        });

        map.on('click', 'route-hit-area', (event) => {
            const routeId = event.features?.[0]?.properties?.id;

            if (typeof routeId === 'string') {
                setFocusedRouteId(routeId);
            }
        });
        map.on('mouseenter', 'route-hit-area', () => {
            map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'route-hit-area', () => {
            map.getCanvas().style.cursor = '';
        });
        map.on('click', 'tram-stops', (event) => {
            const properties = event.features?.[0]?.properties;
            const stopId = properties?.id;
            const routeId = properties?.routeId;

            if (typeof stopId === 'string') {
                setSelectedStop(stopId);
            }

            if (typeof routeId === 'string') {
                setFocusedRouteId(routeId);
            }
        });
        map.on('mouseenter', 'tram-stops', () => {
            map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'tram-stops', () => {
            map.getCanvas().style.cursor = '';
        });

        return () => {
            map.remove();
            mapRef.current = null;
        };
    }, []);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        applyMapTheme(map, theme);
    }, [mapReady, theme]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        (map.getSource('tram-routes') as GeoJSONSource | undefined)?.setData(mapRoutes);
        (map.getSource('tram-stops') as GeoJSONSource | undefined)?.setData(mapStops);
    }, [mapReady, mapRoutes, mapStops]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        const routeExpression: FilterSpecification | null = routeFilter === ALL_ROUTES
            ? null
            : ['==', ['get', 'id'], routeFilter];
        const stopExpression: FilterSpecification | null = routeFilter === ALL_ROUTES
            ? null
            : ['==', ['get', 'routeId'], routeFilter];

        ['route-glow', 'route-inner-glow', 'route-lines', 'route-hit-area'].forEach((layerId) => {
            map.setFilter(layerId, routeExpression);
        });
        ['stop-glow', 'tram-stops'].forEach((layerId) => {
            map.setFilter(layerId, stopExpression);
        });

        map.fitBounds(
            routeFilter === ALL_ROUTES ? getNetworkBounds(routeStops) : getRouteBounds(routeFilter, routeStops),
            {
                padding: { top: 58, right: 62, bottom: 58, left: 62 },
                duration: 750,
                maxZoom: routeFilter === ALL_ROUTES ? 11.2 : 13.5,
            },
        );
    }, [mapReady, routeFilter, routeStops]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        map.setFilter(
            'route-focus',
            focusedRouteId
                ? ['==', ['get', 'id'], focusedRouteId]
                : ['==', ['get', 'id'], ''],
        );
    }, [focusedRouteId, mapReady]);

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        map.setFilter('selected-stop', ['==', ['get', 'id'], selectedStop]);

        if (selectedStop !== ALL_ROUTES) {
            const tramStop = stopOptions.find((item) => item.id === selectedStop);

            if (tramStop) {
                map.flyTo({
                    center: tramStop.coordinates,
                    zoom: 14,
                    duration: 750,
                });
            }
        }
    }, [mapReady, selectedStop, stopOptions]);

    const handleRouteChange = (routeId: string) => {
        setRouteFilter(routeId);
        setSelectedStop(ALL_ROUTES);

        if (routeId !== ALL_ROUTES) {
            setFocusedRouteId(routeId);
        }
    };

    const handleStopChange = (stopId: string) => {
        setSelectedStop(stopId);

        const tramStop = stopOptions.find((item) => item.id === stopId);

        if (tramStop) {
            setFocusedRouteId(tramStop.routeId);
        }
    };

    const resetView = () => {
        mapRef.current?.fitBounds(getNetworkBounds(routeStops), {
            padding: { top: 58, right: 62, bottom: 58, left: 62 },
            duration: 750,
            maxZoom: 11.2,
        });
    };

    const loadStatus = !focusedRoute
        ? ''
        : focusedLoad === null
            ? 'Нет данных для прогноза'
        : focusedLoad >= 75
        ? 'Высокая загрузка'
        : focusedLoad >= 55
            ? 'Средняя загрузка'
            : 'Низкая загрузка';
    const loadStatusColor = !focusedRoute
        ? '#38d1a3'
        : focusedLoad === null
            ? '#8c9eb8'
        : focusedLoad >= 75
            ? '#f10624'
            : focusedLoad >= 55
                ? '#ffb74d'
                : '#38d1a3';

    return (
        <div className={styles.mapShell}>
            <div ref={containerRef} className={styles.mapCanvas} />
            <div className={styles.mapShade} aria-hidden="true" />

            {filtersOpen && (
            <div className={styles.filtersPanel}>
                <button
                    type="button"
                    className={styles.closeFiltersButton}
                    onClick={() => setFiltersOpen(false)}
                    aria-label="Свернуть фильтры карты"
                    title="Свернуть фильтры"
                >
                    ‹
                </button>

                <label className={styles.filterGroup}>
                    <span className={styles.filterLabel}>
                        <span className={styles.filterIcon}><TramIcon /></span>
                        Маршрут
                    </span>
                    <span className={styles.selectWrap}>
                        <select
                            value={routeFilter}
                            onChange={(event) => handleRouteChange(event.target.value)}
                        >
                            <option value={ALL_ROUTES}>Все маршруты</option>
                            {tramRoutes.map((route) => (
                                <option key={route.id} value={route.id}>
                                    {route.id}: {route.name}
                                </option>
                            ))}
                        </select>
                    </span>
                </label>

                <label className={styles.filterGroup}>
                    <span className={styles.filterLabel}>
                        <span className={styles.filterIcon}><PinIcon /></span>
                        Остановка
                    </span>
                    <span className={styles.selectWrap}>
                        <select
                            value={selectedStop}
                            onChange={(event) => handleStopChange(event.target.value)}
                        >
                            <option value={ALL_ROUTES}>Все остановки</option>
                            {stopOptions.map((tramStop) => (
                                <option key={tramStop.id} value={tramStop.id}>
                                    {routeFilter === ALL_ROUTES ? `№${tramStop.routeId} · ` : ''}{tramStop.name}
                                </option>
                            ))}
                        </select>
                    </span>
                </label>

            </div>
            )}

            {!filtersOpen && (
                <button
                    type="button"
                    className={styles.openFiltersButton}
                    onClick={() => setFiltersOpen(true)}
                    aria-label="Открыть фильтры карты"
                >
                    <span><TramIcon /></span>
                    Фильтры
                    <b>›</b>
                </button>
            )}

            <div className={styles.mapControls}>
                <button
                    type="button"
                    onClick={() => mapRef.current?.zoomIn({ duration: 250 })}
                    aria-label="Приблизить карту"
                >
                    +
                </button>
                <button
                    type="button"
                    onClick={() => mapRef.current?.zoomOut({ duration: 250 })}
                    aria-label="Отдалить карту"
                >
                    −
                </button>
                <button
                    type="button"
                    onClick={resetView}
                    aria-label="Показать всю сеть"
                    className={styles.recenterButton}
                >
                    <RecenterIcon />
                </button>
            </div>

            {focusedRoute && (
                <div
                    className={styles.routeCard}
                    style={{ borderColor: `${routeColors[focusedRoute.id]}55` }}
                >
                    <span
                        className={styles.routeCardIcon}
                        style={{
                            color: routeColors[focusedRoute.id],
                            backgroundColor: `${routeColors[focusedRoute.id]}2b`,
                        }}
                    >
                        <TramIcon />
                    </span>
                    <div className={styles.routeCardBody}>
                        <div className={styles.routeCardTop}>
                            <div>
                                <h3>Маршрут {focusedRoute.id}</h3>
                                <p title={focusedRoute.name}>{focusedRoute.name}</p>
                            </div>
                            <div className={styles.routeCardActions}>
                                <button
                                    type="button"
                                    className={styles.openRouteDetails}
                                    onClick={() => setDetailsRouteId(focusedRoute.id)}
                                    aria-label={`Открыть подробности маршрута ${focusedRoute.id}`}
                                    title="Открыть подробности"
                                >
                                    ›
                                </button>
                                <button
                                    type="button"
                                    className={styles.closeRouteCard}
                                    onClick={() => setFocusedRouteId(null)}
                                    aria-label={`Закрыть карточку маршрута ${focusedRoute.id}`}
                                    title="Закрыть"
                                >
                                    ×
                                </button>
                            </div>
                        </div>
                        <div
                            className={styles.loadLine}
                            style={{ color: loadStatusColor }}
                        >
                            <span className={styles.loadDot} />
                            <p>{loadStatus}</p>
                        </div>
                        <strong>{focusedLoad === null ? '—' : `${focusedLoad}%`}</strong>
                        <span className={styles.progressTrack}>
                            <span
                                style={{
                                    width: `${focusedLoad ?? 0}%`,
                                    backgroundColor: routeColors[focusedRoute.id],
                                }}
                            />
                        </span>
                    </div>
                </div>
            )}

            <div className={styles.legend}>
                <span><i className={styles.low} />Низкая</span>
                <span><i className={styles.medium} />Средняя</span>
                <span><i className={styles.high} />Высокая</span>
            </div>

            {detailsRoute && (
                <RouteDetailsModal
                    route={{ ...detailsRoute, load: routeLoads.get(detailsRoute.id) ?? 0 }}
                    stops={routeStops.filter((tramStop) => tramStop.routeId === detailsRoute.id)}
                    theme={theme}
                    rows={rows.filter((row) => row.route === Number(detailsRoute.id))}
                    meta={meta}
                    onClose={() => setDetailsRouteId(null)}
                />
            )}
        </div>
    );
}
