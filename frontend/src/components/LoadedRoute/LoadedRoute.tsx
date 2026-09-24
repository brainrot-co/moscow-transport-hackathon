import styles from './LoadedRoute.module.scss'

import clsx from 'clsx';

export default function LoadedRoute() {
    return (
        <>
            <div className={styles.loadedRoute}>
                <span className={clsx(styles.routeNum, styles.routeRed)}>
                    17
                </span>

                <div className={styles.routeStatsBlock}>
                    <div className={styles.routeStatsTop}>
                        <p className={styles.routeName}>Калужская – Новокосино</p>
                        <p className={styles.loadPercentage}>82%</p>
                    </div>

                    <div className={styles.progressBar}></div>
                </div>
            </div>
        </>
    );
}