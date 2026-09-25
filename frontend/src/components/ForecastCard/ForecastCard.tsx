import styles from './ForecastCard.module.scss'

import goto from '../../assets/goto.svg'
import sunrise from '../../assets/sunrise.svg'
import vector from '../../assets/Vector.svg'

export default function ForecatsCard() {
    return (
        <>
            <div className={styles.forecastCard}>
                <div className={styles.forecastTop}>
                    <div className={styles.forecastLogo}>
                        <img src={sunrise} alt="forecast" />
                        <p>Прогноз</p>
                    </div>

                    <button>
                        <img src={goto} alt="open forecast" />
                    </button>
                </div>

                <div className={styles.forecastBottom}>
                    <p>Наибольшая загрузка ожидается <br></br>в <span>17:00 - 19:00</span></p>
                    <img src={vector} alt="forecast graph" />
                </div>
            </div>
        </>
    );
}