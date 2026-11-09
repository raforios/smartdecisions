'use strict';

/**
 * The frame both products draw around their pages: the side menu with the
 * brand, the top bar with the menu button, the breadcrumb and the account,
 * BearSoft's mark at the foot, and how they behave. SmartDecisions fills it
 * from `shell.js` and SmartBilling from its `app.js`; what goes in the menu
 * is each product's, the frame is one.
 */
(function frameModule() {
    const icon = (name, className) => window.SD_ICONS.svg(name, className);
    const escape = (text) => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;');
    const COLLAPSED_KEY = 'sd_menu_collapsed';

    /** "gerente.demo@…" → "GD": the avatar of the account. */
    function initials(address) {
        const parts = String(address).split('@')[0].split(/[._-]+/).filter(Boolean);
        return escape(parts.slice(0, 2).map((part) => part[0].toUpperCase()).join('') || '?');
    }

    /**
     * Puts the frame on the page and wires it.
     *
     * @param {object} options
     * @param {string} options.homeHref - Where the brand leads.
     * @param {string} options.logoSrc - The bear's face beside the name.
     * @param {string} options.brandHtml - The product's name, e.g. 'Smart<b>Billing</b>'.
     * @param {string} options.navHtml - The menu, already drawn.
     * @param {string} options.crumbsHtml - The breadcrumb, already drawn.
     * @param {string} options.email - The signed-in account.
     * @param {string} options.roleLabel - The account's role, in words.
     * @param {string} [options.accountItems] - Extra lines of the account menu, before «Salir».
     * @param {string} options.footerLogoSrc - BearSoft's mark.
     * @returns {{sidebar: HTMLElement, topbar: HTMLElement, closeMenu: Function}}
     */
    function mount(options) {
        const sidebar = document.createElement('aside');
        sidebar.className = 'sd-sidebar';
        sidebar.id = 'sdSidebar';
        sidebar.innerHTML =
            `<a class="sd-brand" href="${options.homeHref}">` +
            `<img src="${options.logoSrc}" alt=""><span>${options.brandHtml}</span></a>` +
            `<nav class="sd-nav" id="sdNav" aria-label="Menú principal">${options.navHtml}</nav>`;

        const topbar = document.createElement('header');
        topbar.className = 'sd-topbar';
        topbar.innerHTML =
            `<button type="button" class="sd-menu-toggle" id="sdMenuToggle" aria-label="Mostrar u ocultar el menú">${
                icon('menu')}</button>` +
            `<nav class="sd-crumbs" id="sdCrumbs" aria-label="Ubicación">${options.crumbsHtml}</nav>` +
            '<div class="sd-top-actions" id="sdTopActions">' +
            '<div class="sd-account">' +
            `<button type="button" class="sd-account-button" id="sdAccountButton" aria-haspopup="true" ` +
            `aria-expanded="false" aria-controls="sdAccountMenu"><span class="sd-avatar">${
                initials(options.email)}</span>` +
            `<span class="sd-account-role">${escape(options.roleLabel)}</span>${icon('chevronDown', 'sd-caret')}</button>` +
            '<div class="sd-account-menu" id="sdAccountMenu" hidden>' +
            `<p class="sd-account-email" id="userChip">${escape(options.email)}</p>` +
            `<p class="sd-account-meta">${escape(options.roleLabel)}</p>` +
            '<span class="session-chip" id="sessionChip" hidden></span>' +
            (options.accountItems || '') +
            `<button type="button" class="sd-account-item" id="logoutButton">${icon('logout')}` +
            '<span>Salir</span></button></div></div></div>';

        const overlay = document.createElement('div');
        overlay.className = 'sd-overlay';

        document.body.classList.add('sd-app');
        document.body.prepend(sidebar, overlay, topbar);

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
            `aria-label="BearSoft"><img src="${options.footerLogoSrc}" alt="BearSoft"></a>`;
        if (!footer.isConnected) document.body.append(footer);

        // On a narrow screen the menu slides over the page; on a wide one it
        // folds away to give tables and charts the whole width, and the choice
        // is remembered on this browser.
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

        return { sidebar, topbar, closeMenu: () => toggle(false) };
    }

    window.SD_FRAME = { mount };
})();
