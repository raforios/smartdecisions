/**
 * Interface utilities shared by every BILLING screen.
 *
 * Deliberately short: only what the counter really uses. The previous module
 * dragged warehouse helpers —item pickers, accordions, request status
 * badges— that no longer have anyone to serve.
 */

/** Short-lived notices: the same toast SmartDecisions shows (`common/js/ui.js`). */
export function notify(message, variant = 'info') {
    window.SD_UI.toast(message, variant);
}

/**
 * Escapes what came from the service before it enters innerHTML.
 *
 * A product description is written by the merchant, so it is untrusted text:
 * a laboratory with a less-than sign cannot become markup.
 */
export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
}

/**
 * Amount with the decimals that apply.
 *
 * Two by default, as on every note; zero to count units, where "12,00 u."
 * reads as a weight and not as boxes.
 */
export function money(value, decimals = 2) {
    if (value === null || value === undefined) return '—';
    const amount = Number(value);
    if (Number.isNaN(amount)) return String(value);
    return amount.toLocaleString('es-BO', {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals
    });
}

/** Signed percentage, for a variation. */
export function percent(value) {
    if (value === null || value === undefined) return '—';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toLocaleString('es-BO', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    })}%`;
}

/** Short date, the way someone at the counter reads it. */
export function shortDate(value) {
    if (!value) return '—';
    const [date] = String(value).split('T');
    const [year, month, day] = date.split('-');
    return `${day}/${month}/${year}`;
}

/** Date and time of a note. */
export function stamp(value) {
    if (!value) return '—';
    const [date, rest = ''] = String(value).split('T');
    return `${shortDate(date)} ${rest.slice(0, 5)}`;
}

/** Today in ISO, which is how date windows travel. */
export function todayIso(offsetDays = 0) {
    const day = new Date();
    day.setDate(day.getDate() + offsetDays);
    return day.toISOString().slice(0, 10);
}

/**
 * Disables a button while its action runs and returns how to restore it.
 * Two taps on "Cobrar" would be two notes and two prints. The common helper
 * keeps the button's icon (`common/js/ui.js`).
 */
export function setBusy(button, busyLabel) {
    return window.SD_UI.setButtonBusy(button, busyLabel);
}

/** The drawing of a row action (`.btn-icon`), from the common icon set. */
export function rowIcon(name) {
    return window.SD_ICONS.svg(name);
}

/** Error card, for when a screen cannot even open. */
export function errorCard(title, detail) {
    return `<div class="card empty-state">
        <h3>${escapeHtml(title)}</h3>
        <p class="muted">${escapeHtml(detail)}</p>
    </div>`;
}
