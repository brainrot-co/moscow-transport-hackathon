import { useEffect, useState } from 'react';

import { getForecast, getForecastMeta, type ForecastMeta, type ForecastRow } from '../api/forecast';

interface ForecastState {
    rows: ForecastRow[];
    meta: ForecastMeta | null;
    loading: boolean;
    error: string | null;
}

export function useForecast(days = 1): ForecastState {
    const [state, setState] = useState<ForecastState>({
        rows: [],
        meta: null,
        loading: true,
        error: null,
    });

    useEffect(() => {
        const controller = new AbortController();
        void (async () => {
            try {
                const meta = await getForecastMeta();
                if (!meta.available || !meta.data_cutoff) {
                    setState({ rows: [], meta, loading: false, error: null });
                    return;
                }
                const start = new Date(`${meta.data_cutoff}T00:00:00+03:00`);
                const end = new Date(start.getTime() + days * 24 * 60 * 60 * 1000 - 60_000);
                const forecast = await getForecast(start.toISOString(), end.toISOString());
                if (!controller.signal.aborted) {
                    setState({ rows: forecast.data, meta, loading: false, error: null });
                }
            } catch (error) {
                if (!controller.signal.aborted) {
                    setState({
                        rows: [],
                        meta: null,
                        loading: false,
                        error: error instanceof Error ? error.message : 'Не удалось загрузить прогноз',
                    });
                }
            }
        })();
        return () => controller.abort();
    }, [days]);

    return state;
}