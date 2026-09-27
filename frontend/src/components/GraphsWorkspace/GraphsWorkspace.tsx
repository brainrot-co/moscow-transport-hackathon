import {
    useEffect,
    useMemo,
    useRef,
    useState,
    type PointerEvent,
} from 'react';

import {
    getForecastAnalytics,
    type AnalyticsHour,
    type AnalyticsRoute,
    type ForecastAnalyticsResponse,
    type ForecastMeta,
} from '../../api/forecast';
import { routeColors } from '../../data/routeColors';
import InfoHint from '../InfoHint/InfoHint';
import { tramRoutes } from '../Map/routes';
import styles from './GraphsWorkspace.module.scss';

interface GraphsWorkspaceProps {
    meta: ForecastMeta | null;
    reloadToken: number;
}

type HeatmapMode = 'relative' | 'absolute';

const ALL_ROUTE_IDS = tramRoutes.map((route) => Number(route.id));
const CHART_WIDTH = 920;
const CHART_HEIGHT = 380;
const PLOT = { left: 64, right: 26, top: 26, bottom: 42 };

const formatNumber = (value: number) => new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 0,
}).format(Math.round(value));

const formatCompact = (value: number) => new Intl.NumberFormat('ru-RU', {
    notation: 'compact',
    maximumFractionDigits: 1,
}).format(value);

const formatHour = (hour: number | null) => (
    hour === null ? '—' : `${String(hour).padStart(2, '0')}:00`
);

const heatColor = (intensity: number) => {
    if (intensity < 0.25) return `rgba(52, 196, 181, ${0.2 + intensity * 1.8})`;
    if (intensity < 0.5) return `rgba(247, 190, 72, ${0.48 + intensity * 0.45})`;
    if (intensity < 0.75) return `rgba(255, 126, 54, ${0.62 + intensity * 0.32})`;
    return `rgba(241, 6, 36, ${0.7 + intensity * 0.3})`;
};

const linePath = (
    values: Array<number | null>,
    xForIndex: (index: number) => number,
    yForValue: (value: number) => number,
) => {
    let path = '';
    let drawing = false;
    values.forEach((value, index) => {
        if (value === null) {
            drawing = false;
            return;
        }
        path += `${drawing ? ' L' : 'M'} ${xForIndex(index)} ${yForValue(value)}`;
        drawing = true;
    });
    return path;
};

function FlowChart({ hours }: { hours: AnalyticsHour[] }) {
    const [activeHour, setActiveHour] = useState<number | null>(null);
    const [chartWidth, setChartWidth] = useState(CHART_WIDTH);
    const chartShellRef = useRef<HTMLDivElement>(null);
    const plotWidth = chartWidth - PLOT.left - PLOT.right;
    const plotHeight = CHART_HEIGHT - PLOT.top - PLOT.bottom;
    const maximum = Math.max(1, ...hours.flatMap((hour) => (
        [hour.total ?? 0, hour.actual ?? 0, hour.forecast ?? 0]
    )));
    const yMaximum = Math.ceil(maximum / 100) * 100 || 100;
    const xForIndex = (index: number) => PLOT.left + (index / 23) * plotWidth;
    const yForValue = (value: number) => PLOT.top + (1 - value / yMaximum) * plotHeight;
    const actualValues = hours.map((hour) => hour.actual);
    const forecastValues = hours.map((hour) => hour.forecast);
    const firstForecastHour = forecastValues.findIndex((value) => value !== null);
    if (firstForecastHour > 0 && hours[firstForecastHour - 1]?.total !== null) {
        forecastValues[firstForecastHour - 1] = hours[firstForecastHour - 1].total;
    }
    const actualPath = linePath(actualValues, xForIndex, yForValue);
    const forecastPath = linePath(forecastValues, xForIndex, yForValue);
    const selected = activeHour === null ? null : hours[activeHour];

    useEffect(() => {
        const element = chartShellRef.current;
        if (!element) return;
        const observer = new ResizeObserver(([entry]) => {
            const width = Math.max(320, Math.round(entry.contentRect.width));
            setChartWidth((current) => current === width ? current : width);
        });
        observer.observe(element);
        return () => observer.disconnect();
    }, []);

    const handlePointerMove = (event: PointerEvent<SVGSVGElement>) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        const pointerX = ((event.clientX - bounds.left) / bounds.width) * chartWidth;
        const index = Math.round(((pointerX - PLOT.left) / plotWidth) * 23);
        setActiveHour(Math.max(0, Math.min(23, index)));
    };

    return (
        <article className={`${styles.card} ${styles.flowCard}`}>
            <div className={styles.cardHeader}>
                <div>
                    <div className={styles.titleWithInfo}>
                        <h2>Пассажиропоток в течение дня</h2>
                        <InfoHint
                            title="Пассажиропоток в течение дня"
                            description="Почасовая сумма пассажиров по всем выбранным маршрутам. Бирюзовая линия показывает уже полученный факт, красная пунктирная — прогноз на ещё не завершившиеся часы."
                            usage="Наведите на нужный час, чтобы увидеть общий поток и его разбиение на факт и прогноз. Дата и набор маршрутов меняются фильтрами в верхней панели."
                        />
                    </div>
                </div>
                <div className={styles.legend}>
                    <span><i className={styles.actualDot} />Факт</span>
                    <span><i className={styles.forecastDot} />Прогноз</span>
                </div>
            </div>
            <div className={styles.chartShell} ref={chartShellRef}>
                <svg
                    className={styles.flowChart}
                    viewBox={`0 0 ${chartWidth} ${CHART_HEIGHT}`}
                    role="img"
                    aria-label="Почасовой график пассажиропотока"
                    onPointerMove={handlePointerMove}
                    onPointerLeave={() => setActiveHour(null)}
                >
                    {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                        const y = PLOT.top + (1 - ratio) * plotHeight;
                        return (
                            <g key={ratio}>
                                <line
                                    className={styles.gridLine}
                                    x1={PLOT.left}
                                    x2={chartWidth - PLOT.right}
                                    y1={y}
                                    y2={y}
                                />
                                <text className={styles.axisLabel} x={PLOT.left - 10} y={y + 4}>
                                    {formatCompact(yMaximum * ratio)}
                                </text>
                            </g>
                        );
                    })}
                    {[0, 3, 6, 9, 12, 15, 18, 21, 23].map((hour) => (
                        <g key={hour}>
                            <line
                                className={styles.verticalGrid}
                                x1={xForIndex(hour)}
                                x2={xForIndex(hour)}
                                y1={PLOT.top}
                                y2={CHART_HEIGHT - PLOT.bottom}
                            />
                            <text
                                className={styles.hourLabel}
                                x={xForIndex(hour)}
                                y={CHART_HEIGHT - 14}
                            >
                                {String(hour).padStart(2, '0')}
                            </text>
                        </g>
                    ))}
                    <path className={styles.actualLine} d={actualPath} />
                    <path className={styles.forecastLine} d={forecastPath} />
                    {activeHour !== null && selected && (
                        <g className={styles.chartTooltip}>
                            <line
                                x1={xForIndex(activeHour)}
                                x2={xForIndex(activeHour)}
                                y1={PLOT.top}
                                y2={CHART_HEIGHT - PLOT.bottom}
                            />
                            {selected.total !== null && (
                                <circle
                                    cx={xForIndex(activeHour)}
                                    cy={yForValue(selected.total)}
                                    r="4.5"
                                />
                            )}
                        </g>
                    )}
                </svg>
                {selected && (
                    <div
                        className={styles.tooltipBox}
                        style={{
                            left: `${Math.min(82, Math.max(8, (activeHour ?? 0) / 23 * 100))}%`,
                        }}
                    >
                        <b>{formatHour(activeHour)}</b>
                        <span>Всего <strong>{selected.total === null ? '—' : formatNumber(selected.total)}</strong></span>
                        <span>Факт <strong>{selected.actual === null ? '—' : formatNumber(selected.actual)}</strong></span>
                        <span>Прогноз <strong>{selected.forecast === null ? '—' : formatNumber(selected.forecast)}</strong></span>
                    </div>
                )}
            </div>
        </article>
    );
}

function IntradayDispersion({ routes }: { routes: AnalyticsRoute[] }) {
    const rows = useMemo(() => routes.map((route) => {
        const values = route.hourly.filter((value): value is number => value !== null);
        const mean = values.length > 0
            ? values.reduce((sum, value) => sum + value, 0) / values.length
            : null;
        const standardDeviation = mean !== null && values.length >= 2
            ? Math.sqrt(values.reduce(
                (sum, value) => sum + (value - mean) ** 2,
                0,
            ) / values.length)
            : null;
        return {
            route,
            hours: values.length,
            mean,
            standardDeviation,
        };
    }).sort((left, right) => (right.mean ?? -1) - (left.mean ?? -1)), [routes]);
    const scaleMaximum = Math.max(
        1,
        ...rows.map((row) => (row.mean ?? 0) + (row.standardDeviation ?? 0)),
    );

    return (
        <article className={`${styles.card} ${styles.dispersionCard}`}>
            <div className={styles.cardHeader}>
                <div>
                    <div className={styles.titleWithInfo}>
                        <h2>Средний поток и его изменение в течение дня</h2>
                        <InfoHint
                            title="Средний поток и разброс"
                            description="Для каждого маршрута вертикальная метка показывает средний поток за час, а цветная полоса — диапазон среднего ± одно стандартное отклонение. Расчёт использует только доступные часы выбранного дня."
                            usage="Сравнивайте положение меток, чтобы найти маршруты с более высоким средним потоком. Чем длиннее цветная полоса и больше значение «Разброс», тем сильнее нагрузка менялась между часами."
                        />
                    </div>
                </div>
            </div>
            <div className={styles.dispersionRows}>
                {rows.map(({ route, hours, mean, standardDeviation }) => {
                    const color = routeColors[String(route.route)] ?? '#f10624';
                    const rangeStart = mean === null
                        ? 0
                        : Math.max(0, mean - (standardDeviation ?? 0));
                    const rangeEnd = mean === null
                        ? 0
                        : Math.min(scaleMaximum, mean + (standardDeviation ?? 0));
                    return (
                        <div className={styles.dispersionRow} key={route.route}>
                            <div className={styles.routeLabel}>
                                <b style={{ borderColor: color }}>{route.route}</b>
                            </div>
                            <div className={styles.dispersionScale}>
                                {mean !== null && (
                                    <>
                                        <i
                                            className={styles.deviationRange}
                                            style={{
                                                left: `${rangeStart / scaleMaximum * 100}%`,
                                                width: `${Math.max(
                                                    1,
                                                    (rangeEnd - rangeStart) / scaleMaximum * 100,
                                                )}%`,
                                                backgroundColor: color,
                                            }}
                                        />
                                        <i
                                            className={styles.meanMarker}
                                            style={{
                                                left: `${mean / scaleMaximum * 100}%`,
                                                backgroundColor: color,
                                            }}
                                        />
                                    </>
                                )}
                            </div>
                            <div className={styles.dispersionValue}>
                                <strong>
                                    {mean === null
                                        ? 'Нет данных'
                                        : `${formatNumber(mean)} пасс./ч`}
                                </strong>
                                <span>
                                    {standardDeviation === null
                                        ? 'Разброс: —'
                                        : `Разброс: ±${formatNumber(standardDeviation)}`}
                                </span>
                                <small>Данные за {hours} ч.</small>
                            </div>
                        </div>
                    );
                })}
            </div>
        </article>
    );
}

function PeaksHeatmap({ routes }: { routes: AnalyticsRoute[] }) {
    const [mode, setMode] = useState<HeatmapMode>('relative');
    const [activeCell, setActiveCell] = useState<{
        route: number;
        hour: number;
        value: number | null;
        intensity: number;
        source: AnalyticsRoute['hourly_sources'][number];
        x: number;
        y: number;
    } | null>(null);
    const absoluteMaximum = Math.max(
        1,
        ...routes.flatMap((route) => route.hourly.map((value) => value ?? 0)),
    );

    return (
        <article className={`${styles.card} ${styles.heatmapCard}`}>
            <div className={styles.cardHeader}>
                <div>
                    <div className={styles.titleWithInfo}>
                        <h2>Карта пиков по часам</h2>
                        <InfoHint
                            title="Карта пиков по часам"
                            description="Каждая строка — маршрут, каждый цветной прямоугольник — один час. Цвет показывает интенсивность потока по выбранной шкале: от низкой бирюзовой до пиковой красной."
                            usage="Наведите на ячейку, чтобы увидеть маршрут, час, пассажиропоток, процент шкалы и источник данных. Переключатель справа меняет способ сравнения цветов."
                        />
                    </div>
                </div>
                <div className={styles.controlWithInfo}>
                    <InfoHint
                        title="Шкала тепловой карты"
                        description="«Внутри маршрута» считает процент от самого загруженного часа каждой строки. «Между маршрутами» использует один общий максимум для всех выбранных маршрутов."
                        usage="Первый режим удобен для поиска часов-пиков внутри каждого маршрута. Второй — для честного сравнения абсолютной нагрузки разных маршрутов между собой."
                    />
                    <div className={styles.segmented}>
                        <button
                            type="button"
                            className={mode === 'relative' ? styles.segmentActive : ''}
                            onClick={() => setMode('relative')}
                        >
                            Внутри маршрута
                        </button>
                        <button
                            type="button"
                            className={mode === 'absolute' ? styles.segmentActive : ''}
                            onClick={() => setMode('absolute')}
                        >
                            Между маршрутами
                        </button>
                    </div>
                </div>
            </div>
            <div className={styles.heatLegend}>
                <span><i className={styles.heatLow} />Низкая, до 25%</span>
                <span><i className={styles.heatMedium} />Средняя, 25–50%</span>
                <span><i className={styles.heatHigh} />Высокая, 50–75%</span>
                <span><i className={styles.heatPeak} />Пиковая, от 75%</span>
                <em>{mode === 'relative'
                    ? '% от максимального часа этого маршрута'
                    : '% от максимума среди выбранных маршрутов'}</em>
            </div>
            <div className={styles.heatmapScroll}>
                <div className={styles.heatmap}>
                    <div className={styles.heatmapHeader}>
                        <span />
                        <div>
                            {Array.from({ length: 24 }, (_, hour) => (
                                <span key={hour}>{hour % 3 === 0 ? String(hour).padStart(2, '0') : ''}</span>
                            ))}
                        </div>
                    </div>
                    {routes.map((route) => {
                        const routeMaximum = Math.max(1, ...route.hourly.map((value) => value ?? 0));
                        const maximum = mode === 'relative' ? routeMaximum : absoluteMaximum;
                        return (
                            <div className={styles.heatmapRow} key={route.route}>
                                <span>
                                    <b style={{ borderColor: routeColors[String(route.route)] }}>{route.route}</b>
                                </span>
                                <div>
                                    {route.hourly.map((value, hour) => {
                                        const intensity = value === null ? 0 : value / maximum;
                                        return (
                                            <i
                                                key={hour}
                                                className={value === null ? styles.emptyCell : ''}
                                                style={{ backgroundColor: value === null
                                                    ? undefined
                                                    : heatColor(intensity) }}
                                                onPointerMove={(event) => setActiveCell({
                                                    route: route.route,
                                                    hour,
                                                    value,
                                                    intensity,
                                                    source: route.hourly_sources[hour],
                                                    x: Math.min(event.clientX + 14, window.innerWidth - 224),
                                                    y: Math.min(event.clientY + 14, window.innerHeight - 150),
                                                })}
                                                onPointerLeave={() => setActiveCell(null)}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
            {activeCell && (
                <div
                    className={styles.heatTooltip}
                    style={{ left: activeCell.x, top: activeCell.y }}
                >
                    <div>
                        <b>Маршрут № {activeCell.route}</b>
                        <strong>{formatHour(activeCell.hour)}</strong>
                    </div>
                    <dl>
                        <div>
                            <dt>Пассажиропоток</dt>
                            <dd>{activeCell.value === null
                                ? 'Нет данных'
                                : `${formatNumber(activeCell.value)} пасс.`}</dd>
                        </div>
                        <div>
                            <dt>Уровень на шкале</dt>
                            <dd>{activeCell.value === null
                                ? '—'
                                : `${Math.round(activeCell.intensity * 100)}%`}</dd>
                        </div>
                        <div>
                            <dt>Источник</dt>
                            <dd>{activeCell.source === 'actual'
                                ? 'Факт'
                                : activeCell.source === 'mixed'
                                    ? 'Факт + прогноз'
                                    : activeCell.source
                                        ? 'Прогноз'
                                        : 'Нет данных'}</dd>
                        </div>
                    </dl>
                </div>
            )}
        </article>
    );
}

export default function GraphsWorkspace({ meta, reloadToken }: GraphsWorkspaceProps) {
    // пока дату не выбрали вручную, страница идёт за «сейчас» бэкенда: в демо сутки проходят за минуты
    const [pickedDate, setPickedDate] = useState<string | null>(null);
    const date = pickedDate ?? meta?.now?.slice(0, 10) ?? new Date().toISOString().slice(0, 10);
    const [selectedRoutes, setSelectedRoutes] = useState<number[]>(ALL_ROUTE_IDS);
    const [data, setData] = useState<ForecastAnalyticsResponse | null>(null);
    const [loadedQueryKey, setLoadedQueryKey] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [routeMenuOpen, setRouteMenuOpen] = useState(false);
    const [routeSearch, setRouteSearch] = useState('');
    const routePickerRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (!routeMenuOpen) return;
        const handleOutsideClick = (event: globalThis.PointerEvent) => {
            if (!routePickerRef.current?.contains(event.target as Node)) {
                setRouteMenuOpen(false);
            }
        };
        document.addEventListener('pointerdown', handleOutsideClick);
        return () => document.removeEventListener('pointerdown', handleOutsideClick);
    }, [routeMenuOpen]);

    const routeKey = selectedRoutes.join(',');
    // meta.now приходит с опросом дашборда раз в 30 с: вместе с ним пересчитываются факт и прогноз
    const queryKey = `${date}:${routeKey}:${reloadToken}:${meta?.now ?? ''}`;
    const loading = loadedQueryKey !== queryKey;
    useEffect(() => {
        let cancelled = false;
        void getForecastAnalytics(date, selectedRoutes)
            .then((response) => {
                if (!cancelled) {
                    setData(response);
                    setError(null);
                }
            })
            .catch((requestError: unknown) => {
                if (!cancelled) {
                    setError(requestError instanceof Error
                        ? requestError.message
                        : 'Не удалось загрузить аналитику');
                }
            })
            .finally(() => {
                if (!cancelled) setLoadedQueryKey(queryKey);
            });
        return () => {
            cancelled = true;
        };
    }, [date, queryKey, selectedRoutes]);

    const visibleRoutes = useMemo(() => {
        const query = routeSearch.trim().toLocaleLowerCase('ru-RU');
        if (!query) return tramRoutes;
        return tramRoutes.filter((route) => (
            route.id.includes(query) || route.name.toLocaleLowerCase('ru-RU').includes(query)
        ));
    }, [routeSearch]);

    const toggleRoute = (routeId: number) => {
        setSelectedRoutes((current) => {
            if (current.includes(routeId)) {
                return current.length === 1
                    ? current
                    : current.filter((selected) => selected !== routeId);
            }
            return [...current, routeId].sort((left, right) => left - right);
        });
    };

    const routeAnalytics = data?.routes ?? [];
    const total = routeAnalytics.reduce((sum, route) => sum + (route.total ?? 0), 0);
    const busiest = routeAnalytics.reduce<AnalyticsRoute | null>((current, route) => (
        !current || (route.total ?? -1) > (current.total ?? -1) ? route : current
    ), null);
    const peak = (data?.hours ?? []).reduce<AnalyticsHour | null>((current, hour) => (
        !current || (hour.total ?? -1) > (current.total ?? -1) ? hour : current
    ), null);
    const highLoadRoutes = routeAnalytics.filter((route) => route.load_level === 'high').length;

    return (
        <div className={styles.workspace}>
            <div className={styles.filters}>
                <div className={styles.filterIntro}>
                    <b>Оперативная аналитика</b>
                    <span>{loading ? 'Обновляем расчёты…' : `Данные на ${date.split('-').reverse().join('.')}`}</span>
                </div>
                <div className={styles.dateFilter}>
                    <div className={styles.filterCaption}>
                        <label htmlFor="analytics-date">Дата</label>
                        <InfoHint
                            title="Дата расчёта"
                            description="Определяет операционный день, для которого загружаются итоговые показатели, почасовой факт и доступный прогноз."
                            usage="Выберите дату в календаре. Все карточки и графики ниже обновятся одновременно; если данных за день нет, экран покажет пустое состояние."
                        />
                    </div>
                    <input
                        id="analytics-date"
                        type="date"
                        value={date}
                        onChange={(event) => setPickedDate(event.target.value || null)}
                    />
                </div>
                <div className={styles.routePicker} ref={routePickerRef}>
                    <div className={styles.filterCaption}>
                        <span className={styles.filterLabel}>Маршруты</span>
                        <InfoHint
                            title="Фильтр маршрутов"
                            description="Определяет, какие маршруты участвуют во всех показателях и графиках этой вкладки."
                            usage="Откройте список, найдите маршрут по номеру или направлению и включите либо исключите его. Можно выбрать все маршруты; как минимум один всегда остаётся выбранным."
                        />
                    </div>
                    <button
                        className={styles.routePickerButton}
                        type="button"
                        aria-expanded={routeMenuOpen}
                        onClick={() => setRouteMenuOpen((open) => !open)}
                    >
                        <span>{selectedRoutes.length === ALL_ROUTE_IDS.length ? 'Все маршруты' : `Выбрано: ${selectedRoutes.length}`}</span>
                        <b>⌄</b>
                    </button>
                    {routeMenuOpen && (
                        <div className={styles.routeMenu}>
                            <div className={styles.routeMenuTop}>
                                <input
                                    type="search"
                                    placeholder="Номер или направление"
                                    value={routeSearch}
                                    onChange={(event) => setRouteSearch(event.target.value)}
                                />
                                <button type="button" onClick={() => setSelectedRoutes(ALL_ROUTE_IDS)}>
                                    Выбрать все
                                </button>
                            </div>
                            <div className={styles.routeOptions}>
                                {visibleRoutes.map((route) => {
                                    const selected = selectedRoutes.includes(Number(route.id));
                                    return (
                                        <button
                                            type="button"
                                            key={route.id}
                                            className={selected ? styles.routeOptionSelected : ''}
                                            onClick={() => toggleRoute(Number(route.id))}
                                        >
                                            <i style={{ background: routeColors[route.id] }} />
                                            <span><b>{route.id}</b>{route.name}</span>
                                            <em>{selected ? '✓' : ''}</em>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {error && <div className={styles.errorBanner}>Не удалось загрузить графики: {error}</div>}

            <div className={`${styles.content} ${loading ? styles.contentLoading : ''}`}>
                <div className={styles.metrics}>
                    <div>
                        <span>Поток за день</span>
                        <strong>{total > 0 ? formatCompact(total) : '—'}</strong>
                        <small>пассажиров</small>
                    </div>
                    <div>
                        <span>Самый загруженный</span>
                        <strong>{busiest ? `№ ${busiest.route}` : '—'}</strong>
                        <small>{busiest ? formatCompact(busiest.total ?? 0) : 'нет данных'}</small>
                    </div>
                    <div>
                        <span>Пик сети</span>
                        <strong>{formatHour(peak ? new Date(peak.ts).getHours() : null)}</strong>
                        <small>{peak?.total ? formatCompact(peak.total) : 'нет данных'}</small>
                    </div>
                    <div>
                        <span>Выше нормы</span>
                        <strong>{highLoadRoutes}</strong>
                        <small>из {routeAnalytics.length} маршрутов</small>
                    </div>
                </div>

                {data && routeAnalytics.length > 0 ? (
                    <div className={styles.chartGrid}>
                        <FlowChart hours={data.hours} />
                        <IntradayDispersion routes={routeAnalytics} />
                        <PeaksHeatmap routes={routeAnalytics} />
                    </div>
                ) : !loading && !error ? (
                    <div className={styles.emptyState}>
                        <b>Для выбранного набора нет данных</b>
                        <span>Проверьте дату или измените список маршрутов.</span>
                    </div>
                ) : null}
            </div>
        </div>
    );
}
