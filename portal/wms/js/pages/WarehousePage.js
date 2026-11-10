/**
 * A warehouse's layout: its aisles and its elements (racks, shelves,
 * pallets, floor zones), dragged into place on the warehouse's own plan.
 *
 * An element belongs to the aisle it stands beside and is numbered by its
 * order along it, so moving one can change its code and the codes of the
 * ones it passes. Before that happens the page lists every code that changes
 * and waits for the user to confirm.
 */
import { assignAisles, DEFAULT_BAY_M, elementCode, locationCodes, runsAcross, sharedBays } from '../codes.js';
import { freeSpot, overlaps, PlanEditor } from '../plan.js';
import { elementTypes, listFacilities, listWarehouses, savePlan, warehouseLayout } from '../store.js';
import {
    currentUser, escapeHtml, guardLeave, metres, notify, numberOf, pendingCount, saveBar, selection
} from '../ui.js';

const clone = (value) => JSON.parse(JSON.stringify(value));
const SHOWN_CHANGES = 12;
/**
 * An aisle on the plan: its number, which goes in the codes, and its name when
 * the warehouse calls it something else («Galletas», «Saldos»).
 */
export const aisleLabel = (aisle) => (aisle.name && aisle.name !== `Pasillo ${aisle.number}`
    ? `P${aisle.number} · ${aisle.name}` : `Pasillo ${aisle.number}`);
/** The aisle's fill: diagonal stripes, the floor marking of a real aisle. */
const AISLE_STRIPES = '<pattern id="aisleStripes" width="1" height="1" patternUnits="userSpaceOnUse" ' +
    'patternTransform="rotate(45)"><rect width="1" height="1" fill="var(--plan-aisle)"></rect>' +
    '<line x1="0" y1="0" x2="0" y2="1" stroke="var(--plan-aisle-stripe)" stroke-width="0.35"></line></pattern>';

export async function mountWarehouse(host, { go, view }) {
    const facilities = await listFacilities();
    const facility = facilities.find((one) => one.id === selection.facility) || facilities[0];
    const warehouses = facility ? await listWarehouses(facility.id) : [];
    const current = warehouses.find((one) => one.id === selection.warehouse) || warehouses[0];
    if (!current) {
        host.innerHTML = '<div class="card"><p>Esta instalación todavía no tiene almacenes: agrégalos en su plano.</p></div>';
        return;
    }
    selection.warehouse = current.id;
    const types = await elementTypes();
    const layout = await warehouseLayout(current.id);
    const warehouse = layout.warehouse;
    const tag = (entity) => (item) => ({ ...item, entity });
    let saved = [...layout.aisles.map(tag('AISLE')), ...layout.elements.map(tag('ELEMENT'))];
    let draft = clone(saved);
    const aislesOf = (items) => items.filter((one) => one.entity === 'AISLE');
    const elementsOf = (items) => items.filter((one) => one.entity === 'ELEMENT');
    const typeOf = (element) => types.find((one) => one.code === element.type);
    const codeOf = (item, items = draft) => (item.entity === 'AISLE' ? `P${item.number}`
        : elementCode(warehouse, aislesOf(items), types, item));

    host.innerHTML = `
        <header class="sd-page-head"><div>
            <h1>${escapeHtml(warehouse.code)} · ${escapeHtml(warehouse.name)}</h1>
            <p>${escapeHtml(facility.name)} · ${metres(warehouse.width_m)} × ${metres(warehouse.length_m)},
               ${metres(warehouse.height_m)} de alto. Cada elemento toma el pasillo que tiene al lado y el número
               del módulo donde está: impares de un lado, pares del otro.</p>
        </div>
        <label class="field warehouse-pick"><span>Almacén</span>
            <select id="warehousePick">${warehouses.map((one) => `<option value="${escapeHtml(one.id)}"
                ${one.id === current.id ? 'selected' : ''}>${escapeHtml(one.code)} · ${escapeHtml(one.name)}</option>`).join('')}
            </select></label>
        </header>
        <div id="saveBarHost"></div>
        <div class="plan-layout">
            <section class="card plan-card">
                <div class="plan-tools">
                    <form id="addElement" class="tool-group" novalidate>
                        <p class="tool-title">Nuevo elemento</p>
                        <label class="field"><span>Tipo</span>
                            <select name="type">${types.map((one) => `<option value="${one.code}">${escapeHtml(one.name)}</option>`).join('')}</select></label>
                        <label class="field"><span>Ancho (m)</span><input type="number" name="width_m" step="0.1" min="0.5" required></label>
                        <label class="field"><span>Fondo (m)</span><input type="number" name="length_m" step="0.1" min="0.5" required></label>
                        <label class="field"><span>Alto (m)</span><input type="number" name="height_m" step="0.1" min="0"></label>
                        <label class="field" data-levels><span>Niveles</span><input type="number" name="levels" min="1" max="12"></label>
                        <label class="field"><span id="palletsLabel">Palets por nivel</span><input type="number" name="capacity_pallets" min="0"></label>
                        <label class="field"><span>Peso máx. (kg)</span><input type="number" name="capacity_weight_kg" min="0"></label>
                        <button type="submit" class="btn btn-primary" data-btn-icon="plus">Agregar elemento</button>
                    </form>
                    <form id="addAisle" class="tool-group" novalidate>
                        <p class="tool-title">Nuevo pasillo</p>
                        <label class="field"><span>Nombre</span><input name="name" maxlength="40" placeholder="Galletas, Saldos…"></label>
                        <label class="field"><span>Largo (m)</span><input type="number" name="aisle_length" step="0.5" min="2" value="40" required></label>
                        <label class="field"><span>Ancho (m)</span><input type="number" name="aisle_width" step="0.5" min="1" value="3.5" required></label>
                        <label class="field"><span>Módulo (m)</span><input type="number" name="bay_m" step="0.5" min="0.5" value="${DEFAULT_BAY_M}" required></label>
                        <button type="submit" class="btn btn-secondary" data-btn-icon="plus">Agregar pasillo</button>
                    </form>
                </div>
                <div class="plan-legend">${types.map((one) => `<span><i style="background:${one.color}"></i>${escapeHtml(one.name)}</span>`).join('')}
                    <span><i class="is-aisle"></i>Pasillo</span></div>
                <div class="plan-host" id="planHost"></div>
            </section>
            <aside class="card plan-panel" id="planPanel"></aside>
        </div>`;

    const panel = host.querySelector('#planPanel');
    let pending = null;
    const refreshBar = saveBar(host.querySelector('#saveBarHost'), {
        onSave: async (note) => {
            const version = await savePlan({ scope: 'WAREHOUSE', scopeId: warehouse.id, items: draft,
                                             codeOf: (item) => codeOf(item), note, user: currentUser() });
            saved = clone(draft);
            refresh();
            notify(version ? `Versión ${version.version} del layout guardada.` : 'No había cambios.', 'success');
        },
        onDiscard: () => {
            draft = clone(saved);
            pending = null;
            editor.select(null);
            refresh();
        }
    });
    guardLeave(view, () => pendingCount(saved, draft) > 0);

    const editor = new PlanEditor({
        host: host.querySelector('#planHost'), width: warehouse.width_m, length: warehouse.length_m,
        look: (item) => {
            if (item.entity === 'AISLE') {
                return { kind: 'aisle', fill: 'url(#aisleStripes)', stroke: 'var(--plan-aisle-line)',
                         label: aisleLabel(item), title: `${item.name} · ${metres(item.width_m)} × ${metres(item.length_m)}` };
            }
            const type = typeOf(item);
            const code = codeOf(item);
            return { kind: 'element', fill: type.color, stroke: 'var(--plan-element-line)',
                     label: code.replace(`A${warehouse.number}`, ''),
                     title: `${code} · ${type.name}${type.has_levels ? ` · ${item.levels} niveles` : ''}` };
        },
        onSelect: (item) => paint(item),
        onDrop: (item, x, y) => propose(draft.map((one) => (one.id === item.id ? { ...one, pos_x_m: x, pos_y_m: y } : one)),
                                        'Mover'),
        onBlocked: () => notify('Ahí ya hay otro elemento o un pasillo: volvió a su lugar.', 'error'),
        onOpen: () => {},
        defs: AISLE_STRIPES
    });

    /** Numbers the elements of a new arrangement by their aisles. */
    function arrange(items) {
        const aisles = aislesOf(items);
        return [...aisles, ...assignAisles(elementsOf(items), aisles).map((one) => ({ ...one, entity: 'ELEMENT' }))];
    }

    /**
     * Applies a new arrangement, or first shows the codes it changes. A new
     * element has no old code: only the existing ones count as changes.
     */
    function propose(next, what) {
        const arranged = arrange(next);
        if (sharedBays(elementsOf(arranged)).length) {
            notify('Ese módulo del pasillo ya tiene un elemento de ese lado: volvió a su lugar.', 'error');
            refresh();
            return;
        }
        const before = new Map(elementsOf(draft).map((one) => [one.id, codeOf(one)]));
        const changes = elementsOf(arranged)
            .filter((one) => before.has(one.id))
            .map((one) => ({ id: one.id, from: before.get(one.id), to: codeOf(one, arranged) }))
            .filter((change) => change.from !== change.to);
        if (!changes.length) {
            commit(arranged);
            return;
        }
        pending = { arranged, changes, what };
        paint(draft.find((one) => one.id === editor.selectedId) || null);
    }

    function commit(arranged) {
        draft = arranged;
        pending = null;
        refresh();
    }

    function refresh() {
        editor.setItems(draft);
        paint(draft.find((one) => one.id === editor.selectedId) || null);
        refreshBar(pendingCount(saved, draft));
        // Pending changes keep the user here; the selector would drop them.
        host.querySelector('#warehousePick').disabled = pendingCount(saved, draft) > 0;
    }

    function confirmMarkup() {
        const shown = pending.changes.slice(0, SHOWN_CHANGES);
        const more = pending.changes.length - shown.length;
        return `
            <div class="recode-confirm" role="alertdialog" aria-labelledby="recodeTitle">
                <h3 id="recodeTitle">${escapeHtml(pending.what)}: cambian ${pending.changes.length} código${pending.changes.length === 1 ? '' : 's'}</h3>
                <p class="muted small">Las etiquetas impresas siguen llevando a su lugar; conviene reimprimirlas.</p>
                <ul class="recode-list">${shown.map((change) => `
                    <li><span class="code">${escapeHtml(change.from)}</span> → <span class="code is-new">${escapeHtml(change.to)}</span></li>`).join('')}
                    ${more > 0 ? `<li class="muted">y ${more} más</li>` : ''}</ul>
                <div class="form-actions">
                    <button type="button" class="btn btn-cancel btn-small" data-btn-icon="close" id="recodeCancel">Cancelar</button>
                    <button type="button" class="btn btn-save btn-small" data-btn-icon="check" id="recodeOk">Confirmar</button>
                </div>
            </div>`;
    }

    function elementPanel(item) {
        const type = typeOf(item);
        const codes = locationCodes(warehouse, aislesOf(draft), types, item);
        return `
            <form id="itemForm" class="panel-form" novalidate>
                <h3>${escapeHtml(codeOf(item))} <span class="badge badge-info">${escapeHtml(type.name)}</span></h3>
                <div class="field-row">
                    ${type.has_levels ? `<label class="field"><span>Niveles</span><input type="number" name="levels" min="1" max="12" value="${item.levels}"></label>` : ''}
                    <label class="field"><span>Ancho (m)</span><input type="number" name="width_m" step="0.1" min="0.5" value="${item.width_m}"></label>
                    <label class="field"><span>Fondo (m)</span><input type="number" name="length_m" step="0.1" min="0.5" value="${item.length_m}"></label>
                    <label class="field"><span>Alto (m)</span><input type="number" name="height_m" step="0.1" min="0" value="${item.height_m}"></label>
                </div>
                <div class="field-row">
                    <label class="field"><span>Palets por ${type.has_levels ? 'nivel' : 'ubicación'}</span><input type="number" name="capacity_pallets" min="0" value="${item.capacity_pallets ?? ''}"></label>
                    <label class="field"><span>Peso máx. (kg)</span><input type="number" name="capacity_weight_kg" min="0" value="${item.capacity_weight_kg ?? ''}"></label>
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-secondary btn-small" data-btn-icon="check">Aplicar</button>
                    <button type="button" class="btn btn-ghost btn-small" data-btn-icon="refresh" id="rotate">Girar 90°</button>
                    <button type="button" class="btn btn-delete btn-small" data-btn-icon="trash" id="removeItem">Quitar</button>
                </div>
                <p class="panel-label">Ubicaciones (${codes.length})</p>
                <div class="code-chips">${codes.map((code) => `<span class="code">${escapeHtml(code)}</span>`).join('')}</div>
            </form>`;
    }

    function aislePanel(item) {
        return `
            <form id="itemForm" class="panel-form" novalidate>
                <h3>${escapeHtml(aisleLabel(item))}</h3>
                <div class="field-row">
                    <label class="field"><span>Número</span><input type="number" name="number" min="1" value="${item.number}"></label>
                    <label class="field"><span>Nombre</span><input name="name" value="${escapeHtml(item.name)}"></label>
                </div>
                <div class="field-row">
                    <label class="field"><span>Largo (m)</span><input type="number" name="span" step="0.5" min="2" value="${runsAcross(item) ? item.width_m : item.length_m}"></label>
                    <label class="field"><span>Ancho (m)</span><input type="number" name="breadth" step="0.5" min="1" value="${runsAcross(item) ? item.length_m : item.width_m}"></label>
                    <label class="field"><span>Módulo (m)</span><input type="number" name="bay_m" step="0.5" min="0.5" value="${item.bay_m || DEFAULT_BAY_M}"></label>
                </div>
                <p class="muted small">Corre ${runsAcross(item) ? 'de izquierda a derecha' : 'de arriba abajo'}. Cada
                   módulo es una posición: impares de un lado, pares del otro. Mover un elemento sólo cambia su código.</p>
                <div class="form-actions">
                    <button type="submit" class="btn btn-secondary btn-small" data-btn-icon="check">Aplicar</button>
                    <button type="button" class="btn btn-ghost btn-small" data-btn-icon="refresh" id="rotate">Girar 90°</button>
                    <button type="button" class="btn btn-delete btn-small" data-btn-icon="trash" id="removeItem">Quitar</button>
                </div>
            </form>`;
    }

    /** A change of size or position that still fits: inside the plan, on nobody. */
    function fits(candidate) {
        return candidate.pos_x_m + candidate.width_m <= warehouse.width_m &&
            candidate.pos_y_m + candidate.length_m <= warehouse.length_m &&
            !draft.some((other) => other.id !== candidate.id && overlaps(candidate, other));
    }

    function paint(item) {
        if (pending) {
            panel.innerHTML = confirmMarkup();
            panel.querySelector('#recodeOk').addEventListener('click', () => commit(pending.arranged));
            panel.querySelector('#recodeCancel').addEventListener('click', () => {
                pending = null;
                refresh();
            });
            return;
        }
        if (!item) {
            panel.innerHTML = `<p class="muted">Selecciona un pasillo o un elemento para ver y corregir sus datos.
                Arrástralo para moverlo, o usa las flechas del teclado.</p>`;
            return;
        }
        panel.innerHTML = item.entity === 'AISLE' ? aislePanel(item) : elementPanel(item);
        const form = panel.querySelector('#itemForm');
        const change = (changes, what) => {
            const candidate = { ...item, ...changes };
            if (!fits(candidate)) {
                notify('Con esas medidas se sale del almacén o pisa otro elemento.', 'error');
                return;
            }
            propose(draft.map((one) => (one.id === item.id ? candidate : one)), what);
        };
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            if (item.entity === 'AISLE') {
                const number = numberOf(form, 'number', item.number);
                if (aislesOf(draft).some((one) => one.id !== item.id && one.number === number)) {
                    notify(`Ya hay un pasillo ${number}.`, 'error');
                    return;
                }
                const span = numberOf(form, 'span', item.width_m);
                const breadth = numberOf(form, 'breadth', item.length_m);
                change({ number, name: form.elements.name.value.trim() || `Pasillo ${number}`,
                         bay_m: numberOf(form, 'bay_m', item.bay_m || DEFAULT_BAY_M),
                         ...(runsAcross(item) ? { width_m: span, length_m: breadth } : { width_m: breadth, length_m: span }) },
                       'Corregir el pasillo');
                return;
            }
            change({ levels: form.elements.levels ? numberOf(form, 'levels', item.levels) : item.levels,
                     width_m: numberOf(form, 'width_m', item.width_m), length_m: numberOf(form, 'length_m', item.length_m),
                     height_m: numberOf(form, 'height_m', item.height_m),
                     capacity_pallets: numberOf(form, 'capacity_pallets', null),
                     capacity_weight_kg: numberOf(form, 'capacity_weight_kg', null) }, 'Corregir el elemento');
        });
        panel.querySelector('#rotate').addEventListener('click', () =>
            change({ width_m: item.length_m, length_m: item.width_m }, 'Girar'));
        panel.querySelector('#removeItem').addEventListener('click', () => {
            editor.selectedId = null;
            propose(draft.filter((one) => one.id !== item.id), 'Quitar');
        });
    }

    /** Adds a rectangle in the middle of the plan if it is free, else in the first free spot. */
    function place(item) {
        const half = (room) => Math.max(0, Math.round(room)) / 2;
        const centre = { ...item, pos_x_m: half(warehouse.width_m - item.width_m),
                         pos_y_m: half(warehouse.length_m - item.length_m) };
        const spot = draft.some((other) => overlaps(centre, other))
            ? freeSpot(item, draft, warehouse.width_m, warehouse.length_m)
            : { x: centre.pos_x_m, y: centre.pos_y_m };
        if (!spot) {
            notify('No queda lugar libre de ese tamaño en el almacén.', 'error');
            return;
        }
        editor.selectedId = item.id;
        propose([...draft, { ...item, pos_x_m: spot.x, pos_y_m: spot.y }], 'Agregar');
    }

    // Each element is entered with its own measures: the type only proposes them.
    const elementForm = host.querySelector('#addElement');
    const suggest = () => {
        const type = types.find((one) => one.code === elementForm.elements.type.value);
        Object.entries({ ...type.default_size, levels: type.default_levels,
                         capacity_pallets: type.has_levels ? 2 : 1 }).forEach(([key, value]) => {
            elementForm.elements[key].value = value;
        });
        elementForm.elements.capacity_weight_kg.value = '';
        elementForm.querySelector('[data-levels]').hidden = !type.has_levels;
        host.querySelector('#palletsLabel').textContent = type.has_levels ? 'Palets por nivel' : 'Palets';
    };
    elementForm.elements.type.addEventListener('change', suggest);
    suggest();
    elementForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!elementForm.reportValidity()) return;
        const type = types.find((one) => one.code === elementForm.elements.type.value);
        place({ id: crypto.randomUUID(), entity: 'ELEMENT', warehouse_id: warehouse.id, type: type.code,
                width_m: numberOf(elementForm, 'width_m', type.default_size.width_m),
                length_m: numberOf(elementForm, 'length_m', type.default_size.length_m),
                height_m: numberOf(elementForm, 'height_m', 0),
                levels: type.has_levels ? numberOf(elementForm, 'levels', type.default_levels) : 1,
                capacity_pallets: numberOf(elementForm, 'capacity_pallets', null),
                capacity_weight_kg: numberOf(elementForm, 'capacity_weight_kg', null), number: 0, aisle_id: null });
    });
    host.querySelector('#addAisle').addEventListener('submit', (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        if (!form.reportValidity()) return;
        const number = Math.max(0, ...aislesOf(draft).map((one) => one.number)) + 1;
        place({ id: crypto.randomUUID(), entity: 'AISLE', warehouse_id: warehouse.id, number,
                name: form.elements.name.value.trim() || `Pasillo ${number}`,
                width_m: numberOf(form, 'aisle_length', 40), length_m: numberOf(form, 'aisle_width', 3.5),
                bay_m: numberOf(form, 'bay_m', DEFAULT_BAY_M) });
        form.elements.name.value = '';
    });
    host.querySelector('#warehousePick').addEventListener('change', (event) => {
        selection.warehouse = event.target.value;
        mountWarehouse(host, { go, view });
    });

    refresh();
}
