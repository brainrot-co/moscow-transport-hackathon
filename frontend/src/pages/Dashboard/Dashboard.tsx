import styles from './Dashboard.module.scss'

import logoIcon from '../../assets/logo-icon.svg'
import dashIcon from '../../assets/dashboard-icon.svg'
import cogwheel from '../../assets/cogwheel.svg'
import tram from '../../assets/menu-bottom-pic.svg'
import calendar from '../../assets/calendar.svg'
import calendarBig from '../../assets/calendar1.svg'

import LoadGraph from '../../components/LoadGraph/LoadGraph'
import TopLoadedRoutes from '../../components/TopLoadedRoutes/TopLoadedRoutes'
import { Link } from 'react-router-dom'
import { useForecast } from '../../hooks/useForecast';

export default function Dashboard() {
    const { rows, meta, loading, error } = useForecast(1);

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
                                    {meta?.watermark ?? 'нет данных'}
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
                                    <p className={styles.topDate}>{meta?.data_cutoff ?? 'Дата неизвестна'}</p>
                                <div className={styles.topTime}>
                                    <img src={calendar} alt="calendar" />
                                    <h6>{loading ? '...' : error ? 'Ошибка' : 'Готово'}</h6>
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
                                {error ? <p>{error}</p> : <p>{loading ? 'Загрузка прогноза...' : 'Карта маршрутов готовится'}</p>}
                            </div>
                            <div className={styles.columnLeftBottom}>
                                <LoadGraph rows={rows} />
                                <TopLoadedRoutes rows={rows} />
                            </div>
                        </div>
                    </div>
                                 
                </section>
            </div>
        </>
    );
}