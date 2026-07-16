/**
 * Estadísticas gráficas (Chart.js).
 * Vistas:
 *   - Por eje / Por aula y eje  -> GET /reports/seat-distribution?basis&date
 *   - Departamento / Empresa    -> GET /reports/stats?group_by
 * Base: Presentes (por fecha de asistencia) o Registrados (total asignado).
 */
import { Toast } from '../components/Toast.js';

let chartInstance = null;

const VIEWS = {
    axis: { label: 'Por eje', icon: 'fa-diagram-project', seat: true },
    aula: { label: 'Por aula y eje', icon: 'fa-chalkboard', seat: true },
    department: { label: 'Departamento', icon: 'fa-location-dot', seat: false }
};

export const EstadisticasPage = {
    render(container, { config, api }) {
        const today = new Date().toISOString().slice(0, 10);
        const state = { view: 'axis', basis: 'present', date: today, selectedAxis: null };

        const viewButtons = Object.entries(VIEWS).map(([key, v]) =>
            `<button class="btn btn-ghost view-btn" data-view="${key}">
                <i class="fa-solid ${v.icon}"></i> ${v.label}
            </button>`).join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Estadísticas Gráficas</h2>
                    <div class="subtitle">Distribución de participantes por eje, aula o dimensión.</div>
                </div>
                <div class="view-switch">${viewButtons}</div>
            </div>

            <div class="stats-controls" id="stats-controls">
                <div class="basis-toggle">
                    <button class="btn btn-ghost basis-btn" data-basis="present">
                        <i class="fa-solid fa-user-check"></i> Presentes
                    </button>
                    <button class="btn btn-ghost basis-btn" data-basis="registered">
                        <i class="fa-solid fa-user-plus"></i> Registrados
                    </button>
                </div>
                <label class="date-field" id="date-field">
                    <span>Fecha</span>
                    <input type="date" id="stats-date" value="${state.date}" max="${today}">
                </label>
            </div>

            <div class="stat-grid" id="stat-grid"></div>

            <div class="chart-container">
                <canvas id="stats-chart"></canvas>
            </div>

            <div id="aula-detail" class="aula-detail"></div>

            <div class="card" id="detail-card" style="margin-top: 1.5rem;">
                <h3><i class="fa-solid fa-table" style="color:var(--oro)"></i> Detalle</h3>
                <div class="table-wrapper" style="box-shadow:none; border-top:none;">
                    <table class="data-table">
                        <thead><tr id="detail-head"></tr></thead>
                        <tbody id="stats-tbody"></tbody>
                    </table>
                </div>
            </div>
        `;

        const els = {
            controls: container.querySelector('#stats-controls'),
            dateField: container.querySelector('#date-field'),
            dateInput: container.querySelector('#stats-date'),
            statGrid: container.querySelector('#stat-grid'),
            aulaDetail: container.querySelector('#aula-detail'),
            detailHead: container.querySelector('#detail-head'),
            tbody: container.querySelector('#stats-tbody'),
            viewBtns: [...container.querySelectorAll('.view-btn')],
            basisBtns: [...container.querySelectorAll('.basis-btn')]
        };

        function syncButtons() {
            els.viewBtns.forEach(btn => {
                const on = btn.dataset.view === state.view;
                btn.classList.toggle('btn-primary', on);
                btn.classList.toggle('btn-ghost', !on);
            });
            els.basisBtns.forEach(btn => {
                const on = btn.dataset.basis === state.basis;
                btn.classList.toggle('btn-primary', on);
                btn.classList.toggle('btn-ghost', !on);
            });
            const seatView = VIEWS[state.view].seat;
            els.controls.style.display = seatView ? 'flex' : 'none';
            els.dateField.style.display = (seatView && state.basis === 'present') ? 'flex' : 'none';
        }

        async function refresh() {
            syncButtons();
            state.selectedAxis = null;
            els.aulaDetail.innerHTML = '';
            els.statGrid.innerHTML =
                `<div class="loading"><div class="spinner"></div> Cargando estadísticas...</div>`;
            els.tbody.innerHTML = '';
            try {
                if (VIEWS[state.view].seat) {
                    await loadSeat(state, config, api, els);
                } else {
                    await loadDimension(state.view, config, api, els);
                }
            } catch (error) {
                els.statGrid.innerHTML = `<div class="empty-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>${escapeHtml(error.message)}</p></div>`;
                Toast.danger(`No se pudieron cargar estadísticas: ${error.message}`);
            }
        }

        els.viewBtns.forEach(btn =>
            btn.addEventListener('click', () => { state.view = btn.dataset.view; refresh(); }));
        els.basisBtns.forEach(btn =>
            btn.addEventListener('click', () => { state.basis = btn.dataset.basis; refresh(); }));
        els.dateInput.addEventListener('change', () => { state.date = els.dateInput.value; refresh(); });

        refresh();
    }
};

/* ---------- Seat distribution (por eje / por aula y eje) ---------- */

async function loadSeat(state, config, api, els) {
    const params = { basis: state.basis };
    if (state.basis === 'present') params.date = state.date;
    const data = await api.get(config.miningSummit.seatDistributionPath, params);

    renderSeatCards(els.statGrid, data);
    renderSeatChart(data, config, (axis) => showAulaDetail(els.aulaDetail, axis, config));
    renderSeatTable(els, data);

    if (state.view === 'aula') {
        els.aulaDetail.innerHTML =
            `<p class="aula-hint"><i class="fa-solid fa-hand-pointer"></i>
             Pincha una barra (eje) para ver el detalle por aula.</p>`;
    }
}

function renderSeatCards(container, data) {
    const basisLabel = data.basis === 'present'
        ? `Presentes${data.date ? ' · ' + data.date : ''}` : 'Registrados';
    const topAxis = [...data.axes].sort((a, b) => b.count - a.count)[0];
    container.innerHTML = `
        <div class="stat-card"><div class="label">${basisLabel}</div>
            <div class="value">${data.total}</div></div>
        <div class="stat-card"><div class="label">Ejes con datos</div>
            <div class="value">${data.axes.filter(a => a.count > 0).length}/${data.axes.length}</div></div>
        <div class="stat-card"><div class="label">Eje con más personas</div>
            <div class="value" style="font-size:1.1rem;">${topAxis && topAxis.count ? escapeHtml(topAxis.label) : '—'}</div>
            <div class="label" style="margin-top:4px;">${topAxis && topAxis.count ? topAxis.count + ' personas' : ''}</div></div>
        <div class="stat-card"><div class="label">Sin eje asignado</div>
            <div class="value">${data.unassigned}</div></div>
    `;
}

function renderSeatChart(data, config, onAxisClick) {
    const ctx = document.getElementById('stats-chart');
    if (!ctx) return;
    destroyChart();
    const palette = config.ui.chartColors || ['#C9A751'];
    const colors = data.axes.map((a) => palette[(a.number - 1) % palette.length]);
    chartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.axes.map(a => `EJE ${a.number}`),
            datasets: [{
                label: 'Personas',
                data: data.axes.map(a => a.count),
                backgroundColor: colors,
                borderColor: '#ffffff',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            onClick: (_evt, elements) => {
                if (elements.length && onAxisClick) onAxisClick(data.axes[elements[0].index]);
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => data.axes[items[0].dataIndex].label,
                        label: (item) => {
                            const axis = data.axes[item.dataIndex];
                            return `${axis.count} personas · cupo ${axis.capacity}`;
                        }
                    }
                }
            },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
        }
    });
}

function showAulaDetail(container, axis, config) {
    const palette = config.ui.chartColors || ['#C9A751'];
    const color = palette[(axis.number - 1) % palette.length];
    const cards = axis.aulas.map(aula => `
        <div class="aula-card" style="border-top-color:${color}">
            <div class="aula-code">${escapeHtml(aula.mesa_code)}</div>
            <div class="aula-count">${aula.count}</div>
            <div class="aula-cap">de ${aula.capacity} asientos</div>
        </div>`).join('');
    container.innerHTML = `
        <div class="aula-detail-head">
            <span class="eje-badge">EJE ${axis.number}</span>
            <h3>${escapeHtml(axis.label)}</h3>
            <span class="aula-detail-total">${axis.count} personas</span>
        </div>
        <div class="aula-cards">${cards}</div>
    `;
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderSeatTable(els, data) {
    els.detailHead.innerHTML = '<th>Eje</th><th>Personas</th><th>Cupo</th><th>Ocupación</th>';
    if (!data.axes.length) {
        els.tbody.innerHTML = emptyRow(4);
        return;
    }
    els.tbody.innerHTML = data.axes.map(a => {
        const pct = a.capacity ? Math.round((a.count / a.capacity) * 100) : 0;
        return `<tr>
            <td>${a.number}. ${escapeHtml(a.label)}</td>
            <td><strong>${a.count}</strong></td>
            <td>${a.capacity}</td>
            <td>${pct}%</td>
        </tr>`;
    }).join('');
}

/* ---------- Dimension distribution (departamento) ---------- */

async function loadDimension(groupBy, config, api, els) {
    els.aulaDetail.innerHTML = '';
    const data = await api.get(config.miningSummit.statsPath, { group_by: groupBy });
    const dimensionLabel = 'Departamentos';
    const top = data.items[0];
    els.statGrid.innerHTML = `
        <div class="stat-card"><div class="label">Participantes</div>
            <div class="value">${data.total}</div></div>
        <div class="stat-card"><div class="label">${dimensionLabel} distintos</div>
            <div class="value">${data.items.length}</div></div>
        <div class="stat-card"><div class="label">Top</div>
            <div class="value" style="font-size:1.2rem;">${top ? escapeHtml(top.label) : '—'}</div>
            <div class="label" style="margin-top:4px;">${top ? top.count + ' (' + top.percentage + '%)' : ''}</div></div>
    `;
    els.detailHead.innerHTML = '<th>Etiqueta</th><th>Cantidad</th><th>Porcentaje</th>';
    els.tbody.innerHTML = data.items.length
        ? data.items.map(it => `<tr>
            <td>${escapeHtml(it.label)}</td>
            <td><strong>${it.count}</strong></td>
            <td>${it.percentage}%</td></tr>`).join('')
        : emptyRow(3);
    renderDimensionChart(data, config);
}

function renderDimensionChart(data, config) {
    const ctx = document.getElementById('stats-chart');
    if (!ctx) return;
    destroyChart();
    const palette = config.ui.chartColors || ['#C9A751'];
    const colors = data.items.map((_, i) => palette[i % palette.length]);
    const asBar = data.items.length > 8;
    chartInstance = new Chart(ctx, {
        type: asBar ? 'bar' : 'doughnut',
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
                legend: { position: asBar ? 'top' : 'right' },
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const it = data.items[item.dataIndex];
                            return `${it.label}: ${it.count} (${it.percentage}%)`;
                        }
                    }
                }
            },
            scales: asBar ? { y: { beginAtZero: true, ticks: { precision: 0 } } } : {}
        }
    });
}

/* ---------- Helpers ---------- */

function destroyChart() {
    if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
    }
}

function emptyRow(cols) {
    return `<tr><td colspan="${cols}"><div class="empty-state">
        <i class="fa-solid fa-chart-pie"></i>
        <p>Aún no hay datos para mostrar.</p></div></td></tr>`;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
