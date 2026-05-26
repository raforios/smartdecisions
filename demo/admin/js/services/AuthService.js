/**
 * AuthService — talks to the AUTH microservice.
 *
 * `login` calls POST /v1/auth/login and persists the token in
 * localStorage so subsequent admin requests can attach it. `logout`
 * clears the token. `isAuthenticated` is a cheap presence check; the
 * server enforces the actual validity on every protected call.
 */
import { resolveBases, request } from './apiClient.js';

const STORAGE_KEY = 'admin_jwt';

export class AuthService {
    constructor({ authBaseUrl, authBaseUrlFallback } = {}) {
        this.bases = resolveBases({
            remote: authBaseUrl, local: authBaseUrlFallback,
        });
    }

    async login(email, password) {
        const response = await request(this.bases, '/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
            const detail = await response.json().catch(() => null);
            const message = detail?.detail || `HTTP ${response.status}`;
            throw new Error(message);
        }
        const data = await response.json();
        localStorage.setItem(STORAGE_KEY, data.access_token);
        return data.access_token;
    }

    logout() {
        localStorage.removeItem(STORAGE_KEY);
    }

    isAuthenticated() {
        return Boolean(localStorage.getItem(STORAGE_KEY));
    }
}
