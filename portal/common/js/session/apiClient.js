/**
 * apiClient — transport helpers for the ES-module portals.
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
