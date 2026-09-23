/**
 * Utilidades de interfaz que comparten todas las pantallas de BILLING.
 *
 * Deliberadamente corto: sólo lo que el mostrador usa de verdad. El módulo
 * anterior arrastraba ayudantes del almacén —selectores de ítems, acordeones,
 * insignias de estados de solicitud— que ya no tienen a quién servir.
 */

/** Avisos efímeros. El host vive en `index.html`. */
export function notify(message, variant = 'info') {
    const host = document.getElementById('toast-host');
    if (!host) return;
    const toast = document.createElement('div');
    toast.className = `toast is-${variant}`;
    toast.textContent = message;
    host.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 220);
    }, 3800);
}

/**
 * Escapa lo que vino del servicio antes de entrar a innerHTML.
 *
 * La descripción de un producto la escribe el comercio, así que es texto no
 * confiable: un laboratorio con un signo de menor no puede volverse marcado.
 */
export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
}

/**
 * Importe con los decimales que correspondan.
 *
 * Dos por defecto, como en toda nota; cero para contar unidades, donde
 * "12,00 u." se lee como un peso y no como cajas.
 */
export function money(value, decimals = 2) {
    if (value === null || value === undefined) return '—';
    const amount = Number(value);
    if (Number.isNaN(amount)) return String(value);
    return amount.toLocaleString('es-BO', {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals
    });
}

/** Porcentaje con signo, para una variación. */
export function percent(value) {
    if (value === null || value === undefined) return '—';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toFixed(2)}%`;
}

/** Fecha corta, como la lee alguien en el mostrador. */
export function shortDate(value) {
    if (!value) return '—';
    const [date] = String(value).split('T');
    const [year, month, day] = date.split('-');
    return `${day}/${month}/${year}`;
}

/** Fecha y hora de una nota. */
export function stamp(value) {
    if (!value) return '—';
    const [date, rest = ''] = String(value).split('T');
    return `${shortDate(date)} ${rest.slice(0, 5)}`;
}

/** El día de hoy en ISO, que es como viajan las ventanas de fechas. */
export function todayIso(offsetDays = 0) {
    const day = new Date();
    day.setDate(day.getDate() + offsetDays);
    return day.toISOString().slice(0, 10);
}

/**
 * Deshabilita un botón mientras corre su acción y devuelve cómo restaurarlo.
 * Dos toques en "Cobrar" serían dos notas y dos impresiones.
 */
export function setBusy(button, busyLabel) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    return () => {
        button.disabled = false;
        button.textContent = label;
    };
}

/** Tarjeta de error, para cuando una pantalla no puede ni abrirse. */
export function errorCard(title, detail) {
    return `<div class="card empty-state">
        <h3>${escapeHtml(title)}</h3>
        <p class="muted">${escapeHtml(detail)}</p>
    </div>`;
}
