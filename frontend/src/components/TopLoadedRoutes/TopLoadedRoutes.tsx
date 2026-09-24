import styles from './TopLoadedRoutesw.module.scss'

import { Link } from 'react-router-dom'

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

                {/* делать на 1828px!! */}
            </div>
        </>
    );
}