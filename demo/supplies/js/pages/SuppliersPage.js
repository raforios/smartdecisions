/**
 * Suppliers page (Proveedores).
 *
 * CRUD over the vendors a Nota de Ingreso can be issued against. Every field
 * except the email is mandatory, mirroring the backend schema.
 *
 * Removal is deliberately two-sided: a vendor that already issued notes can
 * only be deactivated (the backend rejects the delete), so the table offers
 * "Desactivar" for those and a real delete for the ones never used.
 */
import { hasRole, ROLES } from '../auth.js';
import {
    clear,
    closeModal,
    collapsible,
    el,
    openModal,
    pager,
    showToast,
} from '../ui.js';

export async function mountSuppliers({ host, actions, api }) {
    clear(host);
    actions.innerHTML = '';

    const state = { api, host, actions };

    if (hasRole(ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER)) {
        actions.appendChild(el('button', {
            class: 'sup-btn sup-btn-primary',
            html: '<i class="fa-solid fa-plus"></i> Nuevo proveedor',
            onClick: () => _openModal(state),
        }));
    }

    const searchIn = el('input', { type: 'search', placeholder: 'Nombre, NIT o contacto…' });
    const activeSel = el('select', {}, [
        el('option', { value: '', text: 'Todos' }),
        el('option', { value: '1', text: 'Solo activos' }),
    ]);
    const listHost = el('div', {});

    const reload = () => _load(state, { searchIn, activeSel, listHost });
    let searchTimer = null;
    searchIn.oninput = () => {
        // Debounced so typing a name does not fire one request per keystroke.
        clearTimeout(searchTimer);
        searchTimer = setTimeout(reload, 300);
    };
    activeSel.onchange = reload;

    host.appendChild(el('div', { class: 'sup-filters' }, [
        el('label', { class: 'sup-field' }, [el('span', { text: 'Buscar' }), searchIn]),
        el('label', { class: 'sup-field' }, [el('span', { text: 'Estado' }), activeSel]),
    ]));
    host.appendChild(listHost);
    state.reload = reload;
    await reload();
}

async function _load(state, { searchIn, activeSel, listHost }) {
    clear(listHost);
    listHost.appendChild(el('p', { class: 'sup-placeholder', text: 'Cargando proveedores…' }));
    try {
        const params = { limit: 500 };
        if (searchIn.value.trim()) params.search = searchIn.value.trim();
        if (activeSel.value) params.only_active = true;
        const rows = await state.api.listSuppliers(params);
        clear(listHost);
        if (rows.length === 0) {
            listHost.appendChild(el('div', {
                class: 'sup-empty',
                text: params.search
                    ? 'Ningún proveedor coincide con la búsqueda.'
                    : 'Aún no hay proveedores registrados.',
            }));
            return;
        }
        const box = collapsible({
            title: 'Proveedores',
            subtitle: `${rows.length} proveedor(es)`,
            stateKey: 'suppliers.list',
        });
        const tableHost = el('div', {});
        const pagination = pager({
            pageSize: 10,
            render: page => {
                clear(tableHost);
                tableHost.appendChild(_table(page, state));
            },
        });
        box.body.appendChild(tableHost);
        box.body.appendChild(pagination.el);
        pagination.setRows(rows);
        listHost.appendChild(box.section);
    } catch (err) {
        clear(listHost);
        listHost.appendChild(el('p', { class: 'sup-form-error', text: err.message }));
    }
}

function _table(rows, state) {
    const thead = el('thead', {}, [el('tr', {}, [
        el('th', { text: 'Proveedor' }),
        el('th', { text: 'NIT' }),
        el('th', { text: 'Contacto' }),
        el('th', { text: 'Teléfono' }),
        el('th', { text: 'Correo' }),
        el('th', { text: 'Dirección' }),
        el('th', { text: 'Estado' }),
        el('th', { text: '' }),
    ])]);
    const tbody = el('tbody', {}, rows.map(row => {
        const actionsTd = el('td', { class: 'sup-row-actions' });
        if (hasRole(ROLES.ADMIN, ROLES.WAREHOUSE_MANAGER)) {
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn', title: 'Editar',
                dataset: { tip: 'Editar' },
                html: '<i class="fa-solid fa-pen"></i>',
                onClick: () => _openModal(state, row),
            }));
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn',
                title: row.is_active ? 'Desactivar' : 'Reactivar',
                dataset: { tip: row.is_active ? 'Desactivar' : 'Reactivar' },
                html: row.is_active
                    ? '<i class="fa-solid fa-ban"></i>'
                    : '<i class="fa-solid fa-rotate-left"></i>',
                onClick: () => _toggleActive(state, row),
            }));
        }
        if (hasRole(ROLES.ADMIN)) {
            actionsTd.appendChild(el('button', {
                class: 'sup-icon-btn', title: 'Eliminar',
                dataset: { tip: 'Eliminar' },
                html: '<i class="fa-solid fa-trash"></i>',
                onClick: () => _confirmDelete(state, row),
            }));
        }
        return el('tr', {}, [
            el('td', { text: row.name }),
            el('td', { text: row.nit }),
            el('td', { text: row.contact_person }),
            el('td', { text: row.phone }),
            el('td', { text: row.email || '—' }),
            el('td', { text: row.address }),
            el('td', {}, [el('span', {
                class: `sup-badge ${row.is_active ? 'sup-badge-delivered' : 'sup-badge-closed'}`,
                text: row.is_active ? 'Activo' : 'Inactivo',
            })]),
            actionsTd,
        ]);
    }));
    return el('div', { class: 'sup-table-wrap' }, [
        el('table', { class: 'sup-table' }, [thead, tbody]),
    ]);
}

function _openModal(state, supplier) {
    const isEdit = Boolean(supplier);
    const form = el('form', { class: 'sup-stack', id: 'supplier-form' }, [
        el('div', { class: 'sup-field-row' }, [
            _field('name', 'Nombre del proveedor', { value: supplier?.name, required: true }),
            _field('nit', 'NIT', { value: supplier?.nit, required: true }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('contact_person', 'Persona de contacto', {
                value: supplier?.contact_person, required: true,
            }),
            _field('phone', 'Teléfono / Celular', { value: supplier?.phone, required: true }),
        ]),
        el('div', { class: 'sup-field-row' }, [
            _field('address', 'Dirección', { value: supplier?.address, required: true }),
            _field('email', 'Correo electrónico (opcional)', {
                value: supplier?.email, type: 'email',
            }),
        ]),
    ]);
    const errEl = el('p', { class: 'sup-form-error', hidden: true });
    form.appendChild(errEl);

    const submitBtn = el('button', {
        class: 'sup-btn sup-btn-primary', text: isEdit ? 'Guardar cambios' : 'Crear',
        onClick: async () => {
            errEl.hidden = true;
            if (!form.reportValidity()) return;
            const fd = new FormData(form);
            const payload = {
                name: fd.get('name').trim(),
                nit: fd.get('nit').trim(),
                contact_person: fd.get('contact_person').trim(),
                address: fd.get('address').trim(),
                phone: fd.get('phone').trim(),
                email: fd.get('email').trim() || null,
            };
            try {
                if (isEdit) {
                    await state.api.updateSupplier(supplier.id, payload);
                    showToast('Proveedor actualizado', 'success');
                } else {
                    await state.api.createSupplier(payload);
                    showToast('Proveedor creado', 'success');
                }
                closeModal();
                await state.reload();
            } catch (err) {
                errEl.textContent = err.message;
                errEl.hidden = false;
            }
        },
    });

    openModal({
        title: isEdit ? `Editar proveedor: ${supplier.name}` : 'Nuevo proveedor',
        body: form,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            submitBtn,
        ],
        wide: true,
    });
}

async function _toggleActive(state, supplier) {
    try {
        await state.api.updateSupplier(supplier.id, { is_active: !supplier.is_active });
        showToast(supplier.is_active ? 'Proveedor desactivado' : 'Proveedor reactivado', 'success');
        await state.reload();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function _confirmDelete(state, supplier) {
    const body = el('div', { class: 'sup-stack' }, [
        el('p', { text: `¿Eliminar al proveedor "${supplier.name}"?` }),
        el('p', {
            class: 'sup-muted',
            text: 'Solo se puede eliminar un proveedor que nunca emitió una '
                + 'Nota de Ingreso. Si ya tiene documentos, desactívalo.',
        }),
    ]);
    openModal({
        title: 'Eliminar proveedor',
        body,
        footer: [
            el('button', { class: 'sup-btn sup-btn-ghost', text: 'Cancelar', onClick: closeModal }),
            el('button', {
                class: 'sup-btn sup-btn-danger', text: 'Eliminar',
                onClick: async () => {
                    try {
                        await state.api.deleteSupplier(supplier.id);
                        showToast('Proveedor eliminado', 'success');
                        closeModal();
                        await state.reload();
                    } catch (err) {
                        showToast(err.message, 'error');
                    }
                },
            }),
        ],
    });
}

function _field(name, label, { value, required, type = 'text' } = {}) {
    const wrap = el('label', { class: 'sup-field' }, [el('span', { text: label })]);
    wrap.appendChild(el('input', { name, value: value ?? '', required, type }));
    return wrap;
}
