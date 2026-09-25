import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import arrow from '../../assets/grow-icon.svg';

type TimeRange = 'Сегодня' | '7 дней' | '30 дней';

interface LoadPoint {
    label: string;
    value: number;
}

interface RangeData {
    points: LoadPoint[];
    ticks: number[];
    defaultIndex: number;
}

interface ChartPoint extends LoadPoint {
    x: number;
    y: number;
}

const INITIAL_CHART_WIDTH = 680;
const CHART_HEIGHT = 270;
const PLOT = { left: 68, right: 60, top: 34, bottom: 48 };
const PLOT_HEIGHT = CHART_HEIGHT - PLOT.top - PLOT.bottom;
const BASELINE_Y = PLOT.top + PLOT_HEIGHT;

const rangeData: Record<TimeRange, RangeData> = {
    'Сегодня': {
        points: [
            { label: '06:00', value: 34 },
            { label: '07:00', value: 34 },
            { label: '08:00', value: 43 },
            { label: '09:00', value: 42 },
            { label: '10:00', value: 57 },
            { label: '11:00', value: 60 },
            { label: '12:00', value: 71 },
            { label: '13:00', value: 61 },
            { label: '14:00', value: 72 },
            { label: '15:00', value: 76 },
            { label: '16:00', value: 72 },
            { label: '17:00', value: 68 },
            { label: '18:00', value: 68 },
            { label: '19:00', value: 64 },
            { label: '20:00', value: 60 },
            { label: '21:00', value: 61 },
        ],
        ticks: [0, 3, 6, 9, 12, 15],
        defaultIndex: 8,
    },
    '7 дней': {
        points: [
            { label: 'Пн', value: 61 },
            { label: 'Вт', value: 66 },
            { label: 'Ср', value: 58 },
            { label: 'Чт', value: 72 },
            { label: 'Пт', value: 79 },
            { label: 'Сб', value: 64 },
            { label: 'Вс', value: 55 },
        ],
        ticks: [0, 1, 2, 3, 4, 5, 6],
        defaultIndex: 4,
    },
    '30 дней': {
        points: [
            { label: '1 сен', value: 49 },
            { label: '3 сен', value: 54 },
            { label: '5 сен', value: 58 },
            { label: '7 сен', value: 63 },
            { label: '9 сен', value: 59 },
            { label: '11 сен', value: 67 },
            { label: '13 сен', value: 71 },
            { label: '15 сен', value: 69 },
            { label: '17 сен', value: 76 },
            { label: '19 сен', value: 73 },
            { label: '21 сен', value: 78 },
            { label: '23 сен', value: 70 },
            { label: '25 сен', value: 66 },
            { label: '27 сен', value: 72 },
            { label: '29 сен', value: 68 },
            { label: '30 сен', value: 64 },
        ],
        ticks: [0, 3, 6, 9, 12, 15],
        defaultIndex: 10,
    },
};

const timeRanges = Object.keys(rangeData) as TimeRange[];

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

export default function LoadGraph() {
    const chartRef = useRef<SVGSVGElement>(null);
    const [selectedRange, setSelectedRange] = useState<TimeRange>('Сегодня');
    const [activeIndex, setActiveIndex] = useState(rangeData['Сегодня'].defaultIndex);
    const [chartWidth, setChartWidth] = useState(INITIAL_CHART_WIDTH);
    const currentRange = rangeData[selectedRange];
    const plotWidth = chartWidth - PLOT.left - PLOT.right;

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

    const chartPoints = useMemo<ChartPoint[]>(() => (
        currentRange.points.map((point, index, points) => ({
            ...point,
            x: PLOT.left + (index / (points.length - 1)) * plotWidth,
            y: PLOT.top + ((100 - point.value) / 100) * PLOT_HEIGHT,
        }))
    ), [currentRange, plotWidth]);

    const linePath = useMemo(() => createSmoothPath(chartPoints), [chartPoints]);
    const areaPath = chartPoints.length > 0
        ? `${linePath} L ${chartPoints.at(-1)?.x ?? PLOT.left} ${BASELINE_Y} L ${chartPoints[0].x} ${BASELINE_Y} Z`
        : '';
    const safeActiveIndex = Math.min(activeIndex, chartPoints.length - 1);
    const activePoint = chartPoints[safeActiveIndex];
    const tooltipWidth = 92;
    const tooltipHeight = 49;
    const tooltipX = Math.min(
        Math.max(activePoint.x - tooltipWidth / 2, PLOT.left),
        chartWidth - PLOT.right - tooltipWidth,
    );
    const tooltipY = Math.max(2, activePoint.y - tooltipHeight - 16);

    const selectRange = (range: TimeRange) => {
        setSelectedRange(range);
        setActiveIndex(rangeData[range].defaultIndex);
    };

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const clampedX = Math.min(Math.max(pointerX, PLOT.left), chartWidth - PLOT.right);
        const pointStep = plotWidth / (chartPoints.length - 1);
        const nearestIndex = Math.round((clampedX - PLOT.left) / pointStep);

        setActiveIndex(nearestIndex);
    };

    return (
        <div className={styles.loadGraph}>
            <div className={styles.graphTop}>
                <div className={styles.graphTitle}>
                    <img src={arrow} alt="" />
                    <h6>Динамика загрузки сети</h6>
                </div>

                <div className={styles.timeRangePicker}>
                    <div
                        className={styles.selectedBackground}
                        style={{
                            transform: `translateX(${timeRanges.indexOf(selectedRange) * 100}%)`,
                        }}
                    />

                    {timeRanges.map((range) => (
                        <button
                            key={range}
                            type="button"
                            className={clsx(
                                styles.timeRangeItem,
                                selectedRange === range && styles.selected,
                            )}
                            onClick={() => selectRange(range)}
                        >
                            {range}
                        </button>
                    ))}
                </div>
            </div>

            <svg
                ref={chartRef}
                className={styles.chart}
                viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
                role="img"
                aria-label={`График загрузки сети за период: ${selectedRange}`}
                onPointerMove={handlePointerMove}
            >
                <defs>
                    <linearGradient id="load-area-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f10624" stopOpacity="0.42" />
                        <stop offset="100%" stopColor="#f10624" stopOpacity="0.025" />
                    </linearGradient>
                    <filter id="load-line-glow" x="-20%" y="-40%" width="140%" height="180%">
                        <feGaussianBlur stdDeviation="4" result="blur" />
                    </filter>
                    <filter id="load-point-glow" x="-120%" y="-120%" width="340%" height="340%">
                        <feGaussianBlur stdDeviation="5" result="blur" />
                    </filter>
                </defs>

                {[0, 50, 100].map((value) => {
                    const y = PLOT.top + ((100 - value) / 100) * PLOT_HEIGHT;

                    return (
                        <g key={value}>
                            <line
                                className={styles.horizontalGrid}
                                x1={PLOT.left}
                                y1={y}
                                x2={chartWidth - PLOT.right}
                                y2={y}
                            />
                            <text
                                className={styles.axisLabel}
                                x={PLOT.left - 14}
                                y={y + 5}
                                textAnchor="end"
                            >
                                {value}%
                            </text>
                        </g>
                    );
                })}

                {currentRange.ticks.map((index) => {
                    const point = chartPoints[index];

                    return (
                        <g key={`${point.label}-${index}`}>
                            <line
                                className={styles.verticalGrid}
                                x1={point.x}
                                y1={PLOT.top}
                                x2={point.x}
                                y2={BASELINE_Y}
                            />
                            <text
                                className={styles.axisLabel}
                                x={point.x}
                                y={CHART_HEIGHT - 13}
                                textAnchor="middle"
                            >
                                {point.label}
                            </text>
                        </g>
                    );
                })}

                <path d={areaPath} fill="url(#load-area-gradient)" />
                <path
                    d={linePath}
                    className={styles.lineGlow}
                    filter="url(#load-line-glow)"
                />
                <path d={linePath} className={styles.linePath} />

                <line
                    className={styles.activeGuide}
                    x1={activePoint.x}
                    y1={activePoint.y}
                    x2={activePoint.x}
                    y2={BASELINE_Y}
                />
                <circle
                    cx={activePoint.x}
                    cy={activePoint.y}
                    r="12"
                    className={styles.pointGlow}
                    filter="url(#load-point-glow)"
                />
                <circle
                    cx={activePoint.x}
                    cy={activePoint.y}
                    r="7"
                    className={styles.activePoint}
                />
                <circle
                    cx={activePoint.x}
                    cy={activePoint.y}
                    r="3"
                    className={styles.activePointCenter}
                />

                <g className={styles.tooltip} transform={`translate(${tooltipX} ${tooltipY})`}>
                    <rect width={tooltipWidth} height={tooltipHeight} rx="10" />
                    <text x="12" y="20" className={styles.tooltipTitle}>
                        {activePoint.label}
                    </text>
                    <circle cx="14" cy="35" r="4" />
                    <text x="24" y="39" className={styles.tooltipValue}>
                        {activePoint.value}%
                    </text>
                </g>
            </svg>
        </div>
    );
}
