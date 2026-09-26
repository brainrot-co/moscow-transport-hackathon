import styles from './TopLoadedRoutesw.module.scss'

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

    return (
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
            </div>
        </>
    );
}