/**
 * login.js
 *
 * Entry point for login.html. Loads parametric config, wires the form to
 * AuthService.login() and redirects to the dashboard on success.
 */
import { AuthService } from './services/AuthService.js';
import { ConfigService } from './services/ConfigService.js';
import { Toast } from './components/Toast.js';

(async function init() {
    let config;
    try {
        config = await ConfigService.load();
    } catch (error) {
        document.body.innerHTML = `<div style="padding:2rem;color:#B82227;font-family:sans-serif;">
            Error al cargar configuración: ${error.message}</div>`;
        return;
    }

    // Branding parametrizable
    document.getElementById('hero-logo').src = config.event.logo;
    document.getElementById('hero-title').textContent = config.event.shortName;
    document.getElementById('hero-subtitle').textContent = config.event.longName;
    document.getElementById('hero-tagline').textContent = config.event.subtitle;
    document.getElementById('footer-organizer').textContent = config.event.organizer;
    document.title = `${config.event.fullName} | Acceso de Operador`;

    const auth = new AuthService(config);

    // Si ya hay sesión válida, saltamos directo al dashboard.
    if (auth.isAuthenticated()) {
        window.location.replace(config.auth.appPath);
        return;
    }

    const form    = document.getElementById('login-form');
    const button  = document.getElementById('login-btn');
    const emailEl = document.getElementById('email');
    const passEl  = document.getElementById('password');

    // Mostrar/ocultar la contraseña.
    const togglePass = document.getElementById('toggle-pass');
    if (togglePass) {
        togglePass.addEventListener('click', () => {
            const show = passEl.type === 'password';
            passEl.type = show ? 'text' : 'password';
            togglePass.querySelector('i').className = show ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
            togglePass.setAttribute('aria-label', show ? 'Ocultar contraseña' : 'Mostrar contraseña');
            passEl.focus();
        });
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const email    = emailEl.value.trim();
        const password = passEl.value;

        if (!email || !password) {
            Toast.danger('Email y contraseña son obligatorios.');
            return;
        }

        button.disabled = true;
        button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Ingresando...';
        try {
            await auth.login(email, password);
            Toast.success('Sesión iniciada. Redirigiendo...');
            setTimeout(() => window.location.replace(config.auth.appPath), 400);
        } catch (error) {
            Toast.danger(`Error de autenticación: ${error.message}`);
            button.disabled = false;
            button.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> Iniciar Sesión';
        }
    });
})();
