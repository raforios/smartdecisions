'use strict';

/**
 * Linear Regression tab — trains and predicts with one or more numeric
 * features against a target column. Mirrors the "Precios de casas"
 * (houses.txt) and "Celsius → Fahrenheit" cases from frontend.ipynb:
 *   - Multi-feature scatter (each feature vs target) on a single chart
 *     with toggle-able series.
 *   - Z-Score normalization via /v1/common/normalize-features (so users
 *     can flip the optimizer from "diverge with alpha=0.3" to "converge
 *     with alpha=0.3 + normalize" live).
 *   - Train via /v1/prediction/train-linear-regression.
 *   - Predict via /v1/prediction/predict-linear-regression, applying the
 *     same Z-Score to the input point when training used normalization.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH || !window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;
    const STATE = window.SD_PLAYGROUND_STATE;
    const PARSER = window.SD_PLAYGROUND_PARSER;
    const ML_URL = window.SD_CONFIG.ML_FUNCTIONS_URL.replace(/\/$/, '');

    const empty = qs('#predictionEmpty');
    const content = qs('#predictionContent');
    const nameEl = qs('#predictionDatasetName');
    const statsEl = qs('#predictionDatasetStats');
    const featuresSel = qs('#predictionFeatures');
    const targetSel = qs('#predictionTarget');
    const normalizeChk = qs('#predictionNormalize');

    const trainBtn = qs('#predictionTrainButton');
    const trainNote = qs('#predictionTrainNote');
    const predictBtn = qs('#predictionPredictButton');
    const predictNote = qs('#predictionPredictNote');
    const resultsCard = qs('#predictionResults');
    const resultsGrid = qs('#predictionResultsGrid');

    let lastTrain = null;        // {w_final, b_final, J_history, normalize, mu, sigma, features}
    let featuresChart = null;
    let costChart = null;

    document.addEventListener('sd:dataset-loaded', (event) => {
        if (event.detail && event.detail.tab === 'prediction') refresh();
    });
    document.addEventListener('sd:tab-changed', (event) => {
        if (event.detail && event.detail.tab === 'prediction') refresh();
    });

    function refresh() {
        const ds = STATE.predictionDataset;
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
        applySensibleDefaults(ds);
        renderFeaturesChart();
        lastTrain = null;
        predictBtn.disabled = true;
        resultsCard.hidden = true;
        trainNote.className = 'form-note';
        trainNote.textContent = '';
    }

    function populateColumnSelectors(ds) {
        const labels = (ds.header && ds.header.length === ds.columnCount)
            ? ds.header
            : Array.from({ length: ds.columnCount }, (_, idx) => `col_${idx}`);
        featuresSel.innerHTML = '';
        targetSel.innerHTML = '';
        labels.forEach((label, idx) => {
            const numeric = PARSER.isNumericColumn(ds.rows, idx);
            const featureOpt = document.createElement('option');
            featureOpt.value = String(idx);
            featureOpt.textContent = `${idx}: ${label}${numeric ? '' : ' (no-num)'}`;
            featureOpt.disabled = !numeric;
            featuresSel.appendChild(featureOpt);

            const targetOpt = document.createElement('option');
            targetOpt.value = String(idx);
            targetOpt.textContent = `${idx}: ${label}${numeric ? '' : ' (no-num)'}`;
            targetOpt.disabled = !numeric;
            targetSel.appendChild(targetOpt);
        });
    }

    function applySensibleDefaults(ds) {
        const numericIdx = [];
        for (let i = 0; i < ds.columnCount; i++) {
            if (PARSER.isNumericColumn(ds.rows, i)) numericIdx.push(i);
        }
        if (numericIdx.length === 0) return;
        // Target: last numeric column. Features: all numeric columns except target.
        const target = numericIdx[numericIdx.length - 1];
        const features = numericIdx.filter((idx) => idx !== target);
        targetSel.value = String(target);
        qsAll('#predictionFeatures option').forEach((opt) => {
            opt.selected = features.includes(Number(opt.value));
        });
    }

    [featuresSel, targetSel].forEach((sel) =>
        sel.addEventListener('change', () => renderFeaturesChart())
    );

    // ---------- Feature scatters ----------
    function getSelectedFeatures() {
        return Array.from(featuresSel.options)
            .filter((opt) => opt.selected)
            .map((opt) => Number(opt.value));
    }

    function getTarget() {
        return Number(targetSel.value);
    }

    function buildMatrix() {
        const ds = STATE.predictionDataset;
        const features = getSelectedFeatures();
        const target = getTarget();
        const xs = [];
        const ys = [];
        for (const row of ds.rows) {
            const targetValue = row[target];
            const featureValues = features.map((idx) => row[idx]);
            if (typeof targetValue !== 'number'
                || featureValues.some((v) => typeof v !== 'number')) {
                continue;
            }
            xs.push(featureValues);
            ys.push(targetValue);
        }
        return { xs, ys, features, target };
    }

    function renderFeaturesChart() {
        const { xs, ys, features } = buildMatrix();
        if (xs.length === 0) {
            if (featuresChart) { featuresChart.destroy(); featuresChart = null; }
            return;
        }
        const palette = ['#5ad6c2', '#7aa2ff', '#f1c40f', '#ff6b6b', '#a8e0ff', '#ffb86b'];
        const labels = featureLabels(features);
        const datasets = features.map((featureIdx, position) => ({
            label: labels[position],
            data: xs.map((row, sample) => ({ x: row[position], y: ys[sample] })),
            backgroundColor: palette[position % palette.length],
            pointRadius: 3
        }));
        if (featuresChart) featuresChart.destroy();
        featuresChart = new Chart(qs('#predictionFeaturesChart').getContext('2d'), {
            type: 'scatter',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: {
                    x: { title: { display: true, text: 'feature value' } },
                    y: { title: { display: true, text: targetLabel() } }
                }
            }
        });
    }

    function featureLabels(featureIdxList) {
        const ds = STATE.predictionDataset;
        const header = ds.header && ds.header.length === ds.columnCount ? ds.header : null;
        return featureIdxList.map((idx) =>
            header ? `${idx}:${header[idx]}` : `col_${idx}`
        );
    }
    function targetLabel() {
        const ds = STATE.predictionDataset;
        const idx = getTarget();
        const header = ds.header && ds.header.length === ds.columnCount ? ds.header : null;
        return header ? `${idx}:${header[idx]}` : `col_${idx}`;
    }

    // ---------- Train ----------
    trainBtn.addEventListener('click', async () => {
        const ds = STATE.predictionDataset;
        if (!ds) return;
        trainNote.className = 'form-note';
        trainNote.textContent = '';
        const { xs, ys, features } = buildMatrix();
        if (xs.length < 2 || features.length === 0) {
            setError(trainNote, 'Necesito al menos 2 filas y 1 feature numérica.');
            return;
        }
        const alpha = Number(qs('#predictionAlpha').value);
        const iters = Number(qs('#predictionIters').value);
        if (!alpha || !iters || iters < 1) {
            setError(trainNote, 'Completá alpha y num_iters con valores válidos.');
            return;
        }

        const done = setButtonBusy(trainBtn, 'Entrenando…');
        try {
            let trainingX = xs;
            let mu = null;
            let sigma = null;
            if (normalizeChk.checked) {
                trainNote.classList.add('success');
                trainNote.textContent = 'Normalizando con Z-Score…';
                const normResponse = await window.SD_API.post(
                    `${ML_URL}/v1/common/normalize-features`, { x_matrix: xs }
                );
                trainingX = normResponse.x_norm;
                mu = normResponse.mu;
                sigma = normResponse.sigma;
            }
            const isSingleFeature = features.length === 1;
            const payload = {
                x: isSingleFeature ? trainingX.map((row) => row[0]) : trainingX,
                y: ys,
                w_in: isSingleFeature ? 0 : new Array(features.length).fill(0),
                b_in: 0,
                alpha,
                num_iters: iters
            };
            const response = await window.SD_API.post(
                `${ML_URL}/v1/prediction/train-linear-regression`, payload
            );
            const wFinal = Array.isArray(response.w_final)
                ? response.w_final
                : [response.w_final];
            const lastCost = response.J_history && response.J_history.length
                ? response.J_history[response.J_history.length - 1] : null;
            lastTrain = {
                w_final: wFinal,
                b_final: response.b_final,
                J_history: response.J_history || [],
                normalize: normalizeChk.checked,
                mu,
                sigma,
                features,
                isSingleFeature
            };
            renderResults(lastTrain, lastCost);
            renderCost(lastTrain.J_history);
            predictBtn.disabled = false;
            if (Number.isNaN(lastCost) || lastCost == null || !Number.isFinite(lastCost)) {
                setError(trainNote,
                    'Entrenó pero el costo final no es finito. Probá bajar el alpha o activar Z-Score.');
            } else {
                setSuccess(trainNote,
                    `Entrenamiento OK. Costo final: ${formatNumber(lastCost, 4)}.`);
            }
        } catch (error) {
            setError(trainNote, error.message || 'Error en el entrenamiento.');
        } finally {
            done();
        }
    });

    function renderResults(train, lastCost) {
        resultsCard.hidden = false;
        const cards = [
            { label: 'w_final', value: `[${train.w_final.map((v) => formatNumber(v, 4)).join(', ')}]` },
            { label: 'b_final', value: formatNumber(train.b_final, 4) },
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
        const safeHistory = history.map((v) =>
            (typeof v === 'number' && Number.isFinite(v)) ? v : null
        );
        costChart = new Chart(qs('#predictionCost').getContext('2d'), {
            type: 'line',
            data: {
                labels: safeHistory.map((_, idx) => idx),
                datasets: [{
                    label: 'Cost J',
                    data: safeHistory,
                    borderColor: '#5ad6c2',
                    backgroundColor: 'rgba(90, 214, 194, 0.18)',
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 2,
                    tension: 0.18,
                    spanGaps: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: 'Iteración' } },
                    y: { title: { display: true, text: 'Costo' }, type: 'logarithmic' }
                }
            }
        });
    }

    // ---------- Predict ----------
    predictBtn.addEventListener('click', async () => {
        if (!lastTrain) return;
        predictNote.className = 'form-note';
        predictNote.textContent = '';
        let rawX;
        try {
            rawX = JSON.parse(qs('#predictionPredX').value);
            if (!Array.isArray(rawX)) throw new Error();
            if (rawX.length !== lastTrain.features.length) {
                throw new Error(
                    `Esperaba ${lastTrain.features.length} valor(es), recibí ${rawX.length}.`
                );
            }
        } catch (error) {
            setError(predictNote, error.message
                || `"x" debe ser un array JSON con ${lastTrain.features.length} número(s).`);
            return;
        }

        let xUse = rawX;
        if (lastTrain.normalize && lastTrain.mu && lastTrain.sigma) {
            xUse = rawX.map((value, idx) =>
                (value - lastTrain.mu[idx]) / (lastTrain.sigma[idx] || 1)
            );
        }
        const payload = lastTrain.isSingleFeature
            ? { x_test: xUse[0], w: lastTrain.w_final[0], b: lastTrain.b_final }
            : { x_test: [xUse], w: lastTrain.w_final, b: lastTrain.b_final };

        const done = setButtonBusy(predictBtn, 'Calculando…');
        try {
            const response = await window.SD_API.post(
                `${ML_URL}/v1/prediction/predict-linear-regression`, payload
            );
            const predictions = response.predictions || [];
            const value = predictions[0];
            setSuccess(predictNote,
                `ŷ = ${formatNumber(value, 4)} para x = ${JSON.stringify(rawX)}`);
            toast(`Predicción: ${formatNumber(value, 4)}`, 'success');
        } catch (error) {
            setError(predictNote, error.message || 'Error al predecir.');
        } finally {
            done();
        }
    });

    // ---------- Helpers ----------
    function setError(el, msg) { el.className = 'form-note error'; el.textContent = msg; }
    function setSuccess(el, msg) { el.className = 'form-note success'; el.textContent = msg; }
    function formatNumber(value, decimals = 4) {
        if (value == null || Number.isNaN(value)) return '—';
        if (!Number.isFinite(value)) return '∞';
        return Number(value).toFixed(decimals);
    }
});
