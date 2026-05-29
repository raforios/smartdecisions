/**
 * Catalog page.
 *
 * Four tabs that share the same modal helper:
 *   - Items
 *   - Categorías
 *   - Unidades
 *   - Parámetros del sistema (key/value)
 *
 * Items are the only entity whose CRUD touches Foreign Keys (category, unit),
 * so before showing the modal we lazy-load the dependent lookups once.
 */
import { hasRole, ROLES } from '../auth.js';
import {
    clear,
    closeModal,
    el,
    formatDate,
    formatNumber,
    openModal,
    showToast,
} from '../ui.js';

const TABS = [
    { key: 'items',       label: 'Ítems' },
    { key: 'categories',  label: 'Categorías' },
    { key: 'units',       label: 'Unidades' },
    { key: 'parameters',  label: 'Parámetros' },
];

export async function mountCatalog({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    const tabsEl = el('div', { class: 'sup-tabs' });
    const panelEl = el('div', {});
    host.appendChild(tabsEl);
    host.appendChild(panelEl);

    const state = {
        activeTab: 'items',
        actions,
        api,
        host: panelEl,
        // cached lookups
        categories: null,
        units: null,
    };

    TABS.forEach(tab => {
        const btn = el('button', {
            class: 'sup-tab',
            text: tab.label,
            dataset: { tab: tab.key },
            onClick: () => _activate(tab.key),
        });
        tabsEl.appendChild(btn);
    });

    function _activate(key) {
        state.activeTab = key;
        tabsEl.querySelectorAll('.sup-tab').forEach(b => {
            b.classList.toggle('active', b.dataset.tab === key);
        });
        switch (key) {
            case 'items': return _renderItems(state);
            case 'categories': return _renderCategories(state);
            case 'units': return _renderUnits(state);
            case 'parameters': return _renderParameters(state);
        }
    }

    _activate('items');
}

// --------------------------------------------------------------------- //
// ITEMS                                                                  //
// --------------------------------------------------------------------- //
async function _renderItems(state) {
    state.actions.innerHTML = '';
    if (hasRole(ROLES.ADMIN)) {
        state.actions.appendChild(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-plus"></i> Nuevo ítem',
            onClick: () => _openItemModal(state),
        }));
    }

    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando ítems…' }));
    try {
        const [items, categories, units] = await Promise.all([
            state.api.listItems({ limit: 500 }),
            _ensureCategories(state),
            _ensureUnits(state),
        ]);
        const catById = new Map(categories.map(c => [c.id, c]));
        const unitById = new Map(units.map(u => [u.id, u]));

        clear(state.host);
        state.host.appendChild(_itemsTable(items, catById, unitById, state));
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _itemsTable(items, catById, unitById, state) {
    if (items.length === 0) {
        return el('div', { class: 'sup-empty', text: 'Aún no hay ítems en el catálogo.' });
    }
    const thead = el('thead', {}, [el('tr', {}, [
        el('th', { text: 'Código' }),
        el('th', { text: 'Nombre' }),
        el('th', { text: 'Categoría' }),
        el('th', { text: 'Unidad' }),
        el('th', { text: 'Stock' }),
        el('th', { text: 'Mínimo' }),
        el('th', { text: 'Activo' }),
        el('th', { text: '' }),
    ])]);
    const tbody = el('tbody', {}, items.map(item => {
        const stockTd = el('td', {}, [
            el('span', {
                text: formatNumber(item.current_stock),
                class: Number(item.current_stock) <= Number(item.min_stock) ? 'sup-form-error' : '',
            }),
        ]);
        const activeBadge = el('span', {
            class: `sup-badge ${item.is_active ? 'sup-badge-delivered' : 'sup-badge-closed'}`,
            text: item.is_active ? 'Activo' : 'Inactivo',
        });
        const actionsTd = el('td', { class: 'sup-row-actions' });
        if (hasRole(ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER)) {
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn',
                title: 'Parámetros',
                html: '<i class="fa-solid fa-sliders"></i>',
                onClick: () => _openItemParametersModal(state, item),
            }));
        }
        if (hasRole(ROLES.ADMIN)) {
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn',
                title: 'Editar',
                html: '<i class="fa-solid fa-pen"></i>',
                onClick: () => _openItemModal(state, item),
            }));
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn',
                title: 'Desactivar',
                html: '<i class="fa-solid fa-trash"></i>',
                onClick: () => _confirmDeleteItem(state, item),
            }));
        }
        return el('tr', {}, [
            el('td', { text: item.code }),
            el('td', { text: item.name }),
            el('td', { text: catById.get(item.category_id)?.name || `#${item.category_id}` }),
            el('td', { text: unitById.get(item.unit_id)?.abbreviation || `#${item.unit_id}` }),
            stockTd,
            el('td', { text: formatNumber(item.min_stock) }),
            el('td', {}, [activeBadge]),
            actionsTd,
        ]);
    }));
    return el('div', { class: 'sup-table-wrap' }, [el('table', { class: 'sup-table' }, [thead, tbody])]);
}

function _openItemModal(state, item) {
    const isEdit = Boolean(item);
    const form = el('form', { class: 'sup-stack', id: 'item-form' }, [
        el('div', { class: 'sup-field-row' }, [
            _field('code', 'Código', { value: item?.code, required: true, disabled: isEdit }),
            _field('name', 'Nombre', { value: item?.name, required: true }),
        ]),
        _field('description', 'Descripción', { value: item?.description, textarea: true }),
        el('div', { class: 'sup-field-row' }, [
            _select('category_id', 'Categoría', state.categories, item?.category_id,
                c => `${c.code} — ${c.name}`),
            _select('unit_id', 'Unidad', state.units, item?.unit_id, u => `${u.code} (${u.abbreviation})`),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('min_stock', 'Stock mínimo', {
                value: item?.min_stock ?? '0', type: 'number', step: '0.01', required: true,
            }),
            _field('default_replenishment_qty', 'Cantidad reposición default', {
                value: item?.default_replenishment_qty ?? '0', type: 'number', step: '0.01',
                required: true,
            }),
        ]),
    ]);
    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: isEdit ? 'Guardar cambios' : 'Crear',
        onClick: async () => {
            errEl.hidden = true;
            const fd = new FormData(form);
            const payload = {
                name: fd.get('name'),
                description: fd.get('description') || null,
                category_id: Number(fd.get('category_id')),
                unit_id: Number(fd.get('unit_id')),
                min_stock: Number(fd.get('min_stock')),
                default_replenishment_qty: Number(fd.get('default_replenishment_qty')),
            };
            try {
                if (isEdit) {
                    await state.api.updateItem(item.id, payload);
                    showToast('Ítem actualizado', 'success');
                } else {
                    payload.code = fd.get('code');
                    await state.api.createItem(payload);
                    showToast('Ítem creado', 'success');
                }
                closeModal();
                _renderItems(state);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: isEdit ? `Editar ítem: ${item.code}` : 'Nuevo ítem',
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
        wide: true,
    });
}

function _openItemParametersModal(state, item) {
    const form = el('form', { class: 'sup-stack', id: 'params-form' }, [
        el('p', { class: 'sup-muted', text: `${item.code} — ${item.name}` }),
        el('div', { class: 'sup-field-row' }, [
            _field('min_stock', 'Stock mínimo', {
                value: item.min_stock, type: 'number', step: '0.01',
            }),
            _field('default_replenishment_qty', 'Cantidad reposición default', {
                value: item.default_replenishment_qty, type: 'number', step: '0.01',
            }),
        ]),
    ]);
    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: 'Guardar',
        onClick: async () => {
            errEl.hidden = true;
            const fd = new FormData(form);
            try {
                await state.api.updateItemParameters(item.id, {
                    min_stock: Number(fd.get('min_stock')),
                    default_replenishment_qty: Number(fd.get('default_replenishment_qty')),
                });
                showToast('Parámetros actualizados', 'success');
                closeModal();
                _renderItems(state);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: 'Parámetros del ítem',
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
    });
}

async function _confirmDeleteItem(state, item) {
    if (!confirm(`Desactivar el ítem ${item.code}?`)) return;
    try {
        await state.api.deleteItem(item.id);
        showToast('Ítem desactivado', 'success');
        _renderItems(state);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function _ensureCategories(state) {
    if (!state.categories) {
        state.categories = await state.api.listCategories({ limit: 500 });
    }
    return state.categories;
}
async function _ensureUnits(state) {
    if (!state.units) {
        state.units = await state.api.listUnits({ limit: 500 });
    }
    return state.units;
}

// --------------------------------------------------------------------- //
// Generic simple-entity rendering (categories, units)                    //
// --------------------------------------------------------------------- //
async function _renderCategories(state) {
    await _renderSimpleEntity(state, {
        title: 'Categorías',
        newLabel: 'Nueva categoría',
        loader: () => state.api.listCategories({ limit: 500 }),
        columns: [
            { header: 'Código', key: 'code' },
            { header: 'Nombre', key: 'name' },
            { header: 'Descripción', key: 'description' },
            { header: 'Activa', render: r => r.is_active ? 'Sí' : 'No' },
            { header: 'Creada', render: r => formatDate(r.created_at) },
        ],
        formFields: [
            { name: 'code', label: 'Código', required: true, disabledOnEdit: true },
            { name: 'name', label: 'Nombre', required: true },
            { name: 'description', label: 'Descripción', textarea: true },
            { name: 'is_active', label: 'Activa', type: 'checkbox', defaultValue: true },
        ],
        create: payload => state.api.createCategory(payload),
        update: (id, payload) => state.api.updateCategory(id, payload),
        remove: id => state.api.deleteCategory(id),
        afterChange: () => { state.categories = null; },
    });
}

async function _renderUnits(state) {
    await _renderSimpleEntity(state, {
        title: 'Unidades',
        newLabel: 'Nueva unidad',
        loader: () => state.api.listUnits({ limit: 500 }),
        columns: [
            { header: 'Código', key: 'code' },
            { header: 'Nombre', key: 'name' },
            { header: 'Abreviación', key: 'abbreviation' },
            { header: 'Activa', render: r => r.is_active ? 'Sí' : 'No' },
            { header: 'Creada', render: r => formatDate(r.created_at) },
        ],
        formFields: [
            { name: 'code', label: 'Código', required: true, disabledOnEdit: true },
            { name: 'name', label: 'Nombre', required: true },
            { name: 'abbreviation', label: 'Abreviación', required: true },
            { name: 'is_active', label: 'Activa', type: 'checkbox', defaultValue: true },
        ],
        create: payload => state.api.createUnit(payload),
        update: (id, payload) => state.api.updateUnit(id, payload),
        remove: id => state.api.deleteUnit(id),
        afterChange: () => { state.units = null; },
    });
}

async function _renderSimpleEntity(state, cfg) {
    state.actions.innerHTML = '';
    if (hasRole(ROLES.ADMIN)) {
        state.actions.appendChild(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: `<i class="fa-solid fa-plus"></i> ${cfg.newLabel}`,
            onClick: () => _openSimpleEntityModal(state, cfg, null),
        }));
    }

    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando…' }));
    try {
        const rows = await cfg.loader();
        clear(state.host);
        state.host.appendChild(_simpleEntityTable(state, cfg, rows));
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _simpleEntityTable(state, cfg, rows) {
    if (rows.length === 0) {
        return el('div', { class: 'sup-empty', text: 'Sin registros.' });
    }
    const headers = cfg.columns.map(c => el('th', { text: c.header }));
    headers.push(el('th', { text: '' }));
    const trHead = el('tr', {}, headers);

    const trBody = rows.map(row => {
        const cells = cfg.columns.map(c => {
            const value = c.render ? c.render(row) : row[c.key];
            return el('td', { text: value ?? '—' });
        });
        const td = el('td', { class: 'sup-row-actions' });
        if (hasRole(ROLES.ADMIN)) {
            td.appendChild(el('button', {
                class: 'sup-icon-btn', title: 'Editar',
                html: '<i class="fa-solid fa-pen"></i>',
                onClick: () => _openSimpleEntityModal(state, cfg, row),
            }));
            td.appendChild(el('button', {
                class: 'sup-icon-btn', title: 'Eliminar',
                html: '<i class="fa-solid fa-trash"></i>',
                onClick: async () => {
                    if (!confirm(`Eliminar ${row.code || row.id}?`)) return;
                    try {
                        await cfg.remove(row.id);
                        showToast('Registro eliminado', 'success');
                        cfg.afterChange?.();
                        _renderSimpleEntity(state, cfg);
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                },
            }));
        }
        cells.push(td);
        return el('tr', {}, cells);
    });

    return el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [
            el('thead', {}, [trHead]),
            el('tbody', {}, trBody),
        ]),
    ]);
}

function _openSimpleEntityModal(state, cfg, row) {
    const isEdit = Boolean(row);
    const form = el('form', { class: 'sup-stack' });
    cfg.formFields.forEach(field => {
        if (field.type === 'checkbox') {
            const checked = row ? row[field.name] : field.defaultValue;
            form.appendChild(el('label', { class: 'sup-flex' }, [
                el('input', { type: 'checkbox', name: field.name, checked }),
                el('span', { text: field.label }),
            ]));
        } else {
            form.appendChild(_field(field.name, field.label, {
                value: row?.[field.name] ?? '',
                required: field.required,
                disabled: field.disabledOnEdit && isEdit,
                textarea: field.textarea,
            }));
        }
    });

    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: isEdit ? 'Guardar' : 'Crear',
        onClick: async () => {
            errEl.hidden = true;
            const fd = new FormData(form);
            const payload = {};
            cfg.formFields.forEach(f => {
                if (f.type === 'checkbox') {
                    payload[f.name] = form.querySelector(`[name="${f.name}"]`).checked;
                } else {
                    const v = fd.get(f.name);
                    if (!isEdit || !f.disabledOnEdit) {
                        payload[f.name] = v === '' ? null : v;
                    }
                }
            });
            try {
                if (isEdit) {
                    delete payload.code; // code immutable on edit by convention
                    await cfg.update(row.id, payload);
                    showToast('Actualizado', 'success');
                } else {
                    await cfg.create(payload);
                    showToast('Creado', 'success');
                }
                cfg.afterChange?.();
                closeModal();
                _renderSimpleEntity(state, cfg);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: isEdit ? `Editar` : cfg.newLabel,
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
    });
}

// --------------------------------------------------------------------- //
// PARAMETERS                                                             //
// --------------------------------------------------------------------- //
async function _renderParameters(state) {
    state.actions.innerHTML = '';
    if (hasRole(ROLES.ADMIN)) {
        state.actions.appendChild(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-plus"></i> Nuevo parámetro',
            onClick: () => _openParameterModal(state, null),
        }));
    }

    clear(state.host);
    state.host.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando parámetros…' }));
    try {
        const rows = await state.api.listParameters();
        clear(state.host);
        if (rows.length === 0) {
            state.host.appendChild(el('div', {
                class: 'sup-empty', text: 'Sin parámetros definidos.',
            }));
            return;
        }
        const thead = el('thead', {}, [el('tr', {}, [
            el('th', { text: 'Clave' }),
            el('th', { text: 'Valor' }),
            el('th', { text: 'Descripción' }),
            el('th', { text: 'Actualizado por' }),
            el('th', { text: 'Fecha' }),
            el('th', { text: '' }),
        ])]);
        const tbody = el('tbody', {}, rows.map(p => {
            const actionsTd = el('td', { class: 'sup-row-actions' });
            if (hasRole(ROLES.ADMIN)) {
                actionsTd.appendChild(el('button', {
                    class: 'sup-icon-btn', title: 'Editar',
                    html: '<i class="fa-solid fa-pen"></i>',
                    onClick: () => _openParameterModal(state, p),
                }));
            }
            return el('tr', {}, [
                el('td', { text: p.key }),
                el('td', { text: p.value }),
                el('td', { text: p.description || '—' }),
                el('td', { text: p.updated_by || '—' }),
                el('td', { text: formatDate(p.updated_at, true) }),
                actionsTd,
            ]);
        }));
        state.host.appendChild(el('div', { class: 'sup-table-wrap' }, [
            el('table', { class: 'sup-table' }, [thead, tbody]),
        ]));
    } catch (err) {
        clear(state.host);
        state.host.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _openParameterModal(state, param) {
    const isEdit = Boolean(param);
    const form = el('form', { class: 'sup-stack' }, [
        _field('key', 'Clave', { value: param?.key, required: true, disabled: isEdit }),
        _field('value', 'Valor', { value: param?.value, required: true }),
        _field('description', 'Descripción', { value: param?.description, textarea: true }),
    ]);
    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: 'Guardar',
        onClick: async () => {
            errEl.hidden = true;
            const fd = new FormData(form);
            try {
                await state.api.upsertParameter({
                    key: fd.get('key'),
                    value: fd.get('value'),
                    description: fd.get('description') || null,
                });
                showToast('Parámetro guardado', 'success');
                closeModal();
                _renderParameters(state);
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: isEdit ? `Editar parámetro: ${param.key}` : 'Nuevo parámetro',
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
    });
}

// --------------------------------------------------------------------- //
// Field & select helpers                                                 //
// --------------------------------------------------------------------- //
function _field(name, label, { value, required, type = 'text', step, textarea, disabled } = {}) {
    const wrap = el('label', { class: 'sup-field' }, [el('span', { text: label })]);
    const input = el(textarea ? 'textarea' : 'input', {
        name, value: value ?? '', required, type: textarea ? null : type, step,
        disabled: disabled || null,
    });
    if (textarea) input.textContent = value ?? '';
    wrap.appendChild(input);
    return wrap;
}

function _select(name, label, options, selectedId, labelFn) {
    const wrap = el('label', { class: 'sup-field' }, [el('span', { text: label })]);
    const select = el('select', { name, required: true });
    select.appendChild(el('option', { value: '', text: '— Seleccionar —' }));
    (options || []).forEach(opt => {
        const o = el('option', { value: opt.id, text: labelFn ? labelFn(opt) : opt.name });
        if (Number(selectedId) === Number(opt.id)) o.selected = true;
        select.appendChild(o);
    });
    wrap.appendChild(select);
    return wrap;
}
