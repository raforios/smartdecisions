/**
 * The WMS data, kept in this browser until the `wms` service exists.
 *
 * Every function is async and returns what the API will return, so the pages
 * do not change when this file is replaced by calls to `/v1/wms/*`. Shapes
 * follow the data model (`docs/wms/modelo_datos_tecnico.md`).
 *
 * The first visit seeds a sample facility so the editor opens with a real
 * looking plan, marked as an example.
 */
import { assignAisles } from './codes.js';

const STATE_KEY = 'wms_demo_state';

/** The element catalog: adding a type here adds it to the editor. */
const ELEMENT_TYPES = [
    { code: 'RACK', name: 'Rack', code_letter: 'R', has_levels: true, color: '#2f6fb5',
      default_size: { width_m: 6, length_m: 1.2, height_m: 6 }, default_levels: 4 },
    { code: 'SHELF', name: 'Estante', code_letter: 'E', has_levels: true, color: '#12796f',
      default_size: { width_m: 3, length_m: 0.6, height_m: 2.2 }, default_levels: 5 },
    { code: 'PALLET', name: 'Palé', code_letter: 'T', has_levels: false, color: '#a06a12',
      default_size: { width_m: 1.2, length_m: 1, height_m: 1.5 }, default_levels: 1 },
    { code: 'FLOOR', name: 'Piso', code_letter: 'Z', has_levels: false, color: '#6b7590',
      default_size: { width_m: 6, length_m: 4, height_m: 0 }, default_levels: 1 }
];

const newId = () => (crypto.randomUUID ? crypto.randomUUID()
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`);

/** A sample warehouse: four aisles across, racks on both sides of each. */
function sampleWarehouseLayout(warehouseId) {
    const aisles = [];
    const elements = [];
    for (let index = 0; index < 4; index += 1) {
        const top = 4 + index * 7.4;
        const aisle = { id: newId(), warehouse_id: warehouseId, number: index + 1, name: `Pasillo ${index + 1}`,
                        pos_x_m: 4, pos_y_m: top + 1.2, width_m: 48, length_m: 3.5, bay_m: 6 };
        aisles.push(aisle);
        for (let slot = 0; slot < 8; slot += 1) {
            [top, top + 4.7].forEach((y) => elements.push({
                id: newId(), warehouse_id: warehouseId, type: 'RACK', levels: 4,
                pos_x_m: 4 + slot * 6, pos_y_m: y, width_m: 6, length_m: 1.2, height_m: 6,
                capacity_pallets: 2, capacity_weight_kg: 2000
            }));
        }
    }
    for (let slot = 0; slot < 6; slot += 1) {
        elements.push({ id: newId(), warehouse_id: warehouseId, type: 'FLOOR', levels: 1,
                        pos_x_m: 4 + slot * 8, pos_y_m: 35, width_m: 6, length_m: 4, height_m: 0,
                        capacity_pallets: 12, capacity_weight_kg: 12000 });
    }
    // Numbered as the editor numbers them: by aisle and bay.
    return { aisles, elements: assignAisles(elements, aisles) };
}

function seed() {
    const facilityId = newId();
    const warehouses = [
        { number: 1, code: 'A1', name: 'Producto terminado', width_m: 56, length_m: 42, height_m: 9,
          pos_x_m: 8, pos_y_m: 8 },
        { number: 2, code: 'A2', name: 'Materia prima', width_m: 36, length_m: 30, height_m: 8,
          pos_x_m: 72, pos_y_m: 8 },
        { number: 3, code: 'A3', name: 'Despacho', width_m: 30, length_m: 18, height_m: 6,
          pos_x_m: 72, pos_y_m: 48 }
    ].map((item) => ({ id: newId(), facility_id: facilityId, ...item }));
    const layouts = {};
    warehouses.forEach((warehouse) => {
        layouts[warehouse.id] = warehouse.number === 1 ? sampleWarehouseLayout(warehouse.id)
            : { aisles: [], elements: [] };
    });
    return {
        facilities: [{
            id: facilityId, code: 'PLANTA-01', name: 'Planta Central (ejemplo)', city: 'Cochabamba',
            address: 'Av. Ejemplo 1234', phone: '', email: '', lat: -17.39, lng: -66.16,
            plan_width_m: 120, plan_length_m: 80, is_sample: true
        }],
        warehouses,
        layouts,
        versions: []
    };
}

function read() {
    try {
        const stored = JSON.parse(localStorage.getItem(STATE_KEY) || 'null');
        if (stored) return stored;
    } catch (error) {
        // Unreadable or blocked storage: start again from the sample.
    }
    const fresh = seed();
    write(fresh);
    return fresh;
}

function write(state) {
    try {
        localStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch (error) {
        // Storage blocked: the session keeps working, it just is not remembered.
    }
}

const clone = (value) => JSON.parse(JSON.stringify(value));

export async function elementTypes() {
    return clone(ELEMENT_TYPES);
}

export async function listFacilities() {
    return clone(read().facilities);
}

export async function saveFacility(facility) {
    const state = read();
    const stored = { ...facility, id: facility.id || newId() };
    const index = state.facilities.findIndex((one) => one.id === stored.id);
    if (index >= 0) state.facilities[index] = { ...state.facilities[index], ...stored };
    else state.facilities.push(stored);
    write(state);
    return clone(stored);
}

export async function listWarehouses(facilityId) {
    return clone(read().warehouses.filter((one) => one.facility_id === facilityId));
}

export async function warehouseLayout(warehouseId) {
    const state = read();
    const warehouse = state.warehouses.find((one) => one.id === warehouseId);
    if (!warehouse) return null;
    return clone({ warehouse, ...(state.layouts[warehouseId] || { aisles: [], elements: [] }) });
}

/** What a plan holds, as one list of items: the warehouses, or aisles and elements. */
function planItems(state, scope, scopeId) {
    if (scope === 'FACILITY') return state.warehouses.filter((one) => one.facility_id === scopeId);
    const layout = state.layouts[scopeId] || { aisles: [], elements: [] };
    return [...layout.aisles.map((one) => ({ ...one, entity: 'AISLE' })),
            ...layout.elements.map((one) => ({ ...one, entity: 'ELEMENT' }))];
}

const POSITION = ['pos_x_m', 'pos_y_m'];
const SIZE = ['width_m', 'length_m', 'height_m', 'levels'];

/** One change per item, named by what moved most: its code, its place, its size. */
function diff(before, after, codeOf) {
    const changes = [];
    const old = new Map(before.map((item) => [item.id, item]));
    after.forEach((item) => {
        const previous = old.get(item.id);
        const entity = item.entity || 'WAREHOUSE';
        old.delete(item.id);
        if (!previous) {
            changes.push({ entity, entity_id: item.id, action: 'CREATE', before: null, after: item,
                           old_code: null, new_code: codeOf(item) });
            return;
        }
        const [oldCode, newCode] = [codeOf(previous), codeOf(item)];
        const moved = POSITION.some((key) => previous[key] !== item[key]);
        const resized = SIZE.some((key) => previous[key] !== item[key]);
        const touched = JSON.stringify(previous) !== JSON.stringify(item);
        const action = oldCode !== newCode ? 'RECODE' : moved ? 'MOVE' : resized ? 'RESIZE' : touched ? 'UPDATE' : null;
        if (action) {
            changes.push({ entity, entity_id: item.id, action, before: previous, after: item,
                           old_code: oldCode, new_code: newCode });
        }
    });
    old.forEach((item) => changes.push({ entity: item.entity || 'WAREHOUSE', entity_id: item.id,
        action: 'DELETE', before: item, after: null, old_code: codeOf(item), new_code: null }));
    return changes;
}

/**
 * Saves a whole plan and records it: a full snapshot (even for one small
 * change) and each change one by one. Nothing is recorded when nothing changed.
 *
 * @param {object} save
 * @param {'FACILITY'|'WAREHOUSE'} save.scope
 * @param {string} save.scopeId - The facility or the warehouse.
 * @param {object[]} save.items - Warehouses, or aisles and elements (with `entity`).
 * @param {Function} save.codeOf - The code of an item, to record recodings.
 * @param {string} save.note - Why, in the user's words.
 * @param {string} save.user - Who.
 * @returns {Promise<object|null>} The version written, or null.
 */
export async function savePlan(save) {
    const state = read();
    const before = planItems(state, save.scope, save.scopeId);
    const changes = diff(before, save.items, save.codeOf);
    if (!changes.length) return null;
    if (save.scope === 'FACILITY') {
        state.warehouses = [...state.warehouses.filter((one) => one.facility_id !== save.scopeId),
                            ...save.items.map(({ entity, ...item }) => item)];
        save.items.forEach((item) => {
            if (!state.layouts[item.id]) state.layouts[item.id] = { aisles: [], elements: [] };
        });
    } else {
        const strip = ({ entity, ...item }) => item;
        state.layouts[save.scopeId] = {
            aisles: save.items.filter((one) => one.entity === 'AISLE').map(strip),
            elements: save.items.filter((one) => one.entity === 'ELEMENT').map(strip)
        };
    }
    const previous = state.versions.filter((one) => one.scope === save.scope && one.scope_id === save.scopeId);
    const version = {
        id: newId(), scope: save.scope, scope_id: save.scopeId, version: previous.length + 1,
        snapshot: clone(save.items), note: save.note || '', created_by: save.user,
        created_at: new Date().toISOString(), changes
    };
    state.versions.push(version);
    write(state);
    return clone(version);
}

export async function versions(scope, scopeId) {
    return clone(read().versions.filter((one) => one.scope === scope && one.scope_id === scopeId)
        .sort((one, other) => other.version - one.version));
}

/** Back to the sample: only for the demo, from the facilities page. */
export async function resetSample() {
    const fresh = seed();
    write(fresh);
    return clone(fresh.facilities);
}
