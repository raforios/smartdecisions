'use strict';

/**
 * The portal's own line icons, drawn on a 24-unit grid with the current text
 * colour, so they need no icon font or library. `SD_ICONS.svg(name)` returns
 * the markup; an unknown name returns an empty string.
 */
(function iconsModule() {
    const PATHS = {
        home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
        commerce: '<path d="M4 9l1.5-5h13L20 9"/><path d="M4 9h16v1.5a2.7 2.7 0 01-5.3 0 2.7 2.7 0 01-5.4 0 2.7 2.7 0 01-5.3 0z"/>' +
            '<path d="M5 13v7h14v-7"/><path d="M10 20v-4h4v4"/>',
        sales: '<path d="M4 20h16"/><path d="M7 16v-4"/><path d="M12 16V8"/><path d="M17 16V5"/>',
        clients: '<circle cx="9" cy="8" r="3"/><path d="M3 19c0-3.3 2.7-5 6-5s6 1.7 6 5"/>' +
            '<path d="M16 5.2a3 3 0 010 5.6"/><path d="M18 14.3c1.8.6 3 2.2 3 4.7"/>',
        stock: '<path d="M3 7l9-4 9 4-9 4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/>',
        purchases: '<path d="M3 4h2l2.4 11h11l2-8H6.2"/><circle cx="9" cy="19" r="1.5"/>' +
            '<circle cx="17" cy="19" r="1.5"/>',
        receivables: '<rect x="3" y="7" width="18" height="13" rx="2"/>' +
            '<path d="M6 7l2-3h9l1 3"/><path d="M15 13.5h3"/>',
        routes: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/>' +
            '<path d="M8 18h7a3 3 0 000-6H9a3 3 0 010-6h7"/>',
        settings: '<path d="M4 6h10"/><path d="M18 6h2"/><circle cx="16" cy="6" r="2"/>' +
            '<path d="M4 12h4"/><path d="M12 12h8"/><circle cx="10" cy="12" r="2"/>' +
            '<path d="M4 18h12"/><circle cx="18" cy="18" r="2"/>',
        minerals: '<path d="M3 9l3-5h12l3 5-9 11z"/><path d="M3 9h18"/><path d="M9 9l3 11 3-11-3-5z"/>',
        logout: '<path d="M15 4h3a2 2 0 012 2v12a2 2 0 01-2 2h-3"/><path d="M10 16l-4-4 4-4"/>' +
            '<path d="M6 12h10"/>',
        menu: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
        chevronRight: '<path d="M9 6l6 6-6 6"/>',
        chevronDown: '<path d="M6 9l6 6 6-6"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        upload: '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/>'
    };

    /**
     * The markup of one icon.
     *
     * @param {string} name - Key of the icon.
     * @param {string} [className] - Extra class for sizing in context.
     * @returns {string} An inline SVG, decorative for assistive technology.
     */
    function svg(name, className = '') {
        if (!PATHS[name]) return '';
        return `<svg class="sd-icon ${className}" viewBox="0 0 24 24" fill="none" ` +
            'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" ' +
            `stroke-linejoin="round" aria-hidden="true">${PATHS[name]}</svg>`;
    }

    window.SD_ICONS = { svg };
})();
