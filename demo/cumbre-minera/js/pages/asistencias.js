/**
 * Reporte de asistencias por CI y/o rango de fechas.
 * GET /v1/mining-summit/attendances  (filtros opcionales: ci, date_from, date_to)
 */
import { Toast } from '../components/Toast.js';

export const AsistenciasPage = {
    render(container, { config, api }) {
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Reporte de Asistencias</h2>
                    <div class="subtitle">Filtra por CI y/o rango de fechas. Usa los filtros para acotar la consulta.</div>
                </div>
            </div>

            <div class="card">
                <div class="table-toolbar">
                    <div class="form-field" style="flex: 1; min-width: 200px;">
                        <label for="filter-ci">CI</label>
                        <input id="filter-ci" type="text" inputmode="numeric" pattern="[0-9]+" placeholder="CI exacto (opcional)">
                    </div>
                    <div class="form-field">
                        <label for="date-from">Desde</label>
                        <input id="date-from" type="date">
                    </div>
                    <div class="form-field">
                        <label for="date-to">Hasta</label>
                        <input id="date-to" type="date">
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button id="apply-btn" class="btn btn-primary"><i class="fa-solid fa-filter"></i> Aplicar</button>
                        <button id="clear-btn" class="btn btn-ghost"><i class="fa-solid fa-xmark"></i> Limpiar</button>
                    </div>
                </div>
            </div>

            <div class="stat-grid" id="stat-grid"></div>

            <div class="table-wrapper">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>CI</th>
                            <th>Fecha</th>
                            <th>Hora</th>
                            <th>Marcada por</th>
                        </tr>
                    </thead>
                    <tbody id="attendances-tbody">
                        <tr><td colspan="4"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>
                    </tbody>
                </table>
                <div class="pagination">
                    <span id="page-info">—</span>
                </div>
            </div>
        `;

        const tbody = container.querySelector('#attendances-tbody');
        const statGrid = container.querySelector('#stat-grid');
        const pageInfo = container.querySelector('#page-info');

        async function loadAttendances() {
            const queryParams = {
                ci:        container.querySelector('#filter-ci').value.trim() || undefined,
                date_from: container.querySelector('#date-from').value || undefined,
                date_to:   container.querySelector('#date-to').value || undefined,
                limit:     config.ui.pageSize || 25
            };
            tbody.innerHTML = `<tr><td colspan="4"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            try {
                const data = await api.get(config.miningSummit.attendancesPath, queryParams);
                const items = data.items || [];
                renderRows(tbody, items);
                renderStats(statGrid, items);
                pageInfo.textContent = `${items.length} asistencias`;
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${error.message}</p></div></td></tr>`;
                Toast.danger(`No se pudo cargar: ${error.message}`);
            }
        }

        container.querySelector('#apply-btn').addEventListener('click', loadAttendances);
        container.querySelector('#clear-btn').addEventListener('click', () => {
            container.querySelector('#filter-ci').value = '';
            container.querySelector('#date-from').value = '';
            container.querySelector('#date-to').value = '';
            loadAttendances();
        });

        loadAttendances();
    }
};

function renderRows(tbody, items) {
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
            <i class="fa-solid fa-calendar-xmark"></i>
            <p>Sin asistencias para los filtros aplicados.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(a => `
        <tr>
            <td><strong>${escapeHtml(a.ci)}</strong></td>
            <td>${escapeHtml(a.attendance_date || '—')}</td>
            <td>${formatTime(a.attendance_at)}</td>
            <td>${escapeHtml(a.marked_by || '—')}</td>
        </tr>
    `).join('');
}

function renderStats(container, items) {
    const total = items.length;
    const uniqueCi = new Set(items.map(i => i.ci)).size;
    const uniqueDates = new Set(items.map(i => i.attendance_date)).size;
    container.innerHTML = `
        <div class="stat-card"><div class="label">Total registros</div><div class="value">${total}</div></div>
        <div class="stat-card"><div class="label">Participantes únicos</div><div class="value">${uniqueCi}</div></div>
        <div class="stat-card"><div class="label">Días con asistencia</div><div class="value">${uniqueDates}</div></div>
    `;
}

function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
