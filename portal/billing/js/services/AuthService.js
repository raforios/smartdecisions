/**
 * AuthService — talks to the AUTH microservice.
 *
 * BILLING has no users of its own: the three base services —AUTH, EVENTS and
 * FILES— are the same for every BearSoft product. Only the network part lives
 * here; decoding the token belongs to `js/auth.js`.
 */
import { AUTH_URL, AUTH_URL_LOCAL, STORAGE_TOKEN_KEY } from '../config.js';
import { resolveBases, request } from './apiClient.js';

const BASES = resolveBases({ remote: AUTH_URL, local: AUTH_URL_LOCAL });

/**
 * Asks AUTH for the token and stores it.
 *
 * @param {string} email The user's email.
 * @param {string} password Their password.
 * @returns {Promise<string>} The issued token.
 */
export async function login(email, password) {
    const response = await request(BASES, '/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || `Error ${response.status} al iniciar sesión.`);
    }
    const data = await response.json();
    localStorage.setItem(STORAGE_TOKEN_KEY, data.access_token);
    return data.access_token;
}

/** Whether a token is stored, valid or not: expiring it belongs to `auth.js`. */
export function isAuthenticated() {
    return Boolean(localStorage.getItem(STORAGE_TOKEN_KEY));
}
