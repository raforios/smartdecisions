/**
 * WMS — startup and navigation, in the frame every BearSoft product shares
 * (`common/js/frame.js`). One page with sections, like SmartBilling: the
 * plan stays loaded while the user moves between the facility and a
 * warehouse.
 */
import { clearSession, getEmail, getRole, isTokenExpired } from '../common/js/session/auth.js';
import { LOGIN_PATH } from './config.js';
import { escapeHtml } from './ui.js';
import { mountFacilities } from './pages/FacilitiesPage.js';
import { mountFacilityPlan } from './pages/FacilityPlanPage.js';
import { mountWarehouse } from './pages/WarehousePage.js';
import { mountHistory } from './pages/HistoryPage.js';

const MENU = [
    { group: 'Instalación', items: [
        { id: 'facilities', label: 'Instalaciones', icon: 'pin', mount: mountFacilities },
        { id: 'plan', label: 'Plano de la instalación', icon: 'home', mount: mountFacilityPlan },
        { id: 'warehouse', label: 'Layout del almacén', icon: 'stock', mount: mountWarehouse }
    ] },
    { group: 'Seguimiento', items: [
        { id: 'history', label: 'Historial del layout', icon: 'clock', mount: mountHistory }
    ] }
];

const ROLE_LABELS = { ADMIN: 'Administrador', MANAGER: 'Gerente', SELLER: 'Operador', REQUESTER: 'Consulta' };
const LAST_SECTION_KEY = 'wms_section';

const findSection = (id) => MENU.flatMap((section) =>
    section.items.map((item) => ({ section, item }))).find(({ item }) => item.id === id);

function menuMarkup(current) {
    const icon = window.SD_ICONS.svg;
    return MENU.map((section) => `<div class="sd-section"><p class="sd-group">${
        escapeHtml(section.group)}</p>${section.items.map((item) => {
        const active = item.id === current;
        return `<a class="sd-item${active ? ' is-active' : ''}" href="#${item.id}"` +
            `${active ? ' aria-current="page"' : ''}>${icon(item.icon)}<span>${escapeHtml(item.label)}</span></a>`;
    }).join('')}</div>`).join('');
}

function crumbsMarkup(found) {
    return `<span class="sd-crumb">${escapeHtml(found.section.group)}</span>` +
        window.SD_ICONS.svg('chevronRight', 'sd-crumb-sep') +
        `<span class="sd-crumb is-current" aria-current="page">${escapeHtml(found.item.label)}</span>`;
}

let closeMenu = () => {};

/** Opens a section; a page leaving with unsaved changes may hold the user back. */
async function show(name) {
    const found = findSection(name) || findSection('facilities');
    const view = document.getElementById('view');
    if (view.wmsLeave && !view.wmsLeave()) {
        history.replaceState(null, '', `#${view.wmsSection}`);
        return;
    }
    document.getElementById('sdNav').innerHTML = menuMarkup(found.item.id);
    document.getElementById('sdCrumbs').innerHTML = crumbsMarkup(found);
    document.title = `${found.item.label} — WMS`;
    sessionStorage.setItem(LAST_SECTION_KEY, found.item.id);
    if (location.hash.slice(1) !== found.item.id) history.replaceState(null, '', `#${found.item.id}`);
    closeMenu();
    const container = document.createElement('div');
    view.replaceChildren(container);
    view.wmsLeave = null;
    view.wmsSection = found.item.id;
    await found.item.mount(container, { go: (section) => { location.hash = section; }, view });
}

function logout() {
    clearSession();
    window.location.replace(LOGIN_PATH);
}

const start = async () => {
    if (isTokenExpired() || !getEmail()) {
        logout();
        return;
    }
    const frame = window.SD_FRAME.mount({
        homeHref: '#facilities',
        logoSrc: 'assets/bear-face.jpg',
        brandHtml: '<b>WMS</b>',
        navHtml: menuMarkup(null),
        crumbsHtml: '',
        email: getEmail(),
        roleLabel: ROLE_LABELS[getRole()] || '',
        footerLogoSrc: 'assets/bearsoft-logo.png'
    });
    closeMenu = frame.closeMenu;
    frame.topbar.querySelector('#logoutButton').addEventListener('click', logout);
    window.addEventListener('hashchange', () => show(location.hash.slice(1)));
    await show(location.hash.slice(1) || sessionStorage.getItem(LAST_SECTION_KEY) || 'facilities');
};

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
