/**
 * Reporte gráfico estadístico (Chart.js).
 * GET /v1/mining-summit/reports/stats?group_by=department|company
 */
import { Toast } from '../components/Toast.js';

let chartInstance = null;

export const EstadisticasPage = {
    render(container, { config, api }) {
        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Estadísticas Gráficas</h2>
                    <div class="subtitle">Distribución de participantes por dimensión.</div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button id="btn-department" class="btn btn-primary"><i class="fa-solid fa-location-dot"></i> Por Departamento</button>
                    <button id="btn-company" class="btn btn-ghost"><i class="fa-solid fa-building"></i> Por Empresa</button>
                </div>
            </div>

            <div class="stat-grid" id="stat-grid"></div>

            <div class="chart-container">
                <canvas id="stats-chart"></canvas>
            </div>

            <div class="card" style="margin-top: 1.5rem;">
                <h3><i class="fa-solid fa-table" style="color:var(--oro)"></i> Detalle</h3>
                <div class="table-wrapper" style="box-shadow:none; border-top:none;">
                    <table class="data-table">
                        <thead><tr><th>Etiqueta</th><th>Cantidad</th><th>Porcentaje</th></tr></thead>
                        <tbody id="stats-tbody"></tbody>
                    </table>
                </div>
            </div>
        `;

        const btnDept = container.querySelector('#btn-department');
        const btnComp = container.querySelector('#btn-company');
        const statGrid = container.querySelector('#stat-grid');
        const tbody = container.querySelector('#stats-tbody');

        async function load(groupBy) {
            btnDept.classList.toggle('btn-primary', groupBy === 'department');
            btnDept.classList.toggle('btn-ghost', groupBy !== 'department');
            btnComp.classList.toggle('btn-primary', groupBy === 'company');
            btnComp.classList.toggle('btn-ghost', groupBy !== 'company');

            statGrid.innerHTML = `<div class="loading"><div class="spinner"></div> Cargando estadísticas...</div>`;
            tbody.innerHTML = '';
            try {
                const data = await api.get(config.miningSummit.statsPath, { group_by: groupBy });
                renderStatGrid(statGrid, data, groupBy);
                renderTable(tbody, data.items);
                renderChart(data, config);
            } catch (error) {
                statGrid.innerHTML = `<div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${error.message}</p></div>`;
                Toast.danger(`No se pudieron cargar estadísticas: ${error.message}`);
            }
        }

        btnDept.addEventListener('click', () => load('department'));
        btnComp.addEventListener('click', () => load('company'));

        load('department');
    }
};

function renderStatGrid(container, data, groupBy) {
    const dimensionLabel = groupBy === 'department' ? 'Departamentos' : 'Empresas';
    const top = data.items[0];
    container.innerHTML = `
        <div class="stat-card"><div class="label">Participantes</div><div class="value">${data.total}</div></div>
        <div class="stat-card"><div class="label">${dimensionLabel} distintos</div><div class="value">${data.items.length}</div></div>
        <div class="stat-card">
            <div class="label">Top</div>
            <div class="value" style="font-size: 1.2rem;">${top ? escapeHtml(top.label) : '—'}</div>
            <div class="label" style="margin-top:4px;">${top ? top.count + ' participantes (' + top.percentage + '%)' : ''}</div>
        </div>
    `;
}

function renderTable(tbody, items) {
    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3"><div class="empty-state">
            <i class="fa-solid fa-chart-pie"></i>
            <p>Aún no hay datos para mostrar.</p></div></td></tr>`;
        return;
    }
    tbody.innerHTML = items.map(it => `
        <tr>
            <td>${escapeHtml(it.label)}</td>
            <td><strong>${it.count}</strong></td>
            <td>${it.percentage}%</td>
        </tr>
    `).join('');
}

function renderChart(data, config) {
    const ctx = document.getElementById('stats-chart');
    if (!ctx) return;
    if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
    }
    const palette = config.ui.chartColors || ['#C9A751'];
    const colors = data.items.map((_, i) => palette[i % palette.length]);
    chartInstance = new Chart(ctx, {
        type: data.items.length > 8 ? 'bar' : 'doughnut',
        data: {
            labels: data.items.map(i => i.label),
            datasets: [{
                label: data.group_by,
                data: data.items.map(i => i.count),
                backgroundColor: colors,
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: data.items.length > 8 ? 'top' : 'right' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const item = data.items[ctx.dataIndex];
                            return `${item.label}: ${item.count} (${item.percentage}%)`;
                        }
                    }
                }
            },
            scales: data.items.length > 8
                ? { y: { beginAtZero: true, ticks: { precision: 0 } } }
                : {}
        }
    });
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
