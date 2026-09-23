/**
 * Pantalla de acceso.
 *
 * Contra AUTH, como todo producto de BearSoft. Si ya hay sesión, entra
 * directo en vez de pedir las credenciales otra vez.
 */
import { isTokenExpired } from './auth.js';
import { isAuthenticated, login } from './services/AuthService.js';

document.addEventListener('DOMContentLoaded', () => {
    if (isAuthenticated() && !isTokenExpired()) {
        window.location.replace('index.html');
        return;
    }

    const form = document.getElementById('login-form');
    const submit = document.getElementById('login-submit');
    const error = document.getElementById('login-error');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        error.hidden = true;
        const label = submit.textContent;
        submit.disabled = true;
        submit.textContent = 'Entrando…';
        try {
            const data = new FormData(form);
            await login(data.get('email'), data.get('password'));
            window.location.replace('index.html');
        } catch (failure) {
            error.textContent = failure.message || 'Credenciales inválidas.';
            error.hidden = false;
            submit.disabled = false;
            submit.textContent = label;
        }
    });
});
