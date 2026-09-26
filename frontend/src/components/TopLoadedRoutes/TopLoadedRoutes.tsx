import styles from './TopLoadedRoutes.module.scss'

import LoadedRoute from '../LoadedRoute/LoadedRoute'
import { routeColors } from '../../data/routeColors'
import { tramRoutes } from '../Map/routes'

const topRoutes = [...tramRoutes]
    .sort((firstRoute, secondRoute) => secondRoute.load - firstRoute.load)
    .slice(0, 5)

export default function TopLoadedRoutes() {
    return (
        <div className={styles.topLoadedRoutes}>
            <div className={styles.topLoadedTop}>
                <h5>Топ-5 маршрутов по загрузке</h5>
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
