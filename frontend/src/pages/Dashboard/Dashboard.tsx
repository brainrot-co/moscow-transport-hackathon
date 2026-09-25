import styles from './Dashboard.module.scss'

import logoIcon from '../../assets/logo-icon.svg'
import dashIcon from '../../assets/dashboard-icon.svg'
import cogwheel from '../../assets/cogwheel.svg'
import tram from '../../assets/menu-bottom-pic.svg'
import calendar from '../../assets/calendar.svg'
import calendarBig from '../../assets/calendar1.svg'
import tram2 from '../../assets/tramIcon.svg'
import pass from '../../assets/passenger.svg'
import clock from '../../assets/clock.svg'
import route from '../../assets/routeIcon.svg'

import LoadGraph from '../../components/LoadGraph/LoadGraph'
import TopLoadedRoutes from '../../components/TopLoadedRoutes/TopLoadedRoutes'
import StatCard from '../../components/StatCard/StatCard'
import ForecatsCard from '../../components/ForecastCard/ForecastCard'
import { Link } from 'react-router-dom'

export default function Dashboard() {
    return (
        <>
            <div className={styles.dashboardWrapper}>
                <div className={styles.sideMenuBar}>
                    <div className={styles.logo}>
                        <img src={logoIcon} alt="logo icon" />
                        <p>Московский транспорт</p>
                    </div>
                    <ul className={styles.sideMenu}>
                        <li>
                            <Link to={'/'}>
                                <img src={dashIcon} alt="go to dashboard" />
                                <p>Дашборд</p>
                            </Link>
                        </li>
                    </ul>

                    <div className={styles.menuBottomBlock}>
                        <div className={styles.menuBottomInfo}>
                            <div className={styles.statusOnline}>
                                <span className={styles.onlineStatus}></span>
                                <p className={styles.whenRefreshed}>Данные обновлены<br></br>
                                    25.09.2026 14:32
                                </p>
                            </div>
                            <div className={styles.statusOnline}>
                                <img src={cogwheel} alt="settings" />
                                <p className={styles.whenRefreshed}>Система работает в штатном режиме
                                </p>
                            </div>
                        </div>
                        <img src={tram} alt="tram pic" className={styles.tram}/>
                    </div>
                </div>
                <section className={styles.dashboardContent}>
                    <div className={styles.dashboardTop}>
                        <div className={styles.topGreeting}>
                            <p>Доброе утро,</p>
                            <h4>Трамвайная сеть Москвы</h4>
                            <p>Анализ загрузки и прогноз пассажиропотока</p>
                        </div>

                        <div className={styles.topControls}>
                            <div className={styles.topTimestamp}>
                                <p className={styles.topDate}>25 сентября 2026</p>
                                <div className={styles.topTime}>
                                    <img src={calendar} alt="calendar" />
                                    <h6>14:32</h6>
                                    <div className={styles.topOnline}>
                                        <span></span>
                                        <p>Онлайн</p>
                                    </div>
                                </div>
                            </div>

                            <span className={styles.separator}></span>

                            <div className={styles.forecastRangeSelector}>
                                <div className={styles.rangeContainer}>
                                    <img src={calendarBig} alt="calendar" />
                                    <div className={styles.rangeDisplay}>
                                        <p className={styles.horizon}>Горизонт прогноза</p>
                                        <p className={styles.selectedRange}>1 месяц</p>
                                    </div>
                                </div>
                                <span className={styles.chevron}>⌄</span>
                            </div>
                        </div> 
                    </div>

                    <div className={styles.dashboardContentContainer}>
                        <div className={styles.dashboardColumnLeft}>
                            <div className={styles.mapContainer}>
                                
                            </div>
                            <div className={styles.columnLeftBottom}>
                                <LoadGraph />
                                <TopLoadedRoutes />
                            </div>
                        </div>

                        <div className={styles.dashboardColumnRight}>
                            <div className={styles.statCards}>
                                <StatCard
                                    icon={tram2}
                                    title="Общая загрузка сети"
                                    value="68%"
                                    comparison="+6%"
                                    comparisonText="vs. вчера"
                                    isFirst
                                    containsGraph
                                />
                                <StatCard
                                    icon={pass}
                                    title="Пассажиропоток (сегодня)"
                                    value="1 248 930"
                                    comparison="+12%"
                                    comparisonText="vs. вчера"
                                />
                                <StatCard
                                    icon={route}
                                    title="Активные маршруты"
                                    value="10"
                                    comparison="+12%"
                                    comparisonText="vs. вчера"
                                    isRoute
                                />
                                <StatCard
                                    icon={clock}
                                    title="Средняя задержка"
                                    value="2.4 мин"
                                    comparison="-0.8 мин"
                                    comparisonText="vs. вчера"
                                />
                                <ForecatsCard />
                            </div>
                        </div>
                    </div>
                                 
                </section>
            </div>
        </>
    );
}