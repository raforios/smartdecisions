'use strict';

/**
 * Classification tab — logistic regression over a 2-feature + binary-label
 * dataset. Mirrors the "Admisión universitaria" case (ex2data1.txt) from
 * notebooks/frontend.ipynb:
 *   1. Scatter of both classes.
 *   2. Train via ML_FUNCTIONS /v1/classification/train-logistic-regression.
 *   3. Overlay decision boundary `y = -(b + w0*x) / w1`.
 *   4. Predict a custom (x, y) point via /sigmoid-batch and plot it.
 *   5. Cost J vs iteration chart from J_history.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH || !window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;
    const STATE = window.SD_PLAYGROUND_STATE;
    const PARSER = window.SD_PLAYGROUND_PARSER;
    const ML_URL = window.SD_CONFIG.ML_FUNCTIONS_URL.replace(/\/$/, '');

    const empty = qs('#classificationEmpty');
    const content = qs('#classificationContent');
    const nameEl = qs('#classificationDatasetName');
    const statsEl = qs('#classificationDatasetStats');
    const featureXSel = qs('#classificationFeatureX');
    const featureYSel = qs('#classificationFeatureY');
    const labelSel = qs('#classificationLabelCol');
    const normalizeChk = qs('#classificationNormalize');

    const trainBtn = qs('#classificationTrainButton');
    const trainNote = qs('#classificationTrainNote');
    const predictBtn = qs('#classificationPredictButton');
    const predictNote = qs('#classificationPredictNote');
    const resultsCard = qs('#classificationResults');
    const resultsGrid = qs('#classificationResultsGrid');

    let lastTrain = null;           // {w, b, J_history, normalize, mu, sigma}
    let lastPredictionPoint = null; // {x, y, probability}
    let scatterChart = null;
    let costChart = null;

    document.addEventListener('sd:dataset-loaded', (event) => {
        if (event.detail && event.detail.tab === 'classification') refresh();
    });
    document.addEventListener('sd:tab-changed', (event) => {
        if (event.detail && event.detail.tab === 'classification') refresh();
    });

    function refresh() {
        const ds = STATE.classificationDataset;
        if (!ds) {
            empty.hidden = false;
            content.hidden = true;
            return;
        }
        empty.hidden = true;
        content.hidden = false;
        nameEl.textContent = ds.fileKey;
        statsEl.textContent = `${ds.rows.length} filas · ${ds.columnCount} columnas`;
        populateColumnSelectors(ds);
        // Suggest sensible defaults: first two numeric columns as X/Y, last column as label.
        applySensibleDefaults(ds);
        renderScatter();
        lastTrain = null;
        lastPredictionPoint = null;
        predictBtn.disabled = true;
        resultsCard.hidden = true;
        trainNote.className = 'form-note';
        trainNote.textContent = '';
    }

    function populateColumnSelectors(ds) {
        const labels = (ds.header && ds.header.length === ds.columnCount)
            ? ds.header
            : Array.from({ length: ds.columnCount }, (_, idx) => `col_${idx}`);
        [featureXSel, featureYSel, labelSel].forEach((sel) => {
            sel.innerHTML = '';
            labels.forEach((label, idx) => {
                const opt = document.createElement('option');
                opt.value = String(idx);
                opt.textContent = `${idx}: ${label}`;
                sel.appendChild(opt);
            });
        });
    }

    function applySensibleDefaults(ds) {
        const numericIdx = [];
        for (let i = 0; i < ds.columnCount; i++) {
            if (PARSER.isNumericColumn(ds.rows, i)) numericIdx.push(i);
        }
        featureXSel.value = String(numericIdx[0] ?? 0);
        featureYSel.value = String(numericIdx[1] ?? Math.min(1, ds.columnCount - 1));
        labelSel.value = String(numericIdx[numericIdx.length - 1] ?? ds.columnCount - 1);
    }

    // ---------- Scatter ----------
    [featureXSel, featureYSel, labelSel].forEach((sel) =>
        sel.addEventListener('change', () => renderScatter())
    );

    function extractColumns() {
        const ds = STATE.classificationDataset;
        const xi = Number(featureXSel.value);
        const yi = Number(featureYSel.value);
        const li = Number(labelSel.value);
        const points = ds.rows
            .filter((row) =>
                typeof row[xi] === 'number'
                && typeof row[yi] === 'number'
                && typeof row[li] === 'number'
            )
            .map((row) => ({ x: row[xi], y: row[yi], label: row[li] }));
        return points;
    }

    function applyZScoreIfRequested(points) {
        if (!normalizeChk.checked) {
            return { points, mu: null, sigma: null };
        }
        const xs = points.map((p) => p.x);
        const ys = points.map((p) => p.y);
        const muX = mean(xs);
        const muY = mean(ys);
        const sigX = std(xs, muX);
        const sigY = std(ys, muY);
        const normalized = points.map((p) => ({
            x: (p.x - muX) / (sigX || 1),
            y: (p.y - muY) / (sigY || 1),
            label: p.label
        }));
        return { points: normalized, mu: [muX, muY], sigma: [sigX, sigY] };
    }

    function renderScatter() {
        const points = extractColumns();
        const { points: visualPoints } = applyZScoreIfRequested(points);

        const positives = visualPoints.filter((p) => p.label === 1);
        const negatives = visualPoints.filter((p) => p.label === 0);
        const others = visualPoints.filter((p) => p.label !== 0 && p.label !== 1);

        const datasets = [
            {
                label: 'Clase 1',
                data: positives.map((p) => ({ x: p.x, y: p.y })),
                backgroundColor: '#5ad6c2',
                pointRadius: 5,
                pointStyle: 'rectRot'
            },
            {
                label: 'Clase 0',
                data: negatives.map((p) => ({ x: p.x, y: p.y })),
                backgroundColor: '#ff6b6b',
                pointRadius: 4
            }
        ];
        if (others.length) {
            datasets.push({
                label: `Otras (${others.length})`,
                data: others.map((p) => ({ x: p.x, y: p.y })),
                backgroundColor: '#7aa2ff',
                pointRadius: 3
            });
        }
        // Append decision boundary line dataset when we have a trained model.
        if (lastTrain) {
            const boundary = computeBoundaryLine(visualPoints, lastTrain);
            if (boundary) {
                datasets.push({
                    label: 'Frontera de decisión',
                    type: 'line',
                    data: boundary,
                    borderColor: '#f1c40f',
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    borderWidth: 2,
                    fill: false,
                    showLine: true
                });
            }
        }
        if (lastPredictionPoint) {
            datasets.push({
                label: `Predicción (${lastPredictionPoint.x}, ${lastPredictionPoint.y})`,
                data: [{ x: lastPredictionPoint.x, y: lastPredictionPoint.y }],
                backgroundColor: '#7aa2ff',
                pointRadius: 8,
                pointStyle: 'triangle'
            });
        }

        if (scatterChart) scatterChart.destroy();
        scatterChart = new Chart(qs('#classificationScatter').getContext('2d'), {
            type: 'scatter',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: labelFor(featureXSel) } },
                    y: { title: { display: true, text: labelFor(featureYSel) } }
                }
            }
        });
    }

    function labelFor(sel) {
        const opt = sel.options[sel.selectedIndex];
        return opt ? opt.textContent : '';
    }

    function computeBoundaryLine(points, train) {
        if (!train || !train.w || train.w.length < 2 || train.b == null) return null;
        const xs = points.map((p) => p.x);
        const xMin = Math.min(...xs);
        const xMax = Math.max(...xs);
        // y = -(b + w0*x) / w1
        const w0 = train.w[0];
        const w1 = train.w[1];
        if (Math.abs(w1) < 1e-9) return null;
        return [
            { x: xMin, y: -(train.b + w0 * xMin) / w1 },
            { x: xMax, y: -(train.b + w0 * xMax) / w1 }
        ];
    }

    // ---------- Train ----------
    trainBtn.addEventListener('click', async () => {
        const ds = STATE.classificationDataset;
        if (!ds) return;
        trainNote.className = 'form-note';
        trainNote.textContent = '';
        const points = extractColumns();
        if (points.length < 2) {
            setError(trainNote, 'Necesito al menos 2 filas con números válidos.');
            return;
        }
        const { points: normalized, mu, sigma } = applyZScoreIfRequested(points);
        const xMatrix = normalized.map((p) => [p.x, p.y]);
        const yVector = normalized.map((p) => p.label);
        let w0;
        try {
            w0 = JSON.parse(qs('#classificationW0').value);
            if (!Array.isArray(w0) || w0.length !== 2) throw new Error();
        } catch (_) {
            setError(trainNote, '`w₀ inicial` debe ser un array JSON de 2 números, ej. [0, 0].');
            return;
        }
        const payload = {
            x_matrix: xMatrix,
            y: yVector,
            w_in: w0,
            b_in: Number(qs('#classificationB0').value),
            alpha: Number(qs('#classificationAlpha').value),
            num_iters: Number(qs('#classificationIters').value)
        };

        const done = setButtonBusy(trainBtn, 'Entrenando…');
        try {
            const response = await window.SD_API.post(
                `${ML_URL}/v1/classification/train-logistic-regression`, payload
            );
            lastTrain = {
                w: response.w,
                b: response.b,
                J_history: response.J_history || [],
                normalize: normalizeChk.checked,
                mu,
                sigma
            };
            const lastCost = lastTrain.J_history.length
                ? lastTrain.J_history[lastTrain.J_history.length - 1] : null;
            renderResults(lastTrain, lastCost);
            renderScatter();
            renderCost(lastTrain.J_history);
            predictBtn.disabled = false;
            setSuccess(trainNote, `Entrenamiento OK. Costo final: ${formatNumber(lastCost, 4)}.`);
        } catch (error) {
            setError(trainNote, error.message || 'Error en el entrenamiento.');
        } finally {
            done();
        }
    });

    function renderResults(train, lastCost) {
        resultsCard.hidden = false;
        const cards = [
            { label: 'w', value: `[${train.w.map((v) => formatNumber(v, 4)).join(', ')}]` },
            { label: 'b', value: formatNumber(train.b, 4) },
            { label: 'Costo final', value: formatNumber(lastCost, 6) },
            { label: 'Iteraciones', value: String(train.J_history.length) }
        ];
        if (train.normalize) {
            cards.push(
                { label: 'μ', value: `[${train.mu.map((v) => formatNumber(v, 3)).join(', ')}]` },
                { label: 'σ', value: `[${train.sigma.map((v) => formatNumber(v, 3)).join(', ')}]` }
            );
        }
        resultsGrid.innerHTML = '';
        cards.forEach((card) => {
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `<p class="metric-label">${card.label}</p>` +
                             `<p class="metric-value">${card.value}</p>`;
            resultsGrid.appendChild(node);
        });
    }

    function renderCost(history) {
        if (costChart) costChart.destroy();
        if (!history || history.length === 0) return;
        const labels = history.map((_, idx) => idx);
        costChart = new Chart(qs('#classificationCost').getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Cost J',
                    data: history,
                    borderColor: '#5ad6c2',
                    backgroundColor: 'rgba(90, 214, 194, 0.18)',
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                    tension: 0.18
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'Iteración' } },
                    y: { title: { display: true, text: 'Costo' } }
                }
            }
        });
    }

    // ---------- Predict a custom point ----------
    predictBtn.addEventListener('click', async () => {
        if (!lastTrain) return;
        predictNote.className = 'form-note';
        predictNote.textContent = '';
        const xRaw = Number(qs('#classificationPredX').value);
        const yRaw = Number(qs('#classificationPredY').value);
        if (Number.isNaN(xRaw) || Number.isNaN(yRaw)) {
            setError(predictNote, 'Ambos campos deben ser numéricos.');
            return;
        }
        let xUse = xRaw;
        let yUse = yRaw;
        if (lastTrain.normalize && lastTrain.mu && lastTrain.sigma) {
            xUse = (xRaw - lastTrain.mu[0]) / (lastTrain.sigma[0] || 1);
            yUse = (yRaw - lastTrain.mu[1]) / (lastTrain.sigma[1] || 1);
        }
        const z = lastTrain.w[0] * xUse + lastTrain.w[1] * yUse + lastTrain.b;

        const done = setButtonBusy(predictBtn, 'Calculando…');
        try {
            const response = await window.SD_API.post(
                `${ML_URL}/v1/classification/sigmoid-batch`, { z_values: [z] }
            );
            const probability = extractSigmoid(response);
            const verdict = probability >= 0.5 ? 'Clase 1 (positivo)' : 'Clase 0 (negativo)';
            setSuccess(
                predictNote,
                `Probabilidad: ${(probability * 100).toFixed(2)}% → ${verdict}`
            );
            // Plot the input point on the (possibly normalized) scatter.
            lastPredictionPoint = { x: xUse, y: yUse, probability };
            renderScatter();
            toast(`Predicción: ${(probability * 100).toFixed(2)}%`, 'success');
        } catch (error) {
            setError(predictNote, error.message || 'Error al calcular probabilidad.');
        } finally {
            done();
        }
    });

    function extractSigmoid(response) {
        if (Array.isArray(response)) return Number(response[0]);
        if (response && typeof response === 'object') {
            for (const value of Object.values(response)) {
                if (Array.isArray(value) && value.length) return Number(value[0]);
                if (typeof value === 'number') return value;
            }
        }
        return NaN;
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
    function mean(values) {
        return values.reduce((acc, v) => acc + v, 0) / Math.max(values.length, 1);
    }
    function std(values, mu) {
        const variance = values.reduce((acc, v) => acc + (v - mu) ** 2, 0)
                       / Math.max(values.length, 1);
        return Math.sqrt(variance);
    }
    function formatNumber(value, decimals = 4) {
        if (value == null || Number.isNaN(value)) return '—';
        return Number(value).toFixed(decimals);
    }
});
