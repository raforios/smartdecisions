'use strict';

/**
 * The frame every module page shares: the side menu with the areas and their
 * options, the top bar with the breadcrumb, and what each role may see.
 *
 * It runs as soon as the page is parsed, before any page script, so the
 * elements those scripts look up (#userChip, #logoutButton, #sessionChip)
 * already exist when they ask for them.
 *
 * Levels: Comercial → an area → one of its options (see MENU).
 */
(function shellModule() {
    if (!window.SD_AUTH.requireAuth()) return;
    const role = window.SD_AUTH.getRole();
    if (role === 'SELLER') {
        location.replace(window.SD_CONFIG.SELLER_HOME);
        return;
    }
    const ROOT = new URL('..', document.currentScript.src);
    const icon = window.SD_ICONS.svg;

    const ROLE_LABELS = { MANAGER: 'Gerente', REQUESTER: 'Consulta', ADMIN: 'Administrador' };
    const EDITORS = ['MANAGER', 'ADMIN'];
    // The financial analysis is for the people who run the business (Rafael:
    // «sólo la plana mayor»); FINANCE answers ROLE_NOT_ALLOWED to anyone else.
    const FINANCE_ROLES = ['MANAGER'];
    // The ADMIN runs the platform —parameters, users, the AI, the rates—, not
    // a client's business: it has no client, so its finances and its
    // commercial data would be empty (Rafael, 20-oct).
    const COMMERCIAL_ROLES = ['MANAGER', 'REQUESTER', 'SELLER'];

    // A tree: Comercial holds its areas, an area holds its options. An option
    // is its own page (`page`) or a view of its area page opened by its card
    // (`view`, the card's data-analysis or data-section, as `page#view`).
    // The financial part, the heart of the product, sits above Comercial.
    const VENTAS = [
        ['Resumen comercial', 'resumen'], ['Fuente de volumen', 'volumen'],
        ['Oportunidades', 'oportunidades'], ['Pronóstico', 'pronostico'],
        ['Segmentación', 'segmentacion'], ['Salud de cartera', 'cartera'],
        ['Objetivos', 'objetivos'], ['Tipo de cambio', 'tipo-cambio']
    ].map(([label, page]) => ({ label, page: `ventas/${page}.html` }));
    const MENU = [
        { group: '', items: [
            // The application's welcome; the financial part follows it.
            { label: 'Principal', icon: 'home', page: 'home.html' },
            { label: 'Análisis Financiero', icon: 'finance', page: 'financiero/index.html',
              roles: FINANCE_ROLES, children: [
                { label: 'Resumen', page: 'financiero/index.html' },
                { label: 'Estado de Resultados', page: 'financiero/resultados.html' },
                { label: 'Balance General', page: 'financiero/balance.html' },
                { label: 'Impuestos', page: 'financiero/impuestos.html' },
                { label: 'Proyección', page: 'financiero/proyeccion.html' },
                { label: 'Modelo de negocio', page: 'financiero/modelo.html' },
                { label: 'Catálogo de cuentas', page: 'financiero/cuentas.html' },
                { label: 'Cargar datos', page: 'financiero/cargar.html' }
            ] },
            { label: 'Comercial', icon: 'commerce', page: 'comercial/index.html',
              roles: COMMERCIAL_ROLES, children: [
                { label: 'Ventas', icon: 'sales', page: 'ventas/index.html', children: [
                    ...VENTAS,
                    { label: 'Cargar datos', page: 'ventas/cargar.html', roles: EDITORS }
                ] },
                { label: 'Clientes', icon: 'clients', page: 'clientes/index.html', children: [
                    { label: 'Cartera', page: 'clientes/cartera.html' },
                    { label: 'Ficha del cliente', page: 'clientes/ficha.html' }
                ] },
                { label: 'Inventario', icon: 'stock', page: 'inventario/index.html', children: [
                    { label: 'Stock del día', page: 'inventario/stock.html' },
                    { label: 'Evolución', page: 'inventario/evolucion.html' },
                    { label: 'Stock en ruta', page: 'inventario/ruta.html' },
                    { label: 'Cargar datos', page: 'inventario/cargar.html', roles: EDITORS }
                ] },
                { label: 'Compras', icon: 'purchases', page: 'compras/index.html', children: [
                    { label: 'Cargar datos', page: 'compras/cargar.html', roles: EDITORS }
                ] },
                { label: 'Cobranza', icon: 'receivables', page: 'cobranza/index.html', children: [
                    { label: 'Cargar datos', page: 'cobranza/cargar.html', roles: EDITORS }
                ] },
                { label: 'Rutas', icon: 'routes', page: 'routes/index.html', children: [
                    { label: 'Histórico', view: 'planner' },
                    { label: 'Planes', view: 'plans' },
                    { label: 'En vivo', view: 'live' },
                    { label: 'Optimizar', view: 'optimize' },
                    { label: 'Comparación', view: 'compare' }
                ] }
            ] }
        ] },
        // A company's own configuration: its manager sets it (Rafael, 21-oct).
        { group: 'Configuración', roles: ['MANAGER'], items: [
            { label: 'Parámetros', icon: 'settings', page: 'parametros/index.html', children: [
                { label: 'Configuración comercial', page: 'parametros/index.html' },
                { label: 'Factores externos', page: 'parametros/factores.html' },
                // Each company writes its own prompts (Rafael, 21-oct).
                { label: 'Prompts de la IA', page: 'admin/prompts.html' }
            ] }
        ] },
        // The platform, for the ADMIN only (Rafael, 21-oct): Minerales is no
        // longer shown to the companies.
        { group: 'Administración', roles: ['ADMIN'], items: [
            { label: 'Empresas', icon: 'clients', page: 'admin/empresas.html' },
            { label: 'Usuarios', icon: 'user', page: 'admin/usuarios.html' },
            { label: 'Salud', icon: 'pulse', page: 'admin/salud.html' },
            { label: 'Eventos y alertas', icon: 'clock', page: 'admin/eventos.html' },
            { label: 'Prompts de la IA', icon: 'settings', page: 'admin/prompts.html' },
            { label: 'Catálogo de cuentas', icon: 'finance', page: 'financiero/cuentas.html' },
            { label: 'Tipos de cambio', icon: 'rates', page: 'admin/tipo-cambio.html' },
            { label: 'Minerales', icon: 'minerals', page: 'minerales/index.html' }
        ] }
    ];

    const href = (page, view) => new URL(page, ROOT).pathname + (view ? `#${view}` : '');
    const here = location.pathname.replace(/\/$/, '/index.html');
    const isHere = (page) => href(page) === here;
    const escape = (text) => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;');
    const allowed = (node) => !node.roles || node.roles.includes(role);

    // A view lives on its parent's page.
    (function inheritPages(nodes, parent) {
        nodes.forEach((node) => {
            if (node.view && !node.page) node.page = parent.page;
            if (node.children) inheritPages(node.children, node);
        });
    })(MENU.flatMap((section) => section.items), null);

    const matches = (node) => isHere(node.page) &&
        (node.view ? location.hash.slice(1) === node.view : true);

    /** From the top of the menu to the node on screen; the deepest match wins. */
    function findChain(nodes, chain = []) {
        for (const node of nodes.filter(allowed)) {
            const path = [...chain, node];
            const deeper = node.children && findChain(node.children, path);
            if (deeper) return deeper;
            if (matches(node)) return path;
        }
        return null;
    }
    const currentChain = () => findChain(MENU.filter(allowed).flatMap((s) => s.items)) || [];

    /** A node and, when it is on the way to the current one, its children. */
    function nodeMarkup(node, depth, chain) {
        const open = chain.includes(node);
        const current = chain[chain.length - 1] === node;
        const children = (node.children || []).filter(allowed);
        const kids = open && children.length ? `<div class="sd-subitems sd-depth-${depth + 1}">${
            children.map((child) => nodeMarkup(child, depth + 1, chain)).join('')}</div>` : '';
        // An area carries an icon; an option is a plain line under it.
        const cls = node.icon ? 'sd-item' : 'sd-subitem';
        return `<a class="${cls}${open ? ' is-open' : ''}${current ? ' is-active' : ''}" ` +
            `href="${href(node.page, node.view)}"${current ? ' aria-current="page"' : ''}>` +
            `${node.icon ? icon(node.icon) : ''}<span>${escape(node.label)}</span>` +
            `${children.length ? icon(open ? 'chevronDown' : 'chevronRight', 'sd-caret') : ''}</a>${kids}`;
    }

    function menuMarkup(chain) {
        return MENU.filter(allowed).map((section) => {
            const title = section.group ? `<p class="sd-group">${section.group}</p>` : '';
            return `<div class="sd-section">${title}${
                section.items.filter(allowed).map((item) => nodeMarkup(item, 0, chain)).join('')}</div>`;
        }).join('');
    }

    function crumbsMarkup(chain) {
        // A page outside the menu (Mi cuenta) is named by its own title.
        if (!chain.length) {
            const title = document.querySelector('main h1');
            return title ? `<span class="sd-crumb is-current">${escape(title.textContent)}</span>` : '';
        }
        return chain.map((node, index) => (index === chain.length - 1
            ? `<span class="sd-crumb is-current" aria-current="page">${escape(node.label)}</span>`
            : `<a class="sd-crumb" href="${href(node.page, node.view)}">${escape(node.label)}</a>`))
            .join(icon('chevronRight', 'sd-crumb-sep'));
    }

    /** "gerente.demo@…" → "GD": the avatar of the account. */
    function initials(address) {
        const parts = String(address).split('@')[0].split(/[._-]+/).filter(Boolean);
        return escape(parts.slice(0, 2).map((part) => part[0].toUpperCase()).join('') || '?');
    }

    const email = window.SD_AUTH.getEmail();
    const sidebar = document.createElement('aside');
    sidebar.className = 'sd-sidebar';
    sidebar.id = 'sdSidebar';
    sidebar.innerHTML =
        `<a class="sd-brand" href="${href('home.html')}">` +
        `<img src="${new URL('assets/bear-face.jpg', ROOT).pathname}" alt="">` +
        '<span>Smart<b>Decisions</b></span></a>' +
        `<nav class="sd-nav" id="sdNav" aria-label="Menú principal">${
            menuMarkup(currentChain())}</nav>`;

    const topbar = document.createElement('header');
    topbar.className = 'sd-topbar';
    topbar.innerHTML =
        `<button type="button" class="sd-menu-toggle" id="sdMenuToggle" aria-label="Mostrar u ocultar el menú">${
            icon('menu')}</button>` +
        `<nav class="sd-crumbs" id="sdCrumbs" aria-label="Ubicación">${
            crumbsMarkup(currentChain())}</nav>` +
        '<div class="sd-top-actions" id="sdTopActions">' +
        '<div class="sd-account">' +
        `<button type="button" class="sd-account-button" id="sdAccountButton" aria-haspopup="true" ` +
        `aria-expanded="false" aria-controls="sdAccountMenu"><span class="sd-avatar">${initials(email)}</span>` +
        `<span class="sd-account-role">${ROLE_LABELS[role] || ''}</span>${icon('chevronDown', 'sd-caret')}</button>` +
        '<div class="sd-account-menu" id="sdAccountMenu" hidden>' +
        `<p class="sd-account-email" id="userChip">${escape(email)}</p>` +
        `<p class="sd-account-meta">${ROLE_LABELS[role] || ''}</p>` +
        '<span class="session-chip" id="sessionChip" hidden></span>' +
        `<a class="sd-account-item" href="${href('cuenta.html')}">${icon('user')}<span>Mi cuenta</span></a>` +
        (role === 'MANAGER' ? `<a class="sd-account-item" href="${href('parametros/index.html')}">` +
            `${icon('settings')}<span>Configuración</span></a>` : '') +
        `<button type="button" class="sd-account-item" id="logoutButton">${icon('logout')}` +
        '<span>Salir</span></button></div></div></div>';

    const overlay = document.createElement('div');
    overlay.className = 'sd-overlay';

    document.body.classList.add('sd-app');
    document.body.dataset.role = role;
    document.body.prepend(sidebar, overlay, topbar);

    // Static markup names its icons (data-icon); they are drawn here, once.
    document.querySelectorAll('[data-icon]').forEach((node) => {
        node.innerHTML = icon(node.dataset.icon);
    });

    // Pages that never wired the button (Minerales, Factores) still sign out.
    topbar.querySelector('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

    // The account menu: opens on its button, closes on a click outside or Escape.
    const accountButton = topbar.querySelector('#sdAccountButton');
    const accountMenu = topbar.querySelector('#sdAccountMenu');
    const showAccount = (open) => {
        accountMenu.hidden = !open;
        accountButton.setAttribute('aria-expanded', String(open));
    };
    accountButton.addEventListener('click', (event) => {
        event.stopPropagation();
        showAccount(accountMenu.hidden);
    });
    document.addEventListener('click', (event) => {
        if (!accountMenu.hidden && !accountMenu.contains(event.target)) showAccount(false);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') showAccount(false);
    });

    // The footer is BearSoft's mark, the same on every page.
    const footer = document.querySelector('.demo-footer') || document.createElement('footer');
    footer.className = 'demo-footer sd-footer';
    footer.innerHTML = '<a href="https://bearsoft.com.bo" target="_blank" rel="noopener" ' +
        `aria-label="BearSoft"><img src="${new URL('assets/bearsoft-logo.png', ROOT).pathname}" ` +
        'alt="BearSoft"></a>';
    if (!footer.isConnected) document.body.append(footer);

    // On a narrow screen the menu slides over the page; on a wide one it
    // folds away to give tables and charts the whole width, and the choice is
    // remembered on this browser.
    const COLLAPSED_KEY = 'sd_menu_collapsed';
    const narrow = window.matchMedia('(max-width: 1000px)');
    const toggle = (open) => document.body.classList.toggle('sd-menu-open', open);
    try {
        document.body.classList.toggle('sd-collapsed', localStorage.getItem(COLLAPSED_KEY) === '1');
    } catch (storageError) {
        // Without storage the menu simply starts open.
    }
    topbar.querySelector('#sdMenuToggle').addEventListener('click', () => {
        if (narrow.matches) {
            toggle(true);
            return;
        }
        const collapsed = document.body.classList.toggle('sd-collapsed');
        try {
            localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
        } catch (storageError) {
            // The menu still folds; it just will not be remembered.
        }
    });
    overlay.addEventListener('click', () => toggle(false));

    /** Repaints the menu and the breadcrumb for the option now on screen. */
    function mark() {
        const chain = currentChain();
        document.getElementById('sdNav').innerHTML = menuMarkup(chain);
        document.getElementById('sdCrumbs').innerHTML = crumbsMarkup(chain);
    }

    /** The card that opens a view on the area page. */
    const cardOf = (view) => document.querySelector(
        `.analysis-card[data-analysis="${view}"], .analysis-card[data-section="${view}"]`);

    /**
     * Opens the view named in the hash with its own card, once the page can
     * answer: an analysis page needs its dataset first, so it waits for it.
     */
    function openFromHash(attempt = 0) {
        const card = cardOf(location.hash.slice(1));
        if (!card) return;
        const analysis = window.SD_ANALYSIS && window.SD_ANALYSIS.state;
        if (card.dataset.analysis && !(analysis && analysis.datasetId)) {
            if (attempt < 40) setTimeout(() => openFromHash(attempt + 1), 250);
            return;
        }
        card.click();
    }

    // A card chosen on the page names its view in the address, so the menu,
    // the breadcrumb and a shared link all agree with what is on screen.
    document.addEventListener('click', (event) => {
        const card = event.target.closest('.analysis-card');
        if (!card) return;
        const view = card.dataset.analysis || card.dataset.section;
        const known = (nodes) => nodes.some((node) =>
            (node.view === view && isHere(node.page)) || (node.children && known(node.children)));
        if (!known(MENU.flatMap((section) => section.items))) return;
        history.replaceState(null, '', `#${view}`);
        mark();
    });
    window.addEventListener('hashchange', () => {
        mark();
        openFromHash();
        toggle(false);
    });
    document.addEventListener('DOMContentLoaded', () => setTimeout(openFromHash, 0));

    // A block of a client's own configuration (its starting point, sellers,
    // policies) is hidden from whoever has no client to configure.
    const forClient = COMMERCIAL_ROLES.includes(role);
    if (!forClient) {
        document.querySelectorAll('[data-client-only]').forEach((node) => { node.hidden = true; });
    }

    window.SD_SHELL = {
        role, roleLabel: ROLE_LABELS[role] || '', isEditor: EDITORS.includes(role), forClient
    };
})();
