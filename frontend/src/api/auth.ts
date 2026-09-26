import { apiRequest, clearAccessToken, setAccessToken } from './client';

interface TokenResponse {
    access_token: string;
    token_type: string;
}

export async function login(username: string, password: string, remember: boolean) {
    const body = new URLSearchParams({ username, password });
    const token = await apiRequest<TokenResponse>('/login', {
        method: 'POST',
        body,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        auth: false,
        retryOnUnauthorized: false,
    });
    setAccessToken(token.access_token, remember);
}

export async function logout() {
    try {
        await apiRequest<{ message: string }>('/logout', {
            method: 'POST',
            auth: false,
            retryOnUnauthorized: false,
        });
    } finally {
        clearAccessToken();
    }
}
