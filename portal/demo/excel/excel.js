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

    // The dataset id is persisted so a page reload / session refresh never forces
    // re-uploading the file: the data already lives in S3 + DynamoDB.
    const DATASET_KEY = 'sd_excel_dataset_id';
    const CACHE_KEY = 'sd_excel_results';
    const VIEW_KEY = 'sd_excel_view';
    const state = {
        selectedFile: null,
        datasetId: sessionStorage.getItem(DATASET_KEY) || null,
        opportunities: [],
        sortKey: 'score',
        sortDir: 'desc'
    };

    function setDataset(datasetId) {
        // A different file invalidates every cached result of the previous one.
        if (datasetId !== state.datasetId) sessionStorage.removeItem(CACHE_KEY);
        state.datasetId = datasetId;
        if (datasetId) sessionStorage.setItem(DATASET_KEY, datasetId);
        else sessionStorage.removeItem(DATASET_KEY);
    }

    // ---------- Result cache ----------
    // Analyses are expensive (the affinity engine takes ~30 s) and the session
    // can expire mid-review. Keeping the computed payloads in sessionStorage
    // means a reload — or a re-login in the same tab — restores exactly the
    // screen the user was reading, instead of forcing a re-run.
    function readCache() {
        try {
            const cache = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
            if (cache && cache.datasetId === state.datasetId) return cache;
        } catch (parseError) {
            // A corrupt cache is not an error: it just means "nothing cached".
        }
        return { datasetId: state.datasetId, results: {} };
    }

    function cacheResult(kind, payload) {
        const cache = readCache();
        cache.datasetId = state.datasetId;
        cache.results[kind] = { payload, at: Date.now() };
        try {
            sessionStorage.setItem(CACHE_KEY, JSON.stringify(cache));
        } catch (quotaError) {
            // The cache is a convenience; running out of quota must never break
            // the analysis the user just asked for.
        }
    }

    function cachedResult(kind) {
        return readCache().results[kind] || null;
    }

    const STAMP_IDS = {
        summary: 'stampSummary',
        opportunities: 'stampOpportunities',
        segmentation: 'stampSegmentation'
    };

    function markStamp(kind, timestamp) {
        const node = document.getElementById(STAMP_IDS[kind]);
        if (!node) return;
        const time = new Date(timestamp).toLocaleTimeString('es-BO',
            { hour: '2-digit', minute: '2-digit' });
        node.textContent = `Calculado a las ${time}`;
    }

    // The analysis sections are mutually exclusive views (tab-like): showing one
    // hides the others, so the page doesn't grow into a long vertical stack.
    const ANALYSIS_SECTIONS = ['stepDashboard', 'stepForecast', 'stepSegmentation',
        'stepOpportunities'];
    function showAnalysisView(sectionId, scroll = true) {
        ANALYSIS_SECTIONS.forEach((id) => { qs('#' + id).hidden = (id !== sectionId); });
        sessionStorage.setItem(VIEW_KEY, sectionId);
        if (scroll) {
            qs('#' + sectionId).scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

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

    // PUT the file to S3 with real upload-progress feedback. `fetch` cannot
    // report upload progress, so we use XMLHttpRequest: a 37 MB file takes
    // minutes on a slow link, and without a live percentage the UI looks frozen.
    function putToS3WithProgress(url, file, contentType, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('PUT', url);
            xhr.setRequestHeader('Content-Type', contentType);
            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable && onProgress) {
                    onProgress(event.loaded / event.total);
                }
            });
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) resolve();
                else reject(new Error(`Fallo al subir a S3 (${xhr.status}).`));
            };
            xhr.onerror = () => reject(new Error('Error de red al subir el archivo a S3.'));
            xhr.send(file);
        });
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

            // 2) Upload the bytes straight to S3 (no API Gateway limit), with a
            //    live percentage so a large/slow upload never looks frozen.
            const sizeLabel = formatBytes(file.size);
            note.textContent = `Subiendo ${sizeLabel} a almacenamiento seguro… 0%`;
            await putToS3WithProgress(presign.presigned_url, file, contentType, (ratio) => {
                note.textContent =
                    `Subiendo ${sizeLabel} a almacenamiento seguro… ${Math.round(ratio * 100)}%`;
            });

            // 3) Ask ingest to read it from S3, validate and normalize —
            //    synchronously. The response already carries the outcome.
            note.textContent = 'Validando y procesando el archivo…';
            const result = await window.SD_API.post(`${INGEST_URL}/v1/ingest/excel-from-s3`, {
                file_key: presign.file_key,
                file_name: file.name
            });
            handleIngestResponse(result);
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo subir el archivo.';
            toast(error.message || 'Error al subir.', 'error');
        } finally {
            done();
        }
    });

    function handleIngestResponse(response) {
        setDataset(response.dataset_id);
        renderIngestSummary(response.summary, response.status);

        qs('#stepValidation').hidden = false;

        const isValid = response.status === 'validated';
        qs('#validatedBlock').hidden = !isValid;
        qs('#errorsBlock').hidden = isValid;

        const rejected = (response.summary && response.summary.error_rows) || 0;
        if (isValid) {
            renderRejectedNotice(response.dataset_id, response.summary);
            toast(rejected > 0
                ? `${formatInt(response.summary.valid_rows)} filas cargadas · ` +
                  `${formatInt(rejected)} quedaron fuera.`
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
            <p><strong>${formatInt(summary.valid_rows || 0)}</strong> filas se cargaron.
            <strong>${formatInt(rejected)}</strong> quedaron fuera por datos incompletos —
            descárgalas, complétalas y vuelve a subirlas.</p>
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
            {
                label: 'Filas válidas', value: `${formatInt(valid)} / ${formatInt(total)}`,
                variant: errors === 0 ? 'success' : 'warning'
            },
            { label: 'Errores', value: formatInt(errors), variant: errors === 0 ? '' : 'warning' },
            { label: 'Puntos de venta', value: formatInt(summary.unique_points_of_sale || 0) },
            { label: 'Productos', value: formatInt(summary.unique_products || 0) },
            {
                label: 'Rango de fechas',
                value: formatDateRange(summary.date_range_start, summary.date_range_end)
            }
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

    // If a dataset was already ingested (persisted), skip the upload step and
    // show the analysis menu directly — no need to re-upload after a reload.
    if (state.datasetId) {
        qs('#stepValidation').hidden = false;
        qs('#validatedBlock').hidden = false;
        const note = qs('#runNote');
        note.className = 'form-note success';
        note.textContent = 'Tu archivo sigue cargado. Elige un análisis (o sube otro archivo arriba).';
    }

    // Brings back the exact screen the user was reading before a reload or a
    // re-login: the view only changes when they choose another analysis.
    const VIEW_TO_KIND = {
        stepDashboard: 'summary',
        stepOpportunities: 'opportunities',
        stepSegmentation: 'segmentation',
        stepForecast: 'forecast'
    };

    function restoreLastView() {
        const sectionId = sessionStorage.getItem(VIEW_KEY);
        const kind = VIEW_TO_KIND[sectionId];
        if (!kind) return;
        const cached = cachedResult(kind);
        if (!cached) return;
        if (kind === 'forecast') {
            restoreForecastControls(cached.payload.params);
            renderForecast(cached.payload.data);
            showAnalysisView('stepForecast', false);
        } else {
            ANALYSES[kind].render(cached.payload);
            markStamp(kind, cached.at);
        }
    }

    // ---------- Step 3: analysis menu ----------
    // Every analysis follows the same shape (fetch → cache → render), so it is
    // described once as data instead of three near-identical handlers.
    const ANALYSES = {
        summary: {
            busy: 'Calculando…', running: 'Calculando el resumen comercial…',
            ready: 'Resumen comercial listo.', failed: 'No se pudo calcular el resumen.',
            fetch: () => window.SD_API.get(
                `${ANALYTICS_URL}/v1/analytics/summary/${encodeURIComponent(state.datasetId)}`),
            render: renderCommercialSummary
        },
        opportunities: {
            busy: 'Analizando…', running: 'Ejecutando el motor de oportunidades…',
            ready: 'Oportunidades listas.', failed: 'El motor falló.',
            fetch: () => window.SD_API.post(
                `${ANALYTICS_URL}/v1/analytics/run/${encodeURIComponent(state.datasetId)}`),
            render: renderOpportunities
        },
        segmentation: {
            busy: 'Segmentando…', running: 'Segmentando clientes…',
            ready: 'Segmentación lista.', failed: 'No se pudo segmentar.',
            fetch: () => window.SD_API.get(
                `${ANALYTICS_URL}/v1/analytics/segmentation/${encodeURIComponent(state.datasetId)}`),
            render: renderSegmentation
        }
    };

    /**
     * Shows an analysis, reusing the cached payload unless a recalculation is
     * explicitly requested. `trigger` is the button that shows the busy state.
     */
    async function openAnalysis(kind, trigger, force = false) {
        if (!state.datasetId) return;
        const analysis = ANALYSES[kind];
        if (!force) {
            const cached = cachedResult(kind);
            if (cached) {
                analysis.render(cached.payload);
                markStamp(kind, cached.at);
                return;
            }
        }
        const note = qs('#runNote');
        note.className = 'form-note';
        note.textContent = analysis.running;
        const done = setButtonBusy(trigger, analysis.busy);
        try {
            const payload = await analysis.fetch();
            cacheResult(kind, payload);
            analysis.render(payload);
            markStamp(kind, Date.now());
            note.classList.add('success');
            note.textContent = analysis.ready;
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || analysis.failed;
            toast(error.message || analysis.failed, 'error');
        } finally {
            done();
        }
    }

    qs('#analysisMenu').addEventListener('click', (event) => {
        const card = event.target.closest('.analysis-card');
        if (!card || card.disabled) return;
        const kind = card.dataset.analysis;
        if (kind === 'forecast') openForecast(card);
        else openAnalysis(kind, card);
    });

    // "↻ Recalcular" inside each result section: same analysis, fresh numbers.
    qsAll('[data-recalc]').forEach((button) => {
        button.addEventListener('click', () => openAnalysis(button.dataset.recalc, button, true));
    });

    // ---------- Segmentation ----------
    const TIER_COLOR = { Alto: '#2d7d46', Medio: '#c4a378', Bajo: '#c0392b' };
    let segmentClients = [];
    let segmentTotal = 0;
    let segmentAllClients = 0;

    function renderSegmentation(data) {
        const tiers = data.tiers || [];
        segmentClients = data.clientes || [];
        segmentTotal = tiers.reduce((sum, tier) => sum + (Number(tier.monto) || 0), 0);
        segmentAllClients = data.total_clientes || segmentClients.length;

        // KPI per tier: client count + sales share.
        const kpiBox = qs('#segmentKpis');
        kpiBox.innerHTML = '';
        kpiBox.appendChild(metricCard({
            label: 'Clientes totales', value: formatInt(data.total_clientes || 0)
        }));
        tiers.forEach((tier) => kpiBox.appendChild(metricCard({
            label: `Segmento ${tier.tier}`,
            value: `${formatInt(tier.clientes)} · ${tier.porcentaje}%`,
            hint: `${formatCurrency(tier.monto)} de venta`
        })));

        // Doughnut of sales share by tier.
        makeChart('chartSegmentos', {
            type: 'doughnut',
            data: {
                labels: tiers.map((t) => `${t.tier} (${t.porcentaje}%)`),
                datasets: [{ data: tiers.map((t) => t.monto),
                    backgroundColor: tiers.map((t) => TIER_COLOR[t.tier] || BRAND[0]) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        renderSegmentTable();
        showAnalysisView('stepSegmentation');
    }

    const SEGMENT_PAGE_SIZE = 20;
    let segmentPage = 0;

    function filteredSegmentClients() {
        const tier = qs('#segmentFilter').value;
        const search = qs('#segmentSearch').value.trim().toLowerCase();
        return segmentClients.filter((client) =>
            (!tier || client.tier === tier) &&
            (!search || String(client.cliente).toLowerCase().includes(search)));
    }

    function renderSegmentTable() {
        const rows = filteredSegmentClients();
        const pages = Math.max(1, Math.ceil(rows.length / SEGMENT_PAGE_SIZE));
        segmentPage = Math.min(segmentPage, pages - 1);
        const start = segmentPage * SEGMENT_PAGE_SIZE;
        const pageRows = rows.slice(start, start + SEGMENT_PAGE_SIZE);

        const tbody = qs('#segmentTable tbody');
        tbody.innerHTML = '';
        if (pageRows.length === 0) {
            tbody.innerHTML =
                '<tr class="empty-row"><td colspan="7">Sin clientes para ese filtro.</td></tr>';
        }
        pageRows.forEach((client, index) => {
            const compras = Number(client.compras) || 0;
            const monto = Number(client.monto) || 0;
            const ticket = compras ? monto / compras : 0;
            const share = segmentTotal ? (monto / segmentTotal) * 100 : 0;
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="rank-cell">${start + index + 1}</td>` +
                `<td>${escapeHtml(client.cliente)}</td>` +
                `<td><span class="tier-badge tier-${client.tier}">${client.tier}</span></td>` +
                `<td class="numeric">${formatInt(compras)}</td>` +
                `<td class="numeric strong">${formatCurrency(monto)}</td>` +
                `<td class="numeric">${formatCurrency(ticket)}</td>` +
                `<td class="numeric">${share.toFixed(2)}%</td>`;
            tbody.appendChild(tr);
        });
        // The API caps the client list, so say so instead of letting the user
        // wonder why the "Bajo" tier looks smaller than its KPI card.
        qs('#segmentCount').textContent = segmentClients.length < segmentAllClients
            ? `${formatInt(rows.length)} en pantalla · se listan los ` +
              `${formatInt(segmentClients.length)} clientes de mayor valor ` +
              `de ${formatInt(segmentAllClients)}`
            : `${formatInt(rows.length)} cliente(s)`;
        qs('#segmentPageInfo').textContent = rows.length === 0
            ? '—'
            : `${formatInt(start + 1)}–${formatInt(start + pageRows.length)} de ` +
              `${formatInt(rows.length)} · pág. ${segmentPage + 1}/${pages}`;
        qs('#segmentPrev').disabled = segmentPage === 0;
        qs('#segmentNext').disabled = segmentPage >= pages - 1;
    }

    qs('#segmentFilter').addEventListener('change', () => { segmentPage = 0; renderSegmentTable(); });
    qs('#segmentSearch').addEventListener('input', () => { segmentPage = 0; renderSegmentTable(); });
    qs('#segmentPrev').addEventListener('click', () => { segmentPage -= 1; renderSegmentTable(); });
    qs('#segmentNext').addEventListener('click', () => { segmentPage += 1; renderSegmentTable(); });

    // ---------- Forecast ----------
    qs('#forecastRun').addEventListener('click', () => loadForecast());

    function openForecast(card) {
        if (!state.datasetId) return;
        showAnalysisView('stepForecast');
        // Reuse the last projection (with the controls the user had chosen)
        // instead of recomputing it every time the card is clicked.
        const cached = cachedResult('forecast');
        if (cached) {
            restoreForecastControls(cached.payload.params);
            renderForecast(cached.payload.data);
            qs('#forecastNote').textContent = `Método: ${cached.payload.data.method_label} · ` +
                `${cached.payload.data.months_ahead} meses proyectados. ` +
                'Pulsa "Actualizar" para recalcular.';
            return;
        }
        loadForecast(card);
    }

    function restoreForecastControls(params) {
        if (!params) return;
        qs('#forecastMethod').value = params.method || 'linear';
        qs('#forecastMonths').value = params.months_ahead || '3';
        qs('#forecastGroup').value = params.group_by || '';
    }

    async function loadForecast(card) {
        if (!state.datasetId) return;
        const note = qs('#forecastNote');
        note.className = 'forecast-note';
        note.textContent = 'Calculando el pronóstico…';
        const trigger = card || qs('#forecastRun');
        const done = setButtonBusy(trigger, 'Calculando…');
        try {
            const params = {
                method: qs('#forecastMethod').value,
                months_ahead: qs('#forecastMonths').value
            };
            const group = qs('#forecastGroup').value;
            if (group) params.group_by = group;
            const data = await window.SD_API.get(
                `${ANALYTICS_URL}/v1/analytics/forecast/${encodeURIComponent(state.datasetId)}`,
                params
            );
            cacheResult('forecast', { data, params });
            renderForecast(data);
            note.textContent = `Método: ${data.method_label} · ${data.months_ahead} meses proyectados.`;
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo calcular el pronóstico.';
            toast(error.message || 'Error en el pronóstico.', 'error');
        } finally {
            done();
        }
    }

    function renderForecast(data) {
        const container = qs('#forecastCharts');
        container.innerHTML = '';
        const series = data.series || [];
        if (!series.length) {
            container.innerHTML = '<p class="insight-empty">No hay suficiente historial ' +
                '(se necesitan al menos 2 meses) para proyectar.</p>';
            return;
        }
        series.forEach((serie, index) => {
            const card = document.createElement('div');
            card.className = 'chart-card';
            const total = formatCurrency(serie.total_pronosticado);
            card.innerHTML = `<h3 class="chart-title">${escapeHtml(serie.nombre)} ` +
                `<span class="chart-sub">· proyección ${escapeHtml(total)}</span></h3>` +
                `<canvas id="forecast_${index}"></canvas>`;
            container.appendChild(card);

            const hist = serie.historico || [];
            const fore = serie.pronostico || [];
            // Continuous x-axis: historical months then projected months. The
            // forecast line starts from the last historical point for continuity.
            const labels = hist.map((p) => p.mes).concat(fore.map((p) => p.mes));
            const histData = hist.map((p) => p.monto).concat(fore.map(() => null));
            const foreData = hist.map((p, i) => (i === hist.length - 1 ? p.monto : null))
                .concat(fore.map((p) => p.monto));
            makeChart(`forecast_${index}`, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        { label: 'Histórico', data: histData, borderColor: BRAND[0],
                          backgroundColor: 'rgba(13,30,76,0.08)', fill: true, tension: 0.3 },
                        { label: 'Pronóstico', data: foreData, borderColor: BRAND[1],
                          borderDash: [6, 4], tension: 0.3 }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: true, position: 'bottom' },
                        tooltip: { callbacks: { label: (ctx) => ctx.parsed.y == null ? ''
                            : `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}` } }
                    }
                }
            });
        });
    }

    function renderOpportunities(response) {
        state.opportunities = response.opportunities || [];
        const insight = deriveInsight(response.summary, state.opportunities);
        renderOpportunityHeadline(insight);
        renderOpportunitySummary(response.summary, insight);
        renderProductOpportunities();
        showAnalysisView('stepOpportunities');
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
                'actuales. Prueba con un período más amplio o un catálogo con más variedad.</p>';
            return;
        }
        const count = formatInt(insight.count);
        const pdvs = formatInt(insight.pdvs);
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
                label: 'Acciones sugeridas', value: formatInt(summary.total_opportunities || 0),
                variant: 'accent', hint: 'Recomendaciones de venta cruzada'
            },
            {
                label: 'Puntos de venta',
                value: formatInt(summary.total_pdvs_with_opportunities || 0),
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

    // ---------- Step 4: product summary with per-store drill-down ----------
    // The raw opportunities repeat the same recommended product across hundreds
    // of stores. We group them by product (one row each: total potential + how
    // many stores), and let the user expand a product to see the interested
    // stores — a summary first, detail on demand.
    qs('#pdvFilter').addEventListener('input', () => renderProductOpportunities());

    function groupOpportunitiesByProduct(opportunities) {
        const byProduct = new Map();
        opportunities.forEach((opp) => {
            const key = opp.recommended_product_name || opp.recommended_product_id || '—';
            const group = byProduct.get(key) || { producto: key, total: 0, stores: [] };
            group.total += Number(opp.expected_drop_size_amount) || 0;
            group.stores.push(opp);
            byProduct.set(key, group);
        });
        const groups = [...byProduct.values()];
        groups.forEach((g) => g.stores.sort(
            (a, b) => (b.expected_drop_size_amount || 0) - (a.expected_drop_size_amount || 0)));
        return groups.sort((a, b) => b.total - a.total);
    }

    function renderProductOpportunities() {
        const tbody = qs('#opportunitiesTable tbody');
        tbody.innerHTML = '';
        const filterText = qs('#pdvFilter').value.trim().toLowerCase();
        let groups = groupOpportunitiesByProduct(state.opportunities);
        if (filterText) {
            groups = groups.filter((g) => g.producto.toLowerCase().includes(filterText));
        }
        qs('#filterCount').textContent =
            `${formatInt(groups.length)} producto(s) · ` +
            `${formatInt(state.opportunities.length)} acciones en total`;

        if (groups.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">Sin oportunidades para ese filtro.</td></tr>';
            return;
        }
        groups.forEach((group, index) => {
            const row = document.createElement('tr');
            row.className = 'product-row';
            row.innerHTML =
                `<td><button type="button" class="expand-btn" data-idx="${index}">▸</button>
                    <strong>${escapeHtml(group.producto)}</strong></td>
                 <td class="numeric">${formatInt(group.stores.length)}</td>
                 <td class="numeric strong">${formatCurrency(group.total)}</td>
                 <td class="based-on">Ofrecer a estos comercios en la próxima visita</td>`;
            tbody.appendChild(row);

            // Hidden detail row: the interested stores for this product.
            const detail = document.createElement('tr');
            detail.className = 'detail-row';
            detail.hidden = true;
            const inner = group.stores.slice(0, 50).map((opp) => {
                const store = opp.pdv_name || opp.pdv_id;
                const based = (opp.based_on_products || []).join(', ') || '—';
                return `<tr>
                    <td>${escapeHtml(store)}</td>
                    <td class="based-on">porque compra ${escapeHtml(based)}</td>
                    <td class="numeric">${formatPercent(opp.confidence)}</td>
                    <td class="numeric strong">${formatCurrency(opp.expected_drop_size_amount || 0)}</td>
                </tr>`;
            }).join('');
            detail.innerHTML = `<td colspan="4" class="detail-cell">
                <table class="data-table detail-table"><thead><tr>
                    <th>Comercio</th><th>Motivo</th>
                    <th class="numeric">Probabilidad</th><th class="numeric">Venta potencial</th>
                </tr></thead><tbody>${inner}</tbody></table>
                ${group.stores.length > 50 ? `<p class="based-on" style="margin:.5rem 0 0">` +
                    `Mostrando 50 de ${formatInt(group.stores.length)} comercios.</p>` : ''}
            </td>`;
            tbody.appendChild(detail);

            row.querySelector('.expand-btn').addEventListener('click', (ev) => {
                detail.hidden = !detail.hidden;
                ev.currentTarget.textContent = detail.hidden ? '▸' : '▾';
            });
        });
    }

    // ---------- Commercial summary (dashboard) ----------
    const BRAND = ['#0d1e4c', '#7a4a2a', '#c4a378', '#2d7d46', '#b8860b',
        '#5e6580', '#8a5a3a', '#3a5a8a', '#6a8a4a', '#a07040'];
    const chartRegistry = {};

    function formatKpi(card) {
        if (card.format === 'money') return formatCurrency(card.value);
        return formatInt(card.value);
    }

    function makeChart(canvasId, config) {
        if (!window.Chart) return;
        if (chartRegistry[canvasId]) chartRegistry[canvasId].destroy();
        chartRegistry[canvasId] = new window.Chart(qs('#' + canvasId), config);
    }

    function renderCommercialSummary(data) {
        // KPIs
        const kpiBox = qs('#dashboardKpis');
        kpiBox.innerHTML = '';
        (data.kpis || []).forEach((card) => kpiBox.appendChild(metricCard({
            label: card.label, value: formatKpi(card), hint: card.hint,
            variant: card.label === 'Venta total' ? 'success' : ''
        })));

        // Monthly trend (line)
        const trend = data.tendencia_mensual || [];
        makeChart('chartTrend', {
            type: 'line',
            data: {
                labels: trend.map((p) => p.mes),
                datasets: [{
                    label: 'Venta (Bs)', data: trend.map((p) => p.monto),
                    borderColor: BRAND[0], backgroundColor: 'rgba(13,30,76,0.1)',
                    fill: true, tension: 0.3
                }]
            },
            options: chartOptions('money')
        });

        // Category distribution (doughnut)
        const cat = data.por_categoria || [];
        makeChart('chartCategoria', {
            type: 'doughnut',
            data: {
                labels: cat.map((c) => c.label),
                datasets: [{ data: cat.map((c) => c.monto), backgroundColor: BRAND }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        // Top products / top clients / sellers (horizontal bars)
        horizontalBar('chartTopProductos', data.top_productos, 'Venta (Bs)');
        horizontalBar('chartTopClientes', data.mejor_cliente, 'Venta (Bs)');
        horizontalBar('chartVendedor', (data.por_vendedor || []).slice(0, 10), 'Venta (Bs)', 'monto');

        // Bottom products (table)
        const tbody = qs('#bottomProductosTable tbody');
        tbody.innerHTML = '';
        (data.bottom_productos || []).forEach((row) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${escapeHtml(row.label)}</td>` +
                `<td class="numeric">${formatCurrency(row.monto)}</td>`;
            tbody.appendChild(tr);
        });

        showAnalysisView('stepDashboard');
    }

    function horizontalBar(canvasId, rows, label, valueKey = 'monto') {
        const items = rows || [];
        makeChart(canvasId, {
            type: 'bar',
            data: {
                labels: items.map((r) => r.label),
                datasets: [{ label, data: items.map((r) => r[valueKey]), backgroundColor: BRAND[1] }]
            },
            options: { ...chartOptions('money'), indexAxis: 'y' }
        });
    }

    function chartOptions(format) {
        return {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => format === 'money'
                            ? formatCurrency(ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed)
                            : String(ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed)
                    }
                }
            }
        };
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

    // Every count shown to the user goes through here: raw String(n) leaves
    // figures like 120837 unreadable on the KPI cards.
    function formatInt(value) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO', { maximumFractionDigits: 0 });
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

    // ---------- Session countdown ----------
    // The session used to die silently and bounce the user to the login screen
    // mid-analysis. Showing the remaining time makes that predictable.
    const SESSION_WARNING_MINUTES = 10;
    let sessionWarned = false;

    function renderSessionChip() {
        const chip = qs('#sessionChip');
        const expiry = window.SD_AUTH.getSessionExpiry();
        if (!expiry) {
            chip.hidden = true;
            return;
        }
        const minutes = Math.floor((expiry.getTime() - Date.now()) / 60000);
        chip.hidden = false;
        chip.classList.toggle('warning', minutes <= SESSION_WARNING_MINUTES);
        if (minutes <= 0) {
            chip.textContent = '⏱ Sesión expirada — vuelve a entrar';
            return;
        }
        chip.textContent = minutes >= 60
            ? `⏱ Sesión: ${Math.floor(minutes / 60)} h ${minutes % 60} min`
            : `⏱ Sesión: ${minutes} min`;
        if (minutes <= SESSION_WARNING_MINUTES && !sessionWarned) {
            sessionWarned = true;
            toast(`Tu sesión expira en ${minutes} min. Tus resultados quedan guardados: ` +
                'vuelve a entrar y verás la misma pantalla.', 'info', 9000);
        }
    }

    // ---------- Init ----------
    // Runs last so every helper and configuration object above already exists.
    renderSessionChip();
    setInterval(renderSessionChip, 60000);
    if (state.datasetId) restoreLastView();
});
