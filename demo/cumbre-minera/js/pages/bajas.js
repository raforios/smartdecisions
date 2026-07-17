/**
 * Bajas y Reemplazos.
 * GET /v1/mining-summit/reports/lifecycle
 *
 * Muestra dos secciones: participantes reemplazados (con su sustituto y quién
 * hizo el reemplazo) y participantes que declinaron por completo (con su motivo).
 */
import { Toast } from '../components/Toast.js';

export const BajasPage = {
    async render(container, { config, api }) {
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Bajas y Reemplazos</h2>
                    <div class="subtitle">Participantes reemplazados y declinados, con motivos y responsables.</div>
                </div>
            </div>
            <div class="stat-grid" id="bajas-stats"></div>
            <div id="bajas-content">
                <div class="loading"><div class="spinner"></div> Cargando...</div>
            </div>
        `;

        const stats = container.querySelector('#bajas-stats');
        const content = container.querySelector('#bajas-content');

        try {
            const data = await api.get(config.miningSummit.lifecyclePath);
            stats.innerHTML = `
                <div class="stat-card"><div class="label">Reemplazados</div>
                    <div class="value">${data.total_replaced}</div></div>
                <div class="stat-card"><div class="label">Declinaron (cancelados)</div>
                    <div class="value">${data.total_cancelled}</div></div>
            `;
            content.innerHTML =
                renderReplaced(data.replaced) + renderCancelled(data.cancelled);
        } catch (error) {
            content.innerHTML = `<div class="empty-state">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>${escapeHtml(error.message)}</p></div>`;
            Toast.danger(`No se pudo cargar el reporte: ${error.message}`);
        }
    }
};

function renderReplaced(items) {
    const rows = items.length ? items.map(p => `
        <tr>
            <td><strong>${escapeHtml(p.ci)}</strong></td>
            <td>${escapeHtml(fullName(p))}</td>
            <td>${escapeHtml(p.institution_name || '—')}</td>
            <td>${renderSeat(p)}</td>
            <td>${escapeHtml(p.substitute_name || '—')}<br>
                <small style="color:var(--text-muted)">CI ${escapeHtml(p.substitute_ci || '—')}</small></td>
            <td>${escapeHtml(p.observation || '—')}</td>
            <td>${renderActor(p)}</td>
        </tr>`).join('') : emptyRow(7, 'Sin reemplazos registrados.');
    return `
        <div class="card" style="margin-bottom:1.5rem;">
            <h3><i class="fa-solid fa-people-arrows" style="color:var(--oro)"></i> Reemplazados</h3>
            <div class="table-wrapper" style="box-shadow:none; border-top:none;">
                <table class="data-table">
                    <thead><tr>
                        <th>CI</th><th>Participante saliente</th><th>Institución</th>
                        <th>Asiento</th><th>Sustituto (quien reemplaza)</th>
                        <th>Motivo / justificación</th><th>Realizado por</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>`;
}

function renderCancelled(items) {
    const rows = items.length ? items.map(p => `
        <tr>
            <td><strong>${escapeHtml(p.ci)}</strong></td>
            <td>${escapeHtml(fullName(p))}</td>
            <td>${escapeHtml(p.institution_name || '—')}</td>
            <td>${renderSeat(p)}</td>
            <td>${escapeHtml(p.observation || '—')}</td>
            <td>${renderActor(p)}</td>
        </tr>`).join('') : emptyRow(6, 'Sin bajas registradas.');
    return `
        <div class="card">
            <h3><i class="fa-solid fa-user-slash" style="color:var(--oro)"></i> Declinaron por completo (cancelados)</h3>
            <div class="table-wrapper" style="box-shadow:none; border-top:none;">
                <table class="data-table">
                    <thead><tr>
                        <th>CI</th><th>Participante</th><th>Institución</th>
                        <th>Asiento</th><th>Motivo / justificación</th><th>Realizado por</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>`;
}

function fullName(p) {
    return `${p.first_name || ''} ${p.last_name || ''}`.trim() || '—';
}

function renderSeat(p) {
    if (!p.mesa_code) return '—';
    const eje = p.axis_label
        ? `<br><small style="color:var(--text-muted)">${escapeHtml(p.axis_label)}</small>` : '';
    return `<strong>${escapeHtml(p.mesa_code)}</strong>${eje}`;
}

function renderActor(p) {
    if (!p.status_changed_by) return '—';
    const when = (p.status_changed_at || '').slice(0, 10);
    return `${escapeHtml(p.status_changed_by)}${when ? `<br><small style="color:var(--text-muted)">${when}</small>` : ''}`;
}

function emptyRow(cols, text) {
    return `<tr><td colspan="${cols}"><div class="empty-state">
        <i class="fa-solid fa-folder-open"></i><p>${text}</p></div></td></tr>`;
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
