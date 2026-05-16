/**
 * mercados.js — controla la vista pública de cotizaciones oficiales.
 *
 * Flujo:
 *  1. Lee data/config.json para conocer el base URL del microservicio.
 *  2. Pide el histórico quincenal (todas las quincenas con datos).
 *  3. Pinta:
 *       - KPI cards con la última quincena.
 *       - Selector de año + multi-select de minerales.
 *       - Chart.js de líneas (una serie por mineral seleccionado).
 *       - Tabla con todas las quincenas en filas y minerales en columnas.
 *       - Botones de descarga PNG/PDF que apuntan al endpoint binario.
 */
import { MiningApiService } from './services/MiningApiService.js';

const MONTH_NAMES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
    'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

const MINERAL_COLORS = {
    'Estaño': '#C9A751', 'Plomo': '#5C5C5C', 'Zinc': '#7CA6A6',
    'Cobre': '#B87333', 'Antimonio': '#A0A0A0', 'Wolfram': '#404040',
    'Bismuto': '#6F84A1', 'Oro': '#D4AF37', 'Plata': '#B7B7B7',
};

const state = {
    api: null,
    history: [],
    chart: null,
    selectedYear: null,
    selectedUnit: null,
    selectedMinerals: new Set(),
};

document.addEventListener('DOMContentLoaded', async () => {
    const config = await fetch('data/config.json', { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null);
    if (!config?.api) {
        renderError('No se pudo cargar la configuración del sitio.');
        return;
    }
    state.api = new MiningApiService(config.api);

    const payload = await state.api.getBiweeklyHistory();
    if (!payload?.periods?.length) {
        renderError('El servicio no devolvió quincenas con datos.');
        return;
    }
    state.history = payload.periods;

    initializeYearFilter();
    initializeUnitFilter();
    initializeMineralFilter();
    initializePeriodPicker();
    renderKpisForLastPeriod();
    renderChart();
    renderTable();
});

function renderError(message) {
    document.querySelectorAll('#mercados-kpis, #mercados-table tbody, #lme-chart')
        .forEach(el => el && (el.outerHTML = `<div class="mercados-error">${message}</div>`));
}

// ---------------- Filters ----------------

function initializeYearFilter() {
    const years = [...new Set(state.history.map(p => p.year))].sort((a, b) => b - a);
    state.selectedYear = years[0];
    const select = document.getElementById('year-filter');
    select.innerHTML = ['Todos los años', ...years.map(y => String(y))]
        .map((label, idx) => `<option value="${idx === 0 ? '' : label}">${label}</option>`)
        .join('');
    select.value = String(state.selectedYear);
    select.addEventListener('change', () => {
        state.selectedYear = select.value ? Number(select.value) : null;
        renderChart();
        renderTable();
        initializePeriodPicker();
    });
}

function initializeUnitFilter() {
    const catalog = state.history[0]?.rows || [];
    const units = [...new Set(catalog.map(r => r.unit).filter(Boolean))];
    state.selectedUnit = units[0] || null;
    const select = document.getElementById('unit-filter');
    select.innerHTML = units
        .map(u => `<option value="${u}">${u} — ${unitDescription(u)}</option>`)
        .join('');
    select.value = state.selectedUnit || '';
    select.addEventListener('change', () => {
        state.selectedUnit = select.value || null;
        renderMineralChips();
        renderChart();
    });
}

function initializeMineralFilter() {
    renderMineralChips();
    const container = document.getElementById('mineral-filter');
    container.addEventListener('change', evt => {
        const cb = evt.target;
        if (cb.tagName !== 'INPUT') return;
        if (cb.checked) state.selectedMinerals.add(cb.value);
        else state.selectedMinerals.delete(cb.value);
        renderChart();
    });
}

function renderMineralChips() {
    const catalog = state.history[0]?.rows || [];
    const minerals = catalog
        .filter(r => !state.selectedUnit || r.unit === state.selectedUnit)
        .map(r => r.mineral);
    state.selectedMinerals = new Set(minerals);
    const container = document.getElementById('mineral-filter');
    container.innerHTML = minerals.map(m => `
        <label class="mineral-chip">
            <input type="checkbox" value="${m}" checked>
            <span style="--chip-color:${MINERAL_COLORS[m] || '#888'}">${m}</span>
        </label>
    `).join('');
}

function unitDescription(unit) {
    const map = {
        LF: 'Libra Fina',
        TMF: 'Tonelada Métrica Fina',
        OT: 'Onza Troy',
    };
    return map[unit] || unit;
}

function initializePeriodPicker() {
    const picker = document.getElementById('period-picker');
    const periods = filteredHistory();
    if (!periods.length) {
        picker.innerHTML = '<option value="">— sin datos —</option>';
        updateDownloadLinks(null);
        return;
    }
    picker.innerHTML = periods.map(p => {
        const label = `${MONTH_NAMES_ES[p.month - 1]} ${p.year} · Q${p.half}`;
        return `<option value="${p.year}-${p.month}-${p.half}">${label}</option>`;
    }).reverse().join('');
    picker.addEventListener('change', () => updateDownloadLinks(parsePeriodValue(picker.value)));
    updateDownloadLinks(parsePeriodValue(picker.value));
}

function parsePeriodValue(value) {
    if (!value) return null;
    const [year, month, half] = value.split('-').map(Number);
    return { year, month, half };
}

// ---------------- Render ----------------

function renderKpisForLastPeriod() {
    const last = state.history[state.history.length - 1];
    const label = document.getElementById('mercados-period-label');
    label.textContent = `${MONTH_NAMES_ES[last.month - 1]} ${last.year} · Q${last.half} ` +
        `(${last.period_start} → ${last.period_end})`;
    const container = document.getElementById('mercados-kpis');
    const prev = state.history[state.history.length - 2] || null;
    const prevByMineral = new Map((prev?.rows || []).map(r => [r.mineral, r.avg_price_low]));
    container.innerHTML = last.rows.map(r => {
        const prevValue = prevByMineral.get(r.mineral);
        const delta = (prevValue && prevValue > 0)
            ? ((r.avg_price_low - prevValue) / prevValue) * 100
            : null;
        const deltaCls = delta == null ? '' : (delta >= 0 ? 'up' : 'down');
        const deltaTxt = delta == null ? '—'
            : `${delta >= 0 ? '▲' : '▼'} ${delta.toFixed(2)}%`;
        const unit = r.unit || '';
        return `
            <div class="kpi-card" style="--accent:${MINERAL_COLORS[r.mineral] || '#888'}">
                <h4>${r.mineral} <small>${r.chemical_symbol || ''}</small></h4>
                <div class="kpi-value">${formatPrice(r.avg_price_low)}</div>
                <div class="kpi-unit">USD / ${unit}</div>
                <div class="kpi-delta ${deltaCls}">${deltaTxt}</div>
            </div>
        `;
    }).join('');
}

function renderChart() {
    const ctx = document.getElementById('lme-chart');
    if (!ctx) return;
    updateChartUnitLabel();
    const periods = filteredHistory();
    const labels = periods.map(p =>
        `${MONTH_NAMES_ES[p.month - 1].slice(0, 3)} ${p.year} Q${p.half}`);

    const datasets = [...state.selectedMinerals].map(mineral => {
        const data = periods.map(p => {
            const row = p.rows.find(r => r.mineral === mineral);
            return row ? Number(row.avg_price_low) : null;
        });
        return {
            label: mineral,
            data,
            borderColor: MINERAL_COLORS[mineral] || '#888',
            backgroundColor: hexToRgba(MINERAL_COLORS[mineral] || '#888', 0.12),
            tension: 0.25,
            spanGaps: true,
        };
    });

    const yAxisTitle = state.selectedUnit
        ? `USD / ${state.selectedUnit}`
        : 'USD';

    if (state.chart) state.chart.destroy();
    state.chart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'bottom' } },
            scales: {
                y: {
                    type: 'linear', position: 'left',
                    title: { display: true, text: yAxisTitle },
                },
            },
        },
    });
}

function updateChartUnitLabel() {
    const el = document.getElementById('chart-unit-label');
    if (el) el.textContent = `USD / ${state.selectedUnit || '—'}`;
}

function renderTable() {
    const periods = filteredHistory();
    const table = document.getElementById('mercados-table');
    if (!periods.length) {
        table.querySelector('thead').innerHTML = '';
        table.querySelector('tbody').innerHTML =
            '<tr><td>No hay quincenas registradas para el filtro actual.</td></tr>';
        return;
    }
    const minerals = periods[0].rows.map(r => r.mineral);
    table.querySelector('thead').innerHTML = `
        <tr>
            <th>Periodo</th>
            <th>Rango</th>
            ${minerals.map(m => `<th>${m}</th>`).join('')}
        </tr>
    `;
    table.querySelector('tbody').innerHTML = periods.slice().reverse().map(p => `
        <tr>
            <td>${MONTH_NAMES_ES[p.month - 1]} ${p.year} · Q${p.half}</td>
            <td>${p.period_start} → ${p.period_end}</td>
            ${minerals.map(m => {
                const r = p.rows.find(x => x.mineral === m);
                return `<td class="${r?.is_fallback ? 'is-fallback' : ''}">${
                    r ? formatPrice(r.avg_price_low) : '—'}</td>`;
            }).join('')}
        </tr>
    `).join('');
}

function updateDownloadLinks(period) {
    const png = document.getElementById('dl-png');
    const pdf = document.getElementById('dl-pdf');
    if (!period) {
        png.removeAttribute('href');
        pdf.removeAttribute('href');
        png.classList.add('disabled');
        pdf.classList.add('disabled');
        return;
    }
    png.href = state.api.biweeklyAssetUrl(period.year, period.month, period.half, 'png');
    pdf.href = state.api.biweeklyAssetUrl(period.year, period.month, period.half, 'pdf');
    png.classList.remove('disabled');
    pdf.classList.remove('disabled');
}

// ---------------- Helpers ----------------

function filteredHistory() {
    if (!state.selectedYear) return state.history;
    return state.history.filter(p => p.year === state.selectedYear);
}

function formatPrice(value) {
    const v = Number(value);
    if (!Number.isFinite(v)) return '—';
    if (Math.abs(v - Math.round(v)) < 1e-9) {
        return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
    }
    return v.toLocaleString('en-US', {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
}

function hexToRgba(hex, alpha) {
    const m = hex.replace('#', '').match(/.{1,2}/g);
    if (!m) return `rgba(136,136,136,${alpha})`;
    const [r, g, b] = m.map(h => parseInt(h, 16));
    return `rgba(${r},${g},${b},${alpha})`;
}
