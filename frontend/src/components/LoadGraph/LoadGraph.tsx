import { useState } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import arrow from '../../assets/grow-icon.svg';

const timeRanges = ['Сегодня', '7 дней', '1 месяц'];

export default function LoadGraph() {
    const [selectedRange, setSelectedRange] = useState('Сегодня');

    return (
        <div className={styles.loadGraph}>
            <div className={styles.graphTop}>
                <div className={styles.graphTitle}>
                    <img src={arrow} alt="graph" />
                    <h6>Динамика загрузки сети</h6>
                </div>

                <div className={styles.timeRangePicker}>
                    <div
                        className={styles.selectedBackground}
                        style={{
                            transform: `translateX(${
                                timeRanges.indexOf(selectedRange) * 100
                            }%)`,
                        }}
                    />

                    {timeRanges.map((range) => (
                        <button
                            key={range}
                            type="button"
                            className={clsx(
                                styles.timeRangeItem,
                                selectedRange === range && styles.selected
                            )}
                            onClick={() => setSelectedRange(range)}
                        >
                            {range}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}