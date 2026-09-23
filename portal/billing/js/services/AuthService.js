/**
 * AuthService — habla con el microservicio AUTH.
 *
 * BILLING no tiene usuarios propios: los tres servicios base —AUTH, EVENTS y
 * FILES— son los mismos para todos los productos de BearSoft. Acá sólo vive
 * la parte de red; decodificar el token es cosa de `js/auth.js`.
 */
import { AUTH_URL, AUTH_URL_LOCAL, STORAGE_TOKEN_KEY } from '../config.js';
import { resolveBases, request } from './apiClient.js';

const BASES = resolveBases({ remote: AUTH_URL, local: AUTH_URL_LOCAL });

/**
 * Pide el token a AUTH y lo guarda.
 *
 * @param {string} email Correo del usuario.
 * @param {string} password Su contraseña.
 * @returns {Promise<string>} El token emitido.
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

/** Si hay un token guardado, sea o no válido: expirarlo es cosa de `auth.js`. */
export function isAuthenticated() {
    return Boolean(localStorage.getItem(STORAGE_TOKEN_KEY));
}
