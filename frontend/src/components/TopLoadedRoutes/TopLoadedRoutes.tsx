import styles from './TopLoadedRoutes.module.scss'

<<<<<<< HEAD
import { Link } from 'react-router-dom'
import type { ForecastRow } from '../../api/forecast';

export default function TopLoadedRoutes({ rows }: { rows: ForecastRow[] }) {
    const totals = Array.from(
        rows.reduce((result, row) => {
            const amount = row.value ?? row.yhat ?? 0;
            result.set(row.route, (result.get(row.route) ?? 0) + amount);
            return result;
        }, new Map<number, number>()),
    ).sort(([, left], [, right]) => right - left).slice(0, 5);
=======
import LoadedRoute from '../LoadedRoute/LoadedRoute'
import { routeColors } from '../../data/routeColors'
import { tramRoutes } from '../Map/routes'

const topRoutes = [...tramRoutes]
    .sort((firstRoute, secondRoute) => secondRoute.load - firstRoute.load)
    .slice(0, 5)
>>>>>>> feature/stops_and_func

    return (
<<<<<<< HEAD
        <>
            <div className={styles.topLoadedRoutes}>
                <div className={styles.topLoadedTop}>
                    <h5>Топ маршрутов по загрузке</h5>
                    <Link to={'/'}>
                        Все маршруты →
                    </Link>
                </div>

                {totals.length === 0 ? (
                    <p>Нет данных</p>
                ) : (
                    <ul>
                        {totals.map(([route, amount]) => (
                            <li key={route}>Маршрут {route}: {Math.round(amount).toLocaleString('ru-RU')}</li>
                        ))}
                    </ul>
                )}
=======
        <div className={styles.topLoadedRoutes}>
            <div className={styles.topLoadedTop}>
                <h5>Топ-5 маршрутов по загрузке</h5>
>>>>>>> feature/stops_and_func
            </div>

            <div className={styles.loadedRoutes}>
                {topRoutes.map((route) => (
                    <LoadedRoute
                        key={route.id}
                        routeNum={route.id}
                        routeName={route.name}
                        loadPercentage={route.load}
                        progressColor={routeColors[route.id] ?? '#f10624'}
                    />
                ))}
            </div>
        </div>
    );
}
