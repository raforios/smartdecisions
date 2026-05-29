/**
 * JWT helpers shared by every page.
 *
 * Decoding is signature-less on purpose: the backend already validates the
 * signature on every protected call, so the frontend only needs the public
 * claims (email, role) to render UI and gate routes.
 */
const STORAGE_KEY = 'supplies_jwt';

export function getToken() {
    return localStorage.getItem(STORAGE_KEY);
}

export function getPayload() {
    const token = getToken();
    if (!token) return null;
    try {
        const [, body] = token.split('.');
        const padded = body.replace(/-/g, '+').replace(/_/g, '/');
        return JSON.parse(atob(padded));
    } catch (err) {
        return null;
    }
}

export function getRole() {
    return getPayload()?.role || null;
}

export function getEmail() {
    return getPayload()?.email || null;
}

export function hasRole(...allowed) {
    const role = getRole();
    return allowed.includes(role);
}

/**
 * Returns true if the JWT carries an `exp` claim already in the past.
 * Used at boot time to short-circuit the session before the first API
 * call wastes a round-trip.
 */
export function isTokenExpired() {
    const payload = getPayload();
    if (!payload?.exp) return false;
    return Date.now() / 1000 >= Number(payload.exp);
}

export function clearSession() {
    localStorage.removeItem(STORAGE_KEY);
}

export const ROLES = Object.freeze({
    ADMIN: 'ADMIN',
    WAREHOUSE_MANAGER: 'WAREHOUSE_MANAGER',
    REQUESTER: 'REQUESTER',
});
