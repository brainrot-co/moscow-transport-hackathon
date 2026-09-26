import styles from './LoadedRoute.module.scss';

interface LoadedRouteProps {
    routeNum: string;
    routeName: string;
    loadPercentage: number;
    progressColor: string;
}

export default function LoadedRoute({
    routeNum,
    routeName,
    loadPercentage,
    progressColor,
}: LoadedRouteProps) {
    return (
        <div
            className={styles.loadedRoute}
            aria-label={`Маршрут ${routeNum}: ${routeName}, загрузка ${loadPercentage}%`}
        >
            <span
                className={styles.routeNum}
                style={{ backgroundColor: progressColor }}
            >
                {routeNum}
            </span>

            <div className={styles.routeStatsBlock}>
                <div className={styles.routeStatsTop}>
                    <p className={styles.routeName}>
                        {routeName}
                    </p>

                    <p className={styles.loadPercentage}>
                        {loadPercentage}%
                    </p>
                </div>

                <div className={styles.progressBar}>
                    <div
                        className={styles.progressFill}
                        style={{
                            width: `${loadPercentage}%`,
                            backgroundColor: progressColor,
                        }}
                    />
                </div>
            </div>
        </div>
    );
}
