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
        finance: '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M3 20h18"/>',
        logout: '<path d="M15 4h3a2 2 0 012 2v12a2 2 0 01-2 2h-3"/><path d="M10 16l-4-4 4-4"/>' +
            '<path d="M6 12h10"/>',
        menu: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
        chevronRight: '<path d="M9 6l6 6-6 6"/>',
        chevronDown: '<path d="M6 9l6 6 6-6"/>',
        user: '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-3.9 3.6-6 8-6s8 2.1 8 6"/>',
        rates: '<path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/>',
        clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M8 3v4"/>' +
            '<path d="M16 3v4"/>',
        pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
        bolt: '<path d="M13 3L5 13h6l-1 8 8-10h-6z"/>',
        compare: '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M20 20H3"/>',
        eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
        eyeOff: '<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0112 5c6.4 0 10 7 10 7a17 17 0 01-3.2 4.1"/>' +
            '<path d="M6.6 6.6C3.8 8.4 2 12 2 12s3.6 7 10 7a9.6 9.6 0 005.4-1.6"/><path d="M9.9 9.9a3 3 0 004.2 4.2"/>',
        upload: '<path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/>',
        edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
        trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v6"/><path d="M14 11v6"/>',
        check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
        close: '<path d="M6 6l12 12"/><path d="M18 6L6 18"/>',
        plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
        download: '<path d="M12 4v12"/><path d="M7 11l5 5 5-5"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/>',
        refresh: '<path d="M20 11a8 8 0 10-2.3 5.7"/><path d="M20 4v7h-7"/>',
        power: '<path d="M12 3v9"/><path d="M6.3 7.3a8 8 0 1011.4 0"/>',
        chevronLeft: '<path d="M15 6l-6 6 6 6"/>',
        filter: '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
        pulse: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
        calculator: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8"/><path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/><path d="M8 16h.01"/><path d="M12 16h.01"/><path d="M16 16h.01"/>',
        lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
        login: '<path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M14 4h4a2 2 0 012 2v12a2 2 0 01-2 2h-4"/>',
        undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 010 12h-3"/>',
        play: '<path d="M7 4l13 8-13 8z"/>',
        flag: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
        sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>'
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
