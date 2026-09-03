'use strict';

/**
 * Thin fetch wrapper that injects the JWT automatically and centralizes
 * error handling. On 401 it clears the session and bounces the user to
 * the login page — modules don't need to repeat that logic.
 */
(function () {

    function _buildHeaders(extra) {
        const headers = Object.assign({}, extra || {});
        const token = window.SD_AUTH.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    async function _handleResponse(response) {
        if (response.status === 401) {
            window.SD_AUTH.clearSession();
            // Keep the intended destination so re-login lands back on the module
            // the user was working on instead of dropping them at the home page.
            const next = encodeURIComponent(window.location.pathname);
            window.location.href = `${window.SD_CONFIG.LOGIN_PATH}?next=${next}`;
            throw new Error('Sesión expirada. Vuelve a iniciar sesión.');
        }

        let payload = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            try {
                payload = await response.json();
            } catch (_) { /* tolerate empty body */ }
        }

        if (!response.ok) {
            const detail = payload && (payload.detail || payload.message);
            const message = detail || `Error ${response.status} en el servicio.`;
            const error = new Error(message);
            error.status = response.status;
            error.payload = payload;
            // Services that follow the code contract answer with a stable
            // SCREAMING_SNAKE code instead of a sentence; modules look it up in
            // their own wording catalogue. Legacy services still send prose,
            // which keeps travelling as the message.
            if (typeof detail === 'string' && /^[A-Z][A-Z0-9_]+$/.test(detail)) {
                error.code = detail;
            }
            throw error;
        }
        return payload;
    }

    /**
     * GET helper with optional query params.
     */
    async function get(url, queryParams) {
        let fullUrl = url;
        if (queryParams) {
            const search = new URLSearchParams(queryParams).toString();
            if (search) fullUrl += (url.includes('?') ? '&' : '?') + search;
        }
        const response = await fetch(fullUrl, {
            method: 'GET',
            headers: _buildHeaders({ 'Accept': 'application/json' })
        });
        return _handleResponse(response);
    }

    /**
     * POST helper for JSON bodies.
     */
    async function post(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: _buildHeaders({
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }),
            body: body == null ? undefined : JSON.stringify(body)
        });
        return _handleResponse(response);
    }

    /**
     * POST helper for multipart form data (file uploads).
     */
    async function postFormData(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            headers: _buildHeaders({ 'Accept': 'application/json' }),
            body: formData
        });
        return _handleResponse(response);
    }

    window.SD_API = { get, post, postFormData };
})();
