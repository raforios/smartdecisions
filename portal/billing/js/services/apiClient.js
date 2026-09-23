/**
 * apiClient — transport helpers for the Supplies frontend.
 *
 * Mirrors the convention used by demo/admin/js/services/apiClient.js: a
 * primary/fallback pair with localhost auto-detection, and a `request`
 * helper that only falls back on transport errors (network/CORS), not on
 * HTTP 4xx/5xx (those are surfaced as-is so callers can react).
 */
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

export function resolveBases({ remote, local } = {}) {
    const r = remote?.replace(/\/$/, '') || '';
    const l = local?.replace(/\/$/, '') || '';
    const hostname = typeof window !== 'undefined' ? window.location.hostname : '';
    if (LOCAL_HOSTS.has(hostname) && l) {
        return { primary: l, fallback: r };
    }
    return { primary: r, fallback: l };
}

export async function request(bases, path, options = {}) {
    const candidates = [bases.primary, bases.fallback].filter(Boolean);
    let lastError = null;
    for (const base of candidates) {
        try {
            return await fetch(`${base}${path}`, options);
        } catch (err) {
            lastError = err;
        }
    }
    throw lastError || new Error('All API candidates failed.');
}

/** Builds an Authorization header from the JWT stored in localStorage. */
export function authHeader() {
    const token = localStorage.getItem('supplies_jwt');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Parses the JSON body if the response is OK, otherwise throws an Error
 * whose message is the backend `detail` field (or the HTTP status fallback).
 *
 * Side effect: a 401 from any authenticated call dispatches a
 * `supplies:session-expired` window event so the shell can block the UI
 * with a single modal regardless of which page triggered the call.
 */
export async function parseJsonOrThrow(response) {
    if (response.ok) {
        if (response.status === 204) return null;
        return response.json();
    }
    let detail = null;
    try { detail = await response.json(); } catch (_) { /* ignore */ }

    if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('supplies:session-expired'));
    }

    const message = detail?.detail || `HTTP ${response.status}`;
    const error = new Error(typeof message === 'string' ? message : JSON.stringify(message));
    error.status = response.status;
    error.detail = detail;
    throw error;
}
