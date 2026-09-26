import styles from './Dashboard.module.scss'
import { useEffect, useState } from 'react'

import logoIcon from '../../assets/logo-icon.svg'
import dashIcon from '../../assets/dashboard-icon.svg'
import cogwheel from '../../assets/cogwheel.svg'
import calendar from '../../assets/calendar.svg'

import LoadGraph from '../../components/LoadGraph/LoadGraph'
import TopLoadedRoutes from '../../components/TopLoadedRoutes/TopLoadedRoutes'
import Map from '../../components/Map/Map'
import { Link } from 'react-router-dom'
<<<<<<< HEAD
import { useForecast } from '../../hooks/useForecast';

export default function Dashboard() {
    const { rows, meta, loading, error } = useForecast(1);
=======
import useTheme from '../../hooks/useTheme'

const GraphsIcon = () => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 19V5M4 19h16M7 15l4-4 3 2 5-6" />
    </svg>
)

const ThemeIcon = ({ isLight }: { isLight: boolean }) => (
    <svg viewBox="0 0 24 24" aria-hidden="true">
        {isLight ? (
            <>
                <path d="M20 15.2A8 8 0 0 1 8.8 4a8 8 0 1 0 11.2 11.2Z" />
            </>
        ) : (
            <>
                <circle cx="12" cy="12" r="3.5" />
                <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            </>
        )}
    </svg>
)

const getCurrentDateTime = (now: Date) => {
    const date = now.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    })

    const time = now.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
    })

    return { date, time }
}

export default function Dashboard() {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true)
    const [now, setNow] = useState(() => new Date())
    const { isLightTheme, setIsLightTheme } = useTheme()

    const { date, time } = getCurrentDateTime(now)

    useEffect(() => {
        let intervalId: number | undefined
        const millisecondsUntilNextMinute = 60_000 - (Date.now() % 60_000)
        const timeoutId = window.setTimeout(() => {
            setNow(new Date())
            intervalId = window.setInterval(() => setNow(new Date()), 60_000)
        }, millisecondsUntilNextMinute)

        return () => {
            window.clearTimeout(timeoutId)

            if (intervalId !== undefined) {
                window.clearInterval(intervalId)
            }
        }
    }, [])
>>>>>>> feature/stops_and_func

    return (
        <>
            <div className={`${styles.dashboardWrapper} ${isLightTheme ? styles.lightTheme : ''}`}>
                <aside className={`${styles.sideMenuBar} ${isSidebarOpen ? '' : styles.sideMenuBarCollapsed}`}>
                    <button
                        className={styles.sideMenuToggle}
                        type="button"
                        aria-label={isSidebarOpen ? 'Свернуть боковое меню' : 'Развернуть боковое меню'}
                        aria-expanded={isSidebarOpen}
                        aria-controls="dashboard-sidebar-content"
                        onClick={() => setIsSidebarOpen((isOpen) => !isOpen)}
                    >
                        <span className={styles.sideMenuToggleIcon} aria-hidden="true">
                            {isSidebarOpen ? '‹' : '›'}
                        </span>
                    </button>

<<<<<<< HEAD
                    <div className={styles.menuBottomBlock}>
                        <div className={styles.menuBottomInfo}>
                            <div className={styles.statusOnline}>
                                <span className={styles.onlineStatus}></span>
                                <p className={styles.whenRefreshed}>Данные обновлены<br></br>
                                    {meta?.watermark ?? 'нет данных'}
                                </p>
=======
                    <div className={styles.sideMenuClip}>
                        <div className={styles.sideMenuContent} id="dashboard-sidebar-content">
                            <div className={styles.logo}>
                                <img src={logoIcon} alt="" />
                                <p>Московский транспорт</p>
>>>>>>> feature/stops_and_func
                            </div>
                            <ul className={styles.sideMenu}>
                                <li>
                                    <Link
                                        to={'/dashboard'}
                                        className={`${styles.navLink} ${styles.navLinkActive}`}
                                        aria-label="Дашборд"
                                    >
                                        <img src={dashIcon} alt="" />
                                        <p>Дашборд</p>
                                    </Link>
                                </li>
                                <li>
                                    <button
                                        type="button"
                                        className={styles.navLink}
                                        aria-label="Графики"
                                    >
                                        <span className={styles.sidebarIcon}><GraphsIcon /></span>
                                        <p>Графики</p>
                                    </button>
                                </li>
                            </ul>

                            <div className={styles.sidebarFooter}>
                                <div className={styles.menuBottomBlock} aria-hidden={!isSidebarOpen}>
                                    <div className={styles.menuBottomInfo}>
                                        <div className={styles.statusOnline}>
                                            <span className={styles.onlineStatus}></span>
                                            <p className={styles.whenRefreshed}>Данные обновлены<br />
                                                {date} {time}
                                            </p>
                                        </div>
                                        <div className={styles.statusOnline}>
                                            <img src={cogwheel} alt="" />
                                            <p className={styles.whenRefreshed}>Система работает в штатном режиме</p>
                                        </div>
                                    </div>
                                </div>

                                <div className={styles.sidebarActions}>
                                    <button
                                        type="button"
                                        aria-label={isLightTheme ? 'Включить тёмную тему' : 'Включить светлую тему'}
                                        className={styles.sidebarAction}
                                        onClick={() => setIsLightTheme((isLight) => !isLight)}
                                    >
                                        <span className={styles.sidebarIcon}><ThemeIcon isLight={isLightTheme} /></span>
                                        <span className={styles.sidebarActionLabel}>
                                            {isLightTheme ? 'Тёмная тема' : 'Светлая тема'}
                                        </span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>
                <section className={styles.dashboardContent}>
                    <div className={styles.dashboardTop}>
                        <div className={styles.topGreeting}>
                            <p>Доброе утро,</p>
                            <h4>Трамвайная сеть Москвы</h4>
                            <p>Анализ загрузки и прогноз пассажиропотока</p>
                        </div>

                        <div className={styles.topControls}>
                            <div className={styles.topTimestamp}>
<<<<<<< HEAD
                                    <p className={styles.topDate}>{meta?.data_cutoff ?? 'Дата неизвестна'}</p>
                                <div className={styles.topTime}>
                                    <img src={calendar} alt="calendar" />
                                    <h6>{loading ? '...' : error ? 'Ошибка' : 'Готово'}</h6>
=======
                                <p className={styles.topDate}>
                                    {now.toLocaleDateString('ru-RU', {
                                        day: 'numeric',
                                        month: 'long',
                                        year: 'numeric',
                                    })}
                                </p>
                                <div className={styles.topTime}>
                                    <img src={calendar} alt="calendar" />
                                    <h6>{time}</h6>
>>>>>>> feature/stops_and_func
                                    <div className={styles.topOnline}>
                                        <span></span>
                                        <p>Онлайн</p>
                                    </div>
                                </div>
                            </div>

                        </div> 
                    </div>

                    <div className={styles.dashboardContentContainer}>
                        <div className={styles.dashboardColumnLeft}>
                            <div className={styles.mapContainer}>
<<<<<<< HEAD
                                {error ? <p>{error}</p> : <p>{loading ? 'Загрузка прогноза...' : 'Карта маршрутов готовится'}</p>}
=======
                                <Map theme={isLightTheme ? 'light' : 'dark'} />
>>>>>>> feature/stops_and_func
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
