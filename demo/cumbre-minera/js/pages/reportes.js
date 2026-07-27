/**
 * Reporte general de registrados + búsqueda por CI.
 * GET /v1/mining-summit/participants  (paginado, con filtros)
 * GET /v1/mining-summit/participants/{ci}  (búsqueda directa)
 */
import { Toast } from '../components/Toast.js';
import { printCredential } from '../components/Credential.js?v=20260722c';
import { loadAvailability, buildAxisOptions, renderAvailabilityHint } from '../components/AxisPicker.js';

// Roles de participante (value = código del backend, label = etiqueta en español).
const ROLES = [
    ['PARTICIPANTE', 'Participante'],
    ['MODERADOR', 'Moderador'],
    ['VEEDOR', 'Veedor'],
    ['INVITADO', 'Invitado'],
    ['ORGANIZADOR', 'Organizador'],
    ['PRENSA', 'Prensa'],
    ['FACILITADOR', 'Facilitador'],
    ['SISTEMATIZADOR', 'Sistematizador'],
    ['COMUNICACION', 'Comunicación'],
    ['SISTEMAS', 'Sistemas']
];
const ROLE_OPTIONS = [['', '— Sin rol (registrado sin aula) —'], ...ROLES]
    .map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
// Opciones para el filtro de rol del reporte (sin la opción "sin rol").
const ROLE_FILTER_OPTIONS = ROLES
    .map(([value, label]) => `<option value="${value}">${label}</option>`).join('');

export const ReportesPage = {
    render(container, { config, api, auth }) {
        const departamentos = (config.departments || []).map(
            d => `<option value="${d}">${d}</option>`
        ).join('');
        // Cancel/replace are limited to the registration desk (ADMIN/REGISTRATION).
        const role = auth && auth.getUserRole ? auth.getUserRole() : '';
        const canManage = role === 'ADMIN' || role === 'REGISTRATION';

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Participantes Registrados</h2>
                    <div class="subtitle">Búsqueda por nombre/CI y filtros por rol, institución, aula y departamento (en vivo).</div>
                </div>
                <button id="export-btn" class="btn btn-primary">
                    <i class="fa-solid fa-file-excel"></i> Descargar Excel
                </button>
            </div>

            <div class="card">
                <div class="table-toolbar">
                    <div class="form-field" style="flex:2; min-width:220px;">
                        <label for="q-search">Buscar (nombre completo o CI)</label>
                        <input id="q-search" type="text" placeholder="Filtra por nombre o CI…" autocomplete="off">
                    </div>
                    <div class="form-field">
                        <label for="filter-rol">Rol</label>
                        <select id="filter-rol"><option value="">— Todos —</option>${ROLE_FILTER_OPTIONS}</select>
                    </div>
                    <div class="form-field">
                        <label for="filter-institution">Institución</label>
                        <input id="filter-institution" type="text" placeholder="Institución…" autocomplete="off">
                    </div>
                    <div class="form-field">
                        <label for="filter-aula">Aula</label>
                        <input id="filter-aula" type="text" placeholder="Ej. A7" autocomplete="off">
                    </div>
                    <div class="form-field">
                        <label for="filter-department">Departamento</label>
                        <select id="filter-department"><option value="">— Todos —</option>${departamentos}</select>
                    </div>
                    <div class="form-field" style="align-self:flex-end;">
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
                                <label for="edit-role">Rol</label>
                                <select id="edit-role" name="role">
                                    ${ROLE_OPTIONS}
                                </select>
                                <div class="role-hint">Asigna un rol real (con un eje) para darle aula a un participante "Sin rol".</div>
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

            <div class="modal-overlay" id="replace-overlay">
                <div class="modal-box modal-form" role="dialog" aria-modal="true">
                    <button class="modal-close" id="replace-close" aria-label="Cerrar">&times;</button>
                    <h3><i class="fa-solid fa-people-arrows" style="color:var(--oro)"></i> Reemplazar participante</h3>
                    <div class="edit-subject" id="replace-subject"></div>
                    <p class="avail-hint" style="margin-bottom:1rem;">
                        El nuevo participante hereda el mismo eje, aula e institución.
                        El saliente queda como <strong>REPLACED</strong>.
                    </p>
                    <form id="replace-form">
                        <div class="form-grid">
                            <div class="form-field">
                                <label for="replace-ci">CI del sustituto <span class="req">*</span></label>
                                <input id="replace-ci" name="ci" type="text" required minlength="4" maxlength="20" inputmode="text" pattern="[A-Za-z0-9\-]+">
                            </div>
                            <div class="form-field">
                                <label for="replace-first">Nombre <span class="req">*</span></label>
                                <input id="replace-first" name="first_name" type="text" required maxlength="80">
                            </div>
                            <div class="form-field">
                                <label for="replace-last">Apellido <span class="req">*</span></label>
                                <input id="replace-last" name="last_name" type="text" required maxlength="80">
                            </div>
                            <div class="form-field">
                                <label for="replace-phone">Celular</label>
                                <input id="replace-phone" name="phone" type="tel" maxlength="30">
                            </div>
                            <div class="form-field">
                                <label for="replace-email">Correo</label>
                                <input id="replace-email" name="email" type="email" maxlength="120">
                            </div>
                            <div class="form-field form-field-wide">
                                <label for="replace-obs">Autorización / motivo</label>
                                <input id="replace-obs" name="observation" type="text" maxlength="300" placeholder="Ej. autorizado por la institución">
                            </div>
                        </div>
                        <div class="form-actions">
                            <button id="replace-save" class="btn btn-primary" type="submit">
                                <i class="fa-solid fa-people-arrows"></i> Reemplazar
                            </button>
                            <button id="replace-cancel" class="btn btn-ghost" type="button">Cancelar</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        const state = {
            pageIndex: 0,
            limit: config.ui.pageSize || 25,
            all: [],        // todos los participantes (se traen una vez, paginando el backend)
            filtered: []    // resultado tras aplicar filtros client-side
        };

        const tbody = container.querySelector('#participants-tbody');
        const pageInfo = container.querySelector('#page-info');
        const prevBtn = container.querySelector('#prev-btn');
        const nextBtn = container.querySelector('#next-btn');
        let displayedItems = [];

        const findRow = (ci) => displayedItems.find(item => item.ci === ci);

        // Row actions: reprint QR, edit, replace or decline.
        tbody.addEventListener('click', (event) => {
            const reprint = event.target.closest('button.reprint-btn');
            if (reprint) {
                const participant = findRow(reprint.dataset.ci);
                if (participant) printCredential(participant);
                return;
            }
            const edit = event.target.closest('button.edit-btn');
            if (edit) {
                const participant = findRow(edit.dataset.ci);
                if (participant) editModal.open(participant);
                return;
            }
            const replace = event.target.closest('button.replace-btn');
            if (replace) {
                const participant = findRow(replace.dataset.ci);
                if (participant) replaceModal.open(participant);
                return;
            }
            const decline = event.target.closest('button.decline-btn');
            if (decline) {
                const participant = findRow(decline.dataset.ci);
                if (participant) declineParticipant(participant, { config, api }, () => fetchAll());
            }
        });

        const editModal = createEditModal(container, { config, api }, () => fetchAll());
        const replaceModal = createReplaceModal(container, { config, api }, () => fetchAll());

        // Trae TODOS los participantes recorriendo las páginas del backend, una
        // sola vez; luego el filtrado y la paginación son client-side (instantáneos).
        async function fetchAll() {
            tbody.innerHTML = `<tr><td colspan="10"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            try {
                const all = [];
                let offset = null;
                for (let guard = 0; guard < 200; guard += 1) {
                    const params = { limit: 100 };
                    if (offset) params.last_evaluated_key = offset;
                    const data = await api.get(config.miningSummit.participantsPath, params);
                    all.push(...(data.items || []));
                    offset = data.last_evaluated_key || null;
                    if (!offset) break;
                }
                state.all = all;
                applyFilters();
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${error.message}</p></div></td></tr>`;
                Toast.danger(`No se pudo cargar: ${error.message}`);
            }
        }

        const norm = (s) => String(s == null ? '' : s).toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');

        function applyFilters() {
            const q = norm(container.querySelector('#q-search').value.trim());
            const rol = container.querySelector('#filter-rol').value;
            const inst = norm(container.querySelector('#filter-institution').value.trim());
            const aula = norm(container.querySelector('#filter-aula').value.trim());
            const dep = container.querySelector('#filter-department').value;
            state.filtered = state.all.filter((p) => {
                if (q && !norm(`${p.first_name || ''} ${p.last_name || ''} ${p.ci || ''}`).includes(q)) return false;
                if (rol && p.role !== rol) return false;
                if (inst && !norm(p.institution_name || p.institution_id || '').includes(inst)) return false;
                if (aula && !norm(p.mesa_code || '').includes(aula)) return false;
                if (dep && p.department !== dep) return false;
                return true;
            });
            state.pageIndex = 0;
            renderPage();
        }

        function renderPage() {
            const total = state.filtered.length;
            const pages = Math.max(1, Math.ceil(total / state.limit));
            if (state.pageIndex >= pages) state.pageIndex = pages - 1;
            const start = state.pageIndex * state.limit;
            displayedItems = state.filtered.slice(start, start + state.limit);
            renderRows(tbody, displayedItems, canManage);
            prevBtn.disabled = state.pageIndex === 0;
            nextBtn.disabled = state.pageIndex >= pages - 1;
            pageInfo.textContent = `Página ${state.pageIndex + 1} de ${pages} · ${total} resultados`;
        }

        ['#q-search', '#filter-institution', '#filter-aula'].forEach((sel) =>
            container.querySelector(sel).addEventListener('input', applyFilters));
        ['#filter-rol', '#filter-department'].forEach((sel) =>
            container.querySelector(sel).addEventListener('change', applyFilters));

        container.querySelector('#clear-btn').addEventListener('click', () => {
            ['#q-search', '#filter-institution', '#filter-aula'].forEach((sel) => {
                container.querySelector(sel).value = '';
            });
            container.querySelector('#filter-rol').value = '';
            container.querySelector('#filter-department').value = '';
            applyFilters();
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
                renderPage();
            }
        });
        nextBtn.addEventListener('click', () => {
            state.pageIndex += 1;
            renderPage();
        });

        fetchAll();
    }
};

function renderRows(tbody, items, canManage) {
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
                ${canManage && p.registered ? `
                <button class="btn btn-ghost btn-sm replace-btn" data-ci="${escapeHtml(p.ci)}" title="Reemplazar por otro participante">
                    <i class="fa-solid fa-people-arrows"></i> Reemplazar
                </button>
                <button class="btn btn-ghost btn-sm decline-btn" data-ci="${escapeHtml(p.ci)}" title="Declinar participación (CANCELLED)">
                    <i class="fa-solid fa-user-slash"></i> Declinar
                </button>` : ''}
                <button class="btn btn-ghost btn-sm reprint-btn" data-ci="${escapeHtml(p.ci)}" title="Descargar sticker (PNG)">
                    <i class="fa-solid fa-download"></i> Sticker
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
        form.querySelector('#edit-role').value = participant.role || '';
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
        const roleValue = form.querySelector('#edit-role').value;
        if (roleValue) payload.role = roleValue;
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

async function declineParticipant(participant, { config, api }, onDone) {
    const name = `${participant.first_name || ''} ${participant.last_name || ''}`.trim();
    const observation = window.prompt(
        `Declinar la participación de ${name} (CI ${participant.ci}).\n` +
        'Esto libera su aula y el cupo de su institución.\n\n' +
        'Motivo / autorización (opcional):', ''
    );
    if (observation === null) return; // operator cancelled the prompt
    try {
        await api.patch(
            `${config.miningSummit.participantsPath}/${encodeURIComponent(participant.ci)}/deactivate`,
            observation.trim() ? { observation: observation.trim() } : {}
        );
        Toast.success(`Participación declinada (CI ${participant.ci}). Cupo y aula liberados.`);
        onDone();
    } catch (error) {
        Toast.danger(`No se pudo declinar: ${error.message}`);
    }
}

function createReplaceModal(container, { config, api }, onSaved) {
    const overlay = container.querySelector('#replace-overlay');
    const form = container.querySelector('#replace-form');
    const subject = container.querySelector('#replace-subject');
    const saveBtn = container.querySelector('#replace-save');
    let outgoing = null;

    function close() {
        overlay.classList.remove('is-open');
        outgoing = null;
    }
    overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    container.querySelector('#replace-close').addEventListener('click', close);
    container.querySelector('#replace-cancel').addEventListener('click', close);

    function open(participant) {
        outgoing = participant;
        const seat = participant.mesa_code
            ? `${participant.axis_label || participant.axis || ''} · Aula ${participant.mesa_code}`
            : 'Sin aula fija';
        subject.innerHTML =
            `Sale: <strong>${escapeHtml(participant.first_name || '')} ${escapeHtml(participant.last_name || '')}</strong>
             · CI ${escapeHtml(participant.ci)} · ${escapeHtml(seat)}`;
        form.reset();
        overlay.classList.add('is-open');
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!outgoing) return;
        const payload = {
            ci: form.querySelector('#replace-ci').value.trim(),
            first_name: form.querySelector('#replace-first').value.trim(),
            last_name: form.querySelector('#replace-last').value.trim()
        };
        if (!payload.ci || !payload.first_name || !payload.last_name) {
            Toast.danger('CI, nombre y apellido del sustituto son obligatorios.');
            return;
        }
        const phone = form.querySelector('#replace-phone').value.trim();
        const email = form.querySelector('#replace-email').value.trim();
        const observation = form.querySelector('#replace-obs').value.trim();
        if (phone) payload.phone = phone;
        if (email) payload.email = email;
        if (observation) payload.observation = observation;

        const original = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Reemplazando...';
        try {
            const saved = await api.post(
                `${config.miningSummit.participantsPath}/${encodeURIComponent(outgoing.ci)}/replace`,
                payload
            );
            Toast.success(`Reemplazo hecho: ${saved.first_name} ${saved.last_name} (CI ${saved.ci}).`);
            close();
            onSaved();
        } catch (error) {
            Toast.danger(`No se pudo reemplazar: ${error.message}`);
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
