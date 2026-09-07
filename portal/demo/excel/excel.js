'use strict';

/**
 * Análisis Comercial — module logic.
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
    const PERIOD_KEY = 'sd_excel_period';
    const MAX_ISSUES_SHOWN = 200;

    function readStoredPeriod() {
        try {
            return JSON.parse(sessionStorage.getItem(PERIOD_KEY) || 'null') || {};
        } catch (parseError) {
            return {};
        }
    }

    const state = {
        selectedFile: null,
        datasetId: sessionStorage.getItem(DATASET_KEY) || null,
        period: readStoredPeriod(),
        available: {},
        opportunities: [],
        sortKey: 'score',
        sortDir: 'desc'
    };

    function setDataset(datasetId) {
        // A different file invalidates every cached result of the previous one,
        // and the window of the old file means nothing for the new one.
        if (datasetId !== state.datasetId) {
            sessionStorage.removeItem(CACHE_KEY);
            setPeriod({});
        }
        state.datasetId = datasetId;
        if (datasetId) sessionStorage.setItem(DATASET_KEY, datasetId);
        else sessionStorage.removeItem(DATASET_KEY);
    }

    /**
     * Stores the reporting window and drops every cached result: a number
     * computed over January cannot be shown as if it covered the whole year.
     */
    function setPeriod(period) {
        state.period = period || {};
        sessionStorage.setItem(PERIOD_KEY, JSON.stringify(state.period));
        sessionStorage.removeItem(CACHE_KEY);
    }

    /** Builds the ?date_from=&date_to= suffix every analysis endpoint accepts. */
    function analysisQuery() {
        const params = new URLSearchParams();
        if (state.period.from) params.set('date_from', state.period.from);
        if (state.period.to) params.set('date_to', state.period.to);
        const query = params.toString();
        return query ? `?${query}` : '';
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
        segmentation: 'stampSegmentation',
        portfolio: 'stampPortfolio'
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
        'stepOpportunities', 'stepPortfolio'];
    function showAnalysisView(sectionId, scroll = true) {
        ANALYSIS_SECTIONS.forEach((id) => { qs('#' + id).hidden = (id !== sectionId); });
        sessionStorage.setItem(VIEW_KEY, sectionId);
        resizeChartsIn(sectionId);
        if (scroll) {
            qs('#' + sectionId).scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    /**
     * Chart.js measures the canvas at construction time, and every renderer
     * builds its charts while the section is still `display:none` — which locks
     * in a collapsed size and paints an apparently empty card. Re-measuring
     * once the section is on screen is what makes them appear at full size.
     *
     * The deferral matters: unhiding the section does not lay it out
     * synchronously, so resizing in the same tick reads the same zero size that
     * caused the problem. A timeout rather than requestAnimationFrame, because
     * rAF never fires while the tab is in the background — a demo opened in a
     * background tab would show empty cards until the user resized the window.
     */
    function resizeChartsIn(sectionId) {
        setTimeout(() => {
            const section = qs('#' + sectionId);
            Object.values(chartRegistry).forEach((chart) => {
                if (chart && section.contains(chart.canvas)) chart.resize();
            });
        }, 0);
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
            note.textContent = errorText(error, 'No se pudo descargar la plantilla.');
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
            note.textContent = errorText(error, 'No se pudo subir el archivo.');
            toast(errorText(error, 'Error al subir.'), 'error');
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
            renderIssues(response.issues || []);
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
            toast(errorText(error, 'No se pudo descargar el archivo.'), 'error');
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

    // The backend reports WHY a row failed as a stable code; the wording lives
    // here, in the layer that talks to the user. Keeping the sentence in the
    // backend would leave the future interpretation layer parsing prose instead
    // of reading facts — and would make translating the product impossible.
    const VALIDATION_MESSAGES = {
        REQUIRED_VALUE: 'Este campo es obligatorio y no puede estar vacío.',
        INVALID_TYPE: 'El valor no tiene el formato esperado para esta columna.',
        TEXT_LENGTH: 'El texto debe tener entre 1 y 64 caracteres.',
        BELOW_MINIMUM: 'El valor debe ser mayor al mínimo permitido.',
        OUT_OF_RANGE: 'El valor está fuera del rango permitido.',
        UNKNOWN_COLUMN: 'Esta columna no forma parte de la plantilla.',
        MISSING_COLUMN: 'Falta esta columna obligatoria en el archivo.',
        EMPTY_FILE: 'El archivo no contiene filas de datos.',
        INVALID_VALUE: 'El valor no es válido para esta columna.'
    };

    function validationMessage(code) {
        return VALIDATION_MESSAGES[code] || VALIDATION_MESSAGES.INVALID_VALUE;
    }

    // Same contract for requests the service refuses outright: the backend
    // sends the code, this catalogue owns the sentence.
    const REQUEST_ERROR_MESSAGES = {
        UNSUPPORTED_FILE_FORMAT: 'Formato no soportado. Sube un archivo .xlsx o .csv.',
        EMPTY_UPLOAD: 'El archivo que subiste está vacío.',
        FILES_SERVICE_UNREACHABLE: 'No se pudo contactar al servicio de archivos.',
        FILES_SERVICE_REJECTED_UPLOAD: 'El servicio de archivos rechazó la subida.'
    };

    // Falls back to the raw message so services that still answer with prose
    // keep working while they migrate to codes.
    function errorText(error, fallback) {
        const code = error && error.code;
        return REQUEST_ERROR_MESSAGES[code]
            || ANALYTICS_ERRORS[code]
            || (error && error.message)
            || fallback;
    }

    // Portfolio health: the backend says WHY with a code and ships the facts
    // alongside it (dias_sin_comprar, variacion). The sentence is built here.
    const RISK_REASONS = {
        LONG_SILENCE: (row) =>
            `Sin comprar hace ${formatInt(row.days_without_purchase)} días. ` +
            'Campaña de reactivación.',
        SILENCE: (row) => `No compra hace ${formatInt(row.days_without_purchase)} días.`,
        PURCHASE_DROP: (row) =>
            `Su última compra cayó ${formatDecimal(Math.abs(row.change || 0), 0)}% ` +
            'frente a su promedio mensual.'
    };

    function riskReasonText(row) {
        const build = RISK_REASONS[row && row.reason_code];
        return build ? build(row) : '';
    }

    // Every headline KPI the API can report. The backend sends `metric_code`,
    // `value` and, when the number refers to a period, `reference`.
    const KPI_LABELS = {
        TOTAL_SALES: ['Venta total', 'Suma de todas las ventas del periodo'],
        SALES_COUNT: ['Número de ventas', 'Cantidad de pedidos/transacciones'],
        AVERAGE_TICKET: ['Ticket promedio', 'Venta total ÷ número de ventas'],
        UNITS_SOLD: ['Unidades vendidas', 'Suma de las cantidades vendidas'],
        CLIENT_COUNT: ['Clientes', 'Puntos de venta distintos con compras'],
        PRODUCT_COUNT: ['Productos', 'SKUs distintos vendidos'],
        UNITS_PER_ORDER: ['Unidades por pedido', 'Drop size: unidades que salen en cada pedido'],
        PRODUCTS_PER_ORDER: ['Productos por pedido',
            'Líneas distintas por pedido — mide la venta cruzada'],
        AMOUNT_PER_ORDER: ['Monto por pedido', 'Ticket promedio del período'],
        ORDER_COUNT: ['Pedidos', 'Transacciones distintas en el período'],
        MOM_CHANGE: ['Variación vs mes anterior', 'Crecimiento mes contra mes (MoM)'],
        YOY_CHANGE: ['Variación vs año anterior', null],
        LAST_MONTH_SALES: ['Venta del último mes', null],
        MONTHLY_AVERAGE: ['Promedio mensual', 'Venta media por mes del período'],
        GROSS_MARGIN: ['Margen bruto', 'Venta menos costo de la mercadería vendida'],
        GROSS_MARGIN_PERCENT: ['Margen bruto %',
            'Qué porcentaje de cada boliviano vendido queda'],
        COST_OF_GOODS: ['Costo de la mercadería', 'Lo que costó comprar lo que se vendió'],
        MARGIN_PER_ORDER: ['Margen por pedido', 'Ganancia bruta promedio de cada pedido'],
        PORTFOLIO_CLIENTS: ['Clientes en la cartera',
            'Clientes distintos que compraron en el período'],
        ACTIVE_LAST_MONTH: ['Activos el último mes', 'Compraron en el mes más reciente'],
        COVERAGE: ['Cobertura', 'Activos del último mes sobre la cartera total'],
        CHURN_LAST_MONTH: ['Churn del último mes',
            'Clientes que compraron el mes previo y dejaron de comprar'],
        CLIENTS_AT_RISK: ['Clientes en riesgo',
            'Cayeron fuerte o llevan 2 meses sin comprar — visitarlos ahora'],
        CLIENTS_LOST: ['Clientes perdidos', 'Más de 6 meses sin comprar — campaña de reactivación'],
        PURCHASE_FREQUENCY: ['Frecuencia de compra', 'Pedidos por cliente por mes']
    };

    // A few KPIs read better with the period the number belongs to.
    function kpiLabel(card) {
        const entry = KPI_LABELS[card && card.metric_code];
        if (!entry) return card && card.metric_code ? String(card.metric_code) : '';
        if (card.metric_code === 'LAST_MONTH_SALES' && card.reference) {
            return `Venta de ${card.reference}`;
        }
        return entry[0];
    }

    // Codes the analytics engines report, worded here.
    const MARGIN_ALERT_REASONS = {
        BELOW_COST: 'Se vende por debajo del costo',
        THIN_MARGIN: 'Margen casi nulo'
    };

    const ABC_DESCRIPTIONS = {
        A: 'Núcleo del negocio: concentran el 80% de la venta. Nunca deben quebrar stock.',
        B: 'Complementarios: aportan el siguiente 15%. Mantener con rotación controlada.',
        C: 'Cola larga: el 5% restante. Candidatos a depurar o vender bajo pedido.'
    };

    const FORECAST_METHODS = {
        linear: 'Tendencia lineal',
        moving_average: 'Media móvil'
    };

    const ANALYTICS_ERRORS = {
        INVALID_DATE: 'La fecha no es válida. Usa el formato AAAA-MM-DD.',
        NO_DATE_COLUMN: 'El archivo no tiene una columna de fecha válida, ' +
            'no se puede filtrar por período.',
        EMPTY_PERIOD: 'No hay ventas en el período seleccionado. Elige otro rango.',
        DATASET_UNREADABLE: 'No se pudo leer el archivo del bucket de FILES.'
    };

    const CONCENTRATION_LEVELS = {
        HIGH: 'Alta: la venta depende de muy pocos clientes.',
        MODERATE: 'Moderada: hay dependencia de algunos clientes clave.',
        LOW: 'Baja: la venta está bien repartida entre los clientes.'
    };

    // A dimension the source file left blank still needs a row label.
    function dimensionLabel(value) {
        return value ? String(value) : 'Sin especificar';
    }

    function kpiHint(card) {
        const entry = KPI_LABELS[card && card.metric_code];
        if (card && card.metric_code === 'YOY_CHANGE') {
            return card.reference
                ? `Mismo mes de ${String(card.reference).slice(0, 4)} (YoY)`
                : 'Se necesita un año de historial';
        }
        return entry ? entry[1] : null;
    }

    function renderIssues(issues) {
        const tbody = qs('#errorsTable tbody');
        tbody.innerHTML = '';
        if (issues.length === 0) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = '<td colspan="4">Sin detalles del problema.</td>';
            tbody.appendChild(row);
            return;
        }
        issues.slice(0, MAX_ISSUES_SHOWN).forEach((issue) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${issue.row ?? '-'}</td>
                <td>${escapeHtml(issue.column || '(archivo)')}</td>
                <td>${issue.value == null ? '<em>vacío</em>' : escapeHtml(String(issue.value))}</td>
                <td>${escapeHtml(validationMessage(issue.rule_code))}</td>
            `;
            tbody.appendChild(row);
        });
        if (issues.length > MAX_ISSUES_SHOWN) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = `<td colspan="4">… y ${formatInt(issues.length - MAX_ISSUES_SHOWN)} ` +
                'problemas adicionales.</td>';
            tbody.appendChild(row);
        }
    }

    // Which cached analysis belongs to each section, so a reload lands the user
    // back where they were instead of on an empty screen.
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
            fetch: () => window.SD_API.get(analysisUrl('summary')),
            render: renderCommercialSummary
        },
        opportunities: {
            busy: 'Analizando…', running: 'Ejecutando el motor de oportunidades…',
            ready: 'Oportunidades listas.', failed: 'El motor falló.',
            fetch: () => window.SD_API.post(analysisUrl('run')),
            render: renderOpportunities
        },
        segmentation: {
            busy: 'Segmentando…', running: 'Segmentando clientes…',
            ready: 'Segmentación lista.', failed: 'No se pudo segmentar.',
            fetch: () => window.SD_API.get(analysisUrl('segmentation')),
            render: renderSegmentation
        },
        portfolio: {
            busy: 'Revisando…', running: 'Revisando la salud de la cartera…',
            ready: 'Salud de cartera lista.', failed: 'No se pudo revisar la cartera.',
            fetch: () => window.SD_API.get(analysisUrl('portfolio')),
            render: renderPortfolio
        }
    };

    function analysisUrl(kind) {
        return `${ANALYTICS_URL}/v1/analytics/${kind}/` +
            `${encodeURIComponent(state.datasetId)}${analysisQuery()}`;
    }

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

    // ---------- Reporting window ----------
    // The bar stays hidden until an analysis reports which dates the file
    // actually covers: offering a date picker before knowing the range invites
    // the user to select a window with no sales in it.
    function showPeriodBar(periodo) {
        if (!periodo || !periodo.available_from) return;
        state.available = periodo;
        const bar = qs('#periodBar');
        const from = qs('#periodFrom');
        const to = qs('#periodTo');

        [from, to].forEach((input) => {
            input.min = periodo.available_from;
            input.max = periodo.available_to;
        });
        from.value = state.period.from || '';
        to.value = state.period.to || '';
        bar.hidden = false;

        qs('#periodNote').textContent = periodo.filtered
            ? `Mostrando ${formatDateRange(periodo.from_date, periodo.to_date)} · ` +
              `${formatInt(periodo.filas)} filas`
            : `Datos disponibles: ${formatDateRange(periodo.available_from,
                periodo.available_to)}`;
    }

    qs('#periodApply').addEventListener('click', () => {
        const from = qs('#periodFrom').value;
        const to = qs('#periodTo').value;
        if (from && to && from > to) {
            toast('La fecha "Desde" no puede ser posterior a "Hasta".', 'error');
            return;
        }
        setPeriod({ from: from || null, to: to || null });
        reopenCurrentAnalysis();
    });

    qs('#periodReset').addEventListener('click', () => {
        qs('#periodFrom').value = '';
        qs('#periodTo').value = '';
        setPeriod({});
        reopenCurrentAnalysis();
    });

    /**
     * Recomputes whatever the user is looking at after the window changes. The
     * cache was already dropped, so this always hits the API.
     */
    function reopenCurrentAnalysis() {
        const kind = VIEW_TO_KIND[sessionStorage.getItem(VIEW_KEY)];
        const trigger = qs('#periodApply');
        if (!kind) {
            toast('Período aplicado. Elige un análisis.', 'success');
            return;
        }
        if (kind === 'forecast') loadForecast(trigger);
        else openAnalysis(kind, trigger, true);
    }

    // ---------- Segmentation ----------
    // The backend reports the tier as a code; the colour and the Spanish
    // wording live here, like every other label.
    const TIER_COLOR = { HIGH: '#2d7d46', MEDIUM: '#c4a378', LOW: '#c0392b' };
    const TIER_LABELS = { HIGH: 'Alto', MEDIUM: 'Medio', LOW: 'Bajo' };

    function tierLabel(code) {
        return TIER_LABELS[code] || code || '';
    }
    let segmentClients = [];
    let segmentTotal = 0;
    let segmentAllClients = 0;

    function renderSegmentation(data) {
        const tiers = data.tiers || [];
        segmentClients = data.clients || [];
        segmentTotal = tiers.reduce((sum, tier) => sum + (Number(tier.amount) || 0), 0);
        segmentAllClients = data.total_clients || segmentClients.length;

        // KPI per tier: client count + sales share.
        const kpiBox = qs('#segmentKpis');
        kpiBox.innerHTML = '';
        kpiBox.appendChild(metricCard({
            label: 'Clientes totales', value: formatInt(data.total_clients || 0)
        }));
        tiers.forEach((tier) => kpiBox.appendChild(metricCard({
            label: `Segmento ${tierLabel(tier.tier)}`,
            value: `${formatInt(tier.clients)} · ${formatDecimal(tier.percentage, 1)}%`,
            hint: `${formatCurrency(tier.amount)} de venta`
        })));

        // Doughnut of sales share by tier.
        makeChart('chartSegmentos', {
            type: 'doughnut',
            data: {
                labels: tiers.map(
                    (t) => `${tierLabel(t.tier)} (${formatDecimal(t.percentage, 1)}%)`
                ),
                datasets: [{ data: tiers.map((t) => t.amount),
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
            (!search || String(client.client).toLowerCase().includes(search)));
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
            const purchases = Number(client.purchases) || 0;
            const amount = Number(client.amount) || 0;
            const ticket = purchases ? amount / purchases : 0;
            const share = segmentTotal ? (amount / segmentTotal) * 100 : 0;
            const tr = document.createElement('tr');
            tr.innerHTML = `<td class="rank-cell">${start + index + 1}</td>` +
                `<td>${escapeHtml(client.client)}</td>` +
                `<td><span class="tier-badge tier-${client.tier}">` +
                `${escapeHtml(tierLabel(client.tier))}</span></td>` +
                `<td class="numeric">${formatInt(purchases)}</td>` +
                `<td class="numeric strong">${formatCurrency(amount)}</td>` +
                `<td class="numeric">${formatCurrency(ticket)}</td>` +
                `<td class="numeric">${share.toFixed(2)}%</td>`;
            tbody.appendChild(tr);
        });
        // The API caps the client list, so say so instead of letting the user
        // wonder why the lowest tier looks smaller than its KPI card.
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
            qs('#forecastNote').textContent =
                `Método: ${FORECAST_METHODS[cached.payload.data.method] || ''} · ` +
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
            if (state.period.from) params.date_from = state.period.from;
            if (state.period.to) params.date_to = state.period.to;
            const data = await window.SD_API.get(
                `${ANALYTICS_URL}/v1/analytics/forecast/${encodeURIComponent(state.datasetId)}`,
                params
            );
            cacheResult('forecast', { data, params });
            renderForecast(data);
            note.textContent = `Método: ${FORECAST_METHODS[data.method] || ''} · ` +
                `${data.months_ahead} meses proyectados.`;
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
            const total = formatCurrency(serie.total_forecast);
            card.innerHTML = `<h3 class="chart-title">${escapeHtml(serie.name || 'Total')} ` +
                `<span class="chart-sub">· proyección ${escapeHtml(total)}</span></h3>` +
                `<canvas id="forecast_${index}"></canvas>`;
            container.appendChild(card);

            const hist = serie.history || [];
            const fore = serie.forecast || [];
            // Continuous x-axis: historical months then projected months. The
            // forecast line starts from the last historical point for continuity.
            const labels = hist.map((p) => p.month).concat(fore.map((p) => p.month));
            const histData = hist.map((p) => p.amount).concat(fore.map(() => null));
            const foreData = hist.map((p, i) => (i === hist.length - 1 ? p.amount : null))
                .concat(fore.map((p) => p.amount));
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
            pdvs: summary.total_pos_with_opportunities || 0,
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
                value: formatInt(summary.total_pos_with_opportunities || 0),
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
            const group = byProduct.get(key) || { product: key, total: 0, stores: [] };
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
            groups = groups.filter((g) => g.product.toLowerCase().includes(filterText));
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
                    <strong>${escapeHtml(group.product)}</strong></td>
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

    // A KPI without a value is not zero: a percentage variation with no base
    // period is undefined, and rendering it as 0% would state something false.
    function formatKpi(card) {
        if (card.value == null || isNaN(card.value)) return '—';
        if (card.format === 'money') return formatCurrency(card.value);
        if (card.format === 'percent') return `${formatDecimal(card.value, 1)}%`;
        if (card.format === 'decimal') return formatDecimal(card.value, 2);
        return formatInt(card.value);
    }

    // es-BO writes 22,2 — not 22.2. Mixing separators inside the same dashboard
    // ("Bs 254.641,43" next to "22.2%") reads as a bug to a Bolivian user.
    function formatDecimal(value, decimals) {
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals
        });
    }

    /** Signed percentage with its direction, for variation cells. */
    function formatDelta(value, suffix = '%') {
        if (value == null || isNaN(value)) return '—';
        const number = Number(value);
        const sign = number > 0 ? '+' : '';
        return `${sign}${formatDecimal(number, 1)}${suffix}`;
    }

    function deltaClass(value) {
        if (value == null || isNaN(value)) return '';
        return Number(value) >= 0 ? 'delta-up' : 'delta-down';
    }

    /** Fills a table body from rows, building each cell from `cells(row)`. */
    function fillTable(tableId, rows, cells) {
        const tbody = qs(`#${tableId} tbody`);
        tbody.innerHTML = '';
        (rows || []).forEach((row) => {
            const tr = document.createElement('tr');
            tr.innerHTML = cells(row);
            tbody.appendChild(tr);
        });
    }

    function fillKpis(containerId, cards, variantFor) {
        const box = qs('#' + containerId);
        box.innerHTML = '';
        (cards || []).forEach((card) => box.appendChild(metricCard({
            label: kpiLabel(card),
            value: formatKpi(card),
            hint: kpiHint(card),
            variant: variantFor ? variantFor(card) : ''
        })));
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
            label: kpiLabel(card), value: formatKpi(card), hint: kpiHint(card),
            variant: card.metric_code === 'TOTAL_SALES' ? 'success' : ''
        })));

        // Monthly trend (line)
        const trend = data.monthly_trend || [];
        makeChart('chartTrend', {
            type: 'line',
            data: {
                labels: trend.map((p) => p.month),
                datasets: [{
                    label: 'Venta (Bs)', data: trend.map((p) => p.amount),
                    borderColor: BRAND[0], backgroundColor: 'rgba(13,30,76,0.1)',
                    fill: true, tension: 0.3
                }]
            },
            options: chartOptions('money')
        });

        // Category distribution (doughnut)
        const cat = data.by_category || [];
        makeChart('chartCategoria', {
            type: 'doughnut',
            data: {
                labels: cat.map((c) => dimensionLabel(c.label)),
                datasets: [{ data: cat.map((c) => c.amount), backgroundColor: BRAND }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        // Top products / top clients / sellers (horizontal bars)
        horizontalBar('chartTopProductos', data.top_products, 'Venta (Bs)');
        horizontalBar('chartTopClientes', data.best_clients, 'Venta (Bs)');
        horizontalBar('chartVendedor', (data.by_seller || []).slice(0, 10), 'Venta (Bs)');

        // Bottom products (table)
        fillTable('bottomProductosTable', data.bottom_products, (row) =>
            `<td>${escapeHtml(dimensionLabel(row.label))}</td>` +
            `<td class="numeric">${formatCurrency(row.amount)}</td>`);

        showPeriodBar(data.period);
        renderMargin(data.margin);
        renderGrowth(data.growth);
        renderConcentration(data.concentration);
        renderEfficiency(data.efficiency);

        showAnalysisView('stepDashboard');
    }

    // ---------- Profitability ----------
    function renderMargin(margen) {
        // Hidden rather than zeroed: a file without unit costs has no margin,
        // and "0%" would read as "you earn nothing".
        const block = qs('#marginBlock');
        if (!margen || !margen.available) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        fillKpis('marginKpis', margen.kpis, (card) =>
            card.metric_code === 'GROSS_MARGIN' ? 'success' : '');

        const categories = margen.by_category || [];
        makeChart('chartMargenCategoria', {
            type: 'bar',
            data: {
                labels: categories.map((row) => dimensionLabel(row.label)),
                datasets: [
                    {
                        label: 'Venta (Bs)', data: categories.map((row) => row.amount),
                        backgroundColor: BRAND[5]
                    },
                    {
                        label: 'Margen (Bs)', data: categories.map((row) => row.margin),
                        backgroundColor: BRAND[3]
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: false } }
            }
        });

        fillTable('marginCategoryTable', categories, (row) =>
            `<td>${escapeHtml(dimensionLabel(row.label))}</td>` +
            `<td class="numeric">${formatCurrency(row.amount)}</td>` +
            `<td class="numeric hero">${formatCurrency(row.margin)}</td>` +
            `<td class="numeric">${formatDecimal(row.margin_percentage, 1)}%</td>`);

        const alerts = margen.alerts || [];
        qs('#marginAlerts').hidden = alerts.length === 0;
        fillTable('marginAlertTable', alerts, (row) =>
            `<td>${escapeHtml(dimensionLabel(row.label))}</td>` +
            `<td class="numeric">${formatCurrency(row.amount)}</td>` +
            `<td class="numeric delta-down">${formatCurrency(row.margin)}</td>` +
            `<td>${escapeHtml(MARGIN_ALERT_REASONS[row.reason_code] || '')}</td>`);
    }

    // ---------- Growth ----------
    function renderGrowth(crecimiento) {
        const block = qs('#growthBlock');
        const series = (crecimiento && crecimiento.monthly_change) || [];
        if (!series.length) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        fillKpis('growthKpis', crecimiento.kpis, (card) => {
            if (card.format !== 'percent' || card.value == null) return '';
            return card.value >= 0 ? 'success' : 'warning';
        });

        makeChart('chartGrowth', {
            type: 'bar',
            data: {
                labels: series.map((point) => point.month),
                datasets: [{
                    label: 'Variación (%)',
                    data: series.map((point) => point.change),
                    backgroundColor: series.map((point) =>
                        (point.change || 0) >= 0 ? BRAND[3] : '#c0392b')
                }]
            },
            options: chartOptions('percent')
        });

        // Seasonality needs a full year of history; without it the engine sends
        // nothing and the card would otherwise render an empty canvas.
        const seasonality = crecimiento.seasonality || [];
        qs('#seasonalityCard').hidden = seasonality.length === 0;
        if (seasonality.length) {
            makeChart('chartSeasonality', {
                type: 'line',
                data: {
                    labels: seasonality.map((row) => row.month),
                    datasets: [{
                        label: 'Índice', data: seasonality.map((row) => row.index_value),
                        borderColor: BRAND[1], backgroundColor: 'rgba(122,74,42,0.12)',
                        fill: true, tension: 0.35
                    }]
                },
                options: chartOptions('decimal')
            });
        }

        const mix = crecimiento.category_mix || [];
        qs('#mixCard').hidden = mix.length === 0;
        fillTable('mixTable', mix, (row) =>
            `<td>${escapeHtml(dimensionLabel(row.label))}</td>` +
            `<td class="numeric">${formatDecimal(row.current_share, 1)}%</td>` +
            `<td class="numeric ${deltaClass(row.share_change)}">` +
            `${formatDelta(row.share_change, ' pp')}</td>` +
            `<td class="numeric">${formatCurrency(row.current_amount)}</td>`);
    }

    // ---------- Concentration ----------
    function renderConcentration(concentracion) {
        const block = qs('#concentrationBlock');
        const clients = (concentracion && concentracion.clients) || {};
        if (!clients.total_clients) {
            block.hidden = true;
            return;
        }
        block.hidden = false;

        fillKpis('concentrationKpis', [
            { label: 'Clientes', value: clients.total_clients, format: 'int' },
            {
                label: 'Peso del top 10', value: clients.top10_percentage, format: 'percent',
                hint: 'Qué parte de la venta hacen tus 10 mayores clientes'
            },
            {
                label: 'Clientes que hacen el 80%', value: clients.pareto_clients,
                format: 'int',
                hint: `El ${formatDecimal(clients.pareto_client_percentage, 1)}% de la cartera`
            }
        ]);

        qs('#hhiReading').textContent = CONCENTRATION_LEVELS[clients.hhi_level] || '';

        const abc = (concentracion.abc && concentracion.abc.summary) || [];
        makeChart('chartAbc', {
            type: 'doughnut',
            data: {
                labels: abc.map((row) => `Clase ${row.abc_class}`),
                datasets: [{
                    data: abc.map((row) => row.amount),
                    backgroundColor: [BRAND[3], BRAND[2], BRAND[5]]
                }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        fillTable('abcTable', abc, (row) =>
            `<td><span class="badge badge-${row.abc_class.toLowerCase()}">${row.abc_class}</span></td>` +
            `<td class="numeric">${formatInt(row.products)}</td>` +
            `<td class="numeric">${formatDecimal(row.percentage, 1)}%</td>` +
            `<td class="cell-note">${escapeHtml(ABC_DESCRIPTIONS[row.abc_class] || '')}</td>`);
    }

    // ---------- Efficiency ----------
    function renderEfficiency(eficiencia) {
        const block = qs('#efficiencyBlock');
        const kpis = (eficiencia && eficiencia.kpis) || [];
        if (!kpis.length) {
            block.hidden = true;
            return;
        }
        block.hidden = false;
        fillKpis('efficiencyKpis', kpis);

        fillTable('sellerTable', eficiencia.sellers, (row) =>
            `<td>${escapeHtml(row.seller)}</td>` +
            `<td class="numeric hero">${formatCurrency(row.amount)}</td>` +
            `<td class="numeric">${formatInt(row.orders)}</td>` +
            `<td class="numeric">${formatInt(row.clients)}</td>` +
            `<td class="numeric">${formatCurrency(row.average_ticket)}</td>`);

        const prices = eficiencia.prices || [];
        qs('#priceCard').hidden = prices.length === 0;
        fillTable('priceTable', prices.slice(0, 15), (row) =>
            `<td>${escapeHtml(row.product)}</td>` +
            `<td class="numeric">${formatCurrency(row.previous_price)}</td>` +
            `<td class="numeric">${formatCurrency(row.current_price)}</td>` +
            `<td class="numeric ${deltaClass(row.change)}">${formatDelta(row.change)}</td>`);
    }

    // ---------- Portfolio health ----------
    const RISK_PAGE_SIZE = 15;
    let riskClients = [];
    let riskPage = 0;

    function renderPortfolio(data) {
        fillKpis('portfolioKpis', data.kpis, (card) =>
            card.metric_code === 'CLIENTS_AT_RISK' ? 'warning' : '');

        const movement = data.movement || [];
        makeChart('chartMovement', {
            type: 'bar',
            data: {
                labels: movement.map((row) => row.month),
                datasets: [
                    {
                        label: 'Nuevos', data: movement.map((row) => row.new_clients),
                        backgroundColor: BRAND[3]
                    },
                    {
                        label: 'Recuperados', data: movement.map((row) => row.recovered),
                        backgroundColor: BRAND[2]
                    },
                    {
                        label: 'Perdidos', data: movement.map((row) => -row.lost),
                        backgroundColor: '#c0392b'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { stacked: true }, y: { stacked: true } }
            }
        });

        makeChart('chartActive', {
            type: 'line',
            data: {
                labels: movement.map((row) => row.month),
                datasets: [{
                    label: 'Clientes activos', data: movement.map((row) => row.active),
                    borderColor: BRAND[0], backgroundColor: 'rgba(13,30,76,0.1)',
                    fill: true, tension: 0.3
                }]
            },
            // Counts are anchored at zero on purpose: letting Chart.js pick the
            // range turned a 9-client change into a visual cliff, which reads as
            // a collapse the data does not support.
            options: {
                ...chartOptions('int'),
                scales: { y: { beginAtZero: true } }
            }
        });

        riskClients = data.at_risk || [];
        riskPage = 0;
        renderRiskTable();

        // Kept in its own table: a client gone half a year is a campaign, not a
        // visit, and mixing them buries the names worth chasing this week.
        const lost = data.lost || [];
        qs('#lostCard').hidden = lost.length === 0;
        fillTable('lostTable', lost, (row) =>
            `<td>${escapeHtml(row.client)}</td>` +
            `<td class="numeric">${formatCurrency(row.monthly_average_amount)}</td>` +
            `<td class="numeric">${escapeHtml(row.last_purchase || '—')}</td>` +
            `<td class="numeric">${formatInt(row.days_without_purchase)}</td>`);

        showAnalysisView('stepPortfolio');
    }

    function renderRiskTable() {
        const term = (qs('#riskSearch').value || '').trim().toLowerCase();
        const rows = term
            ? riskClients.filter((row) => (row.client || '').toLowerCase().includes(term))
            : riskClients;
        const pages = Math.max(Math.ceil(rows.length / RISK_PAGE_SIZE), 1);
        riskPage = Math.min(Math.max(riskPage, 0), pages - 1);
        const slice = rows.slice(riskPage * RISK_PAGE_SIZE, (riskPage + 1) * RISK_PAGE_SIZE);

        fillTable('riskTable', slice, (row) =>
            `<td>${escapeHtml(row.client)}</td>` +
            `<td class="numeric">${formatCurrency(row.monthly_average_amount)}</td>` +
            `<td class="numeric">${formatCurrency(row.last_month_amount)}</td>` +
            `<td class="numeric ${deltaClass(row.change)}">${formatDelta(row.change)}</td>` +
            `<td class="numeric">${formatInt(row.days_without_purchase)}</td>` +
            `<td class="cell-note">${escapeHtml(riskReasonText(row))}</td>`);

        qs('#riskPager').innerHTML =
            `<button type="button" class="btn btn-ghost btn-small" id="riskPrev"` +
            `${riskPage === 0 ? ' disabled' : ''}>‹ Anterior</button>` +
            `<span class="pager-info">${formatInt(rows.length)} clientes · ` +
            `página ${riskPage + 1} de ${pages}</span>` +
            `<button type="button" class="btn btn-ghost btn-small" id="riskNext"` +
            `${riskPage >= pages - 1 ? ' disabled' : ''}>Siguiente ›</button>`;
        qs('#riskPrev').addEventListener('click', () => { riskPage -= 1; renderRiskTable(); });
        qs('#riskNext').addEventListener('click', () => { riskPage += 1; renderRiskTable(); });
    }

    qs('#riskSearch').addEventListener('input', () => { riskPage = 0; renderRiskTable(); });

    function horizontalBar(canvasId, rows, label, valueKey = 'amount') {
        const items = rows || [];
        makeChart(canvasId, {
            type: 'bar',
            data: {
                labels: items.map((r) => dimensionLabel(r.label)),
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
                        label: (ctx) => {
                            const value = ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed;
                            if (format === 'money') return formatCurrency(value);
                            if (format === 'percent') return formatDelta(value);
                            if (format === 'int') return formatInt(value);
                            return String(value);
                        }
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

    // ---------- Init ----------
    // Runs last so every helper and configuration object above already exists.
    window.SD_SESSION.mountChip(
        'sessionChip',
        'Tus resultados quedan guardados: vuelve a entrar y verás la misma pantalla.'
    );
    /**
     * Brings a returning user back to a usable screen.
     *
     * The analysis menu used to be revealed only by an upload made in this same
     * session, so somebody arriving with a dataset already loaded — from the
     * home panel, or after a reload — landed on a blank page and was asked to
     * upload the same file again. The dataset's own summary is enough to rebuild
     * that screen, and the service only returns it to its owner.
     */
    async function restoreDataset() {
        try {
            const status = await window.SD_API.get(
                `${window.SD_CONFIG.INGEST_URL}/v1/ingest/${state.datasetId}`
            );
            renderIngestSummary(status.summary, status.status);
            qs('#stepValidation').hidden = false;

            const isValid = status.status === 'validated';
            qs('#validatedBlock').hidden = !isValid;
            qs('#errorsBlock').hidden = isValid;
            if (isValid) {
                renderRejectedNotice(status.dataset_id, status.summary);
            } else {
                renderIssues(status.issues || []);
            }
            restoreLastView();
        } catch (error) {
            // The dataset is gone, or belongs to somebody else: forget it and
            // let the user start from the upload step instead of failing.
            setDataset(null);
        }
    }

    if (state.datasetId) restoreDataset();
});
