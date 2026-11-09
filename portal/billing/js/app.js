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
import { mountCustomers } from './pages/CustomersPage.js';
import { mountManualInvoices } from './pages/ManualInvoicesPage.js';

/**
 * The menu, in the frame SmartDecisions uses (`common/js/frame.js`): groups
 * of sections, each with its icon and, when not everyone may use it, its
 * roles.
 */
const MANAGERS = ['ADMIN', 'MANAGER'];
const MENU = [
    { group: 'Operación', items: [
        { id: 'counter', label: 'Mostrador', icon: 'sales', mount: mountCounter },
        { id: 'cash', label: 'Caja y egresos', icon: 'calculator', mount: mountCash },
        { id: 'sales', label: 'Ventas', icon: 'receivables', mount: mountSales },
        { id: 'customers', label: 'Clientes', icon: 'clients', mount: mountCustomers }
    ] },
    { group: 'Inventario', items: [
        { id: 'catalog', label: 'Catálogo', icon: 'stock', mount: mountCatalog },
        { id: 'purchases', label: 'Recepción', icon: 'purchases', mount: mountPurchases, roles: MANAGERS }
    ] },
    { group: 'Gestión', items: [
        { id: 'dashboard', label: 'Tablero', icon: 'home', mount: mountDashboard },
        { id: 'tills', label: 'Cajas', icon: 'lock', mount: mountCashSessions, roles: MANAGERS },
        { id: 'manual', label: 'Facturas manuales', icon: 'edit', mount: mountManualInvoices, roles: MANAGERS },
        { id: 'settings', label: 'Configuración', icon: 'settings', mount: mountSettings, roles: MANAGERS }
    ] }
];

const ROLE_LABELS = { ADMIN: 'Administrador', MANAGER: 'Gerente', SELLER: 'Vendedor', REQUESTER: 'Consulta' };

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

const role = getRole();
const visibleMenu = () => MENU.map((section) => ({
    ...section, items: section.items.filter((item) => !item.roles || item.roles.includes(role))
})).filter((section) => section.items.length);
const findSection = (id) => visibleMenu().flatMap((section) =>
    section.items.map((item) => ({ section, item }))).find(({ item }) => item.id === id);

/** The menu with the open section marked, the way SmartDecisions draws it. */
function menuMarkup(current) {
    const icon = window.SD_ICONS.svg;
    return visibleMenu().map((section) => `<div class="sd-section"><p class="sd-group">${
        escapeHtml(section.group)}</p>${section.items.map((item) => {
        const active = item.id === current;
        return `<a class="sd-item${active ? ' is-active' : ''}" href="#${item.id}" data-section="${item.id}"` +
            `${active ? ' aria-current="page"' : ''}>${icon(item.icon)}<span>${escapeHtml(item.label)}</span></a>`;
    }).join('')}</div>`).join('');
}

/** Group › section, as the breadcrumb of every SmartDecisions page. */
function crumbsMarkup(found) {
    if (!found) return '';
    return `<span class="sd-crumb">${escapeHtml(found.section.group)}</span>` +
        window.SD_ICONS.svg('chevronRight', 'sd-crumb-sep') +
        `<span class="sd-crumb is-current" aria-current="page">${escapeHtml(found.item.label)}</span>`;
}

let closeMenu = () => {};

async function show(name) {
    const view = document.getElementById('view');
    const found = findSection(name);
    if (!found) return;

    document.getElementById('sdNav').innerHTML = menuMarkup(name);
    document.getElementById('sdCrumbs').innerHTML = crumbsMarkup(found);
    document.title = `${found.item.label} — SmartBilling`;
    sessionStorage.setItem(LAST_SECTION_KEY, name);
    if (location.hash.slice(1) !== name) history.replaceState(null, '', `#${name}`);
    closeMenu();

    // Each section mounts in its own container. If the user switches section
    // while the previous one waits for the API, the previous one keeps working
    // on a container that is no longer on screen: it neither finds nulls when
    // it finishes nor paints its error over the new section.
    const container = document.createElement('div');
    container.innerHTML = '<p class="muted">Cargando…</p>';
    view.replaceChildren(container);
    try {
        await found.item.mount(container);
    } catch (error) {
        if (!container.isConnected) return;
        container.innerHTML = errorCard('No se pudo abrir la sección',
                                        errorText(error, 'El servicio no respondió.'));
    }
}

function logout() {
    clearSession();
    window.location.replace(LOGIN_PATH);
}

/** The frame: brand, menu, breadcrumb, account and the shop's name. */
function mountFrame() {
    const frame = window.SD_FRAME.mount({
        homeHref: '#counter',
        logoSrc: 'assets/bear-face.jpg',
        brandHtml: 'Smart<b>Billing</b>',
        navHtml: menuMarkup(null),
        crumbsHtml: '',
        email: getEmail() || '',
        roleLabel: ROLE_LABELS[role] || '',
        footerLogoSrc: 'assets/bearsoft-logo.png'
    });
    closeMenu = frame.closeMenu;
    // The merchant's name in the bar: it tells one pharmacy from another when
    // someone manages several.
    frame.topbar.querySelector('#sdTopActions').insertAdjacentHTML(
        'afterbegin', '<span class="shop-name" id="shopName">Facturación</span>');
    frame.topbar.querySelector('#logoutButton').addEventListener('click', logout);
    // A section is a link (#cash): it opens without reloading the page.
    window.addEventListener('hashchange', () => show(location.hash.slice(1)));
}

const start = async () => {
    if (isTokenExpired()) {
        logout();
        return;
    }
    mountFrame();

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

    const asked = location.hash.slice(1) || sessionStorage.getItem(LAST_SECTION_KEY);
    const first = visibleMenu()[0].items[0].id;
    await show(findSection(asked) ? asked : first);
};

// Module scripts run after the classic ones (icons, frame, ui) they rely on.
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
