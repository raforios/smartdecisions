/**
 * apiClient — shared base/transport helpers for the admin services.
 *
 * Resolves primary/fallback URLs with localhost auto-detection (same
 * convention as MiningApiService/CmsApiService on the public portal) and
 * exposes a `request` helper that tries the primary first and falls to
 * the secondary only on transport errors (network drop, CORS). HTTP
 * 4xx/5xx responses are returned untouched so the caller can react.
 */
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0']);

export function resolveBases({ remote, local } = {}) {
    const r = remote?.replace(/\/$/, '') || '';
    const l = local?.replace(/\/$/, '') || '';
    const hostname = typeof window !== 'undefined'
        ? window.location.hostname
        : '';
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
    const token = localStorage.getItem('admin_jwt');
    return token ? { Authorization: `Bearer ${token}` } : {};
}
