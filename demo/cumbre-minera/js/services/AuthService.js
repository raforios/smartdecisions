/**
 * AuthService
 *
 * Handles authentication against the AUTH microservice and JWT lifecycle.
 * Tokens and the operator email are persisted in localStorage so that the
 * dashboard pages can rehydrate after a reload.
 */
export class AuthService {
    constructor(config) {
        this.config = config;
        this.tokenKey = config.auth.tokenKey;
        this.userKey  = config.auth.userKey;
        this.authBase = config.endpoints.auth;
        this.loginEndpoint = config.auth.loginEndpoint;
    }

    async login(email, password) {
        const url = `${this.authBase}${this.loginEndpoint}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const data = await response.json();
                detail = data.detail || data.message || detail;
            } catch (_) { /* body may not be JSON */ }
            throw new Error(detail);
        }

        const data = await response.json();
        const token = data.access_token || data.token || data.jwt;
        if (!token) {
            throw new Error('La respuesta del servicio AUTH no incluye access_token.');
        }
        this._persistSession(token, email);
        return { token, email };
    }

    logout() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.userKey);
    }

    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    getUserEmail() {
        return localStorage.getItem(this.userKey);
    }

    /**
     * Returns the access role embedded in the JWT ('role' claim), or null.
     * Drives the role-based menu and section access in the dashboard.
     */
    getUserRole() {
        const token = this.getToken();
        if (!token) return null;
        try {
            const payload = token.split('.')[1];
            const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
            return decoded.role || null;
        } catch (_) {
            return null;
        }
    }

    isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;
        const expiry = this._extractExpiry(token);
        if (!expiry) return true;
        return expiry * 1000 > Date.now();
    }

    requireAuth(redirectTo) {
        if (!this.isAuthenticated()) {
            this.logout();
            window.location.replace(redirectTo || this.config.auth.loginPath);
        }
    }

    _persistSession(token, email) {
        localStorage.setItem(this.tokenKey, token);
        localStorage.setItem(this.userKey, email);
    }

    _extractExpiry(token) {
        try {
            const payload = token.split('.')[1];
            const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
            return decoded.exp || null;
        } catch (_) {
            return null;
        }
    }
}
