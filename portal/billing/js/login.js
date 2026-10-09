/**
 * Sign-in screen.
 *
 * Against AUTH, like every BearSoft product. If there is already a session, it
 * goes straight in instead of asking for the credentials again.
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
