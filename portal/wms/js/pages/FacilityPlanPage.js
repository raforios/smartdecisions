/**
 * The facility's plan: where each warehouse stands. A warehouse is drawn with
 * its measures in the middle of the free space and dragged into place; a
 * double click (or «Abrir») goes down a level, to its own layout.
 */
import { freeSpot, overlaps, PlanEditor } from '../plan.js';
import { listFacilities, listWarehouses, savePlan, warehouseLayout } from '../store.js';
import {
    currentUser, escapeHtml, guardLeave, metres, notify, numberOf, pendingCount, saveBar, selection
} from '../ui.js';

const WAREHOUSE_LOOK = (item) => ({
    kind: 'warehouse', fill: 'var(--plan-warehouse)', stroke: 'var(--plan-warehouse-line)',
    label: item.code, sub: item.name,
    title: `${item.code} · ${item.name} · ${metres(item.width_m)} × ${metres(item.length_m)} × ${metres(item.height_m)}`
});

const clone = (value) => JSON.parse(JSON.stringify(value));

function panelMarkup(item) {
    if (!item) {
        return `<p class="muted">Selecciona un almacén en el plano para ver y corregir sus datos.
            Arrástralo para moverlo; doble clic para abrirlo.</p>`;
    }
    return `
        <form id="warehouseForm" class="panel-form" novalidate>
            <h3>${escapeHtml(item.code)}</h3>
            <label class="field"><span>Nombre</span><input name="name" value="${escapeHtml(item.name)}"></label>
            <div class="field-row">
                <label class="field"><span>Ancho (m)</span><input type="number" step="0.5" min="1" name="width_m" value="${item.width_m}"></label>
                <label class="field"><span>Largo (m)</span><input type="number" step="0.5" min="1" name="length_m" value="${item.length_m}"></label>
                <label class="field"><span>Alto (m)</span><input type="number" step="0.5" min="1" name="height_m" value="${item.height_m}"></label>
            </div>
            <p class="muted small">Posición: ${metres(item.pos_x_m)} desde la izquierda, ${metres(item.pos_y_m)} desde arriba.</p>
            <div class="form-actions">
                <button type="submit" class="btn btn-secondary btn-small" data-btn-icon="check">Aplicar</button>
                <button type="button" class="btn btn-ghost btn-small" data-btn-icon="refresh" id="rotate">Girar 90°</button>
                <button type="button" class="btn btn-primary btn-small" data-btn-icon="play" id="openWarehouse">Abrir almacén</button>
                <button type="button" class="btn btn-delete btn-small" data-btn-icon="trash" id="removeWarehouse">Quitar</button>
            </div>
        </form>`;
}

export async function mountFacilityPlan(host, { go, view }) {
    const facilities = await listFacilities();
    const facility = facilities.find((one) => one.id === selection.facility) || facilities[0];
    if (!facility) {
        host.innerHTML = '<div class="card"><p>Primero crea una instalación.</p></div>';
        return;
    }
    selection.facility = facility.id;
    let saved = await listWarehouses(facility.id);
    let draft = clone(saved);

    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>${escapeHtml(facility.name)}</h1>
            <p>Plano de ${metres(facility.plan_width_m)} × ${metres(facility.plan_length_m)}.
               Cada almacén es un rectángulo con sus medidas; dos almacenes no pueden ocupar el mismo lugar.</p>
        </div></header>
        <div id="saveBarHost"></div>
        <div class="plan-layout">
            <section class="card plan-card">
                <form class="plan-tools" id="addWarehouse" novalidate>
                    <label class="field"><span>Nombre</span><input name="name" placeholder="Producto terminado" required></label>
                    <label class="field"><span>Ancho (m)</span><input type="number" name="width_m" step="0.5" min="1" value="30"></label>
                    <label class="field"><span>Largo (m)</span><input type="number" name="length_m" step="0.5" min="1" value="20"></label>
                    <label class="field"><span>Alto (m)</span><input type="number" name="height_m" step="0.5" min="1" value="8"></label>
                    <button type="submit" class="btn btn-primary" data-btn-icon="plus">Agregar almacén</button>
                </form>
                <div class="plan-host" id="planHost"></div>
            </section>
            <aside class="card plan-panel" id="planPanel"></aside>
        </div>`;

    const panel = host.querySelector('#planPanel');
    const refreshBar = saveBar(host.querySelector('#saveBarHost'), {
        onSave: async (note) => {
            const version = await savePlan({ scope: 'FACILITY', scopeId: facility.id, items: draft,
                                             codeOf: (item) => item.code, note, user: currentUser() });
            saved = clone(draft);
            refresh();
            notify(version ? `Versión ${version.version} del plano guardada.` : 'No había cambios.', 'success');
        },
        onDiscard: () => {
            draft = clone(saved);
            editor.select(null);
            refresh();
        }
    });
    guardLeave(view, () => pendingCount(saved, draft) > 0);

    const editor = new PlanEditor({
        host: host.querySelector('#planHost'), width: facility.plan_width_m, length: facility.plan_length_m,
        look: WAREHOUSE_LOOK,
        onSelect: (item) => paint(item),
        onDrop: (item, x, y) => {
            Object.assign(draft.find((one) => one.id === item.id), { pos_x_m: x, pos_y_m: y });
            refresh();
        },
        onBlocked: () => notify('Ahí ya hay otro almacén: volvió a su lugar.', 'error'),
        onOpen: (item) => openWarehouse(item)
    });

    function refresh() {
        editor.setItems(draft);
        paint(draft.find((one) => one.id === editor.selectedId) || null);
        refreshBar(pendingCount(saved, draft));
    }

    async function openWarehouse(item) {
        if (pendingCount(saved, draft)) {
            notify('Guarda el plano antes de abrir un almacén.', 'error');
            return;
        }
        selection.warehouse = item.id;
        go('warehouse');
    }

    function paint(item) {
        panel.innerHTML = panelMarkup(item);
        if (!item) return;
        const form = panel.querySelector('#warehouseForm');
        const target = () => draft.find((one) => one.id === item.id);
        const fits = (candidate) => candidate.pos_x_m + candidate.width_m <= facility.plan_width_m &&
            candidate.pos_y_m + candidate.length_m <= facility.plan_length_m &&
            !draft.some((other) => other.id !== candidate.id && overlaps(candidate, other));
        const apply = (changes) => {
            const candidate = { ...target(), ...changes };
            if (!fits(candidate)) {
                notify('Con esas medidas se sale del plano o pisa otro almacén.', 'error');
                return;
            }
            Object.assign(target(), changes);
            refresh();
        };
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            apply({ name: form.elements.name.value.trim() || item.name,
                    width_m: numberOf(form, 'width_m', item.width_m),
                    length_m: numberOf(form, 'length_m', item.length_m),
                    height_m: numberOf(form, 'height_m', item.height_m) });
        });
        panel.querySelector('#rotate').addEventListener('click', () =>
            apply({ width_m: item.length_m, length_m: item.width_m }));
        panel.querySelector('#openWarehouse').addEventListener('click', () => openWarehouse(item));
        panel.querySelector('#removeWarehouse').addEventListener('click', async () => {
            const layout = await warehouseLayout(item.id);
            if (layout && (layout.aisles.length || layout.elements.length)) {
                notify('Ese almacén tiene pasillos o elementos: vacíalo antes de quitarlo.', 'error');
                return;
            }
            draft = draft.filter((one) => one.id !== item.id);
            editor.select(null);
            refresh();
        });
    }

    host.querySelector('#addWarehouse').addEventListener('submit', (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        if (!form.reportValidity()) return;
        const number = Math.max(0, ...draft.map((one) => one.number)) + 1;
        const item = { id: crypto.randomUUID(), facility_id: facility.id, number, code: `A${number}`,
                       name: form.elements.name.value.trim(), width_m: numberOf(form, 'width_m', 30),
                       length_m: numberOf(form, 'length_m', 20), height_m: numberOf(form, 'height_m', 8) };
        // In the middle of the plan when it is free; if not, the first free spot.
        const centre = { ...item, pos_x_m: Math.max(0, (facility.plan_width_m - item.width_m) / 2),
                         pos_y_m: Math.max(0, (facility.plan_length_m - item.length_m) / 2) };
        const clash = draft.some((other) => overlaps(centre, other));
        const spot = clash ? freeSpot(item, draft, facility.plan_width_m, facility.plan_length_m)
            : { x: centre.pos_x_m, y: centre.pos_y_m };
        if (!spot) {
            notify('No queda lugar libre de ese tamaño en el plano.', 'error');
            return;
        }
        draft.push({ ...item, pos_x_m: Math.round(spot.x * 2) / 2, pos_y_m: Math.round(spot.y * 2) / 2 });
        form.reset();
        editor.selectedId = item.id;
        refresh();
        notify(`${item.code} agregado: arrástralo a su lugar.`, 'success');
    });

    refresh();
}
