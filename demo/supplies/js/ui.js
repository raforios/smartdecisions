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

export function formatDate(value, withTime = false) {
    if (!value) return '—';
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
