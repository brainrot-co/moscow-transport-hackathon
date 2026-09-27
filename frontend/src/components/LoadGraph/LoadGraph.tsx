import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import type { ForecastRow } from '../../api/forecast';
import { routeColors } from '../../data/routeColors';
import InfoHint from '../InfoHint/InfoHint';
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

interface ChartViewport {
    xMin: number;
    xMax: number;
    yMin: number;
    yMax: number;
}

const DEFAULT_SELECTED_ROUTES = 3;
const PREFERRED_ROUTE_IDS = ['7', '17', '26'];
const HOURS = Array.from({ length: 24 }, (_, index) => index);
const INITIAL_CHART_WIDTH = 680;
const CHART_HEIGHT = 270;
const PLOT = { left: 68, right: 60, top: 34, bottom: 48 };
const PLOT_HEIGHT = CHART_HEIGHT - PLOT.top - PLOT.bottom;
const BASELINE_Y = PLOT.top + PLOT_HEIGHT;
const FULL_X_MIN = 0;
const FULL_X_MAX = 23;

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
    const [tooltipScroll, setTooltipScroll] = useState({ top: 0, max: 1 });
    const [chartWidth, setChartWidth] = useState(INITIAL_CHART_WIDTH);
    const [viewport, setViewport] = useState<ChartViewport | null>(null);
    const dragRef = useRef<{
        pointerId: number;
        startX: number;
        startY: number;
        viewport: ChartViewport;
    } | null>(null);
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
            .slice(0, DEFAULT_SELECTED_ROUTES);
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
    const selectedRouteKey = effectiveSelectedRouteIds.join(',');
    const xMin = viewport?.xMin ?? FULL_X_MIN;
    const xMax = viewport?.xMax ?? FULL_X_MAX;
    const yMin = viewport?.yMin ?? 0;
    const yMax = viewport?.yMax ?? yMaximum;
    const xRange = xMax - xMin;
    const yRange = yMax - yMin;
    const isZoomed = viewport !== null;

    useEffect(() => {
        setViewport(null);
        setTooltipScroll({ top: 0, max: 1 });
    }, [selectedRouteKey, yMaximum]);

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
            })).map((point, index) => ({
                ...point,
                x: PLOT.left + ((index - xMin) / xRange) * plotWidth,
                y: PLOT.top + (1 - (point.value - yMin) / yRange) * PLOT_HEIGHT,
            }));

            return {
                route,
                color: routeColors[route.id] ?? '#f10624',
                points,
                path: createSmoothPath(points),
            };
        })
    ), [plotWidth, selectedRoutes, valuesByRoute, xMin, xRange, yMin, yRange]);

    const xTicks = useMemo(() => {
        const preferredSteps = [1, 2, 4, 6, 12];
        const step = preferredSteps.find((candidate) => xRange / candidate <= 6) ?? 12;
        const firstTick = Math.ceil(xMin / step) * step;
        const ticks: number[] = [];

        for (let hour = firstTick; hour <= xMax + 0.001; hour += step) {
            if (hour >= FULL_X_MIN && hour <= FULL_X_MAX) {
                ticks.push(hour);
            }
        }

        return ticks;
    }, [xMax, xMin, xRange]);

    const safeActiveIndex = Math.min(activeIndex ?? 0, HOURS.length - 1);
    const activeX = routeSeries[0]?.points[safeActiveIndex]?.x ?? PLOT.left;
    const tooltipWidth = 174;
    const tooltipHeight = Math.min(40 + routeSeries.length * 24, 130);
    const tooltipCanScroll = routeSeries.length > 3;
    const tooltipTrackHeight = Math.max(24, tooltipHeight - 48);
    const tooltipThumbHeight = Math.min(34, Math.max(22, tooltipTrackHeight * 0.45));
    const tooltipThumbOffset = tooltipCanScroll
        ? (tooltipScroll.top / Math.max(tooltipScroll.max, 1)) * (tooltipTrackHeight - tooltipThumbHeight)
        : 0;
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

            return [...activeIds, routeId];
        });
    };

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const drag = dragRef.current;

        if (drag) {
            const bounds = event.currentTarget.getBoundingClientRect();
            const deltaX = ((event.clientX - drag.startX) / bounds.width) * chartWidth;
            const deltaY = ((event.clientY - drag.startY) / bounds.height) * CHART_HEIGHT;
            const dragXRange = drag.viewport.xMax - drag.viewport.xMin;
            const dragYRange = drag.viewport.yMax - drag.viewport.yMin;
            const unclampedXMin = drag.viewport.xMin - (deltaX / plotWidth) * dragXRange;
            const unclampedYMin = drag.viewport.yMin + (deltaY / PLOT_HEIGHT) * dragYRange;
            const nextXMin = Math.min(
                Math.max(unclampedXMin, FULL_X_MIN),
                FULL_X_MAX - dragXRange,
            );
            const nextYMin = Math.min(
                Math.max(unclampedYMin, 0),
                yMaximum - dragYRange,
            );

            setViewport({
                xMin: nextXMin,
                xMax: nextXMin + dragXRange,
                yMin: nextYMin,
                yMax: nextYMin + dragYRange,
            });
            setActiveIndex(null);
            return;
        }

        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const clampedX = Math.min(Math.max(pointerX, PLOT.left), chartWidth - PLOT.right);
        const domainHour = xMin + ((clampedX - PLOT.left) / plotWidth) * xRange;
        const nearestIndex = Math.min(
            Math.max(Math.round(domainHour), Math.ceil(xMin)),
            Math.floor(xMax),
        );

        setActiveIndex(nearestIndex);
    };

    const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const pointerY = ((event.clientY - bounds.top) / bounds.height) * CHART_HEIGHT;

        if (
            pointerX < PLOT.left
            || pointerX > chartWidth - PLOT.right
            || pointerY < PLOT.top
            || pointerY > BASELINE_Y
        ) {
            return;
        }

        event.preventDefault();
        const factor = event.deltaY < 0 ? 0.72 : 1.38;
        const nextXRange = Math.min(FULL_X_MAX - FULL_X_MIN, Math.max(2, xRange * factor));
        const nextYRange = Math.min(yMaximum, Math.max(Math.max(yMaximum / 8, 1), yRange * factor));
        const pointerXRatio = (pointerX - PLOT.left) / plotWidth;
        const pointerYRatio = (BASELINE_Y - pointerY) / PLOT_HEIGHT;
        const pointerHour = xMin + pointerXRatio * xRange;
        const pointerValue = yMin + pointerYRatio * yRange;
        const unclampedXMin = pointerHour - pointerXRatio * nextXRange;
        const unclampedYMin = pointerValue - pointerYRatio * nextYRange;
        const nextXMin = Math.min(
            Math.max(unclampedXMin, FULL_X_MIN),
            FULL_X_MAX - nextXRange,
        );
        const nextYMin = Math.min(
            Math.max(unclampedYMin, 0),
            yMaximum - nextYRange,
        );
        const isFullView = nextXRange >= FULL_X_MAX - FULL_X_MIN - 0.001
            && nextYRange >= yMaximum - 0.001;

        setViewport(isFullView ? null : {
            xMin: nextXMin,
            xMax: nextXMin + nextXRange,
            yMin: nextYMin,
            yMax: nextYMin + nextYRange,
        });
    };

    const handlePointerDown = (event: PointerEvent<SVGSVGElement>) => {
        if (!isZoomed || event.button !== 0) {
            return;
        }

        dragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            viewport: { xMin, xMax, yMin, yMax },
        };
        event.currentTarget.setPointerCapture(event.pointerId);
    };

    const handlePointerUp = (event: PointerEvent<SVGSVGElement>) => {
        if (dragRef.current?.pointerId !== event.pointerId) {
            return;
        }

        dragRef.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
        }
    };

    return (
        <div className={styles.loadGraph}>
            <div className={styles.graphTop}>
                <div className={styles.graphTitle}>
                    <h6>Сравнение маршрутов за сегодня</h6>
                    <InfoHint
                        title="Сравнение маршрутов за сегодня"
                        description="Каждая цветная линия показывает почасовой пассажиропоток отдельного маршрута за текущий операционный день. Для будущих часов используется доступный прогноз."
                        usage="Наведите на график, чтобы сравнить точные значения в одном часу. Колесо меняет масштаб, после приближения график можно перетаскивать; кнопка «Сбросить масштаб» возвращает весь день."
                    />
                </div>

                <div className={styles.graphControls}>
                    {isZoomed && (
                        <button
                            type="button"
                            className={styles.resetZoomButton}
                            onClick={() => setViewport(null)}
                        >
                            Сбросить масштаб
                        </button>
                    )}
                    <div className={styles.routeControl}>
                        <InfoHint
                            title="Маршруты для сравнения"
                            description="Определяет, какие маршруты представлены отдельными линиями на этом графике. Цвет линии совпадает с цветом номера маршрута."
                            usage="Откройте список и добавьте или уберите маршруты. Выбранные номера показаны под заголовком; нажмите на номер там, чтобы быстро удалить линию."
                        />
                        <div className={styles.routePicker} ref={pickerRef}>
                            <button
                                type="button"
                                className={clsx(styles.routePickerButton, routeMenuOpen && styles.routePickerButtonOpen)}
                                onClick={() => setRouteMenuOpen((isOpen) => !isOpen)}
                                aria-expanded={routeMenuOpen}
                                aria-haspopup="true"
                            >
                                Маршруты <b>{effectiveSelectedRouteIds.length}</b>
                                <span aria-hidden="true">⌄</span>
                            </button>

                            {routeMenuOpen && (
                                <div className={styles.routeMenu} role="menu" aria-label="Выбор маршрутов для сравнения">
                                    <div className={styles.routeMenuHeader}>
                                        <b>Выберите маршруты</b>
                                        <span>Линии показаны за сегодня</span>
                                    </div>
                                    <div className={styles.routeMenuList}>
                                        {tramRoutes.map((route) => {
                                            const isSelected = effectiveSelectedRouteIds.includes(route.id);
                                            const isUnavailable = !availableRouteIds.has(route.id);
                                            const isDisabled = isUnavailable
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
                </div>
            </div>
            <div className={styles.routeLegend} aria-label="Выбранные маршруты">
                {selectedRoutes.map((route) => (
                    <button
                        key={route.id}
                        type="button"
                        title={route.name}
                        aria-label={`Убрать маршрут №${route.id} из сравнения`}
                        onClick={() => toggleRoute(route.id)}
                        disabled={selectedRoutes.length === 1}
                    >
                        <i style={{ backgroundColor: routeColors[route.id] }} />
                        <b>№{route.id}</b>
                        <span aria-hidden="true">×</span>
                    </button>
                ))}
            </div>

            <svg
                ref={chartRef}
                className={clsx(styles.chart, isZoomed && styles.chartZoomed)}
                viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
                role="img"
                aria-label={`Сравнение пассажиропотока маршрутов ${effectiveSelectedRouteIds.join(', ')} за сегодня по часам`}
                onWheel={handleWheel}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                onPointerLeave={() => {
                    if (!dragRef.current) setActiveIndex(null);
                }}
            >
                <defs>
                    <filter id="route-compare-glow" x="-20%" y="-40%" width="140%" height="180%">
                        <feGaussianBlur stdDeviation="3.5" result="blur" />
                    </filter>
                    <clipPath id="route-compare-clip">
                        <rect x={PLOT.left} y={PLOT.top} width={plotWidth} height={PLOT_HEIGHT} />
                    </clipPath>
                </defs>

                {[yMin, yMin + yRange / 2, yMax].map((value) => {
                    const y = PLOT.top + (1 - (value - yMin) / yRange) * PLOT_HEIGHT;

                    return (
                        <g key={value}>
                            <line className={styles.horizontalGrid} x1={PLOT.left} y1={y} x2={chartWidth - PLOT.right} y2={y} />
                            <text className={styles.axisLabel} x={PLOT.left - 14} y={y + 5} textAnchor="end">{formatCompact(value)}</text>
                        </g>
                    );
                })}

                {xTicks.map((hour) => {
                    const x = PLOT.left + ((hour - xMin) / xRange) * plotWidth;

                    return (
                        <g key={hour}>
                            <line className={styles.verticalGrid} x1={x} y1={PLOT.top} x2={x} y2={BASELINE_Y} />
                            <text className={styles.axisLabel} x={x} y={CHART_HEIGHT - 13} textAnchor="middle">
                                {String(hour).padStart(2, '0')}:00
                            </text>
                        </g>
                    );
                })}

                <g clipPath="url(#route-compare-clip)">
                    {routeSeries.map((series) => (
                        <g key={series.route.id}>
                            <path d={series.path} className={styles.seriesGlow} stroke={series.color} filter="url(#route-compare-glow)" />
                            <path d={series.path} className={styles.seriesLine} stroke={series.color} />
                        </g>
                    ))}
                </g>

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

                        <foreignObject
                            x={tooltipX}
                            y={tooltipY}
                            width={tooltipWidth}
                            height={tooltipHeight}
                            className={styles.tooltipForeignObject}
                        >
                            <div
                                className={clsx(styles.tooltip, tooltipCanScroll && styles.tooltipScrollable)}
                                onPointerMove={(event) => event.stopPropagation()}
                                onWheel={(event) => event.stopPropagation()}
                            >
                                <strong className={styles.tooltipTitle}>
                                    {routeSeries[0]?.points[safeActiveIndex]?.label ?? ''}
                                </strong>
                                <div
                                    key={selectedRouteKey}
                                    className={styles.tooltipList}
                                    onScroll={(event) => setTooltipScroll({
                                        top: event.currentTarget.scrollTop,
                                        max: event.currentTarget.scrollHeight - event.currentTarget.clientHeight,
                                    })}
                                >
                                    {routeSeries.map((series) => (
                                        <div key={`tooltip-${series.route.id}`} className={styles.tooltipRow}>
                                            <i style={{ backgroundColor: series.color }} />
                                            <span>
                                                №{series.route.id} · {Math.round(series.points[safeActiveIndex].value).toLocaleString('ru-RU')} пасс.
                                            </span>
                                        </div>
                                    ))}
                                </div>
                                {tooltipCanScroll && (
                                    <div className={styles.tooltipScrollbar} aria-hidden="true">
                                        <span
                                            style={{
                                                height: tooltipThumbHeight,
                                                transform: `translateY(${tooltipThumbOffset}px)`,
                                            }}
                                        />
                                    </div>
                                )}
                            </div>
                        </foreignObject>
                    </>
                )}
            </svg>
        </div>
    );
}
