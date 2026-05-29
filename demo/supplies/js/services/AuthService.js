/**
 * AuthService — talks to the AUTH microservice.
 *
 * Persists the JWT under the `supplies_jwt` key so sessions stay isolated
 * from the existing CMS admin (`admin_jwt`). The token decoding helpers
 * live in `js/auth.js`; here we only handle the network side.
 */
import { resolveBases, request } from './apiClient.js';

const STORAGE_KEY = 'supplies_jwt';

export class AuthService {
    constructor({ authBaseUrl, authBaseUrlFallback } = {}) {
        this.bases = resolveBases({
            remote: authBaseUrl,
            local: authBaseUrlFallback,
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
