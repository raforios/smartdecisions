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

const SECTIONS = {
    counter: mountCounter,
    sales: mountSales,
    catalog: mountCatalog,
    purchases: mountPurchases,
    dashboard: mountDashboard,
    settings: mountSettings
};

/** La sección abierta sobrevive a un F5: el turno no se pierde por recargar. */
const LAST_SECTION_KEY = 'billing_section';

async function show(name) {
    const view = document.getElementById('view');
    const mount = SECTIONS[name];
    if (!mount) return;

    document.querySelectorAll('.nav-item').forEach((item) => {
        if (item.dataset.section === name) item.setAttribute('aria-current', 'page');
        else item.removeAttribute('aria-current');
    });
    sessionStorage.setItem(LAST_SECTION_KEY, name);

    view.innerHTML = '<p class="muted">Cargando…</p>';
    try {
        await mount(view);
    } catch (error) {
        view.innerHTML = errorCard('No se pudo abrir la sección',
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

    const saved = sessionStorage.getItem(LAST_SECTION_KEY);
    const visible = [...document.querySelectorAll('.nav-item')].filter((item) => !item.hidden);
    await show(saved && SECTIONS[saved] ? saved : visible[0]?.dataset.section || 'counter');
});
