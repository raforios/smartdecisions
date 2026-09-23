/**
 * Shared UI utilities: toast, modal control, formatters, status badges.
 *
 * The DOM elements (`modal-host`, `toast-host`) live in index.html; this
 * module assumes they exist. Every page imports from here instead of
 * touching the modal markup directly.
 */

// ------------------------------ Toast --------------------------------- //
export function showToast(message, variant = 'info') {
    const host = document.getElementById('toast-host');
    if (!host) return;
    const toast = document.createElement('div');
    toast.className = `sup-toast is-${variant}`;
    toast.textContent = message;
    host.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 200);
    }, 3500);
}

// ------------------------------ Modal --------------------------------- //
export function openModal({ title, body, footer, wide = false } = {}) {
    const host = document.getElementById('modal-host');
    if (!host) return;
    document.getElementById('modal-title').textContent = title || '';
    const bodyEl = document.getElementById('modal-body');
    const footerEl = document.getElementById('modal-footer');
    bodyEl.innerHTML = '';
    footerEl.innerHTML = '';
    if (body instanceof Node) bodyEl.appendChild(body);
    else if (typeof body === 'string') bodyEl.innerHTML = body;
    if (footer instanceof Node) footerEl.appendChild(footer);
    else if (Array.isArray(footer)) footer.forEach(b => footerEl.appendChild(b));

    host.querySelector('.sup-modal').classList.toggle('sup-modal-wide', wide);
    host.hidden = false;
}

export function closeModal() {
    const host = document.getElementById('modal-host');
    if (host) host.hidden = true;
}

/** Wires the global close affordances exactly once. */
export function initModalBindings() {
    const host = document.getElementById('modal-host');
    if (!host || host.dataset.bound === '1') return;
    host.querySelector('.sup-modal-backdrop').addEventListener('click', _maybeClose);
    document.getElementById('modal-close').addEventListener('click', _maybeClose);
    host.dataset.bound = '1';
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !host.hidden) _maybeClose();
    });
}

/** Internal close helper that respects the `data-locked` flag. */
function _maybeClose() {
    const host = document.getElementById('modal-host');
    if (host?.dataset.locked === '1') return;
    closeModal();
}

/**
 * Blocks the UI with a non-dismissable modal explaining the session has
 * expired. The single action clears the token and bounces the user to
 * login.html. Safe to call multiple times — only the first one renders.
 */
export function showSessionExpiredModal({ onConfirm } = {}) {
    const host = document.getElementById('modal-host');
    if (!host || host.dataset.locked === '1') return;
    host.dataset.locked = '1';

    // Hide the (X) so it does not look interactive.
    const closeBtn = document.getElementById('modal-close');
    if (closeBtn) closeBtn.hidden = true;

    const body = el('div', { class: 'sup-stack' }, [
        el('p', {
            text: 'Tu sesión expiró por inactividad o porque el token caducó.',
        }),
        el('p', {
            class: 'sup-muted',
            text: 'Vuelve a iniciar sesión para continuar trabajando.',
        }),
    ]);

    const confirm = el('button', {
        class: 'sup-btn sup-btn-primary',
        html: '<i class="fa-solid fa-right-to-bracket"></i> Volver a iniciar sesión',
        onClick: () => {
            if (typeof onConfirm === 'function') onConfirm();
            // The redirect is the caller's responsibility (it owns the
            // AuthService instance), but as a safety net we navigate too.
            window.location.replace('login.html');
        },
    });

    openModal({
        title: 'Sesión expirada',
        body,
        footer: [confirm],
    });
}

// ------------------------------ Formatters ---------------------------- //
export function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined) return '—';
    const n = Number(value);
    if (Number.isNaN(n)) return String(value);
    return n.toLocaleString('es-BO', {
        minimumFractionDigits: 0,
        maximumFractionDigits: fractionDigits,
    });
}

/**
 * Money formatter: always two decimals and thousands separators.
 *
 * formatNumber trims trailing zeros, which is right for quantities (125, not
 * 125,00) but wrong for amounts — a total printed as "683.827,5" reads like a
 * typo on a valued inventory report.
 */
export function formatMoney(value) {
    if (value === null || value === undefined) return '—';
    const amount = Number(value);
    if (Number.isNaN(amount)) return String(value);
    return amount.toLocaleString('es-BO', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

export function formatDate(value, withTime = false) {
    if (!value) return '—';
    // A date-only string is parsed as UTC midnight, which in La Paz (UTC-4)
    // lands on the previous day. Format those by hand instead.
    const dateOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
    if (dateOnly) {
        const [year, month, day] = value.split('-');
        return `${Number(day)}/${Number(month)}/${year}`;
    }
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    const date = d.toLocaleDateString('es-BO');
    if (!withTime) return date;
    const time = d.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
    return `${date} ${time}`;
}

// ------------------------------ Status badges ------------------------- //
const STATUS_CLASS = {
    CREATED: 'sup-badge-created',
    IN_PROCESS: 'sup-badge-inprocess',
    DELIVERED: 'sup-badge-delivered',
    CLOSED: 'sup-badge-closed',
    REJECTED: 'sup-badge-rejected',
    CANCELLED: 'sup-badge-cancelled',
    REQUESTED: 'sup-badge-created',
    IN_RECEPTION: 'sup-badge-inprocess',
    COMPLETED: 'sup-badge-delivered',
};

const STATUS_LABEL = {
    CREATED: 'Creada',
    IN_PROCESS: 'En proceso',
    DELIVERED: 'Entregada',
    CLOSED: 'Cerrada',
    REJECTED: 'Rechazada',
    CANCELLED: 'Anulada',
    REQUESTED: 'Pendiente',
    IN_RECEPTION: 'En recepción',
    COMPLETED: 'Completada',
};

export function statusBadge(status) {
    const cls = STATUS_CLASS[status] || 'sup-badge-closed';
    const label = STATUS_LABEL[status] || status || '—';
    const span = document.createElement('span');
    span.className = `sup-badge ${cls}`;
    span.textContent = label;
    return span;
}

// ------------------------------ DOM helpers --------------------------- //
export function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    Object.entries(props).forEach(([key, value]) => {
        if (value === undefined || value === null || value === false) return;
        if (key === 'class' || key === 'className') node.className = value;
        else if (key === 'dataset') Object.assign(node.dataset, value);
        else if (key.startsWith('on') && typeof value === 'function') {
            node.addEventListener(key.slice(2).toLowerCase(), value);
        }
        else if (key === 'html') node.innerHTML = value;
        else if (key === 'text') node.textContent = value;
        else node.setAttribute(key, value);
    });
    [].concat(children).forEach(child => {
        if (child === null || child === undefined) return;
        if (typeof child === 'string') node.appendChild(document.createTextNode(child));
        else node.appendChild(child);
    });
    return node;
}

export function clear(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
}

// --------------------------- Collapsible sections ---------------------- //
// Open/closed state per stateKey, kept for the lifetime of the page so a
// re-render does not undo what the user opened.
const collapsibleState = new Map();

/**
 * Table section that starts collapsed and opens when its header is clicked.
 *
 * Long inventory tables dominate every screen when they render expanded, so
 * the default is closed: the user sees the whole page at a glance and opens
 * only what they need.
 *
 * @param {Object} options
 * @param {string} options.title      Header text.
 * @param {string} [options.subtitle] Muted hint shown next to the title.
 * @param {boolean} [options.open]    Start expanded (default false).
 * @param {Node} [options.actions]    Controls placed on the right of the header;
 *                                    clicks inside them never toggle the section.
 * @param {string} [options.stateKey] Remembers open/closed under this key, so a
 *                                    page re-render keeps what the user opened.
 * @returns {{section: Node, body: Node, setSubtitle: Function, open: Function}}
 */
export function collapsible({ title, subtitle = '', open = false, actions = null,
                              stateKey = null } = {}) {
    // Pages rebuild their tables from scratch after a filter change or a create.
    // Without this the section the user just opened would snap shut on them.
    const expanded = stateKey && collapsibleState.has(stateKey)
        ? collapsibleState.get(stateKey)
        : open;
    const chevron = el('i', { class: 'fa-solid fa-chevron-right sup-collapsible-chevron' });
    const subEl = el('span', { class: 'sup-collapsible-sub', text: subtitle });
    const head = el('div', {
        class: 'sup-collapsible-head',
        role: 'button',
        tabindex: '0',
        'aria-expanded': String(expanded),
    }, [chevron, el('span', { class: 'sup-collapsible-title', text: title }), subEl]);

    if (actions) {
        const slot = el('div', { class: 'sup-collapsible-actions' }, [actions]);
        slot.addEventListener('click', event => event.stopPropagation());
        head.appendChild(slot);
    }

    const body = el('div', { class: 'sup-collapsible-body' });
    const section = el('section', {
        class: `sup-collapsible${expanded ? ' is-open' : ''}`,
    }, [head, body]);

    function toggle(force) {
        const next = force === undefined ? !section.classList.contains('is-open') : force;
        section.classList.toggle('is-open', next);
        head.setAttribute('aria-expanded', String(next));
        if (stateKey) collapsibleState.set(stateKey, next);
    }

    head.addEventListener('click', () => toggle());
    head.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggle();
        }
    });

    return {
        section,
        body,
        open: value => toggle(value === undefined ? true : value),
        setSubtitle: text => { subEl.textContent = text; },
    };
}

// ------------------------------ Item picker ---------------------------- //
/**
 * Type-to-filter picker for the item catalog.
 *
 * A plain <select> with 380+ options is unusable: the user has to scroll the
 * whole catalog to find one article. This filters by code or description as
 * the user types and shows a short list of matches.
 *
 * @param {Object} options
 * @param {Array} options.items         Items as {id, code, name, current_stock}.
 * @param {Function} [options.onSelect] Called with the chosen item (or null).
 * @param {string} [options.placeholder]
 * @param {number} [options.limit]      Maximum matches listed (default 12).
 * @returns {{el: Node, value: Function, selected: Function, reset: Function}}
 */
export function itemPicker({ items = [], onSelect = null, placeholder = 'Código o descripción…',
                             limit = 12 } = {}) {
    let chosen = null;

    /**
     * Availability badge shown next to every match.
     *
     * Prefers available_stock — physical stock minus what open requests
     * already reserved minus the minimum — because that is the number the
     * user is allowed to ask for. Falls back to the physical balance for
     * screens (kardex, entries) whose payload carries no availability.
     */
    function stockHint(item) {
        const available = item.available_stock;
        if (available !== undefined && available !== null) {
            const amount = Number(available);
            return el('em', {
                class: `sup-picker-stock${amount <= 0 ? ' is-empty' : ''}`,
                text: `disponible ${formatNumber(amount)}`,
            });
        }
        if (item.current_stock === undefined) return null;
        return el('em', {
            class: 'sup-picker-stock',
            text: `stock ${formatNumber(item.current_stock)}`,
        });
    }

    const input = el('input', { type: 'search', placeholder, autocomplete: 'off' });
    const list = el('div', { class: 'sup-picker-list', hidden: true });
    const wrapper = el('div', { class: 'sup-picker' }, [input, list]);

    function label(item) {
        return `${item.code} — ${item.name}`;
    }

    function choose(item) {
        chosen = item;
        input.value = item ? label(item) : '';
        list.hidden = true;
        if (onSelect) onSelect(item);
    }

    function render(term) {
        const needle = term.trim().toLowerCase();
        const matches = (needle
            ? items.filter(item => `${item.code} ${item.name}`.toLowerCase().includes(needle))
            : items
        ).slice(0, limit);

        clear(list);
        if (matches.length === 0) {
            list.appendChild(el('p', { class: 'sup-picker-empty', text: 'Sin coincidencias.' }));
        }
        matches.forEach(item => {
            list.appendChild(el('button', {
                type: 'button',
                class: 'sup-picker-option',
                onClick: () => choose(item),
            }, [
                el('strong', { text: item.code }),
                el('span', { text: item.name }),
                stockHint(item),
            ].filter(Boolean)));
        });
        list.hidden = false;
    }

    input.addEventListener('input', () => {
        // Typing after a selection means the user is looking for another item.
        if (chosen && input.value !== label(chosen)) {
            chosen = null;
            if (onSelect) onSelect(null);
        }
        render(input.value);
    });
    input.addEventListener('focus', () => render(input.value === '' ? '' : input.value));
    // A blur that lands on an option must not close the list before the click.
    input.addEventListener('blur', () => setTimeout(() => { list.hidden = true; }, 150));

    return {
        el: wrapper,
        value: () => (chosen ? chosen.id : null),
        selected: () => chosen,
        reset: () => choose(null),
        setItems: next => { items = next; },
    };
}

// ------------------------------- Pagination ---------------------------- //
/**
 * Client-side pager for tables that would otherwise dump hundreds of rows.
 *
 * @param {Object} options
 * @param {number} [options.pageSize] Rows per page (default 10).
 * @param {Function} options.render   Called with (pageRows, {from, to, total}).
 * @returns {{el: Node, setRows: Function}}
 */
export function pager({ pageSize = 10, render } = {}) {
    let rows = [];
    let page = 0;

    const info = el('span', { class: 'sup-pager-info' });
    const prev = el('button', {
        class: 'sup-btn sup-btn-ghost sup-btn-sm', html: '<i class="fa-solid fa-chevron-left"></i>',
        onClick: () => { page -= 1; paint(); },
    });
    const next = el('button', {
        class: 'sup-btn sup-btn-ghost sup-btn-sm', html: '<i class="fa-solid fa-chevron-right"></i>',
        onClick: () => { page += 1; paint(); },
    });
    const bar = el('div', { class: 'sup-pager' }, [prev, info, next]);

    function paint() {
        const pages = Math.max(1, Math.ceil(rows.length / pageSize));
        page = Math.min(Math.max(page, 0), pages - 1);
        const from = page * pageSize;
        const slice = rows.slice(from, from + pageSize);

        render(slice, { from: from + 1, to: from + slice.length, total: rows.length });
        info.textContent = rows.length === 0
            ? 'Sin registros'
            : `${from + 1}–${from + slice.length} de ${rows.length} · pág. ${page + 1}/${pages}`;
        prev.disabled = page === 0;
        next.disabled = page >= pages - 1;
        bar.hidden = rows.length <= pageSize;
    }

    return {
        el: bar,
        setRows: (nextRows, keepPage = false) => {
            rows = nextRows || [];
            if (!keepPage) page = 0;
            paint();
        },
    };
}
