import styles from './NotFound.module.scss'
import { Link } from 'react-router-dom';

import dashboardIcon from '../../assets/dashboard-icon.svg'
import notFoundBadge from '../../assets/404-pic.svg'
import ThemeToggle from '../../components/ThemeToggle/ThemeToggle'
import useTheme from '../../hooks/useTheme'

export default function NotFound() {
    const { isLightTheme, setIsLightTheme } = useTheme()

    return (
        <>
            <div className={`${styles.containerNotFound} ${isLightTheme ? styles.lightTheme : ''}`}>
                <div className={styles.topControls}>
                    <ThemeToggle
                        isLightTheme={isLightTheme}
                        onToggle={() => setIsLightTheme((isLight) => !isLight)}
                    />
                </div>

                <div className={styles.notFoundContent}>
                    <img src={notFoundBadge} alt="404 not found" className={styles.badge404}/>
                    <h2>Страница не найдена</h2>
                    <p className={styles.notFoundDesc}>К сожалению, мы не можем найти страницу,  которую Вы ищете.
                        Возможно, она была удалена, перемещена или Вы ввели неверный адрес.</p>

                    <Link to={'/dashboard'} className={styles.gotoDashboard}>
                        <img src={dashboardIcon} alt="go to dashboard" />
                        <p>Вернуться на главную</p>
                    </Link>
                </div>
            </div>
        </>
    );
}
