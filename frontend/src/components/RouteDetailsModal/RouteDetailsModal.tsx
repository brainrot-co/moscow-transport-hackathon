import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { createPortal } from 'react-dom';

import type { TramRoute } from '../Map/routes';
import type { RouteStop } from '../Map/transitData';
import styles from './RouteDetailsModal.module.scss';

type Period = 'day' | 'week' | 'year';
type Granularity = 'hour' | 'summary';
type ForecastMode = 'adjusted' | 'model';

interface RouteDetailsModalProps {
    route: TramRoute;
    stops: RouteStop[];
    theme: 'dark' | 'light';
    onClose: () => void;
}

interface ChartDatum {
    label: string;
    model: number;
    group?: string;
}

interface ScenarioOption {
    type: string;
    label: string;
    multiplier: number;
    estimate: string;
}

interface Scenario extends ScenarioOption {
    id: string;
    title: string;
    dateFrom: string;
    dateTo: string;
    days: 'all' | 'weekdays' | 'weekends';
    hourFrom: number;
    hourTo: number;
    active: boolean;
}

const PERIODS: { id: Period; label: string }[] = [
    { id: 'day', label: 'День' },
    { id: 'week', label: 'Неделя' },
    { id: 'year', label: 'Год' },
];

const SCENARIO_OPTIONS: ScenarioOption[] = [
    { type: 'heavy_rain', label: 'Сильный дождь (> 5 мм)', multiplier: 0.96, estimate: 'по исследованию, около −4%' },
    { type: 'heavy_snow', label: 'Сильный снегопад', multiplier: 0.95, estimate: 'экспертная оценка, −5%' },
    { type: 'route_shortened', label: 'Маршрут укорочен', multiplier: 0.7, estimate: 'экспертная оценка, −30%' },
    { type: 'route_closed', label: 'Маршрут не ходит', multiplier: 0, estimate: 'по определению, −100%' },
    { type: 'mass_event', label: 'Крупное мероприятие', multiplier: 1.2, estimate: 'экспертная оценка, +20%' },
    { type: 'custom', label: 'Другое', multiplier: 1, estimate: 'задаётся диспетчером' },
];

const createScenario = (routeId: string): Scenario => ({
    ...SCENARIO_OPTIONS[0],
    id: `${routeId}-weather-demo`,
    title: 'Сильный дождь',
    dateFrom: '2026-09-26',
    dateTo: '2026-09-26',
    days: 'all',
    hourFrom: 0,
    hourTo: 23,
    active: true,
});

const clamp = (value: number, min = 0, max = 100) => Math.min(max, Math.max(min, value));

const getChartData = (route: TramRoute, period: Period, granularity: Granularity): ChartDatum[] => {
    const routeShift = Number(route.id) % 9;

    if (period === 'year') {
        return ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'].map((label, index) => ({
            label,
            model: clamp(route.load - 13 + Math.sin((index + routeShift) * 0.86) * 11 + (index > 7 ? 5 : 0)),
        }));
    }

    if (period === 'week' && granularity === 'summary') {
        return ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((label, index) => ({
            label,
            model: clamp(route.load - 9 + Math.sin((index + routeShift) * 1.15) * 8 - (index > 4 ? 12 : 0)),
        }));
    }

    if (period === 'week' && granularity === 'hour') {
        const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        const hours = [9, 12, 18];

        return days.flatMap((day, dayIndex) => hours.map((hour) => {
            const isWeekend = dayIndex > 4;
            const hourPeak = hour === 9 ? 12 : hour === 18 ? 18 : -4;
            const dayShift = Math.sin((dayIndex + routeShift) * 1.08) * 6;

            return {
                label: `${String(hour).padStart(2, '0')}:00`,
                group: day,
                model: clamp(route.load - 16 + hourPeak + dayShift - (isWeekend ? 12 : 0)),
            };
        }));
    }

    if (period === 'day' && granularity === 'summary') {
        return [
            { label: 'Утро', model: clamp(route.load + 3) },
            { label: 'День', model: clamp(route.load - 15) },
            { label: 'Вечер', model: clamp(route.load + 8) },
            { label: 'Ночь', model: clamp(route.load - 34) },
        ];
    }

    return Array.from({ length: 17 }, (_, index) => {
        const hour = index + 6;
        const morningPeak = 27 * Math.exp(-((hour - 9) ** 2) / 5.2);
        const eveningPeak = 32 * Math.exp(-((hour - 18) ** 2) / 7.5);
        const baseline = route.load - 30 + Math.sin((hour + routeShift) * 0.82) * 4;

        return {
            label: `${String(hour).padStart(2, '0')}:00`,
            model: clamp(baseline + morningPeak + eveningPeak),
        };
    });
};

const formatEffect = (multiplier: number) => {
    const percent = Math.round((multiplier - 1) * 100);

    return `${percent > 0 ? '+' : ''}${percent}%`;
};

const getForecastCsvUrl = (routeId: string) => (
    `/api/routes/${encodeURIComponent(routeId)}/forecast.csv`
);

const DownloadIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14" />
    </svg>
);

const makeSmoothPath = (points: { x: number; y: number }[]) => {
    if (points.length < 2) {
        return '';
    }

    return points.slice(1).reduce((path, point, index) => {
        const previous = points[index];
        const middleX = (previous.x + point.x) / 2;

        return `${path} C ${middleX} ${previous.y}, ${middleX} ${point.y}, ${point.x} ${point.y}`;
    }, `M ${points[0].x} ${points[0].y}`);
};

function RouteLoadChart({
    data,
    correctionMultiplier,
    forecastMode,
}: {
    data: ChartDatum[];
    correctionMultiplier: number;
    forecastMode: ForecastMode;
}) {
    const width = 920;
    const height = 330;
    const plot = { left: 62, right: 30, top: 38, bottom: 48 };
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const baseline = height - plot.bottom;
    const [activeIndex, setActiveIndex] = useState(Math.min(8, data.length - 1));
    const safeActiveIndex = Math.min(activeIndex, data.length - 1);

    const modelPoints = data.map((datum, index) => ({
        x: plot.left + (index / Math.max(data.length - 1, 1)) * plotWidth,
        y: plot.top + ((100 - datum.model) / 100) * plotHeight,
    }));
    const adjustedValues = data.map((datum) => clamp(datum.model * correctionMultiplier));
    const adjustedPoints = adjustedValues.map((value, index) => ({
        x: modelPoints[index].x,
        y: plot.top + ((100 - value) / 100) * plotHeight,
    }));
    const modelPath = makeSmoothPath(modelPoints);
    const adjustedPath = makeSmoothPath(adjustedPoints);
    const areaPath = `${adjustedPath} L ${adjustedPoints.at(-1)?.x ?? plot.left} ${baseline} L ${plot.left} ${baseline} Z`;
    const activeModelPoint = modelPoints[safeActiveIndex];
    const activeAdjustedPoint = adjustedPoints[safeActiveIndex];
    const activeDatum = data[safeActiveIndex];
    const adjustedValue = Math.round(adjustedValues[safeActiveIndex]);
    const tooltipX = Math.min(Math.max(activeAdjustedPoint.x - 54, plot.left), width - plot.right - 108);
    const tooltipY = Math.max(3, Math.min(activeAdjustedPoint.y, activeModelPoint.y) - 75);
    const labelStep = data.length === 21 ? 1 : Math.max(1, Math.ceil(data.length / 7));

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * width;
        const index = Math.round(((pointerX - plot.left) / plotWidth) * Math.max(data.length - 1, 1));

        setActiveIndex(clamp(index, 0, data.length - 1));
    };

    return (
        <svg
            className={styles.chart}
            viewBox={`0 0 ${width} ${height}`}
            role="img"
            aria-label="Прогноз загрузки маршрута: модель и итог после поправок"
            onPointerMove={handlePointerMove}
        >
            <defs>
                <linearGradient id="route-load-area" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f10624" stopOpacity="0.42" />
                    <stop offset="100%" stopColor="#f10624" stopOpacity="0.02" />
                </linearGradient>
            </defs>

            {[0, 50, 100].map((value) => {
                const y = plot.top + ((100 - value) / 100) * plotHeight;

                return (
                    <g key={value}>
                        <line className={styles.gridLine} x1={plot.left} x2={width - plot.right} y1={y} y2={y} />
                        <text className={styles.axisText} x={plot.left - 12} y={y + 5} textAnchor="end">{value}%</text>
                    </g>
                );
            })}

            {data.map((datum, index) => {
                if (index % labelStep !== 0 && index !== data.length - 1) {
                    return null;
                }

                return (
                    <g key={`${datum.group ?? ''}-${datum.label}-${index}`}>
                        {datum.group && index % 3 === 1 && (
                            <text
                                className={styles.weekdayText}
                                x={modelPoints[index].x}
                                y={height - 24}
                                textAnchor="middle"
                            >
                                {datum.group}
                            </text>
                        )}
                        <text
                            className={styles.axisText}
                            x={modelPoints[index].x}
                            y={datum.group ? height - 9 : height - 15}
                            textAnchor="middle"
                        >
                            {datum.label}
                        </text>
                    </g>
                );
            })}

            {data.length === 21 && data.map((_, index) => {
                if (index === 0 || index % 3 !== 0) {
                    return null;
                }

                const separatorX = (modelPoints[index - 1].x + modelPoints[index].x) / 2;

                return <line key={`day-${index}`} className={styles.daySeparator} x1={separatorX} x2={separatorX} y1={plot.top} y2={baseline} />;
            })}

            <path d={areaPath} fill="url(#route-load-area)" opacity={forecastMode === 'adjusted' ? 1 : 0.28} />
            <path d={modelPath} className={styles.modelLine} />
            <path d={adjustedPath} className={styles.adjustedLine} opacity={forecastMode === 'adjusted' ? 1 : 0.34} />

            <line
                className={styles.activeGuide}
                x1={activeAdjustedPoint.x}
                x2={activeAdjustedPoint.x}
                y1={Math.min(activeAdjustedPoint.y, activeModelPoint.y)}
                y2={baseline}
            />
            <circle className={styles.modelPoint} cx={activeModelPoint.x} cy={activeModelPoint.y} r="5" />
            <circle className={styles.adjustedPoint} cx={activeAdjustedPoint.x} cy={activeAdjustedPoint.y} r="7" />

            <g className={styles.chartTooltip} transform={`translate(${tooltipX} ${tooltipY})`}>
                <rect width="108" height="65" rx="10" />
                    <text x="12" y="19">{activeDatum.group ? `${activeDatum.group}, ${activeDatum.label}` : activeDatum.label}</text>
                <text x="12" y="38" className={styles.tooltipModel}>Модель {Math.round(activeDatum.model)}%</text>
                <text x="12" y="56" className={styles.tooltipAdjusted}>Итог {adjustedValue}%</text>
            </g>
        </svg>
    );
}

export default function RouteDetailsModal({ route, stops, theme, onClose }: RouteDetailsModalProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const directions = useMemo(() => (
        [...new Map(stops.map((tramStop) => [tramStop.directionId, tramStop.directionName])).entries()]
            .sort(([first], [second]) => first - second)
    ), [stops]);
    const [directionId, setDirectionId] = useState(directions[0]?.[0] ?? 0);
    const [period, setPeriod] = useState<Period>('day');
    const [granularity, setGranularity] = useState<Granularity>('hour');
    const [forecastMode, setForecastMode] = useState<ForecastMode>('adjusted');
    const [holidayStrength, setHolidayStrength] = useState(1);
    const [schoolHolidayStrength, setSchoolHolidayStrength] = useState(1);
    const [scenarios, setScenarios] = useState<Scenario[]>(() => [createScenario(route.id)]);
    const [scenarioType, setScenarioType] = useState(SCENARIO_OPTIONS[0].type);
    const [scenarioMultiplier, setScenarioMultiplier] = useState(SCENARIO_OPTIONS[0].multiplier);
    const [scenarioTitle, setScenarioTitle] = useState('');
    const [dateFrom, setDateFrom] = useState('2026-09-26');
    const [dateTo, setDateTo] = useState('2026-09-26');
    const [days, setDays] = useState<Scenario['days']>('all');
    const [hourFrom, setHourFrom] = useState(0);
    const [hourTo, setHourTo] = useState(23);
    const [savedFingerprint, setSavedFingerprint] = useState(() => JSON.stringify({
        holidayStrength: 1,
        schoolHolidayStrength: 1,
        scenarios: [createScenario(route.id)],
    }));
    const [saveMessage, setSaveMessage] = useState('');

    const directedStops = useMemo(() => {
        const uniqueStops = new Map<number, RouteStop>();

        stops
            .filter((tramStop) => tramStop.directionId === directionId)
            .forEach((tramStop) => {
                if (!uniqueStops.has(tramStop.sequence)) {
                    uniqueStops.set(tramStop.sequence, tramStop);
                }
            });

        return [...uniqueStops.values()]
            .sort((first, second) => first.sequence - second.sequence);
    }, [directionId, stops]);
    const selectedScenario = SCENARIO_OPTIONS.find((option) => option.type === scenarioType) ?? SCENARIO_OPTIONS[0];
    const currentFingerprint = JSON.stringify({ holidayStrength, schoolHolidayStrength, scenarios });
    const dirty = savedFingerprint !== currentFingerprint;
    const modelFactorMultiplier = Math.exp(-0.755 * (holidayStrength - 1))
        * Math.exp(-0.18 * (schoolHolidayStrength - 1));
    const scenarioProduct = scenarios
        .filter((scenario) => scenario.active)
        .reduce((product, scenario) => product * scenario.multiplier, 1);
    const correctionMultiplier = modelFactorMultiplier * scenarioProduct;
    const chartData = useMemo(
        () => getChartData(route, period, granularity),
        [granularity, period, route],
    );
    const modelAverage = Math.round(chartData.reduce((sum, datum) => sum + datum.model, 0) / chartData.length);
    const adjustedAverage = Math.round(clamp(modelAverage * correctionMultiplier));

    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        const previousOverflow = document.body.style.overflow;

        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', handleKeyDown);
        dialogRef.current?.focus();

        return () => {
            document.body.style.overflow = previousOverflow;
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [onClose]);

    const selectPeriod = (nextPeriod: Period) => {
        setPeriod(nextPeriod);

        if (nextPeriod === 'year') {
            setGranularity('summary');
        } else if (nextPeriod === 'day') {
            setGranularity('hour');
        }
    };

    const updateScenarioType = (nextType: string) => {
        const option = SCENARIO_OPTIONS.find((item) => item.type === nextType) ?? SCENARIO_OPTIONS[0];

        setScenarioType(option.type);
        setScenarioMultiplier(option.multiplier);
    };

    const addScenario = () => {
        const fallbackTitle = selectedScenario.label.replace(/\s*\(.+\)$/, '');

        setScenarios((current) => [
            ...current,
            {
                ...selectedScenario,
                id: `${route.id}-${Date.now()}`,
                multiplier: scenarioMultiplier,
                title: scenarioTitle.trim() || fallbackTitle,
                dateFrom,
                dateTo,
                days,
                hourFrom,
                hourTo,
                active: true,
            },
        ]);
        setScenarioTitle('');
        setSaveMessage('');
    };

    const resetCorrections = () => {
        setHolidayStrength(1);
        setSchoolHolidayStrength(1);
        setScenarios([]);
        setSaveMessage('');
    };

    const saveCorrections = () => {
        setSavedFingerprint(currentFingerprint);
        setSaveMessage('Поправки сохранены для маршрута');
    };

    return createPortal(
        <div className={`${styles.backdrop} ${theme === 'light' ? styles.light : ''}`} onMouseDown={onClose}>
            <div
                ref={dialogRef}
                className={styles.modal}
                role="dialog"
                aria-modal="true"
                aria-labelledby="route-details-title"
                tabIndex={-1}
                onMouseDown={(event) => event.stopPropagation()}
            >
                <header className={styles.header}>
                    <div>
                        <p className={styles.eyebrow}>Детали маршрута</p>
                        <h2 id="route-details-title">Маршрут №{route.id}: {route.name}</h2>
                        <div className={styles.routeMeta}>
                            <span><i />Работает</span>
                            <span>Вагонов: <b>18 / 18</b></span>
                            <span>Остановок: <b>{directedStops.length}</b></span>
                            {directedStops[0]?.sourceDate && <span>Данные: <b>{directedStops[0].sourceDate}</b></span>}
                        </div>
                    </div>
                    <button type="button" className={styles.closeButton} onClick={onClose} aria-label="Закрыть окно">×</button>
                </header>

                <div className={styles.mainGrid}>
                    <aside className={styles.stopsPanel}>
                        <div className={styles.panelHeading}>
                            <div>
                                <p>Маршрут</p>
                                <h3>Все остановки</h3>
                            </div>
                            <span>{directedStops.length}</span>
                        </div>

                        {directions.length > 1 && (
                            <div className={styles.directionPicker} aria-label="Направление движения">
                                {directions.map(([id, name]) => (
                                    <button
                                        key={id}
                                        type="button"
                                        className={directionId === id ? styles.activeDirection : ''}
                                        onClick={() => setDirectionId(id)}
                                        title={name}
                                    >
                                        {id === 0 ? 'Туда' : 'Обратно'}
                                    </button>
                                ))}
                            </div>
                        )}

                        <p className={styles.directionName} title={directions.find(([id]) => id === directionId)?.[1]}>
                            {directions.find(([id]) => id === directionId)?.[1]}
                        </p>

                        <ol className={styles.stopsList}>
                            {directedStops.map((tramStop, index) => {
                                const stopLoad = clamp(route.load - 19 + Math.sin((index + Number(route.id)) * 0.7) * 16);

                                return (
                                    <li key={tramStop.id}>
                                        <span className={styles.stopMarker}>{tramStop.sequence}</span>
                                        <div>
                                            <b>{tramStop.name}</b>
                                            <small>Ожидаемая загрузка {Math.round(stopLoad)}%</small>
                                        </div>
                                    </li>
                                );
                            })}
                        </ol>
                    </aside>

                    <main className={styles.analytics}>
                        <section className={styles.chartCard}>
                            <div className={styles.chartHeader}>
                                <div>
                                    <p className={styles.eyebrow}>Прогноз пассажиропотока</p>
                                    <h3>Динамика загрузки маршрута</h3>
                                </div>
                                <div className={styles.periodPicker}>
                                    {PERIODS.map((item) => (
                                        <button
                                            key={item.id}
                                            type="button"
                                            className={period === item.id ? styles.activePeriod : ''}
                                            onClick={() => selectPeriod(item.id)}
                                        >
                                            {item.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className={styles.chartControls}>
                                <div className={styles.forecastToggle}>
                                    <button type="button" className={forecastMode === 'adjusted' ? styles.toggleActive : ''} onClick={() => setForecastMode('adjusted')}>С поправками</button>
                                    <button type="button" className={forecastMode === 'model' ? styles.toggleActive : ''} onClick={() => setForecastMode('model')}>Модель</button>
                                </div>
                                {period !== 'year' && (
                                    <label className={styles.hourToggle}>
                                        <input
                                            type="checkbox"
                                            checked={granularity === 'hour'}
                                            onChange={(event) => setGranularity(event.target.checked ? 'hour' : 'summary')}
                                        />
                                        <span />
                                        По часам
                                    </label>
                                )}
                                <div className={styles.legend}>
                                    <span><i className={styles.modelLegend} />Модель</span>
                                    <span><i className={styles.adjustedLegend} />Итог</span>
                                </div>
                            </div>

                            <RouteLoadChart
                                data={chartData}
                                correctionMultiplier={correctionMultiplier}
                                forecastMode={forecastMode}
                            />
                        </section>

                        <section className={styles.correctionsCard}>
                            <div className={styles.correctionsHeader}>
                                <div>
                                    <p className={styles.eyebrow}>Управление моделью</p>
                                    <h3>Поправки к прогнозу</h3>
                                    <span>Изменения сразу видны на графике, сохранение — отдельным действием.</span>
                                </div>
                                <div className={styles.previewBadge}>{dirty ? 'Предпросмотр · не сохранено' : 'Сохранено'}</div>
                            </div>

                            <div className={styles.factorGrid}>
                                <label className={styles.factorControl}>
                                    <span><b>Праздники</b><em>сила эффекта модели</em></span>
                                    <input type="range" min="0" max="2" step="0.1" value={holidayStrength} onChange={(event) => { setHolidayStrength(Number(event.target.value)); setSaveMessage(''); }} />
                                    <output>{holidayStrength.toFixed(1)}</output>
                                </label>
                                <label className={styles.factorControl}>
                                    <span><b>Школьные каникулы</b><em>сила эффекта модели</em></span>
                                    <input type="range" min="0" max="2" step="0.1" value={schoolHolidayStrength} onChange={(event) => { setSchoolHolidayStrength(Number(event.target.value)); setSaveMessage(''); }} />
                                    <output>{schoolHolidayStrength.toFixed(1)}</output>
                                </label>
                            </div>

                            <div className={styles.scenarioBuilder}>
                                <div className={styles.builderHeading}>
                                    <div><b>Добавить событие</b><span>погода, ремонт, перекрытие или мероприятие</span></div>
                                    <strong>{formatEffect(scenarioMultiplier)}</strong>
                                </div>
                                <div className={styles.formGrid}>
                                    <label className={styles.wideField}>Тип события
                                        <select value={scenarioType} onChange={(event) => updateScenarioType(event.target.value)}>
                                            {SCENARIO_OPTIONS.map((option) => <option key={option.type} value={option.type}>{option.label}</option>)}
                                        </select>
                                        <small>Подсказка: {selectedScenario.estimate}</small>
                                    </label>
                                    <label>С
                                        <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
                                    </label>
                                    <label>По
                                        <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
                                    </label>
                                    <label>Дни
                                        <select value={days} onChange={(event) => setDays(event.target.value as Scenario['days'])}>
                                            <option value="all">Все дни</option>
                                            <option value="weekdays">Только будни</option>
                                            <option value="weekends">Только выходные</option>
                                        </select>
                                    </label>
                                    <label>Часы с
                                        <input type="number" min="0" max="23" value={hourFrom} onChange={(event) => setHourFrom(Number(event.target.value))} />
                                    </label>
                                    <label>до
                                        <input type="number" min="0" max="23" value={hourTo} onChange={(event) => setHourTo(Number(event.target.value))} />
                                    </label>
                                    <label className={styles.multiplierField}>Коэффициент
                                        <div><input type="range" min="0" max="2" step="0.01" value={scenarioMultiplier} onChange={(event) => setScenarioMultiplier(Number(event.target.value))} /><output>×{scenarioMultiplier.toFixed(2)}</output></div>
                                    </label>
                                    <label className={styles.titleField}>Название
                                        <input type="text" value={scenarioTitle} placeholder={selectedScenario.label} onChange={(event) => setScenarioTitle(event.target.value)} />
                                    </label>
                                    <button type="button" className={styles.addScenarioButton} onClick={addScenario}>Добавить</button>
                                </div>
                            </div>

                            <div className={styles.scenarioList}>
                                {scenarios.length === 0 && <p className={styles.emptyScenarios}>Активных событий нет.</p>}
                                {scenarios.map((scenario) => (
                                    <article key={scenario.id} className={scenario.active ? '' : styles.inactiveScenario}>
                                        <button
                                            type="button"
                                            role="switch"
                                            aria-checked={scenario.active}
                                            className={styles.scenarioSwitch}
                                            onClick={() => setScenarios((current) => current.map((item) => item.id === scenario.id ? { ...item, active: !item.active } : item))}
                                        ><span /></button>
                                        <div><b>{scenario.title}</b><span>{scenario.dateFrom} — {scenario.dateTo} · {scenario.hourFrom}:00–{scenario.hourTo}:00</span></div>
                                        <label>Коэфф.
                                            <input
                                                type="number"
                                                min="0"
                                                max="2"
                                                step="0.01"
                                                value={scenario.multiplier}
                                                onChange={(event) => setScenarios((current) => current.map((item) => item.id === scenario.id ? { ...item, multiplier: Number(event.target.value) } : item))}
                                            />
                                        </label>
                                        <button type="button" className={styles.deleteScenario} onClick={() => setScenarios((current) => current.filter((item) => item.id !== scenario.id))} aria-label={`Удалить ${scenario.title}`}>×</button>
                                    </article>
                                ))}
                            </div>

                            <div className={styles.correctionsFooter}>
                                <div className={styles.footerStatus}>
                                    <p><b>Итог:</b> {modelAverage}% → {adjustedAverage}% <span>{formatEffect(correctionMultiplier)}</span></p>
                                    {saveMessage && <output>{saveMessage}</output>}
                                </div>
                                <div className={styles.footerActions}>
                                    <a
                                        className={styles.downloadButton}
                                        href={getForecastCsvUrl(route.id)}
                                        download={`forecast-route-${route.id}.csv`}
                                    >
                                        <DownloadIcon />
                                        Скачать прогноз в CSV
                                    </a>
                                    <button type="button" className={styles.resetButton} onClick={resetCorrections}>Сбросить</button>
                                    <button type="button" className={styles.saveButton} onClick={saveCorrections} disabled={!dirty}>Сохранить поправки</button>
                                </div>
                            </div>
                        </section>
                    </main>
                </div>
            </div>
        </div>,
        document.body,
    );
}
