import styles from './TopLoadedRoutes.module.scss'

import { Link } from 'react-router-dom'

import LoadedRoute from '../LoadedRoute/LoadedRoute'

export default function TopLoadedRoutes() {
    return (
        <>
            <div className={styles.topLoadedRoutes}>
                <div className={styles.topLoadedTop}>
                    <h5>Топ маршрутов по загрузке</h5>
                    <Link to={'/'}>
                        Все маршруты →
                    </Link>
                </div>

                {/* делать на 1764px!! */}
                <div className={styles.loadedRoutes}>
                    <LoadedRoute />
                </div>
            </div>
        </>
    );
}