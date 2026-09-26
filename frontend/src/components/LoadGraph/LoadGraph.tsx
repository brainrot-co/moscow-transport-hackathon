import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import arrow from '../../assets/grow-icon.svg';
import type { ForecastRow } from '../../api/forecast';
import { routeColors } from '../../data/routeColors';
import { tramRoutes, type TramRoute } from '../Map/routes';

interface LoadPoint {
    label: string;
    value: number;
}

interface ChartPoint extends LoadPoint {
    x: number;
    y: number;
}

interface RouteSeries {
    route: TramRoute;
    color: string;
    points: ChartPoint[];
    path: string;
}

const MAX_SELECTED_ROUTES = 3;
const PREFERRED_ROUTE_IDS = ['7', '17', '26'];
const HOURS = Array.from({ length: 24 }, (_, index) => index);
const TICK_INDEXES = [0, 4, 8, 12, 16, 20, 23];
const INITIAL_CHART_WIDTH = 680;
const CHART_HEIGHT = 270;
const PLOT = { left: 68, right: 60, top: 34, bottom: 48 };
const PLOT_HEIGHT = CHART_HEIGHT - PLOT.top - PLOT.bottom;
const BASELINE_Y = PLOT.top + PLOT_HEIGHT;

const rowValue = (row: ForecastRow) => (
    row.source === 'mixed'
        ? (row.value ?? 0) + (row.yhat ?? 0)
        : row.value ?? row.yhat
);

const formatCompact = (value: number) => new Intl.NumberFormat('ru-RU', {
    notation: 'compact',
    maximumFractionDigits: 1,
}).format(value);

const niceMaximum = (value: number) => {
    if (value <= 0) return 1;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    return Math.ceil(value / magnitude) * magnitude;
};

const createSmoothPath = (points: ChartPoint[]) => {
    if (points.length < 2) {
        return '';
    }

    let path = `M ${points[0].x} ${points[0].y}`;

    for (let index = 0; index < points.length - 1; index += 1) {
        const previous = points[Math.max(0, index - 1)];
        const current = points[index];
        const next = points[index + 1];
        const afterNext = points[Math.min(points.length - 1, index + 2)];
        const controlOneX = current.x + (next.x - previous.x) / 6;
        const controlOneY = current.y + (next.y - previous.y) / 6;
        const controlTwoX = next.x - (afterNext.x - current.x) / 6;
        const controlTwoY = next.y - (afterNext.y - current.y) / 6;

        path += ` C ${controlOneX} ${controlOneY}, ${controlTwoX} ${controlTwoY}, ${next.x} ${next.y}`;
    }

    return path;
};

interface LoadGraphProps {
    rows: ForecastRow[];
}

export default function LoadGraph({ rows }: LoadGraphProps) {
    const chartRef = useRef<SVGSVGElement>(null);
    const pickerRef = useRef<HTMLDivElement>(null);
    const [selectedRouteIds, setSelectedRouteIds] = useState<string[]>([]);
    const [routeMenuOpen, setRouteMenuOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState<number | null>(null);
    const [chartWidth, setChartWidth] = useState(INITIAL_CHART_WIDTH);
    const plotWidth = chartWidth - PLOT.left - PLOT.right;
    const availableRouteIds = useMemo(() => new Set(
        rows
            .filter((row) => row.availability !== 'unavailable' && row.availability !== 'cold_start' && rowValue(row) !== null)
            .map((row) => String(row.route)),
    ), [rows]);

    const effectiveSelectedRouteIds = useMemo(() => {
        const retained = selectedRouteIds.filter((routeId) => availableRouteIds.has(routeId));
        if (retained.length > 0) return retained;
        const preferred = PREFERRED_ROUTE_IDS.filter((routeId) => availableRouteIds.has(routeId));
        return [...preferred, ...availableRouteIds]
            .filter((routeId, index, all) => all.indexOf(routeId) === index)
            .slice(0, MAX_SELECTED_ROUTES);
    }, [availableRouteIds, selectedRouteIds]);

    const selectedRoutes = useMemo(() => (
        effectiveSelectedRouteIds
            .map((routeId) => tramRoutes.find((route) => route.id === routeId))
            .filter((route): route is TramRoute => Boolean(route))
    ), [effectiveSelectedRouteIds]);

    const valuesByRoute = useMemo(() => {
        const result = new Map<string, Map<number, number>>();
        rows.forEach((row) => {
            const value = rowValue(row);
            const hourMatch = row.ts.match(/T(\d{2})/);
            if (value === null || !hourMatch) return;
            const routeId = String(row.route);
            const routeValues = result.get(routeId) ?? new Map<number, number>();
            routeValues.set(Number(hourMatch[1]), value);
            result.set(routeId, routeValues);
        });
        return result;
    }, [rows]);

    const yMaximum = useMemo(() => niceMaximum(Math.max(
        0,
        ...effectiveSelectedRouteIds.flatMap((routeId) => [...(valuesByRoute.get(routeId)?.values() ?? [])]),
    )), [effectiveSelectedRouteIds, valuesByRoute]);

    useEffect(() => {
        const chart = chartRef.current;

        if (!chart) {
            return;
        }

        const updateChartWidth = () => {
            const bounds = chart.getBoundingClientRect();

            if (bounds.width === 0 || bounds.height === 0) {
                return;
            }

            const nextWidth = Math.max(520, Math.round((bounds.width / bounds.height) * CHART_HEIGHT));
            setChartWidth((currentWidth) => currentWidth === nextWidth ? currentWidth : nextWidth);
        };

        updateChartWidth();

        const observer = new ResizeObserver(updateChartWidth);
        observer.observe(chart);

        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!routeMenuOpen) {
            return;
        }

        const handleOutsideClick = (event: globalThis.PointerEvent) => {
            if (!pickerRef.current?.contains(event.target as Node)) {
                setRouteMenuOpen(false);
            }
        };

        document.addEventListener('pointerdown', handleOutsideClick);
        return () => document.removeEventListener('pointerdown', handleOutsideClick);
    }, [routeMenuOpen]);

    const routeSeries = useMemo<RouteSeries[]>(() => (
        selectedRoutes.map((route) => {
            const routeValues = valuesByRoute.get(route.id) ?? new Map<number, number>();
            const points = HOURS.map((hour) => ({
                label: `${String(hour).padStart(2, '0')}:00`,
                value: routeValues.get(hour) ?? 0,
            })).map((point, index, allPoints) => ({
                ...point,
                x: PLOT.left + (index / (allPoints.length - 1)) * plotWidth,
                y: PLOT.top + (1 - point.value / yMaximum) * PLOT_HEIGHT,
            }));

            return {
                route,
                color: routeColors[route.id] ?? '#f10624',
                points,
                path: createSmoothPath(points),
            };
        })
    ), [plotWidth, selectedRoutes, valuesByRoute, yMaximum]);

    const safeActiveIndex = Math.min(activeIndex ?? 0, HOURS.length - 1);
    const activeX = routeSeries[0]?.points[safeActiveIndex]?.x ?? PLOT.left;
    const tooltipWidth = 174;
    const tooltipHeight = 30 + routeSeries.length * 20;
    const tooltipX = Math.min(
        Math.max(activeX - tooltipWidth / 2, PLOT.left),
        chartWidth - PLOT.right - tooltipWidth,
    );
    const tooltipY = 3;

    const toggleRoute = (routeId: string) => {
        setSelectedRouteIds((currentIds) => {
            const retained = currentIds.filter((currentId) => availableRouteIds.has(currentId));
            const activeIds = retained.length > 0 ? retained : effectiveSelectedRouteIds;
            if (activeIds.includes(routeId)) {
                return activeIds.length === 1
                    ? activeIds
                    : activeIds.filter((currentId) => currentId !== routeId);
            }

            return activeIds.length >= MAX_SELECTED_ROUTES
                ? activeIds
                : [...activeIds, routeId];
        });
    };

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const clampedX = Math.min(Math.max(pointerX, PLOT.left), chartWidth - PLOT.right);
        const pointStep = plotWidth / Math.max(HOURS.length - 1, 1);
        const nearestIndex = Math.round((clampedX - PLOT.left) / pointStep);

        setActiveIndex(nearestIndex);
    };

    return (
        <div className={styles.loadGraph}>
            <div className={styles.graphTop}>
                <div className={styles.graphTitle}>
                    <img src={arrow} alt="" />
                    <div>
                        <h6>Сравнение маршрутов</h6>
                        <span>Сегодня · пассажиры по часам</span>
                    </div>
                </div>

                <div className={styles.routePicker} ref={pickerRef}>
                    <button
                        type="button"
                        className={clsx(styles.routePickerButton, routeMenuOpen && styles.routePickerButtonOpen)}
                        onClick={() => setRouteMenuOpen((isOpen) => !isOpen)}
                        aria-expanded={routeMenuOpen}
                        aria-haspopup="true"
                    >
                        Маршруты <b>{effectiveSelectedRouteIds.length}/{MAX_SELECTED_ROUTES}</b>
                        <span aria-hidden="true">⌄</span>
                    </button>

                    {routeMenuOpen && (
                        <div className={styles.routeMenu} role="menu" aria-label="Выбор маршрутов для сравнения">
                            <div className={styles.routeMenuHeader}>
                                <b>Выберите до 3 маршрутов</b>
                                <span>Линии показаны за сегодня</span>
                            </div>
                            <div className={styles.routeMenuList}>
                                {tramRoutes.map((route) => {
                                    const isSelected = effectiveSelectedRouteIds.includes(route.id);
                                    const isUnavailable = !availableRouteIds.has(route.id);
                                    const isDisabled = isUnavailable
                                        || (!isSelected && effectiveSelectedRouteIds.length >= MAX_SELECTED_ROUTES)
                                        || (isSelected && effectiveSelectedRouteIds.length === 1);

                                    return (
                                        <button
                                            key={route.id}
                                            type="button"
                                            role="menuitemcheckbox"
                                            aria-checked={isSelected}
                                            className={clsx(styles.routeOption, isSelected && styles.routeOptionSelected)}
                                            disabled={isDisabled}
                                            onClick={() => toggleRoute(route.id)}
                                        >
                                            <i style={{ backgroundColor: routeColors[route.id] }} />
                                            <span><b>№{route.id}</b>{route.name}</span>
                                            <em>{isUnavailable ? '—' : isSelected ? '✓' : '+'}</em>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>
            <div className={styles.routeLegend} aria-label="Выбранные маршруты">
                {selectedRoutes.map((route) => (
                    <button
                        key={route.id}
                        type="button"
                        title={route.name}
                        onClick={() => toggleRoute(route.id)}
                        disabled={selectedRoutes.length === 1}
                    >
                        <i style={{ backgroundColor: routeColors[route.id] }} />
                        <b>№{route.id}</b>
                        <span>{route.name}</span>
                        {selectedRoutes.length > 1 && <em aria-hidden="true">×</em>}
                    </button>
                ))}
            </div>

            <svg
                ref={chartRef}
                className={styles.chart}
                viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
                role="img"
                aria-label={`Сравнение пассажиропотока маршрутов ${effectiveSelectedRouteIds.join(', ')} за сегодня по часам`}
                onPointerMove={handlePointerMove}
                onPointerLeave={() => setActiveIndex(null)}
            >
                <defs>
                    <filter id="route-compare-glow" x="-20%" y="-40%" width="140%" height="180%">
                        <feGaussianBlur stdDeviation="3.5" result="blur" />
                    </filter>
                </defs>

                {[0, yMaximum / 2, yMaximum].map((value) => {
                    const y = PLOT.top + (1 - value / yMaximum) * PLOT_HEIGHT;

                    return (
                        <g key={value}>
                            <line className={styles.horizontalGrid} x1={PLOT.left} y1={y} x2={chartWidth - PLOT.right} y2={y} />
                            <text className={styles.axisLabel} x={PLOT.left - 14} y={y + 5} textAnchor="end">{formatCompact(value)}</text>
                        </g>
                    );
                })}

                {TICK_INDEXES.map((index) => {
                    const point = routeSeries[0]?.points[index];

                    if (!point) return null;

                    return (
                        <g key={point.label}>
                            <line className={styles.verticalGrid} x1={point.x} y1={PLOT.top} x2={point.x} y2={BASELINE_Y} />
                            <text className={styles.axisLabel} x={point.x} y={CHART_HEIGHT - 13} textAnchor="middle">{point.label}</text>
                        </g>
                    );
                })}

                {routeSeries.map((series) => (
                    <g key={series.route.id}>
                        <path d={series.path} className={styles.seriesGlow} stroke={series.color} filter="url(#route-compare-glow)" />
                        <path d={series.path} className={styles.seriesLine} stroke={series.color} />
                    </g>
                ))}

                {activeIndex !== null && (
                    <>
                        <line className={styles.activeGuide} x1={activeX} y1={PLOT.top} x2={activeX} y2={BASELINE_Y} />

                        {routeSeries.map((series) => {
                            const point = series.points[safeActiveIndex];

                            return (
                                <circle
                                    key={`point-${series.route.id}`}
                                    cx={point.x}
                                    cy={point.y}
                                    r="5"
                                    className={styles.activePoint}
                                    stroke={series.color}
                                />
                            );
                        })}

                        <g className={styles.tooltip} transform={`translate(${tooltipX} ${tooltipY})`}>
                            <rect width={tooltipWidth} height={tooltipHeight} rx="10" />
                            <text x="12" y="19" className={styles.tooltipTitle}>
                                {routeSeries[0]?.points[safeActiveIndex]?.label ?? ''}
                            </text>
                            {routeSeries.map((series, index) => (
                                <g key={`tooltip-${series.route.id}`} transform={`translate(0 ${29 + index * 20})`}>
                                    <circle cx="14" cy="7" r="4" fill={series.color} />
                                    <text x="24" y="11" className={styles.tooltipValue}>
                                        №{series.route.id} · {Math.round(series.points[safeActiveIndex].value).toLocaleString('ru-RU')} пасс.
                                    </text>
                                </g>
                            ))}
                        </g>
                    </>
                )}
            </svg>
        </div>
    );
}
