import { apiRequest } from './client';

export type ForecastSource = 'actual' | 'forecast' | 'forecast_seasonal' | 'mixed';

export interface ForecastRow {
    route: number;
    ts: string;
    source: ForecastSource | null;
    value: number | null;
    yhat_model: number | null;
    yhat: number | null;
    q10: number | null;
    q90: number | null;
    estimated: boolean;
    applied: Array<Record<string, unknown>>;
    availability?: string;
}

export interface ForecastMeta {
    available: boolean;
    short_run_id: string | null;
    year_run_id: string | null;
    watermark: string | null;
    data_cutoff: string | null;
    stale: boolean;
    error?: string | null;
}

export interface ForecastResponse {
    schema_version: number;
    query: {
        date_from: string;
        date_to: string;
        granularity: 'hour' | 'day' | 'week' | 'month';
    };
    data: ForecastRow[];
    meta: ForecastMeta;
}

export function getForecastMeta(): Promise<ForecastMeta> {
    return apiRequest<ForecastMeta>('/forecast/meta');
}

export function getForecast(
    dateFrom: string,
    dateTo: string,
    granularity: 'hour' | 'day' | 'week' | 'month' = 'hour',
): Promise<ForecastResponse> {
    const params = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo,
        granularity,
    });
    return apiRequest<ForecastResponse>(`/forecast?${params.toString()}`);
}