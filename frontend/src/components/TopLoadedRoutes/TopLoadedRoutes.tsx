import styles from './TopLoadedRoutes.module.scss'

import type { ForecastRow } from '../../api/forecast';
import InfoHint from '../InfoHint/InfoHint';
import LoadedRoute from '../LoadedRoute/LoadedRoute'
import { routeColors } from '../../data/routeColors'
import { tramRoutes } from '../Map/routes'

interface TopLoadedRoutesProps {
    rows: ForecastRow[];
    selectedRouteId: string | null;
    onSelectRoute: (routeId: string) => void;
}

export default function TopLoadedRoutes({
    rows,
    selectedRouteId,
    onSelectRoute,
}: TopLoadedRoutesProps) {
    const totals = Array.from(
        rows.reduce((result, row) => {
            if (row.availability === 'unavailable' || row.availability === 'cold_start') {
                return result;
            }
            const amount = row.source === 'mixed'
                ? (row.value ?? 0) + (row.yhat ?? 0)
                : row.value ?? row.yhat;
            if (amount !== null) {
                result.set(row.route, (result.get(row.route) ?? 0) + amount);
            }
            return result;
        }, new Map<number, number>()),
    ).sort(([, left], [, right]) => right - left).slice(0, 5);
    const maximum = totals[0]?.[1] ?? 1;

    return (
        <div className={styles.topLoadedRoutes}>
            <div className={styles.topLoadedTop}>
                <h5>Топ-5 маршрутов по пассажиропотоку за день</h5>
                <InfoHint
                    title="Топ-5 маршрутов за день"
                    description="Рейтинг маршрутов по суммарному пассажиропотоку за текущий операционный день. Длина полосы — доля от самого загруженного маршрута в этой пятёрке."
                    usage="Сравнивайте число пассажиров и длину полос. Нажмите на строку маршрута, чтобы выделить его на карте и открыть связанную оперативную информацию."
                />
            </div>

            <div className={styles.loadedRoutes}>
                {totals.length === 0 ? (
                    <p className={styles.emptyState}>Нет данных за выбранный день</p>
                ) : totals.map(([routeId, amount]) => {
                    const route = tramRoutes.find((item) => Number(item.id) === routeId);
                    return (
                        <LoadedRoute
                            key={routeId}
                            routeNum={String(routeId)}
                            routeName={route?.name ?? 'Маршрут'}
                            passengerCount={Math.round(amount)}
                            loadPercentage={Math.max(1, Math.round((amount / maximum) * 100))}
                            progressColor={routeColors[String(routeId)] ?? '#f10624'}
                            selected={selectedRouteId === String(routeId)}
                            onSelect={() => onSelectRoute(String(routeId))}
                        />
                    );
                })}
            </div>
        </div>
    );
}
