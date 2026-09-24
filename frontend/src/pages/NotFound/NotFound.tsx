import styles from './NotFound.module.scss'
import { Link } from 'react-router-dom';

import DataRefreshed from '../../components/DataRefreshed/DataRefreshed'

import logoIcon from '../../assets/logo-icon.svg'
import dashboardIcon from '../../assets/dashboard-icon.svg'
import notFoundBadge from '../../assets/404-pic.svg'

export default function NotFound() {
    return (
        <>
            <div className={styles.containerNotFound}>
                <div className={styles.leftBarCollapsed}>
                    <img src={logoIcon} alt="logo" />
                    <ul className={styles.menu}>
                        <li>
                            <Link to={'/'} className={styles.menuBtn}>
                                <img src={dashboardIcon} alt="to dashboard" />
                            </Link>
                        </li>
                    </ul>
                </div>

                <DataRefreshed />

                <div className={styles.notFoundContent}>
                    <img src={notFoundBadge} alt="404 not found" className={styles.badge404}/>
                    <h2>Страница не найдена</h2>
                    <p className={styles.notFoundDesc}>К сожалению, мы не можем найти страницу,  которую Вы ищете.
                        Возможно, она была удалена, перемещена или Вы ввели неверный адрес.</p>

                    <Link to={'/'} className={styles.gotoDashboard}>
                        <img src={dashboardIcon} alt="go to dashboard" />
                        <p>Вернуться на главную</p>
                    </Link>
                </div>
            </div>
        </>
    );
}