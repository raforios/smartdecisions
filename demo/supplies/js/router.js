/**
 * Tiny hash-based router for the Supplies SPA.
 *
 * Routes are flat keys (`dashboard`, `catalog`, ...). Each route is bound
 * to a `mount(host, context)` async function. The router takes care of:
 *   - listening to hashchange,
 *   - guarding against roles via the optional `requiresRole` predicate,
 *   - rendering an empty placeholder while a page mounts.
 */
import { hasRole } from './auth.js';

export class Router {
    constructor({ hostEl, titleEl, actionsEl, defaultRoute }) {
        this.hostEl = hostEl;
        this.titleEl = titleEl;
        this.actionsEl = actionsEl;
        this.defaultRoute = defaultRoute;
        this.routes = new Map();
        this.context = {};
        this._currentKey = null;
    }

    setContext(context) {
        this.context = context;
    }

    register(key, { title, requiresRole, mount }) {
        this.routes.set(key, { title, requiresRole, mount });
    }

    start() {
        window.addEventListener('hashchange', () => this._handle());
        this._handle();
    }

    go(key) {
        window.location.hash = `#/${key}`;
    }

    async _handle() {
        const key = (window.location.hash.replace(/^#\/?/, '') || this.defaultRoute).split('/')[0];
        const route = this.routes.get(key);
        if (!route) {
            window.location.hash = `#/${this.defaultRoute}`;
            return;
        }
        if (route.requiresRole && !route.requiresRole.some(r => hasRole(r))) {
            this._renderForbidden();
            return;
        }

        this._currentKey = key;
        this._highlightNav(key);
        this.titleEl.textContent = route.title || '';
        this.actionsEl.innerHTML = '';
        this.hostEl.innerHTML = '<p class="sup-placeholder">Cargando…</p>';

        try {
            await route.mount({
                host: this.hostEl,
                title: this.titleEl,
                actions: this.actionsEl,
                ...this.context,
            });
        } catch (err) {
            console.error('Router mount error', err);
            this.hostEl.innerHTML =
                `<p class="sup-form-error">Error al cargar la vista: ${err.message}</p>`;
        }
    }

    _highlightNav(key) {
        document.querySelectorAll('#sup-nav .sup-nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.route === key);
        });
    }

    _renderForbidden() {
        this.titleEl.textContent = 'Acceso restringido';
        this.actionsEl.innerHTML = '';
        this.hostEl.innerHTML =
            '<div class="sup-card sup-card-padded"><p class="sup-muted">No tienes permisos para acceder a esta vista.</p></div>';
    }
}
