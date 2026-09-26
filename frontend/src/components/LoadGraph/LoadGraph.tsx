import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import arrow from '../../assets/grow-icon.svg';
<<<<<<< HEAD
import type { ForecastRow } from '../../api/forecast';
=======
import { routeColors } from '../../data/routeColors';
import { tramRoutes, type TramRoute } from '../Map/routes';
>>>>>>> feature/stops_and_func

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
const INITIAL_ROUTE_IDS = ['5', '26', '28'];
const HOURS = Array.from({ length: 16 }, (_, index) => index + 6);
const TICK_INDEXES = [0, 3, 6, 9, 12, 15];
const INITIAL_CHART_WIDTH = 680;
const CHART_HEIGHT = 270;
const PLOT = { left: 68, right: 60, top: 34, bottom: 48 };
const PLOT_HEIGHT = CHART_HEIGHT - PLOT.top - PLOT.bottom;
const BASELINE_Y = PLOT.top + PLOT_HEIGHT;

const clamp = (value: number) => Math.max(6, Math.min(96, value));
const gaussian = (value: number, center: number, spread: number) => (
    Math.exp(-((value - center) ** 2) / (2 * spread ** 2))
);

const createRouteDayPoints = (route: TramRoute): LoadPoint[] => {
    const seed = Number(route.id);
    const baseline = 24 + route.load * 0.42;
    const morningAmplitude = 12 + (seed % 5) * 3;
    const eveningAmplitude = 12 + ((seed + 2) % 5) * 3;
    const morningCenter = 8 + (seed % 3) * 0.5;
    const eveningCenter = 17 + (seed % 4) * 0.4;

    return HOURS.map((hour) => {
        const morningPeak = morningAmplitude * gaussian(hour, morningCenter, 1.25);
        const eveningPeak = eveningAmplitude * gaussian(hour, eveningCenter, 1.65);
        const middayPulse = (5 + (seed % 4)) * gaussian(hour, 13.5 + (seed % 2) * 0.5, 1.8);
        const routeRhythm = Math.sin((hour - 6) * (0.66 + (seed % 4) * 0.08) + seed * 0.45) * 4.5;

        return {
            label: `${String(hour).padStart(2, '0')}:00`,
            value: Math.round(clamp(baseline + morningPeak + eveningPeak + middayPulse + routeRhythm)),
        };
    });
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

<<<<<<< HEAD
interface LoadGraphProps {
    rows: ForecastRow[];
}

export default function LoadGraph({ rows }: LoadGraphProps) {
    const [selectedRange, setSelectedRange] = useState('Сегодня');
=======
export default function LoadGraph() {
    const chartRef = useRef<SVGSVGElement>(null);
    const pickerRef = useRef<HTMLDivElement>(null);
    const [selectedRouteIds, setSelectedRouteIds] = useState(INITIAL_ROUTE_IDS);
    const [routeMenuOpen, setRouteMenuOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState<number | null>(null);
    const [chartWidth, setChartWidth] = useState(INITIAL_CHART_WIDTH);
    const plotWidth = chartWidth - PLOT.left - PLOT.right;

    const selectedRoutes = useMemo(() => (
        selectedRouteIds
            .map((routeId) => tramRoutes.find((route) => route.id === routeId))
            .filter((route): route is TramRoute => Boolean(route))
    ), [selectedRouteIds]);

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
            const points = createRouteDayPoints(route).map((point, index, allPoints) => ({
                ...point,
                x: PLOT.left + (index / (allPoints.length - 1)) * plotWidth,
                y: PLOT.top + ((100 - point.value) / 100) * PLOT_HEIGHT,
            }));

            return {
                route,
                color: routeColors[route.id] ?? '#f10624',
                points,
                path: createSmoothPath(points),
            };
        })
    ), [plotWidth, selectedRoutes]);

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
            if (currentIds.includes(routeId)) {
                return currentIds.length === 1
                    ? currentIds
                    : currentIds.filter((currentId) => currentId !== routeId);
            }

            return currentIds.length >= MAX_SELECTED_ROUTES
                ? currentIds
                : [...currentIds, routeId];
        });
    };

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const clampedX = Math.min(Math.max(pointerX, PLOT.left), chartWidth - PLOT.right);
        const pointStep = plotWidth / (HOURS.length - 1);
        const nearestIndex = Math.round((clampedX - PLOT.left) / pointStep);

        setActiveIndex(nearestIndex);
    };
>>>>>>> feature/stops_and_func

    return (
        <div className={styles.loadGraph}>
            <div className={styles.graphTop}>
                <div className={styles.graphTitle}>
                    <img src={arrow} alt="" />
                    <div>
                        <h6>Сравнение маршрутов</h6>
                        <span>Сегодня · загрузка по часам</span>
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
                        Маршруты <b>{selectedRouteIds.length}/{MAX_SELECTED_ROUTES}</b>
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
                                    const isSelected = selectedRouteIds.includes(route.id);
                                    const isDisabled = (!isSelected && selectedRouteIds.length >= MAX_SELECTED_ROUTES)
                                        || (isSelected && selectedRouteIds.length === 1);

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
                                            <em>{isSelected ? '✓' : '+'}</em>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>
<<<<<<< HEAD
            <div className={styles.graphData}>
                {rows.length === 0 ? (
                    <p>Нет данных для выбранного периода</p>
                ) : (
                    rows.slice(0, 24).map((row) => (
                        <div key={`${row.route}-${row.ts}`} className={styles.graphPoint}>
                            <span>{row.route}</span>
                            <strong>{row.value ?? row.yhat ?? '—'}</strong>
                        </div>
                    ))
                )}
            </div>
=======

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
                aria-label={`Сравнение загрузки маршрутов ${selectedRouteIds.join(', ')} за сегодня по часам`}
                onPointerMove={handlePointerMove}
                onPointerLeave={() => setActiveIndex(null)}
            >
                <defs>
                    <filter id="route-compare-glow" x="-20%" y="-40%" width="140%" height="180%">
                        <feGaussianBlur stdDeviation="3.5" result="blur" />
                    </filter>
                </defs>

                {[0, 50, 100].map((value) => {
                    const y = PLOT.top + ((100 - value) / 100) * PLOT_HEIGHT;

                    return (
                        <g key={value}>
                            <line className={styles.horizontalGrid} x1={PLOT.left} y1={y} x2={chartWidth - PLOT.right} y2={y} />
                            <text className={styles.axisLabel} x={PLOT.left - 14} y={y + 5} textAnchor="end">{value}%</text>
                        </g>
                    );
                })}

                {TICK_INDEXES.map((index) => {
                    const point = routeSeries[0].points[index];

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
                                {routeSeries[0].points[safeActiveIndex].label}
                            </text>
                            {routeSeries.map((series, index) => (
                                <g key={`tooltip-${series.route.id}`} transform={`translate(0 ${29 + index * 20})`}>
                                    <circle cx="14" cy="7" r="4" fill={series.color} />
                                    <text x="24" y="11" className={styles.tooltipValue}>
                                        №{series.route.id} · {series.points[safeActiveIndex].value}%
                                    </text>
                                </g>
                            ))}
                        </g>
                    </>
                )}
            </svg>
>>>>>>> feature/stops_and_func
        </div>
    );
}
