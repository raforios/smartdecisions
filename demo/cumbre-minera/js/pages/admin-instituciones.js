/**
 * Administración de Instituciones (solo ADMIN).
 * CRUD sobre /v1/mining-summit/institutions:
 *   GET (lista) · POST (crear) · PATCH /{id} (editar) · DELETE /{id}
 */
import { Toast } from '../components/Toast.js';

export const AdminInstitucionesPage = {
    async render(container, { config, api }) {
        const path = config.miningSummit.institutionsPath;
        const categoryOptions = (config.institutionCategories || [])
            .map(cat => `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`)
            .join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Instituciones</h2>
                    <div class="subtitle">Alta, edición y cupo de las instituciones participantes.</div>
                </div>
                <button id="new-btn" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Nueva institución</button>
            </div>

            <div class="card" id="form-card" hidden>
                <h3 id="form-title"><i class="fa-solid fa-building" style="color:var(--oro)"></i> Nueva institución</h3>
                <form id="inst-form">
                    <input type="hidden" id="inst-id">
                    <div class="form-grid">
                        <div class="form-field form-field-wide">
                            <label for="inst-name">Nombre <span class="req">*</span></label>
                            <input id="inst-name" type="text" required minlength="2" maxlength="160">
                        </div>
                        <div class="form-field">
                            <label for="inst-abbr">Sigla</label>
                            <input id="inst-abbr" type="text" maxlength="40">
                        </div>
                        <div class="form-field form-field-wide">
                            <label for="inst-category">Categoría <span class="req">*</span></label>
                            <select id="inst-category" required>
                                <option value="">— Seleccionar —</option>
                                ${categoryOptions}
                            </select>
                        </div>
                        <div class="form-field">
                            <label for="inst-cupos">Cupo <span class="req">*</span></label>
                            <input id="inst-cupos" type="number" min="0" required>
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
                        <tr><th>Nombre</th><th>Sigla</th><th>Categoría</th><th>Cupo</th><th></th></tr>
                    </thead>
                    <tbody id="inst-tbody">
                        <tr><td colspan="5"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>
                    </tbody>
                </table>
            </div>
        `;

        const formCard = container.querySelector('#form-card');
        const form = container.querySelector('#inst-form');
        const formTitle = container.querySelector('#form-title');
        const tbody = container.querySelector('#inst-tbody');
        const fields = {
            id: container.querySelector('#inst-id'),
            name: container.querySelector('#inst-name'),
            abbr: container.querySelector('#inst-abbr'),
            category: container.querySelector('#inst-category'),
            cupos: container.querySelector('#inst-cupos')
        };
        let cache = [];

        function openForm(item) {
            fields.id.value = item ? item.id : '';
            fields.name.value = item ? (item.name || '') : '';
            fields.abbr.value = item ? (item.abbreviation || '') : '';
            fields.category.value = item ? (item.category || '') : '';
            fields.cupos.value = item ? item.cupos : '';
            formTitle.innerHTML = item
                ? '<i class="fa-solid fa-pen" style="color:var(--oro)"></i> Editar institución'
                : '<i class="fa-solid fa-building" style="color:var(--oro)"></i> Nueva institución';
            formCard.hidden = false;
            formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        function closeForm() {
            form.reset();
            fields.id.value = '';
            formCard.hidden = true;
        }

        async function load() {
            tbody.innerHTML = `<tr><td colspan="5"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            try {
                const data = await api.get(path);
                cache = data.items || [];
                renderRows(tbody, cache);
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><p>${escapeHtml(error.message)}</p></div></td></tr>`;
            }
        }

        container.querySelector('#new-btn').addEventListener('click', () => openForm(null));
        container.querySelector('#cancel-btn').addEventListener('click', closeForm);

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const id = fields.id.value;
            const body = {
                name: fields.name.value.trim(),
                abbreviation: fields.abbr.value.trim() || undefined,
                category: fields.category.value,
                cupos: Number(fields.cupos.value)
            };
            if (!body.name || !body.category || Number.isNaN(body.cupos)) {
                Toast.danger('Nombre, categoría y cupo son obligatorios.');
                return;
            }
            try {
                if (id) {
                    await api.patch(`${path}/${encodeURIComponent(id)}`, body);
                    Toast.success('Institución actualizada.');
                } else {
                    await api.post(path, body);
                    Toast.success('Institución creada.');
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
            const item = cache.find(inst => inst.id === button.dataset.id);
            if (!item) return;
            if (button.dataset.action === 'edit') {
                openForm(item);
            } else if (button.dataset.action === 'delete') {
                if (!window.confirm(`¿Eliminar la institución "${item.name}"?`)) return;
                try {
                    await api.del(`${path}/${encodeURIComponent(item.id)}`);
                    Toast.success('Institución eliminada.');
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
        tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><i class="fa-solid fa-folder-open"></i><p>Sin instituciones.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(inst => `
        <tr>
            <td><strong>${escapeHtml(inst.name)}</strong></td>
            <td>${escapeHtml(inst.abbreviation || '—')}</td>
            <td><small>${escapeHtml(inst.category)}</small></td>
            <td>${inst.cupos}</td>
            <td class="row-actions">
                <button class="btn btn-ghost btn-sm" data-action="edit" data-id="${escapeHtml(inst.id)}" title="Editar"><i class="fa-solid fa-pen"></i></button>
                <button class="btn btn-ghost btn-sm" data-action="delete" data-id="${escapeHtml(inst.id)}" title="Eliminar"><i class="fa-solid fa-trash"></i></button>
            </td>
        </tr>
    `).join('');
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
