import styles from './LoadedRoute.module.scss';

type Color = 'red' | 'green' | 'orange';

interface LoadedRouteProps {
    routeNum: string;
    routeName: string;
    loadPercentage: number;
    progressColor: Color;
}

export default function LoadedRoute({
    routeNum,
    routeName,
    loadPercentage,
    progressColor,
}: LoadedRouteProps) {
    return (
        <div className={styles.loadedRoute}>
            <span
                className={`${styles.routeNum} ${styles[progressColor]}`}
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
                        className={`${styles.progressFill} ${styles[progressColor]}`}
                        style={{
                            width: `${loadPercentage}%`,
                        }}
                    />
                </div>
            </div>
        </div>
    );
}