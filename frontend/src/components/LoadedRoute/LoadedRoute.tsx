import styles from './LoadedRoute.module.scss';

interface LoadedRouteProps {
    routeNum: string;
    routeName: string;
    passengerCount: number;
    loadPercentage: number;
    progressColor: string;
    selected: boolean;
    onSelect: () => void;
}

export default function LoadedRoute({
    routeNum,
    routeName,
    passengerCount,
    loadPercentage,
    progressColor,
    selected,
    onSelect,
}: LoadedRouteProps) {
    return (
        <button
            type="button"
            className={`${styles.loadedRoute} ${selected ? styles.loadedRouteSelected : ''}`}
            onClick={onSelect}
            aria-pressed={selected}
            aria-label={`Маршрут ${routeNum}: ${routeName}, ${passengerCount.toLocaleString('ru-RU')} пассажиров`}
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

                    <p className={styles.passengerCount}>
                        {passengerCount.toLocaleString('ru-RU')} пасс.
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
        </button>
    );
}
