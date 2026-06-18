'use strict';

/**
 * Playground ML — module logic.
 *
 * Maps three tabs (Linear, Logistic, Z-Score + Sigmoid) to the
 * `ml_functions` microservice endpoints. JSON inputs are parsed
 * permissively so users can type either `2.0` or `[1, 2, 3]` in
 * scalar-or-list fields.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

    const ML_URL = window.SD_CONFIG.ML_FUNCTIONS_URL;

    // ---------- Tabs ----------
    qsAll('.tab').forEach((tab) => {
        tab.addEventListener('click', () => {
            qsAll('.tab').forEach((other) => {
                other.classList.remove('is-active');
                other.setAttribute('aria-selected', 'false');
            });
            tab.classList.add('is-active');
            tab.setAttribute('aria-selected', 'true');
            const target = tab.dataset.tab;
            qsAll('.tab-panel').forEach((panel) => {
                panel.classList.toggle('is-active', panel.dataset.panel === target);
            });
        });
    });

    // ---------- Example fixtures (mirror the OpenAPI examples) ----------
    const EXAMPLES = {
        formLinearTrain: {
            x: '[1.0, 2.0, 3.0, 4.0]',
            y: '[3.0, 5.0, 7.0, 9.0]',
            w_in: '0.0', b_in: '0.0', alpha: '0.01', num_iters: '1000'
        },
        formLinearPredict: {
            x_test: '[7.0, 8.0]',
            w: '2.0', b: '1.0'
        },
        formLinearCostGrad: {
            x: '[1.0, 2.0, 3.0]',
            y: '[2.0, 4.0, 6.0]',
            w: '2.0', b: '0.0'
        },
        formLogisticTrain: {
            x_matrix: '[[1.0, 2.0], [1.0, 3.0], [1.0, 4.0]]',
            y: '[0.0, 1.0, 1.0]',
            w_in: '[0.0, 0.0]', b_in: '0.0',
            alpha: '0.01', num_iters: '1000'
        },
        formLogisticPredict: {
            x_matrix: '[[0.5, 1.2], [-0.1, 0.8]]',
            w: '[0.07, 0.06]', b: '-8.06'
        },
        formLogisticCostGrad: {
            x_matrix: '[[1.0, 2.0], [1.0, 3.0]]',
            y: '[0.0, 1.0]',
            w: '[0.1, 0.2]', b: '-0.5'
        },
        formNormalize: {
            x_matrix: '[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]'
        },
        formSigmoid: {
            z_values: '[0.0, 1.0, -1.0, 5.0, -5.0]'
        }
    };

    function applyExample(formEl) {
        const example = EXAMPLES[formEl.id];
        if (!example) return;
        Object.entries(example).forEach(([name, value]) => {
            const field = formEl.elements[name];
            if (field) field.value = value;
        });
    }

    // Initialize every form with the canonical example and wire the reset btn.
    qsAll('form[data-form]').forEach((formEl) => {
        applyExample(formEl);
        const resetBtn = formEl.querySelector('[data-reset]');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                applyExample(formEl);
                clearNote(formEl);
            });
        }
    });

    // ---------- Helpers ----------
    function getNote(formEl) { return formEl.querySelector('[data-note]'); }
    function clearNote(formEl) {
        const note = getNote(formEl);
        if (note) { note.className = 'form-note'; note.textContent = ''; }
    }
    function setError(formEl, msg) {
        const note = getNote(formEl);
        if (note) { note.className = 'form-note error'; note.textContent = msg; }
    }
    function setSuccess(formEl, msg) {
        const note = getNote(formEl);
        if (note) { note.className = 'form-note success'; note.textContent = msg; }
    }

    /**
     * Parses a JSON value, supporting bare numbers (e.g. '2.0').
     * Throws if the field is empty.
     */
    function parseJSONField(name, raw) {
        const text = String(raw == null ? '' : raw).trim();
        if (!text) throw new Error(`El campo "${name}" está vacío.`);
        try {
            return JSON.parse(text);
        } catch (_) {
            throw new Error(`"${name}" no es JSON válido. Ej: 2.0 o [1, 2, 3].`);
        }
    }
    function parseNumberField(name, raw) {
        if (raw == null || String(raw).trim() === '') {
            throw new Error(`El campo "${name}" está vacío.`);
        }
        const value = Number(raw);
        if (Number.isNaN(value)) throw new Error(`"${name}" debe ser numérico.`);
        return value;
    }
    function parseIntField(name, raw) {
        const value = parseNumberField(name, raw);
        if (!Number.isInteger(value)) throw new Error(`"${name}" debe ser entero.`);
        return value;
    }

    function formatNumber(value, decimals = 4) {
        if (value == null || Number.isNaN(value)) return '—';
        return Number(value).toFixed(decimals);
    }
    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;');
    }
    function pillsHTML(pills) {
        return `<div class="result-grid">${
            pills.map((p) =>
                `<div class="result-pill"><div class="label">${escapeHtml(p.label)}</div>` +
                `<div class="value">${escapeHtml(p.value)}</div></div>`
            ).join('')
        }</div>`;
    }
    function showResult(id, html) {
        const box = qs('#' + id);
        box.innerHTML = html;
        box.classList.add('is-shown');
    }
    function table(headers, rows) {
        const head = headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('');
        const body = rows.map((cells) =>
            `<tr>${cells.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`
        ).join('');
        return `<table class="result-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    // ---------- Chart.js helpers ----------
    const charts = {};
    function renderCostChart(canvasId, jHistory, label) {
        const wrapper = qs('#' + canvasId).closest('.chart-wrapper');
        wrapper.classList.add('is-shown');
        if (charts[canvasId]) charts[canvasId].destroy();
        const ctx = qs('#' + canvasId).getContext('2d');
        const labels = jHistory.map((_, idx) => idx);
        charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: label || 'Cost J',
                    data: jHistory,
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
                plugins: {
                    legend: { labels: { color: '#e6edf3' } },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { ticks: { color: '#8b97b3', maxTicksLimit: 10 }, grid: { color: '#26314f' }, title: { display: true, text: 'Iteración', color: '#8b97b3' } },
                    y: { ticks: { color: '#8b97b3' }, grid: { color: '#26314f' }, title: { display: true, text: 'Costo', color: '#8b97b3' } }
                }
            }
        });
    }

    // ---------- Form runner ----------
    const lastWeights = { linear: null, logistic: null };

    function bindForm(formId, buttonLabel, builder, handler) {
        const formEl = qs('#' + formId);
        formEl.addEventListener('submit', async (event) => {
            event.preventDefault();
            clearNote(formEl);
            let payload;
            try {
                payload = builder(formEl);
            } catch (error) {
                setError(formEl, error.message);
                return;
            }
            const submitButton = formEl.querySelector('button[type="submit"]');
            const done = setButtonBusy(submitButton, buttonLabel);
            try {
                const response = await window.SD_API.post(payload.url, payload.body);
                handler(response, formEl);
                setSuccess(formEl, 'OK.');
            } catch (error) {
                setError(formEl, error.message || 'Error en la llamada.');
                toast(error.message || 'Error en la llamada.', 'error');
            } finally {
                done();
            }
        });
    }

    // ---------- LINEAR: train ----------
    bindForm('formLinearTrain', 'Entrenando…',
        (formEl) => ({
            url: `${ML_URL}/v1/prediction/train-linear-regression`,
            body: {
                x: parseJSONField('x', formEl.elements.x.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w_in: parseJSONField('w_in', formEl.elements.w_in.value),
                b_in: parseNumberField('b_in', formEl.elements.b_in.value),
                alpha: parseNumberField('alpha', formEl.elements.alpha.value),
                num_iters: parseIntField('num_iters', formEl.elements.num_iters.value)
            }
        }),
        (response) => {
            lastWeights.linear = { w: response.w_final, b: response.b_final };
            const wText = Array.isArray(response.w_final)
                ? `[${response.w_final.map((v) => formatNumber(v)).join(', ')}]`
                : formatNumber(response.w_final);
            const lastCost = response.J_history && response.J_history.length
                ? response.J_history[response.J_history.length - 1] : null;
            showResult('resultLinearTrain',
                pillsHTML([
                    { label: 'w_final', value: wText },
                    { label: 'b_final', value: formatNumber(response.b_final) },
                    { label: 'Iteraciones', value: String(response.num_iters) },
                    { label: 'Costo final', value: formatNumber(lastCost, 6) }
                ])
            );
            renderCostChart('chartLinearTrain', response.J_history, 'Cost J (Linear)');
        }
    );

    // ---------- LINEAR: predict ----------
    bindForm('formLinearPredict', 'Prediciendo…',
        (formEl) => ({
            url: `${ML_URL}/v1/prediction/predict-linear-regression`,
            body: {
                x_test: parseJSONField('x_test', formEl.elements.x_test.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            }
        }),
        (response) => {
            const rows = response.predictions.map((p, idx) => [`x_test[${idx}]`, formatNumber(p)]);
            showResult('resultLinearPredict',
                `<h4>Predicciones</h4>${table(['Entrada', 'ŷ'], rows)}`
            );
        }
    );
    qs('#reuseLinearWeights').addEventListener('click', () => {
        if (!lastWeights.linear) {
            toast('Primero entrena el modelo lineal.', 'info');
            return;
        }
        const form = qs('#formLinearPredict');
        const { w, b } = lastWeights.linear;
        form.elements.w.value = JSON.stringify(w);
        form.elements.b.value = String(b);
        toast('Pesos copiados al formulario de predicción.', 'success');
    });

    // ---------- LINEAR: cost + gradient ----------
    bindForm('formLinearCostGrad', 'Calculando…',
        (formEl) => ({
            url: `${ML_URL}/v1/prediction/compute-cost`,
            body: {
                x: parseJSONField('x', formEl.elements.x.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            }
        }),
        async (response, formEl) => {
            // Also call gradient endpoint with the same payload so the user sees both.
            const body = {
                x: parseJSONField('x', formEl.elements.x.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            };
            let gradient = null;
            try {
                gradient = await window.SD_API.post(
                    `${ML_URL}/v1/prediction/compute-gradient`, body
                );
            } catch (_) { /* tolerate gradient failure */ }
            const pills = [
                { label: 'cost', value: formatNumber(response.cost, 6) },
                { label: 'dj_db', value: gradient ? formatNumber(gradient.dj_db, 6) : '—' },
                { label: 'dj_dw', value: gradient
                    ? (Array.isArray(gradient.dj_dw)
                        ? `[${gradient.dj_dw.map((v) => formatNumber(v, 4)).join(', ')}]`
                        : formatNumber(gradient.dj_dw, 6))
                    : '—' }
            ];
            showResult('resultLinearCostGrad', pillsHTML(pills));
        }
    );

    // ---------- LOGISTIC: train ----------
    bindForm('formLogisticTrain', 'Entrenando…',
        (formEl) => ({
            url: `${ML_URL}/v1/classification/train-logistic-regression`,
            body: {
                x_matrix: parseJSONField('x_matrix', formEl.elements.x_matrix.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w_in: parseJSONField('w_in', formEl.elements.w_in.value),
                b_in: parseNumberField('b_in', formEl.elements.b_in.value),
                alpha: parseNumberField('alpha', formEl.elements.alpha.value),
                num_iters: parseIntField('num_iters', formEl.elements.num_iters.value)
            }
        }),
        (response) => {
            lastWeights.logistic = { w: response.w, b: response.b };
            const wText = `[${response.w.map((v) => formatNumber(v)).join(', ')}]`;
            const lastCost = response.J_history && response.J_history.length
                ? response.J_history[response.J_history.length - 1] : null;
            showResult('resultLogisticTrain',
                pillsHTML([
                    { label: 'w', value: wText },
                    { label: 'b', value: formatNumber(response.b) },
                    { label: 'Costo final', value: formatNumber(lastCost, 6) }
                ])
            );
            renderCostChart('chartLogisticTrain', response.J_history, 'Cost J (Logistic)');
        }
    );

    // ---------- LOGISTIC: predict ----------
    bindForm('formLogisticPredict', 'Prediciendo…',
        (formEl) => ({
            url: `${ML_URL}/v1/classification/predict-logistic-classification`,
            body: {
                x_matrix: parseJSONField('x_matrix', formEl.elements.x_matrix.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            }
        }),
        (response) => {
            const rows = response.predictions.map((p, idx) => [`x_matrix[${idx}]`, String(p)]);
            const positives = response.predictions.filter((p) => p === 1).length;
            showResult('resultLogisticPredict',
                pillsHTML([
                    { label: 'Total', value: String(response.predictions.length) },
                    { label: 'Clase 1', value: String(positives) },
                    { label: 'Clase 0', value: String(response.predictions.length - positives) }
                ]) + table(['Entrada', 'Clase'], rows)
            );
        }
    );
    qs('#reuseLogisticWeights').addEventListener('click', () => {
        if (!lastWeights.logistic) {
            toast('Primero entrena el modelo logístico.', 'info');
            return;
        }
        const form = qs('#formLogisticPredict');
        const { w, b } = lastWeights.logistic;
        form.elements.w.value = JSON.stringify(w);
        form.elements.b.value = String(b);
        toast('Pesos copiados al formulario de predicción.', 'success');
    });

    // ---------- LOGISTIC: cost + gradient ----------
    bindForm('formLogisticCostGrad', 'Calculando…',
        (formEl) => ({
            url: `${ML_URL}/v1/classification/cost-logistic`,
            body: {
                x_matrix: parseJSONField('x_matrix', formEl.elements.x_matrix.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            }
        }),
        async (response, formEl) => {
            const body = {
                x_matrix: parseJSONField('x_matrix', formEl.elements.x_matrix.value),
                y: parseJSONField('y', formEl.elements.y.value),
                w: parseJSONField('w', formEl.elements.w.value),
                b: parseNumberField('b', formEl.elements.b.value)
            };
            let gradient = null;
            try {
                gradient = await window.SD_API.post(
                    `${ML_URL}/v1/classification/gradient-logistic`, body
                );
            } catch (_) {}
            // The cost endpoint returns either a `cost` field or a bare number;
            // tolerate both shapes.
            const costValue = (response && (response.cost ?? response));
            const pills = [
                { label: 'cost', value: formatNumber(typeof costValue === 'number' ? costValue : null, 6) },
                { label: 'dj_db', value: gradient ? formatNumber(gradient.dj_db, 6) : '—' },
                { label: 'dj_dw', value: gradient
                    ? `[${gradient.dj_dw.map((v) => formatNumber(v, 4)).join(', ')}]`
                    : '—' }
            ];
            showResult('resultLogisticCostGrad', pillsHTML(pills));
        }
    );

    // ---------- COMMON: normalize ----------
    bindForm('formNormalize', 'Normalizando…',
        (formEl) => ({
            url: `${ML_URL}/v1/common/normalize-features`,
            body: {
                x_matrix: parseJSONField('x_matrix', formEl.elements.x_matrix.value)
            }
        }),
        (response) => {
            const muText = `[${response.mu.map((v) => formatNumber(v)).join(', ')}]`;
            const sigmaText = `[${response.sigma.map((v) => formatNumber(v)).join(', ')}]`;
            const rows = response.x_norm.map((row, idx) => [`x[${idx}]`,
                `[${row.map((v) => formatNumber(v)).join(', ')}]`]);
            showResult('resultNormalize',
                pillsHTML([
                    { label: 'μ', value: muText },
                    { label: 'σ', value: sigmaText }
                ]) + `<h4>x normalizado</h4>` + table(['Fila', 'Valores'], rows)
            );
        }
    );

    // ---------- COMMON: sigmoid ----------
    bindForm('formSigmoid', 'Calculando…',
        (formEl) => ({
            url: `${ML_URL}/v1/classification/sigmoid-batch`,
            body: {
                z_values: parseJSONField('z_values', formEl.elements.z_values.value)
            }
        }),
        (response) => {
            // The endpoint may return a list directly, or {sigmoid_values}, etc.
            // Tolerate both: if response is an object, scan for an array.
            let values = Array.isArray(response) ? response : null;
            if (!values && response && typeof response === 'object') {
                for (const v of Object.values(response)) {
                    if (Array.isArray(v)) { values = v; break; }
                }
            }
            values = values || [];
            const rows = values.map((v, idx) => [`z[${idx}]`, formatNumber(v, 6)]);
            showResult('resultSigmoid',
                `<h4>σ(z)</h4>` + table(['Entrada', 'σ(z)'], rows)
            );
        }
    );
});
