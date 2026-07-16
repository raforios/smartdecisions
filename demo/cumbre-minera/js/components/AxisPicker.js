/**
 * AxisPicker: shared helpers to pick a thematic axis (eje) with live seat
 * availability, used by both the registration form and the participant edit
 * modal. Full axes are disabled and a hint lists which axes still have room.
 */

/** Fetches per-axis availability; returns [] on failure (caller shows a hint). */
export async function loadAvailability(api, config) {
    try {
        const response = await api.get(config.miningSummit.availabilityPath);
        return (response && response.items) || [];
    } catch (_error) {
        return [];
    }
}

/** Builds the <option>s for an axis <select>; full axes are disabled. */
export function buildAxisOptions(items, selected) {
    const empty = '<option value="">— Sin eje (asistencia rotativa) —</option>';
    const options = items.map(axis => {
        const full = axis.free <= 0;
        const label = `EJE ${axis.number} · ${axis.label} (${axis.free} libres)`;
        const attrs = [
            `value="${axis.axis}"`,
            full ? 'disabled' : '',
            axis.axis === selected ? 'selected' : ''
        ].filter(Boolean).join(' ');
        return `<option ${attrs}>${escapeHtml(label)}${full ? ' — LLENO' : ''}</option>`;
    }).join('');
    return empty + options;
}

/**
 * Renders an availability hint listing axes with free aulas. When `onlyAxis`
 * is given (e.g. the axis the operator just failed to seat into), it highlights
 * the alternatives with room.
 */
export function renderAvailabilityHint(container, items, onlyAxis) {
    if (!items.length) {
        container.innerHTML = '';
        return;
    }
    const withRoom = items.filter(axis => axis.free > 0);
    if (!withRoom.length) {
        container.innerHTML = `<div class="avail-hint avail-empty">
            <i class="fa-solid fa-triangle-exclamation"></i>
            No hay aulas con disponibilidad en ningún eje.</div>`;
        return;
    }
    const intro = onlyAxis
        ? 'El eje elegido está lleno. Ejes con aulas disponibles:'
        : 'Disponibilidad por eje:';
    const rows = withRoom.map(axis => {
        const aulas = axis.aulas
            .filter(aula => aula.free > 0)
            .map(aula => `${escapeHtml(aula.mesa_code)} (${aula.free})`)
            .join(' · ');
        return `<div class="avail-row">
            <span class="avail-axis">EJE ${axis.number} · ${escapeHtml(axis.label)}</span>
            <span class="avail-free">${axis.free} libres</span>
            <span class="avail-aulas">${aulas}</span>
        </div>`;
    }).join('');
    container.innerHTML = `<div class="avail-hint">
        <div class="avail-intro"><i class="fa-solid fa-chalkboard-user"></i> ${intro}</div>
        ${rows}
    </div>`;
}

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
