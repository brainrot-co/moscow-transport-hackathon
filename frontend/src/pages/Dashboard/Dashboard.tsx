import styles from './Dashboard.module.scss'
import { useState } from 'react'

import logoIcon from '../../assets/logo-icon.svg'
import dashIcon from '../../assets/dashboard-icon.svg'
import cogwheel from '../../assets/cogwheel.svg'

import LoadGraph from '../../components/LoadGraph/LoadGraph'
import TopLoadedRoutes from '../../components/TopLoadedRoutes/TopLoadedRoutes'
import Map from '../../components/Map/Map'
import { Link, useNavigate } from 'react-router-dom'
import useTheme from '../../hooks/useTheme'
import { useForecast } from '../../hooks/useForecast'
import { logout } from '../../api/auth'

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
    const [focusedRouteId, setFocusedRouteId] = useState<string | null>(null)
    const { isLightTheme, setIsLightTheme } = useTheme()
    const { rows, meta, load, loading, error, refresh } = useForecast(1)
    const navigate = useNavigate()
    const nowValue = meta?.now
        ? /(?:Z|[+-]\d{2}:?\d{2})$/.test(meta.now) ? meta.now : `${meta.now}+03:00`
        : null
    const now = nowValue ? new Date(nowValue) : new Date()

    const { date, time } = getCurrentDateTime(now)

    const handleLogout = async () => {
        await logout()
        navigate('/login', { replace: true })
    }

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
                    <div className={styles.sideMenuClip}>
                        <div className={styles.sideMenuContent} id="dashboard-sidebar-content">
                            <div className={styles.logo}>
                                <img src={logoIcon} alt="" />
                                <p>Московский транспорт</p>
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
                                            <p className={styles.whenRefreshed}>Последнее обновление<br />
                                                {loading ? 'Обновляем…' : `${date} · ${time}`}
                                            </p>
                                        </div>
                                        <button
                                            type="button"
                                            className={styles.refreshDataButton}
                                            onClick={refresh}
                                            disabled={loading}
                                        >
                                            <img src={cogwheel} alt="" />
                                            <span>{loading ? 'Обновляем данные…' : 'Обновить данные'}</span>
                                        </button>
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
                                    <button
                                        type="button"
                                        aria-label="Выйти из системы"
                                        className={styles.sidebarAction}
                                        onClick={() => void handleLogout()}
                                    >
                                        <span className={styles.sidebarIcon} aria-hidden="true">↪</span>
                                        <span className={styles.sidebarActionLabel}>Выйти</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>
                <section className={styles.dashboardContent}>
                    <div className={styles.dashboardTop}>
                        <div className={styles.topGreeting}>
                            <h4>Трамвайная сеть Москвы</h4>
                        </div>

                        <div className={styles.topControls}>
                            <div className={styles.topTimestamp}>
                                <p className={styles.topDate}>
                                    {now.toLocaleDateString('ru-RU', {
                                        day: 'numeric',
                                        month: 'long',
                                        year: 'numeric',
                                    })}
                                </p>
                                <div className={styles.topTime}>
                                    <h6>{loading ? '…' : time}</h6>
                                </div>
                            </div>

                        </div> 
                    </div>

                    {(error || !meta?.available || meta?.stale) && (
                        <div className={`${styles.dataBanner} ${error ? styles.dataBannerError : ''}`}>
                            {error
                                ? `Не удалось загрузить прогноз: ${error}`
                                : !meta?.available
                                    ? 'Прогноз ещё не готов. Данные появятся после первого прогона ML-worker.'
                                    : `Данные устарели: последний полный день — ${meta.watermark ?? 'неизвестен'}.`}
                        </div>
                    )}

                    <div className={styles.dashboardContentContainer}>
                        <div className={styles.dashboardColumnLeft}>
                            <div className={styles.mapContainer}>
                                <Map
                                    theme={isLightTheme ? 'light' : 'dark'}
                                    rows={rows}
                                    meta={meta}
                                    load={load}
                                    focusedRouteId={focusedRouteId}
                                    onFocusedRouteChange={setFocusedRouteId}
                                />
                            </div>
                            <div className={styles.columnLeftBottom}>
                                <LoadGraph rows={rows} />
                                <TopLoadedRoutes
                                    rows={rows}
                                    selectedRouteId={focusedRouteId}
                                    onSelectRoute={setFocusedRouteId}
                                />
                            </div>
                        </div>

                    </div>
                                 
                </section>
            </div>
        </>
    );
}
