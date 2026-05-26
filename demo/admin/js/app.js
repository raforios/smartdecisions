/**
 * Entry point for the admin shell (index.html).
 *
 * Boot sequence:
 *   1. Load config.json (shared with the public portal).
 *   2. If no JWT, bounce to login.html.
 *   3. Instantiate CmsAdminService + FilesService.
 *   4. Wire sidebar navigation, logout, "Nuevo" button.
 *   5. Mount the first entity panel (news).
 */
import { AuthService } from './services/AuthService.js';
import { CmsAdminService } from './services/CmsAdminService.js';
import { FilesService } from './services/FilesService.js';
import { ENTITY_CONFIGS } from './entityConfigs.js';
import { EntityPanel } from './EntityPanel.js';

const CONFIG_URL = '../data/config.json';
const DEFAULT_ENTITY = 'news';

document.addEventListener('DOMContentLoaded', async () => {
    const config = await fetch(CONFIG_URL, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null);
    if (!config?.api) {
        document.body.innerHTML = '<p class="form-error">No se pudo cargar config.json</p>';
        return;
    }

    const auth = new AuthService(config.api);
    if (!auth.isAuthenticated()) {
        window.location.replace('login.html');
        return;
    }

    const cmsAdmin = new CmsAdminService(config.api);
    const files = new FilesService(config.api);

    _showCurrentUser();
    document.getElementById('logout-btn').onclick = () => {
        auth.logout();
        window.location.replace('login.html');
    };

    const hostEl = document.getElementById('panel-host');
    const titleEl = document.getElementById('panel-title');
    const newBtn = document.getElementById('new-item-btn');

    const panels = Object.fromEntries(
        Object.entries(ENTITY_CONFIGS).map(([key, cfg]) => [
            key,
            new EntityPanel({ entity: key, config: cfg, cmsAdmin, files }),
        ]),
    );

    function activate(entity) {
        document.querySelectorAll('#admin-nav .nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.entity === entity);
        });
        panels[entity].mount(hostEl, titleEl, newBtn);
    }

    document.querySelectorAll('#admin-nav .nav-item').forEach(btn => {
        btn.onclick = () => activate(btn.dataset.entity);
    });

    activate(DEFAULT_ENTITY);
});


function _showCurrentUser() {
    // The JWT carries `email` in the payload; decode without verifying
    // signature (the server validated it on every protected call).
    const token = localStorage.getItem('admin_jwt');
    if (!token) return;
    try {
        const [, body] = token.split('.');
        const padded = body.replace(/-/g, '+').replace(/_/g, '/');
        const payload = JSON.parse(atob(padded));
        if (payload?.email) {
            document.getElementById('current-user').textContent = payload.email;
        }
    } catch (err) {
        // Token is opaque to us if decoding fails; ignore silently.
    }
}
