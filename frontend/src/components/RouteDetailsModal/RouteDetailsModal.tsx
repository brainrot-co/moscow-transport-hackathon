import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { createPortal } from 'react-dom';

import type { TramRoute } from '../Map/routes';
import type { RouteStop } from '../Map/transitData';
import {
    createScenario as createScenarioRequest,
    deleteScenario as deleteScenarioRequest,
    getScenarios,
    previewForecast,
    updateScenario as updateScenarioRequest,
    type ForecastMeta,
    type ForecastRow,
    type ScenarioDraft,
} from '../../api/forecast';
import styles from './RouteDetailsModal.module.scss';

type Period = 'day' | 'week' | 'year';
type Granularity = 'hour' | 'summary';
type ForecastMode = 'adjusted' | 'model';

interface RouteDetailsModalProps {
    route: TramRoute;
    stops: RouteStop[];
    theme: 'dark' | 'light';
    rows: ForecastRow[];
    meta: ForecastMeta | null;
    onClose: () => void;
}

interface ChartDatum {
    label: string;
    model: number;
    adjusted: number;
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
    persistedId?: number;
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

const clamp = (value: number, min = 0, max = 100) => Math.min(max, Math.max(min, value));

const formatStopsCount = (count: number) => {
    const lastTwoDigits = count % 100;
    const lastDigit = count % 10;

    if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return `${count} остановок`;
    if (lastDigit === 1) return `${count} остановка`;
    if (lastDigit >= 2 && lastDigit <= 4) return `${count} остановки`;
    return `${count} остановок`;
};

const rowAmount = (row: ForecastRow, field: 'model' | 'adjusted') => {
    if (row.source === 'actual') return row.value ?? 0;
    if (row.source === 'mixed') {
        return (row.value ?? 0) + (field === 'model' ? row.yhat_model ?? 0 : row.yhat ?? 0);
    }
    return field === 'model' ? row.yhat_model ?? 0 : row.yhat ?? 0;
};

const niceMaximum = (value: number) => {
    const safeValue = Math.max(1, value);
    const magnitude = 10 ** Math.floor(Math.log10(safeValue));
    return Math.ceil(safeValue / magnitude) * magnitude;
};

const getChartData = (
    rows: ForecastRow[],
    period: Period,
    granularity: Granularity,
): ChartDatum[] => rows.map((row) => {
    const timestamp = new Date(row.ts);
    const isHourly = period !== 'year' && granularity === 'hour';
    const [, monthText] = row.ts.slice(0, 10).split('-');
    const year = Number(row.ts.slice(0, 4));
    const month = Number(monthText);
    const bucketHours = period === 'year'
        ? new Date(Date.UTC(year, month, 0)).getUTCDate() * 24
        : isHourly ? 1 : 24;
    const label = isHourly
        ? timestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
        : period === 'year'
            ? timestamp.toLocaleDateString('ru-RU', { month: 'short', timeZone: 'Europe/Moscow' })
            : timestamp.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', timeZone: 'Europe/Moscow' });
    return {
        label,
        group: period === 'week' && isHourly
            ? timestamp.toLocaleDateString('ru-RU', {
                weekday: 'short',
                day: '2-digit',
                month: '2-digit',
                timeZone: 'Europe/Moscow',
            })
            : undefined,
        model: rowAmount(row, 'model') / bucketHours,
        adjusted: rowAmount(row, 'adjusted') / bucketHours,
    };
});

const formatEffect = (multiplier: number) => {
    const percent = Math.round((multiplier - 1) * 100);

    return `${percent > 0 ? '+' : ''}${percent}%`;
};

const addDays = (date: string, days: number) => {
    const value = new Date(`${date}T00:00:00Z`);
    value.setUTCDate(value.getUTCDate() + days);
    return value.toISOString().slice(0, 10);
};

const previewRange = (today: string, period: Period) => {
    const days = period === 'day' ? 1 : period === 'week' ? 7 : 365;
    return {
        startDate: today,
        endDate: addDays(today, days - 1),
        dateFrom: `${today}T00:00:00+03:00`,
        dateTo: `${addDays(today, days - 1)}T23:00:00+03:00`,
    };
};

const scenarioPayload = (scenario: Scenario, routeId: number): ScenarioDraft => ({
    kind: 'scenario',
    factor: scenario.type,
    value: scenario.multiplier,
    routes: [routeId],
    date_from: scenario.dateFrom,
    date_to: scenario.dateTo,
    days: scenario.days,
    hour_from: scenario.hourFrom,
    hour_to: scenario.hourTo,
    title: scenario.title,
    active: scenario.active,
});

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
    forecastMode,
    yMaximum,
    showWeekStarts,
}: {
    data: ChartDatum[];
    forecastMode: ForecastMode;
    yMaximum: number;
    showWeekStarts: boolean;
}) {
    const width = 920;
    const height = 330;
    const plot = { left: 62, right: 30, top: 38, bottom: 48 };
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const baseline = height - plot.bottom;
    const [activeIndex, setActiveIndex] = useState(Math.min(8, data.length - 1));
    const safeActiveIndex = Math.min(activeIndex, data.length - 1);

    if (data.length === 0) {
        return <div className={styles.chartEmpty}>Нет данных для выбранного периода</div>;
    }

    const modelPoints = data.map((datum, index) => ({
        x: plot.left + (index / Math.max(data.length - 1, 1)) * plotWidth,
        y: plot.top + (1 - datum.model / yMaximum) * plotHeight,
    }));
    const adjustedValues = data.map((datum) => datum.adjusted);
    const adjustedPoints = adjustedValues.map((value, index) => ({
        x: modelPoints[index].x,
        y: plot.top + (1 - value / yMaximum) * plotHeight,
    }));
    const modelPath = makeSmoothPath(modelPoints);
    const adjustedPath = makeSmoothPath(adjustedPoints);
    const areaPath = `${adjustedPath} L ${adjustedPoints.at(-1)?.x ?? plot.left} ${baseline} L ${plot.left} ${baseline} Z`;
    const activeModelPoint = modelPoints[safeActiveIndex];
    const activeAdjustedPoint = adjustedPoints[safeActiveIndex];
    const activeDatum = data[safeActiveIndex];
    const adjustedValue = Math.round(adjustedValues[safeActiveIndex]);
    const tooltipWidth = 108;
    const tooltipX = activeAdjustedPoint.x - tooltipWidth / 2;
    const tooltipY = Math.max(3, Math.min(activeAdjustedPoint.y, activeModelPoint.y) - 75);
    const tooltipFits = tooltipX >= plot.left && tooltipX + tooltipWidth <= width - plot.right;
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

            {[0, yMaximum / 2, yMaximum].map((value) => {
                const y = plot.top + (1 - value / yMaximum) * plotHeight;

                return (
                    <g key={value}>
                        <line className={styles.gridLine} x1={plot.left} x2={width - plot.right} y1={y} y2={y} />
                        <text className={styles.axisText} x={plot.left - 12} y={y + 5} textAnchor="end">{new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}</text>
                    </g>
                );
            })}

            {data.map((datum, index) => {
                if (index % labelStep !== 0 && (showWeekStarts || index !== data.length - 1)) {
                    return null;
                }

                return (
                    <g key={`${datum.group ?? ''}-${datum.label}-${index}`}>
                        {datum.group && (
                            <text
                                className={styles.weekdayText}
                                x={modelPoints[index].x}
                                y={showWeekStarts ? height - 15 : height - 24}
                                textAnchor="middle"
                            >
                                {datum.group}
                            </text>
                        )}
                        {!showWeekStarts && (
                            <text
                                className={styles.axisText}
                                x={modelPoints[index].x}
                                y={datum.group ? height - 9 : height - 15}
                                textAnchor="middle"
                            >
                                {datum.label}
                            </text>
                        )}
                    </g>
                );
            })}

            {(showWeekStarts || data.length === 21) && data.map((_, index) => {
                const separatorStep = showWeekStarts ? 24 : 3;
                if (index === 0 || index % separatorStep !== 0) {
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

            {tooltipFits && (
                <g className={styles.chartTooltip} transform={`translate(${tooltipX} ${tooltipY})`}>
                    <rect width={tooltipWidth} height="65" rx="10" />
                        <text x="12" y="19">{activeDatum.group ? `${activeDatum.group}, ${activeDatum.label}` : activeDatum.label}</text>
                    <text x="12" y="38" className={styles.tooltipModel}>Модель {Math.round(activeDatum.model).toLocaleString('ru-RU')}</text>
                    <text x="12" y="56" className={styles.tooltipAdjusted}>Итог {adjustedValue.toLocaleString('ru-RU')}</text>
                </g>
            )}
        </svg>
    );
}

export default function RouteDetailsModal({ route, stops, theme, rows, meta, onClose }: RouteDetailsModalProps) {
    const dialogRef = useRef<HTMLDivElement>(null);
    const persistedScenarioIds = useRef(new Set<number>());
    const factorIds = useRef<Record<string, number>>({});
    const today = meta?.now?.slice(0, 10) ?? new Date().toISOString().slice(0, 10);
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
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [scenarioType, setScenarioType] = useState(SCENARIO_OPTIONS[0].type);
    const [scenarioMultiplier, setScenarioMultiplier] = useState(SCENARIO_OPTIONS[0].multiplier);
    const [scenarioTitle, setScenarioTitle] = useState('');
    const [dateFrom, setDateFrom] = useState(today);
    const [dateTo, setDateTo] = useState(today);
    const [days, setDays] = useState<Scenario['days']>('all');
    const [hourFrom, setHourFrom] = useState(0);
    const [hourTo, setHourTo] = useState(23);
    const [scenarioBuilderOpen, setScenarioBuilderOpen] = useState(false);
    const [savedFingerprint, setSavedFingerprint] = useState(() => JSON.stringify({
        holidayStrength: 1,
        schoolHolidayStrength: 1,
        scenarios: [],
    }));
    const [saveMessage, setSaveMessage] = useState('');
    const [saving, setSaving] = useState(false);
    const [previewRows, setPreviewRows] = useState(rows);
    const [previewError, setPreviewError] = useState('');
    const [previewLoading, setPreviewLoading] = useState(false);

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
    const displayRows = meta?.available ? previewRows : rows;
    const routeScaleMaximum = useMemo(() => niceMaximum(Math.max(
        1,
        ...rows.flatMap((row) => [rowAmount(row, 'model'), rowAmount(row, 'adjusted')]),
    ) * 1.15), [route.id, rows]);
    const chartData = useMemo(
        () => getChartData(displayRows, period, granularity),
        [displayRows, granularity, period],
    );
    const modelAverage = chartData.length
        ? Math.round(chartData.reduce((sum, datum) => sum + datum.model, 0) / chartData.length)
        : 0;
    const adjustedAverage = chartData.length
        ? Math.round(chartData.reduce((sum, datum) => sum + datum.adjusted, 0) / chartData.length)
        : 0;
    const correctionMultiplier = modelAverage > 0 ? adjustedAverage / modelAverage : 1;
    useEffect(() => {
        let cancelled = false;
        void getScenarios().then((stored) => {
            if (cancelled) return;
            const holiday = stored.find((item) => item.kind === 'model_factor' && item.factor === 'holiday');
            const school = stored.find((item) => item.kind === 'model_factor' && item.factor === 'school_holiday');
            if (holiday) factorIds.current.holiday = holiday.id;
            if (school) factorIds.current.school_holiday = school.id;
            const nextHoliday = holiday?.value ?? 1;
            const nextSchool = school?.value ?? 1;
            const nextScenarios = stored
                .filter((item) => item.kind === 'scenario' && (!item.routes || item.routes.includes(Number(route.id))))
                .map((item): Scenario => {
                    const option = SCENARIO_OPTIONS.find((candidate) => candidate.type === item.factor)
                        ?? { type: item.factor, label: item.title ?? item.factor, multiplier: item.value, estimate: 'сохранённый сценарий' };
                    return {
                        ...option,
                        id: String(item.id),
                        persistedId: item.id,
                        multiplier: item.value,
                        title: item.title ?? option.label,
                        dateFrom: item.date_from,
                        dateTo: item.date_to,
                        days: item.days,
                        hourFrom: item.hour_from ?? 0,
                        hourTo: item.hour_to ?? 23,
                        active: item.active ?? true,
                    };
                });
            persistedScenarioIds.current = new Set(nextScenarios.map((item) => item.persistedId!));
            setHolidayStrength(nextHoliday);
            setSchoolHolidayStrength(nextSchool);
            setScenarios(nextScenarios);
            setSavedFingerprint(JSON.stringify({
                holidayStrength: nextHoliday,
                schoolHolidayStrength: nextSchool,
                scenarios: nextScenarios,
            }));
        }).catch(() => {
            if (!cancelled) setSaveMessage('Не удалось загрузить сохранённые поправки');
        });
        return () => { cancelled = true; };
    }, [route.id]);

    useEffect(() => {
        if (!meta?.available) {
            return;
        }
        let cancelled = false;
        const timer = window.setTimeout(() => {
            const range = previewRange(today, period);
            const apiGranularity = period === 'year'
                ? 'month'
                : granularity === 'hour' ? 'hour' : 'day';
            setPreviewLoading(true);
            setPreviewError('');
            void previewForecast({
                date_from: range.dateFrom,
                date_to: range.dateTo,
                routes: [Number(route.id)],
                granularity: apiGranularity,
                model_factors: {
                    holiday: holidayStrength,
                    school_holiday: schoolHolidayStrength,
                },
                draft: scenarios
                    .filter((scenario) => scenario.active)
                    .map((scenario) => scenarioPayload(scenario, Number(route.id))),
            }).then((response) => {
                if (!cancelled) setPreviewRows(response.data);
            }).catch((error) => {
                if (!cancelled) setPreviewError(error instanceof Error ? error.message : 'Ошибка предпросмотра');
            }).finally(() => {
                if (!cancelled) setPreviewLoading(false);
            });
        }, 250);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [granularity, holidayStrength, meta?.available, period, route.id, rows, scenarios, schoolHolidayStrength, today]);

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

        if (dateTo < dateFrom) {
            setSaveMessage('Дата окончания не может быть раньше даты начала');
            return;
        }
        if (hourTo < hourFrom) {
            setSaveMessage('Час окончания не может быть раньше часа начала');
            return;
        }

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

    const saveCorrections = async () => {
        setSaving(true);
        setSaveMessage('Сохраняем поправки…');

        try {
            const saveModelFactor = async (factor: 'holiday' | 'school_holiday', value: number) => {
                const existingId = factorIds.current[factor];
                if (existingId) {
                    const stored = await updateScenarioRequest(existingId, { value, active: true });
                    factorIds.current[factor] = stored.id;
                    return;
                }

                const stored = await createScenarioRequest({
                    kind: 'model_factor',
                    factor,
                    value,
                    routes: null,
                    date_from: '2020-01-01',
                    date_to: '2100-12-31',
                    days: 'all',
                    hour_from: null,
                    hour_to: null,
                    title: factor === 'holiday' ? 'Сила эффекта праздников' : 'Сила эффекта школьных каникул',
                    active: true,
                });
                factorIds.current[factor] = stored.id;
            };

            await Promise.all([
                saveModelFactor('holiday', holidayStrength),
                saveModelFactor('school_holiday', schoolHolidayStrength),
            ]);

            const nextScenarios: Scenario[] = [];
            for (const scenario of scenarios) {
                const payload = scenarioPayload(scenario, Number(route.id));
                const stored = scenario.persistedId
                    ? await updateScenarioRequest(scenario.persistedId, {
                        value: payload.value,
                        date_from: payload.date_from,
                        date_to: payload.date_to,
                        days: payload.days,
                        hour_from: payload.hour_from,
                        hour_to: payload.hour_to,
                        title: payload.title,
                        active: payload.active,
                    })
                    : await createScenarioRequest(payload);
                nextScenarios.push({ ...scenario, id: String(stored.id), persistedId: stored.id });
            }

            const keptIds = new Set(nextScenarios.map((scenario) => scenario.persistedId));
            const removedIds = [...persistedScenarioIds.current].filter((id) => !keptIds.has(id));
            await Promise.all(removedIds.map((id) => deleteScenarioRequest(id)));
            persistedScenarioIds.current = new Set(
                nextScenarios.map((scenario) => scenario.persistedId).filter((id): id is number => id !== undefined),
            );

            const nextFingerprint = JSON.stringify({
                holidayStrength,
                schoolHolidayStrength,
                scenarios: nextScenarios,
            });
            setScenarios(nextScenarios);
            setSavedFingerprint(nextFingerprint);
            setSaveMessage('Поправки сохранены для маршрута');
        } catch (error) {
            setSaveMessage(error instanceof Error ? `Не удалось сохранить: ${error.message}` : 'Не удалось сохранить поправки');
        } finally {
            setSaving(false);
        }
    };

    const downloadForecast = () => {
        const escapeCell = (value: unknown) => {
            const stringValue = value == null ? '' : String(value);
            return `"${stringValue.replaceAll('"', '""')}"`;
        };
        const header = ['route', 'timestamp', 'source', 'actual', 'model', 'adjusted', 'q10', 'q90', 'availability', 'applied'];
        const lines = displayRows.map((row) => [
            row.route,
            row.ts,
            row.source,
            row.value,
            row.yhat_model,
            row.yhat,
            row.q10,
            row.q90,
            row.availability,
            JSON.stringify(row.applied),
        ].map(escapeCell).join(','));
        const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `forecast-route-${route.id}.csv`;
        link.click();
        URL.revokeObjectURL(url);
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
                            <span>{formatStopsCount(directedStops.length)}</span>
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

                        <ol className={styles.stopsList}>
                            {directedStops.map((tramStop) => (
                                    <li key={tramStop.id}>
                                        <span className={styles.stopMarker}>{tramStop.sequence}</span>
                                        <div>
                                            <b>{tramStop.name}</b>
                                        </div>
                                    </li>
                            ))}
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
                                {period === 'week' && (
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
                                forecastMode={forecastMode}
                                yMaximum={routeScaleMaximum}
                                showWeekStarts={period === 'week' && granularity === 'hour'}
                            />
                            {(previewLoading || previewError) && (
                                <p className={`${styles.previewStatus} ${previewError ? styles.previewError : ''}`} role={previewError ? 'alert' : 'status'}>
                                    {previewError || 'Пересчитываем прогноз…'}
                                </p>
                            )}
                        </section>

                        <section className={styles.correctionsCard}>
                            <div className={styles.correctionsHeader}>
                                <div>
                                    <p className={styles.eyebrow}>Общие настройки</p>
                                    <h3>Поправки к прогнозу всех маршрутов</h3>
                                    <span>Эти параметры применяются ко всей трамвайной сети.</span>
                                </div>
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
                        </section>

                        <section className={styles.correctionsCard}>
                            <div className={styles.correctionsHeader}>
                                <div>
                                    <p className={styles.eyebrow}>Настройки маршрута</p>
                                    <h3>Поправки к прогнозу маршрута №{route.id}</h3>
                                    <span>События ниже влияют только на открытый маршрут.</span>
                                </div>
                                <div className={styles.previewBadge}>{dirty ? 'Предпросмотр · не сохранено' : 'Сохранено'}</div>
                            </div>

                            <div className={`${styles.scenarioBuilder} ${scenarioBuilderOpen ? styles.scenarioBuilderOpen : ''}`}>
                                <button
                                    type="button"
                                    className={styles.builderHeading}
                                    onClick={() => setScenarioBuilderOpen((isOpen) => !isOpen)}
                                    aria-expanded={scenarioBuilderOpen}
                                >
                                    <div><b>Создать событие</b><span>погода, ремонт, перекрытие или мероприятие</span></div>
                                    <span className={styles.builderSummary}>
                                        <strong>{formatEffect(scenarioMultiplier)}</strong>
                                        <i aria-hidden="true">⌄</i>
                                    </span>
                                </button>
                                {scenarioBuilderOpen && <div className={styles.formGrid}>
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
                                </div>}
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
                                    <p><b>Среднее:</b> {modelAverage.toLocaleString('ru-RU')} → {adjustedAverage.toLocaleString('ru-RU')} пасс. <span>{formatEffect(correctionMultiplier)}</span></p>
                                    {saveMessage && <output>{saveMessage}</output>}
                                </div>
                                <div className={styles.footerActions}>
                                    <button
                                        type="button"
                                        className={styles.downloadButton}
                                        onClick={downloadForecast}
                                        disabled={displayRows.length === 0}
                                    >
                                        <DownloadIcon />
                                        Скачать прогноз в CSV
                                    </button>
                                    <button type="button" className={styles.resetButton} onClick={resetCorrections}>Сбросить</button>
                                    <button type="button" className={styles.saveButton} onClick={saveCorrections} disabled={!dirty || saving}>{saving ? 'Сохраняем…' : 'Сохранить поправки'}</button>
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
