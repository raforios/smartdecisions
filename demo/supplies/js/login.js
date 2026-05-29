/**
 * Entry point for login.html.
 *
 * Reads the AUTH base URLs from data/config.json, wires the form, and
 * redirects to the supplies shell on success. Errors are surfaced inline.
 */
import { AuthService } from './services/AuthService.js';

const CONFIG_URL = '../data/config.json';

document.addEventListener('DOMContentLoaded', async () => {
    const config = await fetch(CONFIG_URL, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null);
    if (!config?.api) {
        _showError('No se pudo cargar la configuración del sitio.');
        return;
    }

    const auth = new AuthService(config.api);
    if (auth.isAuthenticated()) {
        window.location.replace('index.html');
        return;
    }

    const form = document.getElementById('login-form');
    const submit = document.getElementById('login-submit');
    form.addEventListener('submit', async event => {
        event.preventDefault();
        _hideError();
        submit.disabled = true;
        const original = submit.textContent;
        submit.textContent = 'Entrando…';
        try {
            const data = new FormData(form);
            await auth.login(data.get('email'), data.get('password'));
            window.location.replace('index.html');
        } catch (err) {
            _showError(err.message || 'Credenciales inválidas.');
            submit.disabled = false;
            submit.textContent = original;
        }
    });
});

function _showError(message) {
    const el = document.getElementById('login-error');
    el.textContent = message;
    el.hidden = false;
}

function _hideError() {
    document.getElementById('login-error').hidden = true;
}
