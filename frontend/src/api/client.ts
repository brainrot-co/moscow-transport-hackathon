export const API_URL = import.meta.env.VITE_API_URL ?? '/api/v1';

const LOCAL_TOKEN_KEY = 'transport-access-token';
const SESSION_TOKEN_KEY = 'transport-session-token';

export class ApiError extends Error {
    public readonly status: number;
    public readonly detail: string;

    constructor(
        status: number,
        detail: string,
    ) {
        super(detail);
        this.name = 'ApiError';
        this.status = status;
        this.detail = detail;
    }
}

export function getAccessToken() {
    return window.sessionStorage.getItem(SESSION_TOKEN_KEY)
        ?? window.localStorage.getItem(LOCAL_TOKEN_KEY);
}

export function setAccessToken(token: string, persistent = false) {
    clearAccessToken();
    const storage = persistent ? window.localStorage : window.sessionStorage;
    storage.setItem(persistent ? LOCAL_TOKEN_KEY : SESSION_TOKEN_KEY, token);
}

export function clearAccessToken() {
    window.localStorage.removeItem(LOCAL_TOKEN_KEY);
    window.sessionStorage.removeItem(SESSION_TOKEN_KEY);
}

interface ApiRequestOptions extends RequestInit {
    auth?: boolean;
    retryOnUnauthorized?: boolean;
}

let refreshInFlight: Promise<string> | null = null;

async function parseError(response: Response) {
    let detail = `Request failed with status ${response.status}`;
    try {
        const body = (await response.json()) as { detail?: string };
        detail = body.detail ?? detail;
    } catch {
        // Keep the HTTP status when the server did not return JSON.
    }
    return new ApiError(response.status, detail);
}

async function refreshAccessToken() {
    if (!refreshInFlight) {
        refreshInFlight = (async () => {
            const response = await fetch(`${API_URL}/refresh`, {
                method: 'POST',
                credentials: 'include',
                headers: { Accept: 'application/json' },
            });
            if (!response.ok) {
                clearAccessToken();
                throw await parseError(response);
            }
            const body = (await response.json()) as { access_token: string };
            const persistent = window.localStorage.getItem(LOCAL_TOKEN_KEY) !== null;
            setAccessToken(body.access_token, persistent);
            return body.access_token;
        })().finally(() => {
            refreshInFlight = null;
        });
    }
    return refreshInFlight;
}

export async function apiRequest<T>(
    path: string,
    options: ApiRequestOptions = {},
): Promise<T> {
    const {
        auth = true,
        retryOnUnauthorized = true,
        headers,
        ...init
    } = options;
    const token = auth ? getAccessToken() : null;
    const response = await fetch(`${API_URL}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...headers,
        },
    });

    if (response.status === 401 && auth && retryOnUnauthorized) {
        const refreshedToken = await refreshAccessToken();
        return apiRequest<T>(path, {
            ...options,
            headers: {
                ...headers,
                Authorization: `Bearer ${refreshedToken}`,
            },
            retryOnUnauthorized: false,
        });
    }
    if (!response.ok) {
        throw await parseError(response);
    }
    if (response.status === 204) {
        return undefined as T;
    }
    return (await response.json()) as T;
}
