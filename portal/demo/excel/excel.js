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

    // ---------- Step 2b: upload + validate ----------
    uploadButton.addEventListener('click', async () => {
        if (!state.selectedFile) return;
        const note = qs('#uploadNote');
        note.className = 'form-note';
        note.textContent = '';
        const done = setButtonBusy(uploadButton, 'Subiendo…');
        try {
            const formData = new FormData();
            formData.append('file', state.selectedFile);
            const response = await window.SD_API.postFormData(
                `${INGEST_URL}/v1/ingest/excel`,
                formData
            );
            handleIngestResponse(response);
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo subir el archivo.';
            toast(error.message || 'Error al subir.', 'error');
        } finally {
            done();
        }
    });

    function handleIngestResponse(response) {
        state.datasetId = response.dataset_id;
        renderIngestSummary(response.summary, response.status);

        qs('#stepValidation').hidden = false;

        const isValid = response.status === 'validated';
        qs('#validatedBlock').hidden = !isValid;
        qs('#errorsBlock').hidden = isValid;

        if (isValid) {
            toast('Archivo validado. Listo para analizar.', 'success');
        } else {
            renderErrors(response.errors || []);
            toast(`Validación falló: ${(response.errors || []).length} error(es).`, 'error');
        }

        qs('#stepValidation').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        renderOpportunitySummary(response.summary);
        renderOpportunitiesTable();
        qs('#stepOpportunities').hidden = false;
        qs('#stepOpportunities').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function renderOpportunitySummary(summary) {
        const totalValue = summary.total_expected_value;
        const cards = [
            { label: 'Oportunidades', value: String(summary.total_opportunities || 0), variant: 'accent' },
            { label: 'PdVs con acciones', value: String(summary.total_pdvs_with_opportunities || 0) },
            {
                label: 'Impacto esperado',
                value: totalValue == null ? '—' : formatCurrency(totalValue),
                variant: totalValue == null ? '' : 'success',
                hint: totalValue == null ? 'Faltan precios en el dataset.' : 'Suma de drop size $ esperado.'
            },
            { label: 'Reglas evaluadas', value: String(summary.affinity_rules_evaluated || 0) }
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
            <td>${productLabel}</td>
            <td class="based-on">${escapeHtml(basedOn)}</td>
            <td class="numeric">${formatNumber(opp.lift, 2)}</td>
            <td class="numeric">${formatPercent(opp.confidence)}</td>
            <td class="numeric">${formatNumber(opp.expected_drop_size_units, 1)}</td>
            <td class="numeric">${amount}</td>
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
        return `$ ${Number(value).toLocaleString('es-BO', {
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
