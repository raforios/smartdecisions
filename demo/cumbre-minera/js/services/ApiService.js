/**
 * ApiService
 *
 * Thin fetch wrapper that automatically attaches the bearer token issued by
 * the AUTH microservice to every request, builds query strings, and routes
 * 401 responses back to the login screen.
 */
export class ApiService {
    constructor(baseUrl, authService, onUnauthorized) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.auth = authService;
        this.onUnauthorized = onUnauthorized || (() => {});
    }

    async get(path, queryParams = {}) {
        const query = this._buildQuery(queryParams);
        return this._request('GET', `${path}${query}`);
    }

    async post(path, body) {
        return this._request('POST', path, body);
    }

    async patch(path, body) {
        return this._request('PATCH', path, body);
    }

    async del(path) {
        return this._request('DELETE', path);
    }

    /**
     * Downloads a binary file (e.g. an .xlsx report) with the bearer token
     * attached and triggers a browser "Save as" using the given filename.
     */
    async download(path, filename, queryParams = {}) {
        const query = this._buildQuery(queryParams);
        const headers = {};
        const token = this.auth.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(`${this.baseUrl}${path}${query}`, { method: 'GET', headers });

        if (response.status === 401) {
            this.auth.logout();
            this.onUnauthorized();
            throw new Error('Sesión expirada. Vuelve a iniciar sesión.');
        }
        if (!response.ok) {
            const text = await response.text();
            const payload = text ? this._safeJson(text) : null;
            const detail = (payload && (payload.detail || payload.message))
                || `Error HTTP ${response.status}`;
            throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    async _request(method, path, body) {
        const headers = { 'Content-Type': 'application/json' };
        const token = this.auth.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const init = { method, headers };
        if (body !== undefined) init.body = JSON.stringify(body);

        const response = await fetch(`${this.baseUrl}${path}`, init);

        if (response.status === 401) {
            this.auth.logout();
            this.onUnauthorized();
            throw new Error('Sesión expirada. Vuelve a iniciar sesión.');
        }

        const text = await response.text();
        const payload = text ? this._safeJson(text) : null;

        if (!response.ok) {
            const detail = (payload && (payload.detail || payload.message))
                || `Error HTTP ${response.status}`;
            const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
            error.status = response.status;
            error.payload = payload;
            throw error;
        }
        return payload;
    }

    _buildQuery(params) {
        const entries = Object.entries(params).filter(
            ([, v]) => v !== null && v !== undefined && v !== ''
        );
        if (entries.length === 0) return '';
        const search = new URLSearchParams();
        entries.forEach(([k, v]) => search.append(k, v));
        return `?${search.toString()}`;
    }

    _safeJson(text) {
        try { return JSON.parse(text); }
        catch (_) { return text; }
    }
}
