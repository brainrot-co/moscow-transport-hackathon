import { useCallback, useEffect, useState } from 'react';

import {
    getForecast,
    getForecastMeta,
    getRouteLoad,
    type ForecastMeta,
    type ForecastRow,
    type RouteLoadResponse,
} from '../api/forecast';

interface ForecastState {
    rows: ForecastRow[];
    meta: ForecastMeta | null;
    load: RouteLoadResponse | null;
    loading: boolean;
    error: string | null;
    refresh: () => void;
}

export function useForecast(days = 1): ForecastState {
    const [reload, setReload] = useState(0);
    const [state, setState] = useState<ForecastState>({
        rows: [],
        meta: null,
        load: null,
        loading: true,
        error: null,
        refresh: () => undefined,
    });
    const refresh = useCallback(() => setReload((value) => value + 1), []);

    useEffect(() => {
        let cancelled = false;
        setState((current) => ({ ...current, loading: true, error: null, refresh }));
        void (async () => {
            try {
                const meta = await getForecastMeta();
                if (!meta.available || !meta.now) {
                    if (!cancelled) {
                        setState({ rows: [], meta, load: null, loading: false, error: null, refresh });
                    }
                    return;
                }
                const date = meta.now.slice(0, 10);
                const start = new Date(`${date}T00:00:00+03:00`);
                const end = new Date(start.getTime() + days * 24 * 60 * 60 * 1000 - 60 * 60 * 1000);
                const [forecast, load] = await Promise.all([
                    getForecast(start.toISOString(), end.toISOString(), 'hour'),
                    getRouteLoad(date),
                ]);
                if (!cancelled) {
                    setState({
                        rows: forecast.data,
                        meta: forecast.meta,
                        load,
                        loading: false,
                        error: null,
                        refresh,
                    });
                }
            } catch (error) {
                if (!cancelled) {
                    setState({
                        rows: [],
                        meta: null,
                        load: null,
                        loading: false,
                        error: error instanceof Error ? error.message : 'Не удалось загрузить прогноз',
                        refresh,
                    });
                }
            }
        })();
        const interval = window.setInterval(refresh, 30_000);
        return () => {
            cancelled = true;
            window.clearInterval(interval);
        };
    }, [days, refresh, reload]);

    return state;
}
