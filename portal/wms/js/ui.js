/**
 * Small helpers of the WMS pages. Toasts, busy buttons, icons and the table
 * pager are the common ones (`common/js/ui.js`, `common/js/icons.js`).
 */
import { getEmail } from '../common/js/session/auth.js';

export function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
}

export function notify(message, variant = 'info') {
    window.SD_UI.toast(message, variant);
}

export const icon = (name) => window.SD_ICONS.svg(name);

/** Metres the way a plan reads them: «56 m», «1,2 m». */
export function metres(value) {
    return `${Number(value).toLocaleString('es-BO', { maximumFractionDigits: 2 })} m`;
}

export function stamp(value) {
    return new Date(value).toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' });
}

/** Who is changing the layout, for its history. */
export const currentUser = () => getEmail() || '';

/** The facility and the warehouse the user is working on, per tab. */
export const selection = {
    get facility() { return sessionStorage.getItem('wms_facility'); },
    set facility(id) { sessionStorage.setItem('wms_facility', id); },
    get warehouse() { return sessionStorage.getItem('wms_warehouse'); },
    set warehouse(id) { sessionStorage.setItem('wms_warehouse', id); }
};

/** A number from a form field, or the fallback when it is empty or not a number. */
export function numberOf(form, name, fallback = 0) {
    const value = Number(String(form.elements[name].value).replace(',', '.'));
    return Number.isFinite(value) && form.elements[name].value !== '' ? value : fallback;
}

/**
 * The bar of a plan with unsaved changes: how many, a note, save or discard.
 * Saving writes a version of the plan (its history); discarding reloads it.
 */
export function saveBar(host, { onSave, onDiscard }) {
    host.innerHTML = `
        <div class="save-bar" hidden>
            <span class="save-count"></span>
            <input type="text" id="saveNote" maxlength="200" placeholder="Motivo del cambio (opcional)">
            <button type="button" class="btn btn-cancel btn-small" data-btn-icon="undo" id="discardPlan">Descartar</button>
            <button type="button" class="btn btn-save btn-small" data-btn-icon="check" id="savePlan">Guardar versión</button>
        </div>`;
    const bar = host.querySelector('.save-bar');
    host.querySelector('#savePlan').addEventListener('click', async (event) => {
        const done = window.SD_UI.setButtonBusy(event.currentTarget, 'Guardando…');
        try {
            await onSave(host.querySelector('#saveNote').value.trim());
            host.querySelector('#saveNote').value = '';
        } finally {
            done();
        }
    });
    host.querySelector('#discardPlan').addEventListener('click', onDiscard);
    return (count) => {
        bar.hidden = !count;
        bar.querySelector('.save-count').textContent =
            `${count} cambio${count === 1 ? '' : 's'} sin guardar`;
    };
}

/** How many items differ between the saved plan and the one on screen. */
export function pendingCount(saved, draft) {
    const old = new Map(saved.map((item) => [item.id, JSON.stringify(item)]));
    let count = 0;
    draft.forEach((item) => {
        if (old.get(item.id) !== JSON.stringify(item)) count += 1;
        old.delete(item.id);
    });
    return count + old.size;
}

/** Keeps the user on a plan with unsaved changes until they save or discard. */
export function guardLeave(view, isDirty) {
    view.wmsLeave = () => {
        if (!isDirty()) return true;
        notify('Guarda o descarta los cambios del plano antes de salir.', 'error');
        return false;
    };
}
