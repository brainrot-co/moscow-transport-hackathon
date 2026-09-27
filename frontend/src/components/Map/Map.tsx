import { useEffect, useMemo, useRef, useState } from 'react';
import {
    LngLatBounds,
    Map as MapLibreMap,
    Popup,
    setWorkerUrl,
    type ExpressionSpecification,
    type GeoJSONSource,
    type LngLatLike,
} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

import styles from './Map.module.scss';
import { routeColors } from '../../data/routeColors';
import InfoHint from '../InfoHint/InfoHint';
import RouteDetailsModal from '../RouteDetailsModal/RouteDetailsModal';
import type { ForecastMeta, ForecastRow, LoadLevel, RouteLoad, RouteLoadResponse } from '../../api/forecast';
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
    load?: RouteLoadResponse | null;
    focusedRouteId: string | null;
    onFocusedRouteChange: (routeId: string | null) => void;
}

const networkBounds = new LngLatBounds();

tramRoutes.forEach((route) => {
    route.coordinates.forEach((coordinate) => networkBounds.extend(coordinate));
});

const getRouteBounds = (routeId: string, stops: RouteStop[]) => {
    const bounds = new LngLatBounds();
    const matchingStops = stops.filter((tramStop) => tramStop.routeId === routeId);

    if (matchingStops.length > 0) {
        matchingStops.forEach((tramStop) => bounds.extend(tramStop.coordinates));
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

const LOAD_LEVEL_COLORS: Record<LoadLevel, string> = {
    low: '#38d1a3',
    medium: '#ffb74d',
    high: '#f10624',
};
const NO_LOAD_LEVEL_COLOR = '#8c9eb8';

const formatPassengers = (routeLoad: RouteLoad | null) => (
    routeLoad?.value == null ? '—' : `${Math.round(routeLoad.value).toLocaleString('ru-RU')} пасс.`
);

const formatDeviation = (routeLoad: RouteLoad | null) => {
    if (routeLoad?.value == null || routeLoad.ratio === null) {
        return null;
    }
    const deviation = Math.round((routeLoad.ratio - 1) * 100);
    return `${deviation > 0 ? '+' : ''}${deviation}% к норме`;
};

const describeNorm = (routeLoad: RouteLoad | null, dayKind: RouteLoadResponse['day_kind'] | undefined) => {
    if (!routeLoad?.norm_from || !routeLoad.norm_to) {
        return 'Недостаточно истории для нормы маршрута';
    }
    const days = dayKind === 'day_off' ? 'выходных и праздников' : 'рабочих дней';
    return `Норма маршрута: ${routeLoad.norm_days} ${days} с ${routeLoad.norm_from} по ${routeLoad.norm_to}`;
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

export default function Map({
    theme = 'dark',
    rows = [],
    meta = null,
    load = null,
    focusedRouteId,
    onFocusedRouteChange,
}: MapProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const mapRef = useRef<MapLibreMap | null>(null);
    const themeRef = useRef(theme);
    const routeFilterRef = useRef(ALL_ROUTES);
    const stopPopupRef = useRef<Popup | null>(null);
    const [mapReady, setMapReady] = useState(false);

    themeRef.current = theme;
    const [routeFilter, setRouteFilter] = useState(ALL_ROUTES);
    const [selectedStop, setSelectedStop] = useState(ALL_ROUTES);
    const [detailsRouteId, setDetailsRouteId] = useState<string | null>(null);
    const [filtersOpen, setFiltersOpen] = useState(false);
    const [showStops, setShowStops] = useState(true);
    const [showLoadColors, setShowLoadColors] = useState(false);
    const [routeStops, setRouteStops] = useState<RouteStop[]>(fallbackRouteStops);
    const [mapRoutes, setMapRoutes] = useState<RoutesMapGeoJson>(INITIAL_ROUTES_GEOJSON);
    const [mapStops, setMapStops] = useState<StopsMapGeoJson>(INITIAL_STOPS_GEOJSON);
    const showStopPopup = (map: MapLibreMap, coordinates: LngLatLike, name: string) => {
        stopPopupRef.current?.remove();

        const popup = new Popup({
            closeButton: false,
            closeOnClick: true,
            offset: 12,
            className: styles.stopPopup,
        })
            .setLngLat(coordinates)
            .setText(name)
            .addTo(map);

        popup.on('close', () => {
            if (stopPopupRef.current === popup) {
                stopPopupRef.current = null;
            }
        });
        stopPopupRef.current = popup;
    };
    const focusedRoute = focusedRouteId ? findRoute(focusedRouteId) : null;
    const detailsRoute = detailsRouteId ? findRoute(detailsRouteId) : null;
    const focusedLoad = focusedRoute
        ? load?.data.find((item) => String(item.route) === focusedRoute.id) ?? null
        : null;
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
            attributionControl: { compact: false },
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

            applyMapTheme(map, themeRef.current);
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => setMapReady(true));
            });
        });

        map.on('click', 'route-hit-area', (event) => {
            const routeId = event.features?.[0]?.properties?.id;

            if (typeof routeId === 'string') {
                setRouteFilter(routeId);
                setSelectedStop(ALL_ROUTES);
                onFocusedRouteChange(routeId);
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
            const stopName = properties?.name;

            if (
                routeFilterRef.current === ALL_ROUTES
                || routeId !== routeFilterRef.current
                || typeof stopId !== 'string'
            ) {
                return;
            }

            setSelectedStop(stopId);
            showStopPopup(
                map,
                event.lngLat,
                typeof stopName === 'string' ? stopName : 'Остановка',
            );
        });
        map.on('mouseenter', 'tram-stops', () => {
            map.getCanvas().style.cursor = 'pointer';
        });
        map.on('mouseleave', 'tram-stops', () => {
            map.getCanvas().style.cursor = '';
        });

        return () => {
            stopPopupRef.current?.remove();
            stopPopupRef.current = null;
            map.remove();
            mapRef.current = null;
        };
    }, [onFocusedRouteChange]);

    useEffect(() => {
        setRouteFilter(focusedRouteId ?? ALL_ROUTES);
        setSelectedStop(ALL_ROUTES);
    }, [focusedRouteId]);

    useEffect(() => {
        routeFilterRef.current = routeFilter;
        stopPopupRef.current?.remove();
        stopPopupRef.current = null;
    }, [routeFilter]);

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

        ['route-glow', 'route-inner-glow', 'route-lines', 'route-hit-area'].forEach((layerId) => {
            map.setFilter(layerId, null);
        });
        ['stop-glow', 'tram-stops'].forEach((layerId) => {
            map.setFilter(layerId, null);
        });

        map.fitBounds(
            focusedRouteId
                ? getRouteBounds(focusedRouteId, routeStops)
                : getNetworkBounds(routeStops),
            {
            padding: { top: 58, right: 62, bottom: 58, left: 62 },
            duration: 750,
                maxZoom: focusedRouteId ? 13.5 : 11.2,
            },
        );
    }, [focusedRouteId, mapReady, routeStops]);

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

        const visibility = showStops ? 'visible' : 'none';
        ['stop-glow', 'tram-stops', 'selected-stop'].forEach((layerId) => {
            map.setLayoutProperty(layerId, 'visibility', visibility);
        });

        if (!showStops) {
            stopPopupRef.current?.remove();
            stopPopupRef.current = null;
        }
    }, [mapReady, showStops]);

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
        onFocusedRouteChange(routeId === ALL_ROUTES ? null : routeId);
    };

    const handleStopChange = (stopId: string) => {
        setSelectedStop(stopId);

        const tramStop = stopOptions.find((item) => item.id === stopId);

        if (tramStop) {
            onFocusedRouteChange(tramStop.routeId);
            const map = mapRef.current;

            if (map) {
                showStopPopup(map, tramStop.coordinates, tramStop.name);
            }
        }
    };

    const resetView = () => {
        mapRef.current?.fitBounds(getNetworkBounds(routeStops), {
            padding: { top: 58, right: 62, bottom: 58, left: 62 },
            duration: 750,
            maxZoom: 11.2,
        });
    };

    const clearRouteFocus = () => {
        stopPopupRef.current?.remove();
        stopPopupRef.current = null;
        onFocusedRouteChange(null);
        setRouteFilter(ALL_ROUTES);
        setSelectedStop(ALL_ROUTES);
        setShowLoadColors(false);
    };

    const loadStatusColor = focusedLoad?.load_level
        ? LOAD_LEVEL_COLORS[focusedLoad.load_level]
        : NO_LOAD_LEVEL_COLOR;

    useEffect(() => {
        const map = mapRef.current;

        if (!map || !mapReady) {
            return;
        }

        const routeColor: ExpressionSpecification = showLoadColors && focusedRouteId
            ? [
                'case',
                ['==', ['get', 'id'], focusedRouteId],
                loadStatusColor,
                ['get', 'color'],
            ]
            : ['get', 'color'];
        const stopColor: ExpressionSpecification = showLoadColors && focusedRouteId
            ? [
                'case',
                ['==', ['get', 'routeId'], focusedRouteId],
                loadStatusColor,
                ['get', 'color'],
            ]
            : ['get', 'color'];
        const stopFill: string | ExpressionSpecification = showLoadColors && focusedRouteId
            ? [
                'case',
                ['==', ['get', 'routeId'], focusedRouteId],
                loadStatusColor,
                '#f3f7fd',
            ]
            : '#f3f7fd';

        ['route-glow', 'route-inner-glow', 'route-lines', 'route-focus'].forEach((layerId) => {
            map.setPaintProperty(layerId, 'line-color', routeColor);
        });
        map.setPaintProperty(
            'route-glow',
            'line-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'id'], focusedRouteId], 0.32, 0.008]
                : 0.28,
        );
        map.setPaintProperty(
            'route-inner-glow',
            'line-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'id'], focusedRouteId], 0.56, 0.025]
                : 0.52,
        );
        map.setPaintProperty(
            'route-lines',
            'line-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'id'], focusedRouteId], 1, 0.08]
                : 1,
        );
        map.setPaintProperty('stop-glow', 'circle-color', stopColor);
        map.setPaintProperty(
            'stop-glow',
            'circle-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'routeId'], focusedRouteId], 0.24, 0.01]
                : 0.24,
        );
        map.setPaintProperty('tram-stops', 'circle-color', stopFill);
        map.setPaintProperty(
            'tram-stops',
            'circle-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'routeId'], focusedRouteId], 0.96, 0.1]
                : 0.96,
        );
        map.setPaintProperty(
            'tram-stops',
            'circle-stroke-opacity',
            focusedRouteId
                ? ['case', ['==', ['get', 'routeId'], focusedRouteId], 1, 0.1]
                : 1,
        );
        map.setPaintProperty(
            'tram-stops',
            'circle-stroke-color',
            showLoadColors && focusedRouteId ? '#ffffff' : stopColor,
        );
        map.setPaintProperty('selected-stop', 'circle-stroke-color', stopColor);
    }, [focusedRouteId, loadStatusColor, mapReady, showLoadColors]);

    return (
        <div className={styles.mapShell}>
            <div
                ref={containerRef}
                className={`${styles.mapCanvas} ${mapReady ? styles.mapCanvasReady : ''}`}
            />
            <div className={styles.mapShade} aria-hidden="true" />

            {filtersOpen && (
            <div className={styles.filtersPanel}>
                <div className={styles.filterGroup}>
                    <div className={styles.filterLabel}>
                        <span className={styles.filterIcon}><TramIcon /></span>
                        <label htmlFor="map-route-filter">Маршрут</label>
                        <InfoHint
                            title="Фильтр маршрута на карте"
                            description="Оставляет в фокусе выбранный маршрут, его остановки и оперативную карточку с пассажиропотоком. Остальная сеть становится менее заметной."
                            usage="Выберите номер или кликните по линии на карте. Значение «Все маршруты» возвращает общий обзор сети."
                        />
                        <button
                            type="button"
                            className={styles.closeFiltersButton}
                            onClick={() => setFiltersOpen(false)}
                            aria-label="Свернуть фильтры карты"
                            title="Свернуть фильтры"
                        >
                            ×
                        </button>
                    </div>
                    <span className={styles.selectWrap}>
                        <select
                            id="map-route-filter"
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
                </div>

                <div className={styles.filterGroup}>
                    <div className={styles.filterLabel}>
                        <span className={styles.filterIcon}><PinIcon /></span>
                        <label htmlFor="map-stop-filter">Остановка</label>
                        <InfoHint
                            title="Фильтр остановки"
                            description="Показывает доступные остановки выбранного маршрута или всей сети и позволяет быстро перейти к нужной точке."
                            usage="Выберите остановку — карта приблизит её и покажет название. После выбора маршрута список автоматически сократится до его остановок."
                        />
                    </div>
                    <span className={styles.selectWrap}>
                        <select
                            id="map-stop-filter"
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
                </div>

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

            <div className={styles.mapInfo}>
                <InfoHint
                    title="Карта трамвайной сети"
                    description="Показывает геометрию маршрутов и остановки. Цвет контура соответствует маршруту, а выбранная линия выделяется на фоне остальной сети."
                    usage="Кликните по линии для выбора маршрута, по остановке — для её названия. Кнопки справа меняют масштаб и возвращают обзор всей сети; фильтры слева помогают быстро найти объект."
                />
            </div>

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

            <div className={styles.mapToggles}>
                <div className={styles.toggleWithInfo}>
                    <label className={styles.mapToggle}>
                        <input
                            type="checkbox"
                            checked={showStops}
                            onChange={(event) => setShowStops(event.target.checked)}
                        />
                        <span>Остановки</span>
                    </label>
                    <InfoHint
                        title="Отображение остановок"
                        description="Управляет видимостью точек остановок на карте и не меняет расчёты пассажиропотока."
                        usage="Отключите точки, если они мешают читать линии маршрутов. Включите обратно, чтобы выбирать остановки на карте."
                    />
                </div>
            </div>

            {focusedRoute && (
                <div className={styles.loadToggleRow}>
                    <label className={styles.mapToggle}>
                        <input
                            type="checkbox"
                            checked={showLoadColors}
                            onChange={(event) => setShowLoadColors(event.target.checked)}
                        />
                        <span>Цвет загруженности</span>
                    </label>
                    <InfoHint
                        title="Цвет загруженности"
                        description="Заменяет фирменный цвет выбранного маршрута на цвет его текущего уровня нагрузки: низкий, средний или высокий."
                        usage="Сначала выберите маршрут, затем включите переключатель. Легенда рядом подскажет значение цвета; выключение вернёт цвет номера маршрута."
                    />
                    {showLoadColors && (
                        <div className={styles.legend}>
                            <span><i className={styles.low} />Низкая</span>
                            <span><i className={styles.medium} />Средняя</span>
                            <span><i className={styles.high} />Высокая</span>
                        </div>
                    )}
                </div>
            )}

            {focusedRoute && (
                <div
                    className={`${styles.routeCard} ${
                        filtersOpen ? styles.routeCardBelowPanel : styles.routeCardBelowButton
                    }`}
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
                                <div className={styles.openRouteDetailsRow}>
                                    <InfoHint
                                        title="Подробный прогноз маршрута"
                                        description="Кнопка открывает модальное окно с подробным прогнозом выбранного маршрута: почасовой динамикой, диапазоном прогноза и действующими поправками."
                                        usage="Нажмите на стрелку, чтобы открыть прогноз. Закройте модальное окно, чтобы вернуться к карте."
                                    />
                                    <button
                                        type="button"
                                        className={styles.openRouteDetails}
                                        onClick={() => setDetailsRouteId(focusedRoute.id)}
                                        aria-label={`Открыть подробный прогноз маршрута ${focusedRoute.id}`}
                                        title="Открыть подробный прогноз"
                                    >
                                        ›
                                    </button>
                                </div>
                                <button
                                    type="button"
                                    className={styles.closeRouteCard}
                                    onClick={clearRouteFocus}
                                    aria-label={`Закрыть карточку маршрута ${focusedRoute.id}`}
                                    title="Закрыть"
                                >
                                    ×
                                </button>
                            </div>
                        </div>
                        <strong title={describeNorm(focusedLoad, load?.day_kind)}>
                            {formatPassengers(focusedLoad)}
                        </strong>
                        {formatDeviation(focusedLoad) && (
                            <span
                                className={styles.loadDeviation}
                                title={describeNorm(focusedLoad, load?.day_kind)}
                            >
                                {formatDeviation(focusedLoad)}
                            </span>
                        )}
                        <span className={styles.progressTrack}>
                            <span
                                style={{
                                    // медиана нормы — середина полосы, вдвое больше нормы — полная полоса
                                    width: `${Math.min(100, (focusedLoad?.ratio ?? 0) * 50)}%`,
                                    backgroundColor: routeColors[focusedRoute.id],
                                }}
                            />
                        </span>
                    </div>
                </div>
            )}

            {detailsRoute && (
                <RouteDetailsModal
                    route={detailsRoute}
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
