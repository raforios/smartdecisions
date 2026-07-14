/**
 * Administración de Aulas (solo ADMIN).
 * CRUD sobre /v1/mining-summit/mesas:
 *   GET (lista) · POST (crear) · PATCH /{code} (capacidad/eje) · DELETE /{code}
 * Las opciones de eje se obtienen de /v1/mining-summit/axes.
 */
import { Toast } from '../components/Toast.js';

export const AdminAulasPage = {
    async render(container, { config, api }) {
        const path = config.miningSummit.mesasPath;
        const axesPath = config.miningSummit.axesPath;

        let axes = [];
        try {
            const axesData = await api.get(axesPath);
            axes = axesData.items || [];
        } catch (error) {
            Toast.danger(`No se pudieron cargar los ejes: ${error.message}`);
        }
        const axisOptions = axes
            .map(axis => `<option value="${escapeHtml(axis.axis)}">${axis.number}. ${escapeHtml(axis.label)}</option>`)
            .join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Aulas</h2>
                    <div class="subtitle">Aulas asignadas al evento: capacidad y eje temático.</div>
                </div>
                <button id="new-btn" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Nueva aula</button>
            </div>

            <div class="card" id="form-card" hidden>
                <h3 id="form-title"><i class="fa-solid fa-chalkboard" style="color:var(--oro)"></i> Nueva aula</h3>
                <form id="aula-form">
                    <div class="form-grid">
                        <div class="form-field">
                            <label for="aula-code">Código <span class="req">*</span></label>
                            <input id="aula-code" type="text" required maxlength="20" placeholder="Ej. A18">
                        </div>
                        <div class="form-field">
                            <label for="aula-block">Bloque <span class="req">*</span></label>
                            <input id="aula-block" type="text" required maxlength="40">
                        </div>
                        <div class="form-field">
                            <label for="aula-location">Ubicación <span class="req">*</span></label>
                            <input id="aula-location" type="text" required maxlength="60" placeholder="Ej. Primer Piso">
                        </div>
                        <div class="form-field">
                            <label for="aula-capacity">Capacidad <span class="req">*</span></label>
                            <input id="aula-capacity" type="number" min="1" required>
                        </div>
                        <div class="form-field form-field-wide">
                            <label for="aula-axis">Eje temático <span class="req">*</span></label>
                            <select id="aula-axis" required>
                                <option value="">— Seleccionar —</option>
                                ${axisOptions}
                            </select>
                        </div>
                    </div>
                    <div class="form-actions">
                        <button id="save-btn" class="btn btn-primary" type="submit"><i class="fa-solid fa-floppy-disk"></i> Guardar</button>
                        <button id="cancel-btn" class="btn btn-ghost" type="button"><i class="fa-solid fa-xmark"></i> Cancelar</button>
                    </div>
                </form>
            </div>

            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr><th>Código</th><th>Bloque</th><th>Ubicación</th><th>Capacidad</th><th>Eje temático</th><th></th></tr>
                    </thead>
                    <tbody id="aula-tbody">
                        <tr><td colspan="6"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>
                    </tbody>
                </table>
            </div>
        `;

        const formCard = container.querySelector('#form-card');
        const form = container.querySelector('#aula-form');
        const formTitle = container.querySelector('#form-title');
        const tbody = container.querySelector('#aula-tbody');
        const fields = {
            code: container.querySelector('#aula-code'),
            block: container.querySelector('#aula-block'),
            location: container.querySelector('#aula-location'),
            capacity: container.querySelector('#aula-capacity'),
            axis: container.querySelector('#aula-axis')
        };
        let editingCode = null;
        let cache = [];

        function openForm(item) {
            editingCode = item ? item.code : null;
            fields.code.value = item ? item.code : '';
            fields.block.value = item ? (item.block || '') : '';
            fields.location.value = item ? (item.location || '') : '';
            fields.capacity.value = item ? item.capacity : '';
            fields.axis.value = item ? (item.axis || '') : '';
            // On edit only capacity and axis change; identity fields stay fixed.
            fields.code.readOnly = Boolean(item);
            fields.block.readOnly = Boolean(item);
            fields.location.readOnly = Boolean(item);
            formTitle.innerHTML = item
                ? '<i class="fa-solid fa-pen" style="color:var(--oro)"></i> Editar aula'
                : '<i class="fa-solid fa-chalkboard" style="color:var(--oro)"></i> Nueva aula';
            formCard.hidden = false;
            formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        function closeForm() {
            form.reset();
            editingCode = null;
            formCard.hidden = true;
        }

        async function load() {
            tbody.innerHTML = `<tr><td colspan="6"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            try {
                const data = await api.get(path);
                cache = data.items || [];
                renderRows(tbody, cache);
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>${escapeHtml(error.message)}</p></div></td></tr>`;
            }
        }

        container.querySelector('#new-btn').addEventListener('click', () => openForm(null));
        container.querySelector('#cancel-btn').addEventListener('click', closeForm);

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const capacity = Number(fields.capacity.value);
            const axis = fields.axis.value;
            if (Number.isNaN(capacity) || capacity < 1 || !axis) {
                Toast.danger('Capacidad (≥1) y eje son obligatorios.');
                return;
            }
            try {
                if (editingCode) {
                    await api.patch(`${path}/${encodeURIComponent(editingCode)}`, { capacity, axis });
                    Toast.success('Aula actualizada.');
                } else {
                    await api.post(path, {
                        code: fields.code.value.trim(),
                        block: fields.block.value.trim(),
                        location: fields.location.value.trim(),
                        capacity,
                        axis
                    });
                    Toast.success('Aula creada.');
                }
                closeForm();
                load();
            } catch (error) {
                Toast.danger(`No se pudo guardar: ${error.message}`);
            }
        });

        tbody.addEventListener('click', async (event) => {
            const button = event.target.closest('button[data-action]');
            if (!button) return;
            const item = cache.find(aula => aula.code === button.dataset.code);
            if (!item) return;
            if (button.dataset.action === 'edit') {
                openForm(item);
            } else if (button.dataset.action === 'delete') {
                if (!window.confirm(`¿Eliminar el aula "${item.code}"?`)) return;
                try {
                    await api.del(`${path}/${encodeURIComponent(item.code)}`);
                    Toast.success('Aula eliminada.');
                    load();
                } catch (error) {
                    Toast.danger(`No se pudo eliminar: ${error.message}`);
                }
            }
        });

        load();
    }
};

function renderRows(tbody, items) {
    if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="fa-solid fa-folder-open"></i><p>Sin aulas.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(aula => `
        <tr>
            <td><strong>${escapeHtml(aula.code)}</strong></td>
            <td>${escapeHtml(aula.block || '—')}</td>
            <td>${escapeHtml(aula.location || '—')}</td>
            <td>${aula.capacity}</td>
            <td><small>${escapeHtml(aula.axis_label || aula.axis || '—')}</small></td>
            <td class="row-actions">
                <button class="btn btn-ghost btn-sm" data-action="edit" data-code="${escapeHtml(aula.code)}" title="Editar"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-ghost btn-sm" data-action="delete" data-code="${escapeHtml(aula.code)}" title="Eliminar"><i class="fa-solid fa-trash"></i></button>
            </td>
        </tr>
    `).join('');
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
