'use strict';

/**
 * Utilities tab — direct access to the two standalone ML_FUNCTIONS
 * helpers that the technical reviewer of the prospect tends to ask
 * about as APIs in isolation:
 *
 *   - Z-Score normalization via POST /v1/common/normalize-features
 *   - Sigmoid in batch via POST /v1/classification/sigmoid-batch
 *
 * Both panels can either work on a hand-crafted JSON payload (default,
 * pre-filled with the canonical OpenAPI example) or — for the Z-Score
 * helper — pull the numeric columns from a dataset already loaded in the
 * Classification or Linear Regression tab.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH || !window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const STATE = window.SD_PLAYGROUND_STATE;
    const PARSER = window.SD_PLAYGROUND_PARSER;
    const ML_URL = window.SD_CONFIG.ML_FUNCTIONS_URL.replace(/\/$/, '');

    // ---------- Z-Score panel ----------
    const zscoreSource = qs('#zscoreSource');
    const zscoreLoadBtn = qs('#zscoreLoadButton');
    const zscoreMatrix = qs('#zscoreMatrix');
    const zscoreRunBtn = qs('#zscoreRunButton');
    const zscoreResetBtn = qs('#zscoreResetButton');
    const zscoreNote = qs('#zscoreNote');
    const zscoreResults = qs('#zscoreResults');
    const zscoreMetrics = qs('#zscoreMetrics');
    const zscoreTable = qs('#zscoreTable');

    const ZSCORE_EXAMPLE = '[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]';

    zscoreSource.addEventListener('change', () => {
        const isManual = zscoreSource.value === 'manual';
        zscoreLoadBtn.hidden = isManual;
        zscoreMatrix.readOnly = !isManual && false; // keep editable so user can tweak
    });

    zscoreLoadBtn.addEventListener('click', () => {
        const source = zscoreSource.value;
        const ds = source === 'dataset_class'
            ? STATE.classificationDataset
            : STATE.predictionDataset;
        if (!ds) {
            setError(zscoreNote, 'No hay dataset cargado en esa tab todavía.');
            return;
        }
        const numericIdx = [];
        for (let i = 0; i < ds.columnCount; i++) {
            if (PARSER.isNumericColumn(ds.rows, i)) numericIdx.push(i);
        }
        if (numericIdx.length === 0) {
            setError(zscoreNote, 'Ese dataset no tiene columnas numéricas.');
            return;
        }
        const matrix = ds.rows
            .filter((row) => numericIdx.every((i) => typeof row[i] === 'number'))
            .map((row) => numericIdx.map((i) => row[i]));
        zscoreMatrix.value = JSON.stringify(matrix);
        setSuccess(zscoreNote,
            `Cargada matriz ${matrix.length} × ${numericIdx.length} desde ${ds.fileKey}.`);
    });

    zscoreResetBtn.addEventListener('click', () => {
        zscoreSource.value = 'manual';
        zscoreLoadBtn.hidden = true;
        zscoreMatrix.value = ZSCORE_EXAMPLE;
        zscoreNote.className = 'form-note';
        zscoreNote.textContent = '';
        zscoreResults.hidden = true;
    });

    zscoreRunBtn.addEventListener('click', async () => {
        zscoreNote.className = 'form-note';
        zscoreNote.textContent = '';
        let matrix;
        try {
            matrix = JSON.parse(zscoreMatrix.value);
            if (!Array.isArray(matrix) || matrix.length === 0
                || !Array.isArray(matrix[0])) {
                throw new Error();
            }
        } catch (_) {
            setError(zscoreNote, 'x_matrix debe ser una matriz JSON 2D no vacía.');
            return;
        }

        const done = setButtonBusy(zscoreRunBtn, 'Normalizando…');
        try {
            const response = await window.SD_API.post(
                `${ML_URL}/v1/common/normalize-features`, { x_matrix: matrix }
            );
            renderZScoreResults(response);
            setSuccess(zscoreNote,
                `OK — ${response.x_norm.length} filas × ${response.x_norm[0].length} columnas normalizadas.`);
        } catch (error) {
            setError(zscoreNote, error.message || 'Error al normalizar.');
        } finally {
            done();
        }
    });

    function renderZScoreResults(response) {
        const muText = `[${response.mu.map((v) => formatNumber(v, 4)).join(', ')}]`;
        const sigmaText = `[${response.sigma.map((v) => formatNumber(v, 4)).join(', ')}]`;
        zscoreMetrics.innerHTML = '';
        [
            { label: 'μ (media por columna)', value: muText },
            { label: 'σ (desv. estándar)', value: sigmaText },
            { label: 'Filas', value: String(response.x_norm.length) },
            { label: 'Columnas', value: String(response.x_norm[0].length) }
        ].forEach((card) => {
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `<p class="metric-label">${escapeHtml(card.label)}</p>` +
                             `<p class="metric-value">${escapeHtml(card.value)}</p>`;
            zscoreMetrics.appendChild(node);
        });

        const thead = zscoreTable.querySelector('thead');
        const tbody = zscoreTable.querySelector('tbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';
        const headerRow = document.createElement('tr');
        const headerCells = ['fila']
            .concat(response.x_norm[0].map((_, idx) => `col_${idx}`));
        headerCells.forEach((label) => {
            const th = document.createElement('th');
            th.textContent = label;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        const PREVIEW_LIMIT = 30;
        const visible = response.x_norm.slice(0, PREVIEW_LIMIT);
        visible.forEach((row, idx) => {
            const tr = document.createElement('tr');
            const indexCell = document.createElement('td');
            indexCell.textContent = String(idx);
            tr.appendChild(indexCell);
            row.forEach((value) => {
                const td = document.createElement('td');
                td.textContent = formatNumber(value, 4);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        if (response.x_norm.length > PREVIEW_LIMIT) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = headerCells.length;
            td.style.textAlign = 'center';
            td.style.color = 'var(--muted)';
            td.textContent =
                `… ${response.x_norm.length - PREVIEW_LIMIT} fila(s) más, no mostradas.`;
            tr.appendChild(td);
            tbody.appendChild(tr);
        }
        zscoreResults.hidden = false;
    }

    // ---------- Sigmoid panel ----------
    const sigmoidValues = qs('#sigmoidValues');
    const sigmoidRunBtn = qs('#sigmoidRunButton');
    const sigmoidResetBtn = qs('#sigmoidResetButton');
    const sigmoidNote = qs('#sigmoidNote');
    const sigmoidResults = qs('#sigmoidResults');
    const sigmoidMetrics = qs('#sigmoidMetrics');
    const sigmoidTable = qs('#sigmoidTable');

    const SIGMOID_EXAMPLE = '[-5, -1, 0, 1, 2, 5]';
    let sigmoidChart = null;

    sigmoidResetBtn.addEventListener('click', () => {
        sigmoidValues.value = SIGMOID_EXAMPLE;
        sigmoidNote.className = 'form-note';
        sigmoidNote.textContent = '';
        sigmoidResults.hidden = true;
        if (sigmoidChart) { sigmoidChart.destroy(); sigmoidChart = null; }
    });

    sigmoidRunBtn.addEventListener('click', async () => {
        sigmoidNote.className = 'form-note';
        sigmoidNote.textContent = '';
        let zList;
        try {
            zList = JSON.parse(sigmoidValues.value);
            if (!Array.isArray(zList) || zList.length === 0) throw new Error();
            zList = zList.map(Number);
            if (zList.some(Number.isNaN)) throw new Error();
        } catch (_) {
            setError(sigmoidNote, 'z_values debe ser un array JSON de números.');
            return;
        }

        const done = setButtonBusy(sigmoidRunBtn, 'Calculando…');
        try {
            const response = await window.SD_API.post(
                `${ML_URL}/v1/classification/sigmoid-batch`, { z_values: zList }
            );
            const probs = extractList(response);
            if (!probs || probs.length !== zList.length) {
                throw new Error('Respuesta inesperada del API de sigmoid.');
            }
            renderSigmoidResults(zList, probs);
            const positives = probs.filter((p) => p >= 0.5).length;
            setSuccess(sigmoidNote,
                `OK — ${zList.length} valor(es) procesado(s). ${positives} ≥ 0.5.`);
        } catch (error) {
            setError(sigmoidNote, error.message || 'Error al calcular σ(z).');
        } finally {
            done();
        }
    });

    function extractList(response) {
        if (Array.isArray(response)) return response.map(Number);
        if (response && typeof response === 'object') {
            for (const value of Object.values(response)) {
                if (Array.isArray(value)) return value.map(Number);
            }
        }
        return null;
    }

    function renderSigmoidResults(zList, probs) {
        sigmoidMetrics.innerHTML = '';
        const positives = probs.filter((p) => p >= 0.5).length;
        [
            { label: 'Total', value: String(zList.length) },
            { label: 'σ(z) ≥ 0.5', value: String(positives) },
            { label: 'σ(z) < 0.5', value: String(zList.length - positives) },
            { label: 'σ(z) máx', value: formatNumber(Math.max(...probs), 4) },
            { label: 'σ(z) mín', value: formatNumber(Math.min(...probs), 4) }
        ].forEach((card) => {
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `<p class="metric-label">${escapeHtml(card.label)}</p>` +
                             `<p class="metric-value">${escapeHtml(card.value)}</p>`;
            sigmoidMetrics.appendChild(node);
        });

        // Chart with both the input z (line) and σ(z) (scatter)
        const points = zList
            .map((z, idx) => ({ x: z, y: probs[idx] }))
            .sort((a, b) => a.x - b.x);
        if (sigmoidChart) sigmoidChart.destroy();
        sigmoidChart = new Chart(qs('#sigmoidChart').getContext('2d'), {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'σ(z)',
                    data: points,
                    borderColor: '#5ad6c2',
                    backgroundColor: '#5ad6c2',
                    pointRadius: 5,
                    showLine: true,
                    tension: 0.3,
                    fill: false
                }, {
                    label: 'Threshold 0.5',
                    type: 'line',
                    data: [
                        { x: Math.min(...zList), y: 0.5 },
                        { x: Math.max(...zList), y: 0.5 }
                    ],
                    borderColor: '#f1c40f',
                    borderDash: [4, 4],
                    pointRadius: 0,
                    borderWidth: 1.5,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'z' } },
                    y: {
                        title: { display: true, text: 'σ(z)' },
                        min: 0,
                        max: 1
                    }
                }
            }
        });

        const tbody = sigmoidTable.querySelector('tbody');
        tbody.innerHTML = '';
        zList.forEach((z, idx) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${formatNumber(z, 4)}</td>` +
                           `<td>${formatNumber(probs[idx], 6)}</td>` +
                           `<td>${probs[idx] >= 0.5 ? '1' : '0'}</td>`;
            tbody.appendChild(tr);
        });

        sigmoidResults.hidden = false;
    }

    // ---------- Helpers ----------
    function setError(el, msg) {
        el.className = 'form-note error';
        el.textContent = msg;
    }
    function setSuccess(el, msg) {
        el.className = 'form-note success';
        el.textContent = msg;
    }
    function formatNumber(value, decimals = 4) {
        if (value == null || Number.isNaN(value)) return '—';
        if (!Number.isFinite(value)) return '∞';
        return Number(value).toFixed(decimals);
    }
    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;');
    }
});
