const API_URL = import.meta.env.VITE_API_URL ?? '/api/v1';

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, {
        ...init,
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            ...init?.headers,
        },
    });

    if (!response.ok) {
        let detail = `Request failed with status ${response.status}`;
        try {
            const body = (await response.json()) as { detail?: string };
            detail = body.detail ?? detail;
        } catch {
            // Keep the HTTP status when the server did not return JSON.
        }
        throw new Error(detail);
    }

    return (await response.json()) as T;
}