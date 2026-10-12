'use strict';

/**
 * Template download, file upload straight to S3 and the validation result.
 * Sales creates the dataset; the other files attach to it.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Step 1: template download ----------
    // The version is INGEST's, not ours: the card title and the file name
    // follow what the service publishes, so a new contract never ships with a
    // stale "v1" on the screen.
    const template = { version: '' };
    window.SD_API.get(`${A.INGEST_URL}/v1/ingest/template`)
        .then((info) => {
            template.version = info.template_version || '';
            qs('#templateTitle').textContent = template.version
                ? `Plantilla ${template.version}` : 'Plantilla';
        })
        .catch(() => { /* the title stays generic; the download still works */ });

    qs('#downloadTemplateButton').addEventListener('click', async () => {
        const button = qs('#downloadTemplateButton');
        const note = qs('#templateNote');
        const done = setButtonBusy(button, 'Descargando…');
        note.className = 'form-note';
        note.textContent = '';
        try {
            const contract = qs('#contractSelect').value;
            const response = await fetch(
                `${A.INGEST_URL}/v1/ingest/template/file/${contract}`, {
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
            anchor.download = `plantilla_${qs('#contractSelect').value}.xlsx`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(downloadUrl);
            note.classList.add('success');
            note.textContent = 'Plantilla descargada.';
        } catch (error) {
            note.classList.add('error');
            note.textContent = A.errorText(error, 'No se pudo descargar la plantilla.');
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
        A.state.selectedFile = file;
        fileChip.hidden = false;
        fileChip.textContent = `${file.name} · ${A.formatBytes(file.size)}`;
        uploadButton.disabled = false;
    }

    // ---------- Step 2b: direct-to-S3 upload (pre-signed) + validate ----------
    // Real sales exports easily exceed the ~10 MB API Gateway limit, so the file
    // is uploaded straight to S3 and only its key travels through the API.
    uploadButton.addEventListener('click', async () => {
        if (!A.state.selectedFile) return;
        const note = qs('#uploadNote');
        note.className = 'form-note';
        note.textContent = '';
        if (qs('#contractSelect').value !== 'ventas' && !A.state.datasetId) {
            note.classList.add('error');
            note.textContent = 'Primero carga el archivo de Ventas: es el que crea el ' +
                'conjunto de datos al que se enganchan los demás.';
            return;
        }
        const done = setButtonBusy(uploadButton, 'Subiendo…');
        try {
            const file = A.state.selectedFile;

            // 1-2) FILES signs the PUT and the bytes go straight to S3 (no API
            //    Gateway limit), with a live percentage so a large/slow upload
            //    never looks frozen.
            const sizeLabel = A.formatBytes(file.size);
            note.textContent = `Subiendo ${sizeLabel} a almacenamiento seguro… 0%`;
            const fileKey = await window.SD_API.uploadToBucket(file, (ratio) => {
                note.textContent =
                    `Subiendo ${sizeLabel} a almacenamiento seguro… ${Math.round(ratio * 100)}%`;
            });

            // 3) Ask ingest to read it from S3, validate and normalize —
            //    synchronously. The response already carries the outcome.
            //    One file, one contract: sales creates the dataset and the other
            //    three attach to the one already loaded.
            note.textContent = 'Validando y procesando el archivo…';
            const contract = qs('#contractSelect').value;
            if (contract === 'ventas') {
                handleIngestResponse(await window.SD_API.post(
                    `${A.INGEST_URL}/v1/ingest/excel-from-s3`,
                    { file_key: fileKey, file_name: file.name }
                ));
            } else {
                const summary = await window.SD_API.post(
                    `${A.INGEST_URL}/v1/ingest/${encodeURIComponent(A.state.datasetId)}` +
                    `/${A.COMPANION_PATHS[contract]}/from-s3`,
                    { file_key: fileKey, file_name: file.name }
                );
                note.classList.add('success');
                note.textContent =
                    `${A.CONTRACT_LABELS[contract]}: ${summary.summary.valid_rows} fila(s) ` +
                    `cargada(s).`;
                toast(`${A.CONTRACT_LABELS[contract]} cargado.`, 'success');
            }
        } catch (error) {
            note.classList.add('error');
            note.textContent = A.errorText(error, 'No se pudo subir el archivo.');
            toast(A.errorText(error, 'Error al subir.'), 'error');
        } finally {
            done();
        }
    });

    function handleIngestResponse(response) {
        A.setDataset(response.dataset_id);
        renderIngestSummary(response.summary, response.status);

        qs('#stepValidation').hidden = false;

        const isValid = response.status === 'validated';
        qs('#validatedBlock').hidden = !isValid;
        qs('#errorsBlock').hidden = isValid;
        qs('#analysisArea').hidden = !isValid;

        const rejected = (response.summary && response.summary.error_rows) || 0;
        if (isValid) {
            renderRejectedNotice(response.dataset_id, response.summary);
            toast(rejected > 0
                ? `${A.formatInt(response.summary.valid_rows)} filas cargadas · ` +
                  `${A.formatInt(rejected)} quedaron fuera.`
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
            <p><strong>${A.formatInt(summary.valid_rows || 0)}</strong> filas se cargaron.
            <strong>${A.formatInt(rejected)}</strong> quedaron fuera por datos incompletos —
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
                `${A.INGEST_URL}/v1/ingest/${encodeURIComponent(datasetId)}/rejected`,
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
            toast(A.errorText(error, 'No se pudo descargar el archivo.'), 'error');
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
                label: 'Filas válidas', value: `${A.formatInt(valid)} / ${A.formatInt(total)}`,
                variant: errors === 0 ? 'success' : 'warning'
            },
            { label: 'Errores', value: A.formatInt(errors), variant: errors === 0 ? '' : 'warning' },
            { label: 'Puntos de venta', value: A.formatInt(summary.unique_points_of_sale || 0) },
            { label: 'Productos', value: A.formatInt(summary.unique_products || 0) },
            {
                label: 'Rango de fechas',
                value: A.formatDateRange(summary.date_range_start, summary.date_range_end)
            }
        ];
        const container = qs('#ingestSummary');
        container.innerHTML = '';
        cards.forEach((card) => container.appendChild(A.metricCard(card)));
        A.arrangeMetrics(container);
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
        issues.slice(0, A.MAX_ISSUES_SHOWN).forEach((issue) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${issue.row ?? '-'}</td>
                <td>${A.escapeHtml(issue.column || '(archivo)')}</td>
                <td>${issue.value == null ? '<em>vacío</em>' : A.escapeHtml(String(issue.value))}</td>
                <td>${A.escapeHtml(validationMessage(issue.rule_code))}</td>
            `;
            tbody.appendChild(row);
        });
        if (issues.length > A.MAX_ISSUES_SHOWN) {
            const row = document.createElement('tr');
            row.className = 'empty-row';
            row.innerHTML = `<td colspan="4">… y ${A.formatInt(issues.length - A.MAX_ISSUES_SHOWN)} ` +
                'problemas adicionales.</td>';
            tbody.appendChild(row);
        }
    }

    Object.assign(A, {
        renderIngestSummary, renderIssues, renderRejectedNotice
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
