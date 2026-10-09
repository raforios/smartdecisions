/**
 * BILLING — startup and navigation.
 *
 * One page with sections, not routes: the counter opens once at the start of
 * the shift and is not reloaded all day. The menu hides what the role cannot
 * do, but the backend is the one in charge — this only avoids showing a
 * button that would answer 403.
 */
import { clearSession, getEmail, getRole, isTokenExpired } from './auth.js';
import { LOGIN_PATH } from './config.js';
import { BillingService, errorText } from './services/BillingService.js';
import { errorCard, escapeHtml, notify } from './ui.js';

import { mountCounter } from './pages/CounterPage.js';
import { mountSales } from './pages/SalesPage.js';
import { mountCatalog } from './pages/CatalogPage.js';
import { mountPurchases } from './pages/PurchasesPage.js';
import { mountDashboard } from './pages/DashboardPage.js';
import { mountSettings } from './pages/SettingsPage.js';
import { mountCash } from './pages/CashPage.js';
import { mountCashSessions } from './pages/CashSessionsPage.js';

const SECTIONS = {
    counter: mountCounter,
    cash: mountCash,
    tills: mountCashSessions,
    sales: mountSales,
    catalog: mountCatalog,
    purchases: mountPurchases,
    dashboard: mountDashboard,
    settings: mountSettings
};

/** The open section survives an F5: the shift is not lost by reloading. */
const LAST_SECTION_KEY = 'billing_section';

/** How often to check for tills left to close. */
const TILL_ALERT_EVERY_MS = 5 * 60 * 1000;

/**
 * Open-till warning: past the hour the merchant configured, or open since
 * another day. To the seller, their own; to the manager, all of them.
 */
async function refreshTillAlert() {
    const banner = document.getElementById('till-alert');
    try {
        const alerts = await BillingService.tillAlerts();
        if (!alerts.items.length) {
            banner.hidden = true;
            return;
        }
        const names = alerts.items.map((item) => escapeHtml(item.user_email)
            + (item.expired ? ` (desde el ${escapeHtml(item.business_day)})` : '')).join(', ');
        banner.innerHTML = `<div class="card form-error">Cajas sin cerrar: ${names}.
            Cada caja es de un día: ciérralas antes de que termine.</div>`;
        banner.hidden = false;
    } catch (error) {
        // The warning is a help: if it fails, the rest of the portal carries on.
        banner.hidden = true;
    }
}

async function show(name) {
    const view = document.getElementById('view');
    const mount = SECTIONS[name];
    if (!mount) return;

    document.querySelectorAll('.nav-item').forEach((item) => {
        if (item.dataset.section === name) item.setAttribute('aria-current', 'page');
        else item.removeAttribute('aria-current');
    });
    sessionStorage.setItem(LAST_SECTION_KEY, name);

    // Each section mounts in its own container. If the user switches section
    // while the previous one waits for the API, the previous one keeps working
    // on a container that is no longer on screen: it neither finds nulls when
    // it finishes nor paints its error over the new section.
    const container = document.createElement('div');
    container.innerHTML = '<p class="muted">Cargando…</p>';
    view.replaceChildren(container);
    try {
        await mount(container);
    } catch (error) {
        if (!container.isConnected) return;
        container.innerHTML = errorCard('No se pudo abrir la sección',
                                        errorText(error, 'El servicio no respondió.'));
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    if (isTokenExpired()) {
        clearSession();
        window.location.replace(LOGIN_PATH);
        return;
    }

    const role = getRole();
    document.getElementById('userChip').textContent = `${getEmail() || 'usuario'} · ${role || '—'}`;
    document.getElementById('logout').addEventListener('click', () => {
        clearSession();
        window.location.replace(LOGIN_PATH);
    });

    // A button the role cannot use is not shown: pressing it would only give
    // a 403 and the feeling that the system is broken.
    document.querySelectorAll('.nav-item[data-roles]').forEach((item) => {
        if (!item.dataset.roles.split(',').includes(role)) item.hidden = true;
    });

    document.getElementById('nav').addEventListener('click', (event) => {
        const button = event.target.closest('.nav-item');
        if (button && !button.hidden) show(button.dataset.section);
    });

    // The merchant's name in the bar: it tells one pharmacy from another when
    // someone manages several.
    try {
        const settings = await BillingService.getSettings();
        document.getElementById('shopName').textContent = settings.trade_name;
    } catch (error) {
        if (error.code === 'SETTINGS_NOT_FOUND') {
            document.getElementById('shopName').textContent = 'Sin configurar';
            notify('Configura el comercio antes de vender.', 'info');
            await show('settings');
            return;
        }
        document.getElementById('view').innerHTML = errorCard(
            'No se pudo conectar con el servicio',
            errorText(error, 'Revisa que BILLING esté corriendo.')
        );
        return;
    }

    refreshTillAlert();
    setInterval(refreshTillAlert, TILL_ALERT_EVERY_MS);

    const saved = sessionStorage.getItem(LAST_SECTION_KEY);
    const visible = [...document.querySelectorAll('.nav-item')].filter((item) => !item.hidden);
    await show(saved && SECTIONS[saved] ? saved : visible[0]?.dataset.section || 'counter');
});
