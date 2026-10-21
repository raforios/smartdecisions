'use strict';

/**
 * UI helpers shared across module pages: toast notifications, button-busy
 * state, button icons, the one table pager and a small `qs/qsAll` shortcut
 * so module code stays terse.
 */
(function () {

    function qs(selector, root) {
        return (root || document).querySelector(selector);
    }

    function qsAll(selector, root) {
        return Array.from((root || document).querySelectorAll(selector));
    }

    function _ensureToastContainer() {
        let container = document.getElementById('sd-toast-container');
        if (container) return container;
        container = document.createElement('div');
        container.id = 'sd-toast-container';
        container.className = 'sd-toast-container';
        document.body.appendChild(container);
        return container;
    }

    /**
     * Shows an ephemeral notification.
     * variant ∈ {'info', 'success', 'error'}.
     */
    function toast(message, variant = 'info', timeoutMs = 4500) {
        const container = _ensureToastContainer();
        const node = document.createElement('div');
        node.className = `sd-toast sd-toast-${variant}`;
        node.textContent = message;
        container.appendChild(node);
        setTimeout(() => {
            node.classList.add('sd-toast-leaving');
            setTimeout(() => node.remove(), 250);
        }, timeoutMs);
    }

    /**
     * Toggles a busy state on a <button>: disables it and shows the loading
     * label until `done()` is called. Returns the done() callback.
     */
    function setButtonBusy(button, busyLabel) {
        // Markup, not text: an analysis card is a button with an icon, a title
        // and a description inside, and restoring textContent flattened it
        // into one plain line after the first click.
        const originalMarkup = button.innerHTML;
        const originalDisabled = button.disabled;
        button.disabled = true;
        button.dataset.sdBusy = '1';
        if (busyLabel) button.textContent = busyLabel;
        return function done() {
            button.disabled = originalDisabled;
            delete button.dataset.sdBusy;
            if (busyLabel) button.innerHTML = originalMarkup;
        };
    }

    /**
     * The eye beside a password field: shows or hides what was typed, and the
     * button says which way it goes. Used by the login and by Mi cuenta.
     */
    function revealToggle(input, button) {
        const paint = () => {
            const shown = input.type === 'text';
            button.innerHTML = window.SD_ICONS.svg(shown ? 'eyeOff' : 'eye');
            button.setAttribute('aria-pressed', String(shown));
            button.setAttribute('aria-label', shown ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
        };
        button.addEventListener('click', () => {
            input.type = input.type === 'password' ? 'text' : 'password';
            paint();
        });
        paint();
        return () => { input.type = 'password'; paint(); };
    }

    /**
     * The icon of every button that names one (`data-btn-icon="check"`): the
     * buttons of every page carry their icon the same way, before the label.
     */
    function decorateButtons(root = document) {
        if (!window.SD_ICONS) return;
        root.querySelectorAll('.btn[data-btn-icon]:not([data-icon-done])').forEach((button) => {
            // "Siguiente" points forward: its icon goes after the label.
            const where = button.hasAttribute('data-btn-icon-after') ? 'beforeend' : 'afterbegin';
            button.insertAdjacentHTML(where, window.SD_ICONS.svg(button.dataset.btnIcon));
            button.dataset.iconDone = '1';
        });
    }
    // ---------- Tables: ten rows a page, the same pager everywhere ----------
    // Ten fits on screen without scrolling, which is what lets rows be
    // compared at a glance (Rafael, 21-oct: every table has a pager). A module
    // draws all its rows; the pager hides the ones off the page. A detail row
    // travels with the row above it. Financial statements are read whole and
    // are left out (`data-no-pager`, `.statement-table`), as are tables nested
    // inside another table.
    const PAGE_SIZE = 10;
    const pageable = (table) => !table.hasAttribute('data-no-pager') &&
        !table.classList.contains('statement-table') && !table.parentElement.closest('table');
    const number = (value) => Number(value).toLocaleString('es-BO');

    /** The rows of a table grouped as the reader sees them: a row and its detail. */
    function rowGroups(tbody) {
        const groups = [];
        Array.from(tbody.rows).forEach((row) => {
            if (row.classList.contains('detail-row') && groups.length) groups[groups.length - 1].push(row);
            else groups.push([row]);
        });
        return groups;
    }

    function pagerFor(table) {
        const anchor = table.closest('.table-wrapper') || table;
        let pager = anchor.nextElementSibling;
        if (!pager || !pager.classList.contains('table-pager')) {
            pager = document.createElement('div');
            pager.className = 'pager table-pager';
            pager.hidden = true;
            anchor.insertAdjacentElement('afterend', pager);
            pager.addEventListener('click', (event) => {
                const step = event.target.closest('[data-pager]');
                if (!step || step.disabled) return;
                table.sdPage += step.dataset.pager === 'next' ? 1 : -1;
                paginate(table);
            });
        }
        return pager;
    }

    function paginate(table) {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const groups = rowGroups(tbody);
        const pages = Math.max(1, Math.ceil(groups.length / PAGE_SIZE));
        table.sdPage = Math.min(Math.max(table.sdPage || 0, 0), pages - 1);
        const first = table.sdPage * PAGE_SIZE;
        groups.forEach((group, index) => group.forEach((row) =>
            row.classList.toggle('is-paged-out', index < first || index >= first + PAGE_SIZE)));
        const anchor = table.closest('.table-wrapper') || table;
        if (pages <= 1) {
            const pager = anchor.nextElementSibling;
            if (pager && pager.classList.contains('table-pager')) pager.hidden = true;
            anchor.style.minHeight = '';
            return;
        }
        const pager = pagerFor(table);
        const last = Math.min(groups.length, first + PAGE_SIZE);
        pager.innerHTML =
            '<button type="button" class="btn btn-ghost btn-small" data-pager="prev" ' +
            `data-btn-icon="chevronLeft"${table.sdPage === 0 ? ' disabled' : ''}>Anterior</button>` +
            `<span class="pager-info">${number(first + 1)}–${number(last)} de ${number(groups.length)}` +
            ` · página ${table.sdPage + 1} de ${pages}</span>` +
            '<button type="button" class="btn btn-ghost btn-small" data-pager="next" data-btn-icon="chevronRight" ' +
            `data-btn-icon-after${table.sdPage >= pages - 1 ? ' disabled' : ''}>Siguiente</button>`;
        pager.hidden = false;
        decorateButtons(pager);
        // The last page keeps the height of a full one, so the card does not jump.
        if (table.sdPage === 0) {
            anchor.style.minHeight = '';
            if (anchor.offsetHeight) anchor.style.minHeight = `${anchor.offsetHeight}px`;
        }
    }

    /** Every pageable table, once: it re-pages whenever its module redraws the rows. */
    function watchTables(root = document) {
        root.querySelectorAll('table.data-table:not([data-pager-watched])').forEach((table) => {
            if (!pageable(table) || !table.tBodies[0]) return;
            table.dataset.pagerWatched = '1';
            // New content (a search, another filter) starts on page one; a
            // refresh of the same rows keeps the page the reader was on.
            new MutationObserver(() => {
                const count = rowGroups(table.tBodies[0]).length;
                if (count !== table.sdCount) table.sdPage = 0;
                table.sdCount = count;
                paginate(table);
            }).observe(table.tBodies[0], { childList: true });
            table.sdCount = rowGroups(table.tBodies[0]).length;
            paginate(table);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        decorateButtons();
        watchTables();
        // Buttons and tables drawn later by a module get the same, once per
        // frame however many nodes a map or a chart adds.
        let queued = false;
        new MutationObserver(() => {
            if (queued) return;
            queued = true;
            requestAnimationFrame(() => { queued = false; decorateButtons(); watchTables(); });
        }).observe(document.body, { childList: true, subtree: true });
    });

    window.SD_UI = { qs, qsAll, toast, setButtonBusy, revealToggle, decorateButtons, paginate };
})();
