import styles from './StatCard.module.scss'
import increase from '../../assets/increase.svg'
import graph from '../../assets/graph.svg'
import clsx from 'clsx'

interface StatCardProps {
    icon: string
    title: string
    value: string
    comparison?: string
    comparisonText?: string
    isFirst?: boolean
    isRoute?: boolean
    containsGraph?: boolean
}

export default function StatCard({
    icon,
    title,
    value,
    comparison,
    comparisonText,
    isFirst,
    isRoute,
    containsGraph
} : StatCardProps) {
    const decreased = comparison?.startsWith('-') ?? false
    
    return (
        <>
            <div className={clsx(styles.statCard, 
                isFirst && styles.first)}
                >
                <div className={styles.statIcon}>
                    <img src={icon} alt="tram" />
                </div>

                <div className={styles.statData}>
                    <h6 className={styles.statName}>{title}</h6>
                    <div className={styles.statValues}>
                        {!isRoute && <h2 className={styles.statValue}>{value}</h2>}
                        {isRoute && <h2 className={styles.routeValue}>{value} <span>/ 10</span></h2>}

                        { !isRoute &&
                        <div className={styles.statComparison}>
                            <div className={styles.margin}>
                                <img src={increase} alt="change in value" className={clsx(
                                    styles.increaseIcon,
                                    decreased && styles.decreased
                                )}/>
                                <p>{comparison}</p>
                            </div>
                            <p className={styles.versus}>{comparisonText}</p>
                        </div> }

                        {isRoute &&
                            <div className={styles.routeWorking}>
                                <span></span>
                                <p>в работе</p>
                            </div>
                        }
                    </div>
                </div>
                { containsGraph &&
                <div className={styles.graph}>
                    <img src={graph} alt="graph" />
                </div> }
            </div>
        </>
    );
}