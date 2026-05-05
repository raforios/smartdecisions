/**
 * Toast - lightweight notification stack (no dependencies).
 *
 * Usage:
 *   import { Toast } from './components/Toast.js';
 *   Toast.success('Participante registrado');
 *   Toast.danger('Error: ...', { timeoutMs: 6000 });
 */
const ICONS = {
    success: 'fa-solid fa-circle-check',
    danger:  'fa-solid fa-circle-exclamation',
    info:    'fa-solid fa-circle-info'
};

const DEFAULT_TIMEOUT = 4000;

function ensureStack() {
    let stack = document.querySelector('.toast-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.className = 'toast-stack';
        document.body.appendChild(stack);
    }
    return stack;
}

function show(message, kind = 'info', { timeoutMs = DEFAULT_TIMEOUT } = {}) {
    const stack = ensureStack();
    const node = document.createElement('div');
    node.className = `toast ${kind}`;
    node.innerHTML = `<i class="${ICONS[kind] || ICONS.info}"></i><span>${message}</span>`;
    stack.appendChild(node);
    setTimeout(() => {
        node.style.opacity = '0';
        node.style.transform = 'translateX(20px)';
        node.style.transition = 'all 0.3s ease';
        setTimeout(() => node.remove(), 300);
    }, timeoutMs);
}

export const Toast = {
    success: (msg, opts) => show(msg, 'success', opts),
    danger:  (msg, opts) => show(msg, 'danger',  opts),
    info:    (msg, opts) => show(msg, 'info',    opts),
    configure(defaults) {
        if (defaults && typeof defaults.timeoutMs === 'number') {
            // Allow callers to bump the default timeout from config.json.
            show.__defaultTimeout = defaults.timeoutMs;
        }
    }
};
