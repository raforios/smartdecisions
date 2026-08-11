'use strict';

/**
 * Authentication helpers — wrap the AUTH service login/logout flow and
 * persist the JWT in sessionStorage so all module pages can read it.
 *
 * Session keys are defined in config.js so changes propagate everywhere.
 */
(function () {
    const TOKEN_KEY = window.SD_CONFIG.STORAGE_TOKEN_KEY;
    const EMAIL_KEY = window.SD_CONFIG.STORAGE_EMAIL_KEY;

    function getToken() {
        return sessionStorage.getItem(TOKEN_KEY) || '';
    }

    function getEmail() {
        return sessionStorage.getItem(EMAIL_KEY) || '';
    }

    function isAuthenticated() {
        return !!getToken();
    }

    /**
     * Reads the `exp` claim of the stored JWT and returns it as a Date, so the
     * UI can tell the user how long the session lasts instead of letting it die
     * silently mid-analysis. Returns null when unknown — callers must treat
     * that as "no information", never as "expired".
     */
    function getSessionExpiry() {
        const token = getToken();
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        try {
            let base64 = parts[1].replaceAll('-', '+').replaceAll('_', '/');
            while (base64.length % 4 !== 0) base64 += '=';
            const payload = JSON.parse(atob(base64));
            return payload.exp ? new Date(payload.exp * 1000) : null;
        } catch (decodeError) {
            return null;
        }
    }

    function clearSession() {
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(EMAIL_KEY);
    }

    /**
     * Posts credentials to AUTH and returns the access token on success.
     * Throws an Error with a user-friendly message on failure.
     */
    async function login(email, password) {
        const url = `${window.SD_CONFIG.AUTH_URL}/v1/auth/login`;
        let response;
        try {
            response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
        } catch (networkError) {
            throw new Error('No se pudo contactar al servicio de autenticación.');
        }

        let payload = {};
        try {
            payload = await response.json();
        } catch (_) {
            // body may be empty for some error codes
        }

        if (!response.ok) {
            const detail = payload && (payload.detail || payload.message);
            throw new Error(detail || 'Credenciales inválidas.');
        }

        const token = payload.access_token;
        if (!token) {
            throw new Error('La respuesta del servicio no incluye access_token.');
        }
        sessionStorage.setItem(TOKEN_KEY, token);
        sessionStorage.setItem(EMAIL_KEY, email);
        return token;
    }

    function logout() {
        clearSession();
        window.location.href = window.SD_CONFIG.LOGIN_PATH;
    }

    /**
     * Module pages call this on load. If there is no session, redirect to
     * the login screen preserving the intended destination as ?next=...
     */
    function requireAuth() {
        if (isAuthenticated()) {
            return true;
        }
        const next = encodeURIComponent(window.location.pathname);
        window.location.href = `${window.SD_CONFIG.LOGIN_PATH}?next=${next}`;
        return false;
    }

    window.SD_AUTH = {
        getToken,
        getEmail,
        getSessionExpiry,
        isAuthenticated,
        clearSession,
        login,
        logout,
        requireAuth
    };
})();
