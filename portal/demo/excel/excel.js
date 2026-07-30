'use strict';

/**
 * Excel → Oportunidades — module logic.
 *
 * Flow:
 *   1. Download the v1 template (GET ingest/v1/ingest/template/file).
 *   2. User drops/picks a file → POST multipart to ingest/v1/ingest/excel.
 *   3. If valid → enable "run analytics" button → POST analytics/v1/analytics/run/{id}.
 *   4. Render opportunities table sortable by columns and filterable by PdV.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

    const INGEST_URL = window.SD_CONFIG.INGEST_URL;
    const ANALYTICS_URL = window.SD_CONFIG.ANALYTICS_URL;

    const state = {
        selectedFile: null,
        datasetId: null,
        opportunities: [],
        sortKey: 'score',
        sortDir: 'desc'
    };

    // ---------- Step 1: template download ----------
    qs('#downloadTemplateButton').addEventListener('click', async () => {
        const button = qs('#downloadTemplateButton');
        const note = qs('#templateNote');
        const done = setButtonBusy(button, 'Descargando…');
        note.className = 'form-note';
        note.textContent = '';
        try {
            const response = await fetch(`${INGEST_URL}/v1/ingest/template/file`, {
                method: 'GET',
                headers: { 'Authorization': `Bearer ${window.SD_AUTH.getToken()}` }
            });
            if (response.status === 401) {
                window.SD_AUTH.clearSession();
                window.location.href = window.SD_CONFIG.LOGIN_PATH;
                return;
            }
            if (!response.ok) {
                throw new Error(`Error ${response.status} al descargar la plantilla.`);
            }
            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = downloadUrl;
            anchor.download = 'template_ventas_v1.xlsx';
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(downloadUrl);
            note.classList.add('success');
            note.textContent = 'Plantilla descargada.';
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo descargar la plantilla.';
        } finally {
            done();
        }
    });

    // ---------- Step 2: file picker + drag & drop ----------
    const fileInput = qs('#fileInput');
    const uploadZone = qs('#uploadZone');
    const fileChip = qs('#fileChip');
    const uploadButton = qs('#uploadButton');

    qs('#chooseFileLink').addEventListener('click', (event) => {
        event.preventDefault();
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (file) selectFile(file);
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
        uploadZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            uploadZone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach((eventName) => {
        uploadZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            uploadZone.classList.remove('dragover');
        });
    });
    uploadZone.addEventListener('drop', (event) => {
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (file) selectFile(file);
    });

    function selectFile(file) {
        const allowed = /\.(xlsx|csv)$/i;
        if (!allowed.test(file.name)) {
            toast('Solo se aceptan archivos .xlsx o .csv.', 'error');
            return;
        }
        state.selectedFile = file;
        fileChip.hidden = false;
        fileChip.textContent = `${file.name} · ${formatBytes(file.size)}`;
        uploadButton.disabled = false;
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    const FILES_URL = window.SD_CONFIG.FILES_URL;
    const INGEST_BUCKET = window.SD_CONFIG.INGEST_BUCKET;

    function contentTypeFor(fileName) {
        return fileName.toLowerCase().endsWith('.csv')
            ? 'text/csv'
            : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    }

    // ---------- Step 2b: direct-to-S3 upload (pre-signed) + validate ----------
    // Real sales exports easily exceed the ~10 MB API Gateway limit, so the file
    // is uploaded straight to S3 and only its key travels through the API.
    uploadButton.addEventListener('click', async () => {
        if (!state.selectedFile) return;
        const note = qs('#uploadNote');
        note.className = 'form-note';
        note.textContent = '';
        const done = setButtonBusy(uploadButton, 'Subiendo…');
        try {
            const file = state.selectedFile;
            const contentType = contentTypeFor(file.name);
            const safeName = file.name.replace(/[^\w.\-]+/g, '_');

            // 1) Ask FILES for a pre-signed PUT URL.
            note.textContent = 'Preparando la subida…';
            const presign = await window.SD_API.post(`${FILES_URL}/v1/s3/upload-presigned`, {
                bucket_name: INGEST_BUCKET,
                file_path: 'ingest/raw',
                file_name: `${Date.now()}_${safeName}`,
                validation: false,
                content_type: contentType
            });

            // 2) Upload the bytes straight to S3 (no API Gateway limit).
            note.textContent = `Subiendo ${formatBytes(file.size)} a almacenamiento seguro…`;
            const putResponse = await fetch(presign.presigned_url, {
                method: 'PUT',
                headers: { 'Content-Type': contentType },
                body: file
            });
            if (!putResponse.ok) {
                throw new Error(`Fallo al subir a S3 (${putResponse.status}).`);
            }

            // 3) Ask ingest to process it in the background (returns 202 + id).
            note.textContent = 'Encolando el procesamiento…';
            const accepted = await window.SD_API.post(`${INGEST_URL}/v1/ingest/excel-from-s3`, {
                file_key: presign.file_key,
                file_name: file.name
            });

            // 4) Poll for the outcome (large files take minutes to normalize).
            const result = await pollDatasetStatus(accepted.dataset_id, note);
            handleIngestResponse(result);
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo subir el archivo.';
            toast(error.message || 'Error al subir.', 'error');
        } finally {
            done();
        }
    });

    // Polls the dataset until the async job finishes (validated/failed).
    async function pollDatasetStatus(datasetId, note) {
        const intervalMs = 2500;
        const maxTries = 240; // ~10 min ceiling
        for (let attempt = 1; attempt <= maxTries; attempt += 1) {
            await new Promise((resolve) => setTimeout(resolve, intervalMs));
            const data = await window.SD_API.get(
                `${INGEST_URL}/v1/ingest/${encodeURIComponent(datasetId)}`
            );
            if (data.status && data.status !== 'processing') {
                return data;
            }
            if (note) {
                note.textContent = `Procesando el archivo… (${Math.round(attempt * intervalMs / 1000)} s)`;
            }
        }
        throw new Error('El procesamiento está tardando demasiado. Volvé a intentarlo en unos minutos.');
    }

    function handleIngestResponse(response) {
        state.datasetId = response.dataset_id;
        renderIngestSummary(response.summary, response.status);

        qs('#stepValidation').hidden = false;

        const isValid = response.status === 'validated';
        qs('#validatedBlock').hidden = !isValid;
        qs('#errorsBlock').hidden = isValid;

        const rejected = (response.summary && response.summary.error_rows) || 0;
        if (isValid) {
            renderRejectedNotice(response.dataset_id, response.summary);
            toast(rejected > 0
                ? `${response.summary.valid_rows} filas cargadas · ${rejected} quedaron fuera.`
                : 'Archivo validado. Listo para analizar.', 'success');
        } else {
            renderErrors(response.errors || []);
            toast('No se pudo cargar el archivo. Revisa los errores.', 'error');
        }

        qs('#stepValidation').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Shows how many rows were left out and offers the "fix & re-upload" file.
    function renderRejectedNotice(datasetId, summary) {
        const el = qs('#rejectedNotice');
        const rejected = (summary && summary.error_rows) || 0;
        if (rejected <= 0) {
            el.hidden = true;
            el.innerHTML = '';
            return;
        }
        el.hidden = false;
        el.innerHTML = `
            <p><strong>${(summary.valid_rows || 0).toLocaleString('es-BO')}</strong> filas se cargaron.
            <strong>${rejected.toLocaleString('es-BO')}</strong> quedaron fuera por datos incompletos —
            descargalas, completalas y volvé a subirlas.</p>
            <button type="button" class="btn btn-ghost btn-small" id="downloadRejectedButton">
                Descargar filas no cargadas (.csv)
            </button>`;
        qs('#downloadRejectedButton').addEventListener('click', () => downloadRejected(datasetId));
    }

    async function downloadRejected(datasetId) {
        const button = qs('#downloadRejectedButton');
        const done = setButtonBusy(button, 'Descargando…');
        try {
            const response = await fetch(
                `${INGEST_URL}/v1/ingest/${encodeURIComponent(datasetId)}/rejected`,
                { headers: { 'Authorization': `Bearer ${window.SD_AUTH.getToken()}` } }
            );
            if (!response.ok) {
                throw new Error(`Error ${response.status} al descargar.`);
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = 'filas_no_cargadas.csv';
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            toast(error.message || 'No se pudo descargar el archivo.', 'error');
        } finally {
            done();
        }
    }

    function renderIngestSummary(summary, status) {
        const valid = summary.valid_rows || 0;
        const total = summary.total_rows || 0;
        const errors = summary.error_rows || 0;
        const cards = [
            { label: 'Filas válidas', value: `${valid}/${total}`, variant: errors === 0 ? 'success' : 'warning' },
            { label: 'Errores', value: String(errors), variant: errors === 0 ? '' : 'warning' },
            { label: 'Puntos de venta', value: String(summary.unique_points_of_sale || 0) },
            { label: 'Productos', value: String(summary.unique_products || 0) },
            { label: 'Rango de fechas', value: formatDateRange(summary.date_range_start, summary.date_range_end), small: true }
        ];
        const container = qs('#ingestSummary');
        container.innerHTML = '';
        cards.forEach((card) => container.appendChild(metricCard(card)));
    }

    function renderErrors(errors) {
        const tbody = qs('#errorsTable tbody');
        tbody.innerHTML = '';
        if (errors.length === 0) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = '<td colspan="4">Sin detalles de error.</td>';
            tbody.appendChild(row);
            return;
        }
        errors.slice(0, 200).forEach((err) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${err.row ?? '-'}</td>
                <td>${escapeHtml(err.column ?? '-')}</td>
                <td>${err.value == null ? '<em>vacío</em>' : escapeHtml(String(err.value))}</td>
                <td>${escapeHtml(err.message ?? '')}</td>
            `;
            tbody.appendChild(row);
        });
        if (errors.length > 200) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = `<td colspan="4">… y ${errors.length - 200} errores adicionales.</td>`;
            tbody.appendChild(row);
        }
    }

    // ---------- Step 3: run analytics ----------
    qs('#runAnalyticsButton').addEventListener('click', async () => {
        if (!state.datasetId) return;
        const button = qs('#runAnalyticsButton');
        const note = qs('#runNote');
        note.className = 'form-note';
        note.textContent = 'Ejecutando motor — puede tardar unos segundos en datasets grandes…';
        const done = setButtonBusy(button, 'Analizando…');
        try {
            const response = await window.SD_API.post(
                `${ANALYTICS_URL}/v1/analytics/run/${encodeURIComponent(state.datasetId)}`
            );
            handleAnalyticsResponse(response);
            note.classList.add('success');
            note.textContent = 'Análisis completado.';
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'El motor falló.';
            toast(error.message || 'Error al ejecutar analytics.', 'error');
        } finally {
            done();
        }
    });

    function handleAnalyticsResponse(response) {
        state.opportunities = response.opportunities || [];
        const insight = deriveInsight(response.summary, state.opportunities);
        renderOpportunityHeadline(insight);
        renderOpportunitySummary(response.summary, insight);
        renderOpportunitiesTable();
        qs('#stepOpportunities').hidden = false;
        qs('#stepOpportunities').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Aggregates the raw opportunities into the plain-language story the manager
    // needs: how much, where, and which categories to push first.
    function deriveInsight(summary, opportunities) {
        const byCategory = new Map();
        opportunities.forEach((opp) => {
            const name = opp.recommended_product_name || opp.recommended_product_id || '—';
            const entry = byCategory.get(name) || { name, value: 0, count: 0 };
            entry.value += Number(opp.expected_drop_size_amount) || 0;
            entry.count += 1;
            byCategory.set(name, entry);
        });
        const ranking = [...byCategory.values()].sort((a, b) => b.value - a.value);
        return {
            count: summary.total_opportunities || 0,
            pdvs: summary.total_pdvs_with_opportunities || 0,
            totalValue: summary.total_expected_value,
            topCategory: ranking[0] || null,
            top3: ranking.slice(0, 3)
        };
    }

    function renderOpportunityHeadline(insight) {
        const el = qs('#opportunityHeadline');
        if (!insight.count) {
            el.innerHTML =
                '<p class="insight-empty">No se encontraron oportunidades con los datos ' +
                'actuales. Probá con un período más amplio o un catálogo con más variedad.</p>';
            return;
        }
        const count = insight.count.toLocaleString('es-BO');
        const pdvs = insight.pdvs.toLocaleString('es-BO');
        const valueText = insight.totalValue == null ? null : formatCurrency(insight.totalValue);
        const lead = valueText
            ? `Detectamos <strong>${count} acciones de venta</strong> en <strong>${pdvs} ` +
              `puntos de venta</strong>, con una venta potencial de <strong>${valueText}</strong>.`
            : `Detectamos <strong>${count} acciones de venta</strong> en <strong>${pdvs} ` +
              'puntos de venta</strong>.';
        const top = insight.topCategory
            ? ` La mayor oportunidad está en <strong>${escapeHtml(insight.topCategory.name)}</strong>.`
            : '';
        const chips = insight.top3.map((cat, index) =>
            `<span class="insight-chip"><span class="chip-rank">${index + 1}</span> ` +
            `${escapeHtml(cat.name)} · <strong>${formatCurrency(cat.value)}</strong></span>`
        ).join('');
        el.innerHTML = `
            <p class="insight-lead">${lead}${top}</p>
            <p class="insight-action">👉 Acción sugerida: prioriza ofrecer estas categorías en la
             próxima visita a cada punto de venta.</p>
            ${chips ? `<div class="insight-topcats">
                <span class="insight-topcats-label">Top categorías por venta potencial:</span>
                ${chips}</div>` : ''}
        `;
    }

    function renderOpportunitySummary(summary, insight) {
        const totalValue = summary.total_expected_value;
        const cards = [
            {
                label: 'Acciones sugeridas', value: String(summary.total_opportunities || 0),
                variant: 'accent', hint: 'Recomendaciones de venta cruzada'
            },
            {
                label: 'Puntos de venta', value: String(summary.total_pdvs_with_opportunities || 0),
                hint: 'Con al menos una recomendación'
            },
            {
                label: 'Venta potencial',
                value: totalValue == null ? '—' : formatCurrency(totalValue),
                variant: totalValue == null ? '' : 'success',
                hint: totalValue == null ? 'Faltan precios en el archivo.' : 'Impacto esperado en Bs'
            },
            {
                label: 'Categoría estrella',
                value: insight.topCategory ? insight.topCategory.name : '—',
                hint: 'Mayor venta potencial'
            }
        ];
        const container = qs('#opportunitySummary');
        container.innerHTML = '';
        cards.forEach((card) => container.appendChild(metricCard(card)));
    }

    // ---------- Step 4: sortable + filterable table ----------
    qs('#pdvFilter').addEventListener('input', () => renderOpportunitiesTable());

    qsAll('#opportunitiesTable thead th[data-sort]').forEach((header) => {
        header.addEventListener('click', () => {
            const key = header.dataset.sort;
            if (state.sortKey === key) {
                state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                state.sortKey = key;
                state.sortDir = key === 'pdv' || key === 'product' || key === 'based_on' ? 'asc' : 'desc';
            }
            renderOpportunitiesTable();
        });
    });

    function renderOpportunitiesTable() {
        const tbody = qs('#opportunitiesTable tbody');
        tbody.innerHTML = '';
        const filterText = qs('#pdvFilter').value.trim().toLowerCase();
        const filtered = state.opportunities.filter((opp) => {
            if (!filterText) return true;
            const haystack = [
                opp.pdv_id,
                opp.pdv_name,
                opp.recommended_product_id,
                opp.recommended_product_name
            ].filter(Boolean).join(' ').toLowerCase();
            return haystack.includes(filterText);
        });
        const sorted = sortOpportunities(filtered, state.sortKey, state.sortDir);
        qs('#filterCount').textContent =
            `${sorted.length} de ${state.opportunities.length} oportunidades`;
        updateSortHeaders();

        if (sorted.length === 0) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = '<td colspan="8">Sin oportunidades para ese filtro.</td>';
            tbody.appendChild(row);
            return;
        }
        sorted.forEach((opp) => tbody.appendChild(opportunityRow(opp)));
    }

    function sortOpportunities(items, key, direction) {
        const factor = direction === 'asc' ? 1 : -1;
        const keyToValue = {
            pdv: (opp) => (opp.pdv_name || opp.pdv_id || '').toLowerCase(),
            product: (opp) => (opp.recommended_product_name || opp.recommended_product_id || '').toLowerCase(),
            based_on: (opp) => (opp.based_on_products || []).join(', ').toLowerCase(),
            lift: (opp) => opp.lift || 0,
            confidence: (opp) => opp.confidence || 0,
            units: (opp) => opp.expected_drop_size_units || 0,
            amount: (opp) => opp.expected_drop_size_amount || 0,
            score: (opp) => opp.opportunity_score || 0
        };
        const valueOf = keyToValue[key] || keyToValue.score;
        return [...items].sort((a, b) => {
            const va = valueOf(a);
            const vb = valueOf(b);
            if (va < vb) return -1 * factor;
            if (va > vb) return  1 * factor;
            return 0;
        });
    }

    function updateSortHeaders() {
        qsAll('#opportunitiesTable thead th[data-sort]').forEach((header) => {
            header.classList.remove('asc', 'desc');
            if (header.dataset.sort === state.sortKey) {
                header.classList.add(state.sortDir);
            }
        });
    }

    function opportunityRow(opp) {
        const row = document.createElement('tr');
        row.title = opp.rationale || '';
        const pdvLabel = opp.pdv_name ? `${opp.pdv_name} <span class="based-on">(${opp.pdv_id})</span>` : opp.pdv_id;
        const productLabel = opp.recommended_product_name
            ? `${opp.recommended_product_name} <span class="based-on">(${opp.recommended_product_id})</span>`
            : opp.recommended_product_id;
        const basedOn = (opp.based_on_products || []).join(', ') || '—';
        const amount = opp.expected_drop_size_amount != null
            ? formatCurrency(opp.expected_drop_size_amount)
            : '—';
        row.innerHTML = `
            <td>${pdvLabel}</td>
            <td><strong>${productLabel}</strong></td>
            <td class="based-on">${escapeHtml(basedOn)}</td>
            <td class="numeric strong">${amount}</td>
            <td class="numeric">${formatNumber(opp.expected_drop_size_units, 1)}</td>
            <td class="numeric">${formatPercent(opp.confidence)}</td>
            <td class="numeric">${formatNumber(opp.lift, 2)}</td>
            <td class="numeric">${formatNumber(opp.opportunity_score, 2)}</td>
        `;
        return row;
    }

    // ---------- helpers ----------
    function metricCard({ label, value, variant, hint }) {
        const node = document.createElement('div');
        node.className = 'metric';
        node.innerHTML = `
            <p class="metric-label">${escapeHtml(label)}</p>
            <p class="metric-value ${variant || ''}">${escapeHtml(String(value))}</p>
            ${hint ? `<p class="metric-hint">${escapeHtml(hint)}</p>` : ''}
        `;
        return node;
    }

    function formatNumber(value, decimals = 2) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    function formatPercent(value) {
        if (value == null || isNaN(value)) return '—';
        return `${(Number(value) * 100).toFixed(1)}%`;
    }

    function formatCurrency(value) {
        if (value == null || isNaN(value)) return '—';
        return `Bs ${Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}`;
    }

    function formatDateRange(start, end) {
        if (!start && !end) return '—';
        return `${start || '?'} → ${end || '?'}`;
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }
});
