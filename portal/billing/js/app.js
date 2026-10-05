/**
 * BILLING — arranque y navegación.
 *
 * Una sola página con secciones, no rutas: el mostrador se abre una vez al
 * empezar el turno y no se recarga en todo el día. El menú esconde lo que el
 * rol no puede hacer, pero quien manda es el backend — esto sólo evita
 * mostrar un botón que iba a responder 403.
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

/** La sección abierta sobrevive a un F5: el turno no se pierde por recargar. */
const LAST_SECTION_KEY = 'billing_section';

/** Cada cuánto se revisa si hay cajas por cerrar. */
const TILL_ALERT_EVERY_MS = 5 * 60 * 1000;

/**
 * Aviso de cajas abiertas: pasada la hora que configuró el comercio, o
 * abiertas desde otro día. Al vendedor, la suya; al gerente, todas.
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
        // El aviso es una ayuda: si falla, el resto del portal sigue igual.
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

    // Cada sección se monta en su propio contenedor. Si el usuario cambia de
    // sección mientras la anterior espera al API, la anterior sigue sobre un
    // contenedor que ya no está en pantalla: ni encuentra nulos al terminar
    // ni pinta su error encima de la sección nueva.
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

    // Un botón que el rol no puede usar no se muestra: pulsarlo sólo daría un
    // 403 y la sensación de que el sistema está roto.
    document.querySelectorAll('.nav-item[data-roles]').forEach((item) => {
        if (!item.dataset.roles.split(',').includes(role)) item.hidden = true;
    });

    document.getElementById('nav').addEventListener('click', (event) => {
        const button = event.target.closest('.nav-item');
        if (button && !button.hidden) show(button.dataset.section);
    });

    // El nombre del comercio en la barra: es lo que distingue una farmacia de
    // otra cuando alguien administra varias.
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
