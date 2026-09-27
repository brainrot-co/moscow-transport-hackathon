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
    now: string | null;
    published_at: string | null;
    stale: boolean;
    cold_start_routes: number[];
    model: Record<string, string | null>;
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

export type LoadLevel = 'low' | 'medium' | 'high';

export interface RouteLoad {
    route: number;
    value: number | null;
    load_level: LoadLevel | null;
    ratio: number | null;
    norm_low: number | null;
    norm_median: number | null;
    norm_high: number | null;
    norm_days: number;
    norm_from: string | null;
    norm_to: string | null;
}

export interface RouteLoadResponse {
    schema_version: number;
    date: string;
    day_kind: 'workday' | 'day_off';
    day_type: string | null;
    norm_weeks: number;
    low_quantile: number;
    high_quantile: number;
    min_deviation: number;
    data: RouteLoad[];
    meta: ForecastMeta;
}

export function getRouteLoad(date: string): Promise<RouteLoadResponse> {
    return apiRequest<RouteLoadResponse>(`/forecast/load?${new URLSearchParams({ date }).toString()}`);
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

export interface ScenarioDraft {
    kind: 'model_factor' | 'scenario';
    factor: string;
    value: number;
    routes: number[] | null;
    date_from: string;
    date_to: string;
    days: 'all' | 'weekdays' | 'weekends';
    hour_from: number | null;
    hour_to: number | null;
    title?: string | null;
    comment?: string | null;
    source_url?: string | null;
    active?: boolean;
}

export interface ScenarioRecord extends ScenarioDraft {
    id: number;
    created_by: number;
    created_at: string;
    updated_at: string;
}

export interface ForecastPreviewRequest {
    date_from: string;
    date_to: string;
    routes?: number[];
    granularity?: 'hour' | 'day' | 'week' | 'month';
    model_factors?: Record<string, number>;
    draft?: ScenarioDraft[];
}

export function previewForecast(payload: ForecastPreviewRequest) {
    return apiRequest<ForecastResponse>('/forecast/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export function getScenarios(dateFrom?: string, dateTo?: string) {
    const params = new URLSearchParams({ active: 'true' });
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    return apiRequest<ScenarioRecord[]>(`/scenarios?${params.toString()}`);
}

export function createScenario(payload: ScenarioDraft) {
    return apiRequest<ScenarioRecord>('/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export function updateScenario(id: number, payload: Partial<ScenarioDraft>) {
    return apiRequest<ScenarioRecord>(`/scenarios/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
}

export function deleteScenario(id: number) {
    return apiRequest<void>(`/scenarios/${id}`, { method: 'DELETE' });
}
