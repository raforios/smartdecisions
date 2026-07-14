/**
 * Reporte general de registrados + búsqueda por CI.
 * GET /v1/mining-summit/participants  (paginado, con filtros)
 * GET /v1/mining-summit/participants/{ci}  (búsqueda directa)
 */
import { Toast } from '../components/Toast.js';
import { printCredential } from '../components/Credential.js';

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
                        <label for="filter-company">Empresa</label>
                        <input id="filter-company" type="text" placeholder="Nombre de empresa">
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

        // Reprint the QR credential of the row's participant.
        tbody.addEventListener('click', (event) => {
            const button = event.target.closest('button.reprint-btn');
            if (!button) return;
            const participant = displayedItems.find(item => item.ci === button.dataset.ci);
            if (participant) printCredential(participant);
        });

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
                company:         container.querySelector('#filter-company').value.trim() || undefined,
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
            container.querySelector('#filter-company').value = '';
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
            <td>${escapeHtml(p.institution_name || p.company || '—')}</td>
            <td>${escapeHtml(p.role || '—')}</td>
            <td>${renderAula(p)}</td>
            <td>${escapeHtml(p.department || '—')}</td>
            <td>${escapeHtml(p.email || '—')}</td>
            <td>${escapeHtml(p.phone || '—')}</td>
            <td>${escapeHtml(p.registered_date || '—')}</td>
            <td class="row-actions">
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

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
