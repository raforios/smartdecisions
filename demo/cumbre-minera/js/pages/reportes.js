/**
 * Reporte general de registrados + búsqueda por CI.
 * GET /v1/mining-summit/participants  (paginado, con filtros)
 * GET /v1/mining-summit/participants/{ci}  (búsqueda directa)
 */
import { Toast } from '../components/Toast.js';
import { printCredential } from '../components/Credential.js';
import { loadAvailability, buildAxisOptions, renderAvailabilityHint } from '../components/AxisPicker.js';

export const ReportesPage = {
    render(container, { config, api }) {
        const departamentos = (config.departments || []).map(
            d => `<option value="${d}">${d}</option>`
        ).join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Participantes Registrados</h2>
                    <div class="subtitle">Lista paginada con filtros y búsqueda directa por CI.</div>
                </div>
                <button id="export-btn" class="btn btn-primary">
                    <i class="fa-solid fa-file-excel"></i> Descargar Excel
                </button>
            </div>

            <div class="card">
                <div class="table-toolbar">
                    <div class="form-field" style="flex: 1; min-width: 200px;">
                        <label for="ci-search">Búsqueda por CI</label>
                        <input id="ci-search" type="text" inputmode="numeric" pattern="[0-9]+" placeholder="Buscar CI exacto…">
                    </div>
                    <div class="form-field">
                        <label for="filter-department">Departamento</label>
                        <select id="filter-department">
                            <option value="">— Todos —</option>
                            ${departamentos}
                        </select>
                    </div>
                    <div class="form-field">
                        <label for="filter-from">Registrados desde</label>
                        <input id="filter-from" type="date">
                    </div>
                    <div class="form-field">
                        <label for="filter-to">Hasta</label>
                        <input id="filter-to" type="date">
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button id="apply-btn" class="btn btn-primary"><i class="fa-solid fa-filter"></i> Aplicar</button>
                        <button id="clear-btn" class="btn btn-ghost"><i class="fa-solid fa-xmark"></i> Limpiar</button>
                    </div>
                </div>
            </div>

            <div class="table-wrapper">
                <table class="data-table" id="participants-table">
                    <thead>
                        <tr>
                            <th>CI</th>
                            <th>Nombre completo</th>
                            <th>Institución</th>
                            <th>Rol</th>
                            <th>Aula</th>
                            <th>Departamento</th>
                            <th>Email</th>
                            <th>Celular</th>
                            <th>Registrado</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody id="participants-tbody">
                        <tr><td colspan="10"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>
                    </tbody>
                </table>
                <div class="pagination">
                    <span id="page-info">—</span>
                    <button id="prev-btn" disabled><i class="fa-solid fa-chevron-left"></i> Anterior</button>
                    <button id="next-btn" disabled>Siguiente <i class="fa-solid fa-chevron-right"></i></button>
                </div>
            </div>

            <div class="modal-overlay" id="edit-overlay">
                <div class="modal-box modal-form" role="dialog" aria-modal="true">
                    <button class="modal-close" id="edit-close" aria-label="Cerrar">&times;</button>
                    <h3><i class="fa-solid fa-user-pen" style="color:var(--oro)"></i> Editar participante</h3>
                    <div class="edit-subject" id="edit-subject"></div>
                    <form id="edit-form">
                        <div class="form-grid">
                            <div class="form-field">
                                <label for="edit-first">Nombre</label>
                                <input id="edit-first" name="first_name" type="text" maxlength="80">
                            </div>
                            <div class="form-field">
                                <label for="edit-last">Apellido</label>
                                <input id="edit-last" name="last_name" type="text" maxlength="80">
                            </div>
                            <div class="form-field">
                                <label for="edit-department">Departamento</label>
                                <select id="edit-department" name="department">
                                    <option value="">— Seleccionar —</option>
                                    ${departamentos}
                                </select>
                            </div>
                            <div class="form-field">
                                <label for="edit-phone">Celular</label>
                                <input id="edit-phone" name="phone" type="tel" maxlength="30">
                            </div>
                            <div class="form-field form-field-wide">
                                <label for="edit-institution">Institución / Organización</label>
                                <select id="edit-institution" name="institution_id">
                                    <option value="">— Cargando… —</option>
                                </select>
                            </div>
                            <div class="form-field form-field-wide">
                                <label for="edit-axis">Eje temático</label>
                                <select id="edit-axis" name="axis">
                                    <option value="">— Cargando disponibilidad… —</option>
                                </select>
                                <div id="edit-availability"></div>
                            </div>
                        </div>
                        <div class="form-actions">
                            <button id="edit-save" class="btn btn-primary" type="submit">
                                <i class="fa-solid fa-floppy-disk"></i> Guardar
                            </button>
                            <button id="edit-cancel" class="btn btn-ghost" type="button">Cancelar</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        const state = {
            keys: [null],
            pageIndex: 0,
            limit: config.ui.pageSize || 25,
            filters: {}
        };

        const tbody = container.querySelector('#participants-tbody');
        const pageInfo = container.querySelector('#page-info');
        const prevBtn = container.querySelector('#prev-btn');
        const nextBtn = container.querySelector('#next-btn');
        let displayedItems = [];

        // Row actions: reprint the QR credential or open the edit modal.
        tbody.addEventListener('click', (event) => {
            const reprint = event.target.closest('button.reprint-btn');
            if (reprint) {
                const participant = displayedItems.find(item => item.ci === reprint.dataset.ci);
                if (participant) printCredential(participant);
                return;
            }
            const edit = event.target.closest('button.edit-btn');
            if (edit) {
                const participant = displayedItems.find(item => item.ci === edit.dataset.ci);
                if (participant) editModal.open(participant);
            }
        });

        const editModal = createEditModal(container, { config, api }, () => loadPage());

        async function loadPage() {
            tbody.innerHTML = `<tr><td colspan="10"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            const queryParams = {
                limit: state.limit,
                ...state.filters
            };
            const lastKey = state.keys[state.pageIndex];
            if (lastKey) queryParams.last_evaluated_key = lastKey;
            try {
                const data = await api.get(config.miningSummit.participantsPath, queryParams);
                displayedItems = data.items || [];
                renderRows(tbody, displayedItems);
                const nextKey = data.last_evaluated_key || null;
                if (nextKey && state.keys[state.pageIndex + 1] !== nextKey) {
                    state.keys[state.pageIndex + 1] = nextKey;
                }
                prevBtn.disabled = state.pageIndex === 0;
                nextBtn.disabled = !nextKey;
                pageInfo.textContent = `Página ${state.pageIndex + 1} · ${data.items.length} resultados`;
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${error.message}</p></div></td></tr>`;
                Toast.danger(`No se pudo cargar: ${error.message}`);
            }
        }

        container.querySelector('#apply-btn').addEventListener('click', () => {
            const ciSearch = container.querySelector('#ci-search').value.trim();
            if (ciSearch) {
                searchByCi(ciSearch);
                return;
            }
            state.filters = {
                department:      container.querySelector('#filter-department').value || undefined,
                registered_from: container.querySelector('#filter-from').value || undefined,
                registered_to:   container.querySelector('#filter-to').value || undefined
            };
            state.keys = [null];
            state.pageIndex = 0;
            loadPage();
        });

        container.querySelector('#clear-btn').addEventListener('click', () => {
            container.querySelector('#ci-search').value = '';
            container.querySelector('#filter-department').value = '';
            container.querySelector('#filter-from').value = '';
            container.querySelector('#filter-to').value = '';
            state.filters = {};
            state.keys = [null];
            state.pageIndex = 0;
            loadPage();
        });

        const exportBtn = container.querySelector('#export-btn');
        exportBtn.addEventListener('click', async () => {
            const original = exportBtn.innerHTML;
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generando...';
            try {
                await api.download(config.miningSummit.participantsExportPath, 'participantes.xlsx');
                Toast.success('Reporte de participantes descargado.');
            } catch (error) {
                Toast.danger(`No se pudo exportar: ${error.message}`);
            } finally {
                exportBtn.disabled = false;
                exportBtn.innerHTML = original;
            }
        });

        prevBtn.addEventListener('click', () => {
            if (state.pageIndex > 0) {
                state.pageIndex -= 1;
                loadPage();
            }
        });
        nextBtn.addEventListener('click', () => {
            if (state.keys[state.pageIndex + 1]) {
                state.pageIndex += 1;
                loadPage();
            }
        });

        async function searchByCi(ci) {
            tbody.innerHTML = `<tr><td colspan="10"><div class="loading"><div class="spinner"></div> Buscando...</div></td></tr>`;
            try {
                const item = await api.get(`${config.miningSummit.participantsPath}/${encodeURIComponent(ci)}`);
                displayedItems = item ? [item] : [];
                renderRows(tbody, displayedItems);
                pageInfo.textContent = item ? '1 resultado' : '0 resultados';
                prevBtn.disabled = true;
                nextBtn.disabled = true;
            } catch (error) {
                if (error.status === 404) {
                    renderRows(tbody, []);
                    pageInfo.textContent = '0 resultados';
                    Toast.info(`No se encontró participante con CI ${ci}.`);
                } else {
                    Toast.danger(`Error en búsqueda: ${error.message}`);
                }
            }
        }

        loadPage();
    }
};

function renderRows(tbody, items) {
    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state">
            <i class="fa-solid fa-folder-open"></i>
            <p>Sin resultados.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(p => `
        <tr>
            <td><strong>${escapeHtml(p.ci)}</strong></td>
            <td>${escapeHtml(p.first_name || '')} ${escapeHtml(p.last_name || '')}</td>
            <td>${escapeHtml(p.institution_name || '—')}</td>
            <td>${escapeHtml(p.role || '—')}</td>
            <td>${renderAula(p)}</td>
            <td>${escapeHtml(p.department || '—')}</td>
            <td>${escapeHtml(p.email || '—')}</td>
            <td>${escapeHtml(p.phone || '—')}</td>
            <td>${escapeHtml((p.registered_at || '').slice(0, 10) || '—')}</td>
            <td class="row-actions">
                <button class="btn btn-ghost btn-sm edit-btn" data-ci="${escapeHtml(p.ci)}" title="Editar / acreditar">
                    <i class="fa-solid fa-pen"></i> Editar
                </button>
                <button class="btn btn-ghost btn-sm reprint-btn" data-ci="${escapeHtml(p.ci)}" title="Reimprimir QR">
                    <i class="fa-solid fa-qrcode"></i> QR
                </button>
            </td>
        </tr>
    `).join('');
}

function renderAula(p) {
    if (!p.mesa_code) {
        return p.assignment_type === 'ROTATIVO' ? 'Rotativa' : '—';
    }
    const eje = p.axis_label
        ? `<br><small style="color:var(--text-muted)">${escapeHtml(p.axis_label)}</small>`
        : '';
    return `<strong>${escapeHtml(p.mesa_code)}</strong>${eje}`;
}

function createEditModal(container, { config, api }, onSaved) {
    const overlay = container.querySelector('#edit-overlay');
    const form = container.querySelector('#edit-form');
    const subject = container.querySelector('#edit-subject');
    const institutionSelect = container.querySelector('#edit-institution');
    const axisSelect = container.querySelector('#edit-axis');
    const axisHint = container.querySelector('#edit-availability');
    const saveBtn = container.querySelector('#edit-save');
    let current = null;
    let institutionsLoaded = false;

    function close() {
        overlay.classList.remove('is-open');
        current = null;
    }
    overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    container.querySelector('#edit-close').addEventListener('click', close);
    container.querySelector('#edit-cancel').addEventListener('click', close);

    async function ensureInstitutions() {
        if (institutionsLoaded) return;
        try {
            const response = await api.get(config.miningSummit.institutionsPath);
            institutionSelect.innerHTML = buildInstitutionOptions((response && response.items) || []);
            institutionsLoaded = true;
        } catch (error) {
            institutionSelect.innerHTML = '<option value="">— No se pudo cargar —</option>';
            Toast.danger(`Instituciones: ${error.message}`);
        }
    }

    async function refreshAvailability(selected, failedAxis) {
        const availability = await loadAvailability(api, config);
        axisSelect.innerHTML = buildAxisOptions(availability, selected);
        renderAvailabilityHint(axisHint, availability, failedAxis);
        return availability;
    }

    async function open(participant) {
        current = participant;
        subject.innerHTML =
            `<strong>${escapeHtml(participant.first_name || '')} ${escapeHtml(participant.last_name || '')}</strong>
             · CI ${escapeHtml(participant.ci)}`;
        form.querySelector('#edit-first').value = participant.first_name || '';
        form.querySelector('#edit-last').value = participant.last_name || '';
        form.querySelector('#edit-department').value = participant.department || '';
        form.querySelector('#edit-phone').value = participant.phone || '';
        overlay.classList.add('is-open');
        await ensureInstitutions();
        institutionSelect.value = participant.institution_id || '';
        await refreshAvailability(participant.axis || '');
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!current) return;
        const payload = {};
        const first = form.querySelector('#edit-first').value.trim();
        const last = form.querySelector('#edit-last').value.trim();
        if (first) payload.first_name = first;
        if (last) payload.last_name = last;
        const department = form.querySelector('#edit-department').value;
        if (department) payload.department = department;
        const phone = form.querySelector('#edit-phone').value.trim();
        if (phone) payload.phone = phone;
        if (institutionSelect.value) payload.institution_id = institutionSelect.value;
        if (axisSelect.value) payload.axis = axisSelect.value;

        const original = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Guardando...';
        try {
            const updated = await api.patch(
                `${config.miningSummit.participantsPath}/${encodeURIComponent(current.ci)}`,
                payload
            );
            Toast.success(`Participante actualizado (CI ${updated.ci}).`);
            close();
            onSaved();
        } catch (error) {
            Toast.danger(`No se pudo guardar: ${error.message}`);
            // The chosen axis may be full: refresh and show the ejes with room.
            await refreshAvailability(axisSelect.value, payload.axis);
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = original;
        }
    });

    return { open };
}

function buildInstitutionOptions(items) {
    const groups = new Map();
    items.forEach(item => {
        if (!groups.has(item.category)) groups.set(item.category, []);
        groups.get(item.category).push(item);
    });
    let html = '<option value="">— Sin institución —</option>';
    for (const [category, list] of groups) {
        const options = list.map(
            item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`
        ).join('');
        html += `<optgroup label="${escapeHtml(category)}">${options}</optgroup>`;
    }
    return html;
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
