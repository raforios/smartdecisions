/**
 * Sign-in screen of the ES-module portals, the same one SmartDecisions shows.
 *
 * Against AUTH, like every BearSoft product. If there is already a session, it
 * goes straight in instead of asking for the credentials again.
 */
import { REMEMBER_EMAIL_KEY as REMEMBER_KEY } from '/js/config.js';
import { isTokenExpired } from './auth.js';
import { isAuthenticated, login } from './AuthService.js';

function remembered() {
    try {
        return localStorage.getItem(REMEMBER_KEY) || '';
    } catch (error) {
        return '';
    }
}

function store(value) {
    try {
        if (value) localStorage.setItem(REMEMBER_KEY, value);
        else localStorage.removeItem(REMEMBER_KEY);
    } catch (error) {
        // Storage blocked: nothing is remembered.
    }
}

// The classic scripts (common/js/ui.js) run before this module, so SD_UI exists.
const start = () => {
    if (isAuthenticated() && !isTokenExpired()) {
        window.location.replace('index.html');
        return;
    }

    const { qs, setButtonBusy, revealToggle } = window.SD_UI;
    const form = qs('#loginForm');
    const note = qs('#loginNote');
    const button = qs('#loginButton');
    const remember = qs('#rememberEmail');
    revealToggle(qs('#loginPassword'), qs('#passwordToggle'));

    const email = remembered();
    if (email) {
        form.elements.email.value = email;
        remember.checked = true;
        qs('#loginPassword').focus();
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        note.className = 'form-note';
        note.textContent = '';
        const data = new FormData(form);
        const address = String(data.get('email') || '').trim();
        const password = String(data.get('password') || '');
        if (!address || !password) {
            note.classList.add('error');
            note.textContent = 'Completa tu correo y tu contraseña.';
            return;
        }
        const done = setButtonBusy(button, 'Entrando…');
        try {
            await login(address, password);
            store(remember.checked ? address : '');
            window.location.replace('index.html');
        } catch (failure) {
            note.classList.add('error');
            note.textContent = failure.message || 'No se pudo iniciar sesión.';
            done();
        }
    });
};

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
