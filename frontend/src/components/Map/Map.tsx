import { useEffect, useMemo, useRef, useState } from 'react';
import {
    LngLatBounds,
    Map as MapLibreMap,
    setWorkerUrl,
    type FilterSpecification,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

import styles from './Map.module.scss';
import { routeColors } from '../../data/routeColors';
import {
    findRoute,
    routesGeoJson,
    stopsGeoJson,
    tramRoutes,
} from './routes';

setWorkerUrl(workerUrl);

const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark';
const ALL_ROUTES = 'all';

const networkBounds = new LngLatBounds();

tramRoutes.forEach((route) => {
    route.coordinates.forEach((coordinate) => networkBounds.extend(coordinate));
});

const getRouteBounds = (routeId: string) => {
    const bounds = new LngLatBounds();

    findRoute(routeId).coordinates.forEach((coordinate) => bounds.extend(coordinate));

    return bounds;
};

const applyDarkBlueTheme = (map: MapLibreMap) => {
    const styleLayers = map.getStyle().layers ?? [];

    styleLayers.forEach((layer) => {
        const layerId = layer.id.toLowerCase();

        if (layer.type === 'background') {
            map.setPaintProperty(layer.id, 'background-color', '#061321');
            return;
        }

        if (layer.type === 'fill') {
            const fillColor = layerId.includes('water')
                ? '#071a2c'
                : layerId.includes('building')
                    ? '#10243a'
                    : layerId.includes('park')
                        || layerId.includes('wood')
                        || layerId.includes('grass')
                        || layerId.includes('landcover')
                        ? '#0a1d2d'
                        : '#081827';

            map.setPaintProperty(layer.id, 'fill-color', fillColor);
            map.setPaintProperty(layer.id, 'fill-outline-color', '#10283d');
            return;
        }

        if (layer.type === 'line') {
            const lineColor = layerId.includes('motorway') || layerId.includes('trunk')
                ? '#254563'
                : layerId.includes('road')
                    || layerId.includes('street')
                    || layerId.includes('bridge')
                    || layerId.includes('tunnel')
                    ? '#193550'
                    : layerId.includes('boundary')
                        ? '#27435f'
                        : layerId.includes('water')
                            ? '#12314b'
                            : '#122b43';

            map.setPaintProperty(layer.id, 'line-color', lineColor);
            return;
        }

        if (layer.type === 'symbol') {
            map.setPaintProperty(layer.id, 'text-color', '#6f87a3');
            map.setPaintProperty(layer.id, 'text-halo-color', '#061321');
            map.setPaintProperty(layer.id, 'text-halo-width', 1.1);
            map.setPaintProperty(layer.id, 'icon-opacity', 0.55);
            return;
        }

        if (layer.type === 'circle') {
            map.setPaintProperty(layer.id, 'circle-color', '#193750');
            map.setPaintProperty(layer.id, 'circle-stroke-color', '#071421');
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

const ClockIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3.2 2" />
    </svg>
);

const RecenterIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m4 11 16-7-7 16-2-7-7-2Z" />
    </svg>
);

export default function Map() {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<MapLibreMap | null>(null);
    const [mapReady, setMapReady] = useState(false);
    const [routeFilter, setRouteFilter] = useState(ALL_ROUTES);
    const [selectedStop, setSelectedStop] = useState(ALL_ROUTES);
    const [timeRange, setTimeRange] = useState('12:00 — 20:00');
    const [focusedRouteId, setFocusedRouteId] = useState<string | null>(null);
    const [filtersOpen, setFiltersOpen] = useState(false);

    const focusedRoute = focusedRouteId ? findRoute(focusedRouteId) : null;
    const stopOptions = useMemo(() => {
        const routes = routeFilter === ALL_ROUTES
            ? tramRoutes
            : tramRoutes.filter((route) => route.id === routeFilter);

        return routes.flatMap((route) => route.stops.map((tramStop) => ({
            ...tramStop,
            routeId: route.id,
        })));
    }, [routeFilter]);

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
            applyDarkBlueTheme(map);

            map.addSource('tram-routes', {
                type: 'geojson',
                data: routesGeoJson,
            });
            map.addSource('tram-stops', {
                type: 'geojson',
                data: stopsGeoJson,
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
            routeFilter === ALL_ROUTES ? networkBounds : getRouteBounds(routeFilter),
            {
                padding: { top: 58, right: 62, bottom: 58, left: 62 },
                duration: 750,
                maxZoom: routeFilter === ALL_ROUTES ? 11.2 : 13.5,
            },
        );
    }, [mapReady, routeFilter]);

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
        mapRef.current?.fitBounds(networkBounds, {
            padding: { top: 58, right: 62, bottom: 58, left: 62 },
            duration: 750,
            maxZoom: 11.2,
        });
    };

    const loadStatus = !focusedRoute
        ? ''
        : focusedRoute.load >= 75
        ? 'Высокая загрузка'
        : focusedRoute.load >= 55
            ? 'Средняя загрузка'
            : 'Низкая загрузка';
    const loadStatusColor = !focusedRoute
        ? '#38d1a3'
        : focusedRoute.load >= 75
            ? '#f10624'
            : focusedRoute.load >= 55
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
                                    {tramStop.name}
                                </option>
                            ))}
                        </select>
                    </span>
                </label>

                <label className={styles.filterGroup}>
                    <span className={styles.filterLabel}>
                        <span className={styles.filterIcon}><ClockIcon /></span>
                        Время
                    </span>
                    <span className={styles.selectWrap}>
                        <select
                            value={timeRange}
                            onChange={(event) => setTimeRange(event.target.value)}
                        >
                            <option>06:00 — 12:00</option>
                            <option>12:00 — 20:00</option>
                            <option>20:00 — 00:00</option>
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
                        <div
                            className={styles.loadLine}
                            style={{ color: loadStatusColor }}
                        >
                            <span className={styles.loadDot} />
                            <p>{loadStatus}</p>
                        </div>
                        <strong>{focusedRoute.load}%</strong>
                        <span className={styles.progressTrack}>
                            <span
                                style={{
                                    width: `${focusedRoute.load}%`,
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
        </div>
    );
}
