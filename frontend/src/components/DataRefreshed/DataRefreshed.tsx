import styles from './DataRefreshed.module.scss'
import userIcon from '../../assets/user.svg'

import { Link } from 'react-router-dom';

export default function DataRefreshed() {
    return (
        <>
            <div className={styles.refreshedBadgeContainer}>
                <div className={styles.statusOnline}>
                    <span className={styles.onlineStatus}></span>
                    <p className={styles.whenRefreshed}>Данные обновлены<br></br>
                        25.09.2026 14:32
                    </p>
                </div>
                <span className={styles.separator}></span>
                <Link to={'/'} className={styles.userIcon}>
                    <img src={userIcon} alt="user profile" />
                </Link>
            </div>
        </>
    );
}