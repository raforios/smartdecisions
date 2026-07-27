/**
 * Reporte de asistencias por CI y/o rango de fechas.
 * GET /v1/mining-summit/attendances  (filtros opcionales: ci, date_from, date_to)
 *
 * El endpoint solo devuelve {ci, attendance_date, attendance_at, marked_by}.
 * Para mostrar el nombre completo del asistente hacemos un join client-side
 * cargando el directorio de participantes una sola vez por render de página.
 */
import { Toast } from '../components/Toast.js';

export const AsistenciasPage = {
    render(container, { config, api }) {
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Reporte de Asistencias</h2>
                    <div class="subtitle">Busca por nombre o CI (en vivo) y acota por rango de fechas.</div>
                </div>
                <button id="export-btn" class="btn btn-primary">
                    <i class="fa-solid fa-file-excel"></i> Descargar Excel
                </button>
            </div>

            <div class="card">
                <div class="table-toolbar">
                    <div class="form-field" style="flex:2; min-width:220px;">
                        <label for="att-search">Buscar (nombre o CI)</label>
                        <input id="att-search" type="text" placeholder="Filtra por nombre o CI…" autocomplete="off">
                    </div>
                    <div class="form-field">
                        <label for="date-from">Desde</label>
                        <input id="date-from" type="date">
                    </div>
                    <div class="form-field">
                        <label for="date-to">Hasta</label>
                        <input id="date-to" type="date">
                    </div>
                    <div class="form-field" style="align-self:flex-end;">
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
                            <th>Participante</th>
                            <th>Institución</th>
                            <th>Aula</th>
                            <th>Fecha</th>
                            <th>Hora</th>
                            <th>Usuario activo</th>
                        </tr>
                    </thead>
                    <tbody id="attendances-tbody">
                        <tr><td colspan="7"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>
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

        // Cache del directorio CI -> "Nombre Apellido". Se carga la primera vez
        // que se necesita y se reutiliza en sucesivas búsquedas dentro de la misma
        // visita a la sección.
        let participantsByCi = null;

        async function ensureParticipantsLoaded() {
            if (participantsByCi) return participantsByCi;
            participantsByCi = new Map();
            let lastKey = null;
            do {
                const params = { limit: 100 };
                if (lastKey) params.last_evaluated_key = lastKey;
                const data = await api.get(config.miningSummit.participantsPath, params);
                for (const p of (data.items || [])) {
                    participantsByCi.set(p.ci, {
                        name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
                        institution: p.institution_name || p.company || '',
                        mesa: p.mesa_code || '',
                        axisLabel: p.axis_label || ''
                    });
                }
                lastKey = data.last_evaluated_key;
            } while (lastKey);
            return participantsByCi;
        }

        let allRows = [];
        const norm = (s) => String(s == null ? '' : s).toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '');

        // Trae todas las asistencias (con el rango de fechas, si se puso) y las
        // guarda; el filtro por nombre/CI es client-side (instantáneo).
        async function loadAttendances() {
            const dateFrom = container.querySelector('#date-from').value || undefined;
            const dateTo = container.querySelector('#date-to').value || undefined;
            tbody.innerHTML = `<tr><td colspan="7"><div class="loading"><div class="spinner"></div> Cargando...</div></td></tr>`;
            try {
                await ensureParticipantsLoaded();
                const rows = [];
                let lastKey = null;
                do {
                    const params = { limit: 100 };
                    if (dateFrom) params.date_from = dateFrom;
                    if (dateTo) params.date_to = dateTo;
                    if (lastKey) params.last_evaluated_key = lastKey;
                    const data = await api.get(config.miningSummit.attendancesPath, params);
                    rows.push(...(data.items || []));
                    lastKey = data.last_evaluated_key || null;
                } while (lastKey);
                allRows = rows;
                applySearch();
            } catch (error) {
                tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${error.message}</p></div></td></tr>`;
                Toast.danger(`No se pudo cargar: ${error.message}`);
            }
        }

        function applySearch() {
            const pmap = participantsByCi || new Map();
            const q = norm(container.querySelector('#att-search').value.trim());
            const filtered = !q ? allRows : allRows.filter((a) =>
                norm(`${a.ci} ${(pmap.get(a.ci) || {}).name || ''}`).includes(q));
            renderRows(tbody, filtered, pmap);
            renderStats(statGrid, filtered);
            pageInfo.textContent = `${filtered.length} asistencias`;
        }

        const exportBtn = container.querySelector('#export-btn');
        exportBtn.addEventListener('click', async () => {
            const original = exportBtn.innerHTML;
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generando...';
            try {
                await api.download(config.miningSummit.attendancesExportPath, 'asistencias.xlsx');
                Toast.success('Reporte de asistencias descargado.');
            } catch (error) {
                Toast.danger(`No se pudo exportar: ${error.message}`);
            } finally {
                exportBtn.disabled = false;
                exportBtn.innerHTML = original;
            }
        });

        container.querySelector('#att-search').addEventListener('input', applySearch);
        container.querySelector('#date-from').addEventListener('change', loadAttendances);
        container.querySelector('#date-to').addEventListener('change', loadAttendances);
        container.querySelector('#clear-btn').addEventListener('click', () => {
            container.querySelector('#att-search').value = '';
            container.querySelector('#date-from').value = '';
            container.querySelector('#date-to').value = '';
            loadAttendances();
        });

        loadAttendances();
    }
};

function renderRows(tbody, items, participantsByCi) {
    if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
            <i class="fa-solid fa-calendar-xmark"></i>
            <p>Sin asistencias para los filtros aplicados.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(a => {
        const info = participantsByCi.get(a.ci) || {};
        const aula = info.mesa
            ? `<strong>${escapeHtml(info.mesa)}</strong>${info.axisLabel ? `<br><small style="color:var(--text-muted)">${escapeHtml(info.axisLabel)}</small>` : ''}`
            : '—';
        return `
            <tr>
                <td><strong>${escapeHtml(a.ci)}</strong></td>
                <td>${escapeHtml(info.name || '—')}</td>
                <td>${escapeHtml(info.institution || '—')}</td>
                <td>${aula}</td>
                <td>${escapeHtml(a.attendance_date || '—')}</td>
                <td>${formatTime(a.attendance_at)}</td>
                <td>${escapeHtml(a.marked_by || '—')}</td>
            </tr>
        `;
    }).join('');
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
