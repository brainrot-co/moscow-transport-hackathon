import { useState } from 'react';
import clsx from 'clsx';

import styles from './LoadGraph.module.scss';
import arrow from '../../assets/grow-icon.svg';
import type { ForecastRow } from '../../api/forecast';

const timeRanges = ['Сегодня', '7 дней', '30 дней'];

interface LoadGraphProps {
    rows: ForecastRow[];
}

export default function LoadGraph({ rows }: LoadGraphProps) {
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
            <div className={styles.graphData}>
                {rows.length === 0 ? (
                    <p>Нет данных для выбранного периода</p>
                ) : (
                    rows.slice(0, 24).map((row) => (
                        <div key={`${row.route}-${row.ts}`} className={styles.graphPoint}>
                            <span>{row.route}</span>
                            <strong>{row.value ?? row.yhat ?? '—'}</strong>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}