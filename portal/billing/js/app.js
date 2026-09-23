/**
 * Entry point for the Supplies shell (index.html).
 *
 * Boot sequence:
 *   1. Load config.json shared across the portal.
 *   2. Redirect to login.html if no JWT is present.
 *   3. Instantiate AuthService + SuppliesService.
 *   4. Wire sidebar nav, role-based visibility, logout, hamburger drawer.
 *   5. Register page mounts on the router and start it.
 */
import { AuthService } from './services/AuthService.js';
import { SuppliesService } from './services/SuppliesService.js';
import { Router } from './router.js';
import { clearSession, getEmail, getRole, hasRole, isTokenExpired, ROLES } from './auth.js';
import { initModalBindings, showSessionExpiredModal } from './ui.js';

import { mountDashboard } from './pages/DashboardPage.js';
import { mountCatalog } from './pages/CatalogPage.js';
import { mountRequests } from './pages/RequestsPage.js';
import { mountEntries } from './pages/EntriesPage.js';
import { mountSuppliers } from './pages/SuppliersPage.js';
import { mountKardex } from './pages/KardexPage.js';
import { mountReports } from './pages/ReportsPage.js';

const CONFIG_URL = '../data/config.json';

document.addEventListener('DOMContentLoaded', async () => {
    const config = await fetch(CONFIG_URL, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null);
    if (!config?.api) {
        document.body.innerHTML =
            '<p class="sup-form-error">No se pudo cargar config.json</p>';
        return;
    }

    const auth = new AuthService(config.api);
    if (!auth.isAuthenticated() || isTokenExpired()) {
        // Either no token at all or the local clock confirms expiry —
        // bounce straight to login without flashing the shell.
        clearSession();
        window.location.replace('login.html');
        return;
    }

    const supplies = new SuppliesService(config.api);

    // Single global listener for 401-induced session expiry. The
    // apiClient dispatches the event from any failed authenticated call;
    // we block the UI and let the user re-login.
    window.addEventListener('supplies:session-expired', () => {
        showSessionExpiredModal({ onConfirm: () => auth.logout() });
    });

    _renderCurrentUser();
    _applyRoleVisibility();
    _wireLogout(auth);
    _wireSidebarToggle();
    initModalBindings();

    const router = new Router({
        hostEl: document.getElementById('sup-page'),
        titleEl: document.getElementById('page-title'),
        actionsEl: document.getElementById('page-actions'),
        defaultRoute: _defaultRouteForRole(),
    });

    router.setContext({ api: supplies, router });

    router.register('dashboard', {
        title: 'Dashboard',
        mount: mountDashboard,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER, ROLES.REQUESTER],
    });
    router.register('catalog', {
        title: 'Catálogo',
        mount: mountCatalog,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER],
    });
    router.register('requests', {
        title: 'Solicitudes',
        mount: mountRequests,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER, ROLES.REQUESTER],
    });
    router.register('entries', {
        title: 'Notas de Ingreso',
        mount: mountEntries,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER],
    });
    router.register('suppliers', {
        title: 'Proveedores',
        mount: mountSuppliers,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER],
    });
    router.register('kardex', {
        title: 'Kárdex',
        mount: mountKardex,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER],
    });
    router.register('reports', {
        title: 'Reportes',
        mount: mountReports,
        requiresRole: [ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER],
    });

    document.querySelectorAll('#sup-nav .sup-nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.route;
            router.go(target);
            _closeSidebarOnMobile();
        });
    });

    router.start();
});


function _renderCurrentUser() {
    document.getElementById('current-user-email').textContent = getEmail() || '—';
    document.getElementById('current-user-role').textContent = getRole() || '—';
}

function _applyRoleVisibility() {
    document.querySelectorAll('#sup-nav .sup-nav-item').forEach(btn => {
        const required = (btn.dataset.roles || '').split(',').map(s => s.trim()).filter(Boolean);
        if (!required.length) return;
        btn.hidden = !required.some(r => hasRole(r));
    });
}

function _wireLogout(auth) {
    document.getElementById('logout-btn').addEventListener('click', () => {
        auth.logout();
        window.location.replace('login.html');
    });
}

const COLLAPSE_KEY = 'supplies_sidebar_collapsed';

function _wireSidebarToggle() {
    const shell = document.querySelector('.sup-shell');
    const toggle = document.getElementById('sidebar-toggle');
    const backdrop = document.getElementById('sup-sidebar-backdrop');
    toggle.addEventListener('click', () => shell.classList.toggle('sidebar-open'));
    backdrop.addEventListener('click', () => shell.classList.remove('sidebar-open'));

    // Desktop: fold the menu away for more table width, and remember the
    // choice — someone who works on reports all day should not re-hide it
    // on every page load.
    const collapse = document.getElementById('sidebar-collapse');
    if (localStorage.getItem(COLLAPSE_KEY) === '1') {
        shell.classList.add('sidebar-collapsed');
    }
    collapse.addEventListener('click', () => {
        const collapsed = shell.classList.toggle('sidebar-collapsed');
        localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    });
}

function _closeSidebarOnMobile() {
    const shell = document.querySelector('.sup-shell');
    if (window.matchMedia('(max-width: 900px)').matches) {
        shell.classList.remove('sidebar-open');
    }
}

function _defaultRouteForRole() {
    // REQUESTERS land on their request workspace directly; others on dashboard.
    return hasRole(ROLES.REQUESTER)
            && !hasRole(ROLES.ADMIN) && !hasRole(ROLES.WAREHOUSE_MANAGER)
        ? 'requests'
        : 'dashboard';
}
