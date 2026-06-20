'use strict';

/**
 * Datasets tab — uploads a local .csv/.txt to S3 through the FILES service,
 * lists the contents of the bucket and previews any selected item parsed
 * client-side. From the preview the user can ship the parsed payload to
 * either the Classification or the Linear Regression tab.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH || !window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;
    const FILES = window.SD_PLAYGROUND_FILES;
    const PARSER = window.SD_PLAYGROUND_PARSER;
    const STATE = window.SD_PLAYGROUND_STATE;

    const DATASET_PREFIX = 'playground';
    const PREVIEW_MAX_ROWS = 25;

    qs('#bucketLabel').textContent = FILES.BUCKET;

    // ---------- Upload ----------
    const fileInput = qs('#datasetFileInput');
    const uploadZone = qs('#datasetUploadZone');
    const fileChip = qs('#datasetFileChip');
    const uploadButton = qs('#datasetUploadButton');
    const uploadNote = qs('#datasetUploadNote');
    let stagedFile = null;

    qs('#datasetChooseLink').addEventListener('click', (event) => {
        event.preventDefault();
        fileInput.click();
    });
    fileInput.addEventListener('change', () => {
        const file = fileInput.files && fileInput.files[0];
        if (file) stage(file);
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
        if (file) stage(file);
    });

    function stage(file) {
        if (!/\.(csv|txt)$/i.test(file.name)) {
            toast('Solo se aceptan .csv o .txt en este módulo.', 'error');
            return;
        }
        stagedFile = file;
        fileChip.hidden = false;
        fileChip.textContent = `${file.name} · ${formatBytes(file.size)}`;
        uploadButton.disabled = false;
    }

    uploadButton.addEventListener('click', async () => {
        if (!stagedFile) return;
        const done = setButtonBusy(uploadButton, 'Subiendo…');
        uploadNote.className = 'form-note';
        uploadNote.textContent = '';
        try {
            const payload = await FILES.uploadFile(stagedFile, DATASET_PREFIX);
            const uploadedKey = payload.file_key
                || payload.file_s3_key
                || `${DATASET_PREFIX}/${stagedFile.name}`;
            uploadNote.classList.add('success');
            uploadNote.textContent = `OK — subido como ${uploadedKey}`;
            toast(`"${stagedFile.name}" subido al bucket.`, 'success');
            await refreshList();
            // Auto-select the just-uploaded file in the list.
            highlight(uploadedKey);
        } catch (error) {
            uploadNote.classList.add('error');
            uploadNote.textContent = error.message || 'Error al subir.';
            toast(error.message || 'Error al subir.', 'error');
        } finally {
            done();
        }
    });

    // ---------- Listing ----------
    const list = qs('#datasetList');
    const listNote = qs('#datasetListNote');
    const countEl = qs('#datasetCount');
    qs('#datasetRefreshButton').addEventListener('click', () => refreshList());

    async function refreshList() {
        listNote.className = 'form-note';
        listNote.textContent = 'Listando archivos…';
        list.innerHTML = '';
        try {
            const payload = await FILES.listFiles();
            const items = Array.isArray(payload) ? payload : (payload.files || payload.items || []);
            const flatKeys = items.map((item) =>
                typeof item === 'string' ? item : (item.key || item.file_key || item.name)
            ).filter(Boolean);
            const filtered = flatKeys.filter((key) => /\.(csv|txt)$/i.test(key)).sort();
            renderList(filtered);
            countEl.textContent = `${filtered.length} archivo(s)`;
            listNote.textContent = '';
        } catch (error) {
            listNote.classList.add('error');
            listNote.textContent = error.message || 'No se pudo listar.';
            renderList([]);
            countEl.textContent = '—';
        }
    }

    function renderList(keys) {
        list.innerHTML = '';
        if (keys.length === 0) {
            const empty = document.createElement('li');
            empty.className = 'empty';
            empty.textContent = 'Sin .csv o .txt en el bucket.';
            list.appendChild(empty);
            return;
        }
        keys.forEach((key) => {
            const item = document.createElement('li');
            item.dataset.key = key;
            const left = document.createElement('span');
            left.textContent = key;
            const right = document.createElement('span');
            right.className = 'ext-tag';
            right.textContent = key.split('.').pop().toUpperCase();
            item.appendChild(left);
            item.appendChild(right);
            item.addEventListener('click', () => loadPreview(key));
            list.appendChild(item);
        });
    }

    function highlight(key) {
        qsAll('#datasetList li').forEach((node) => {
            node.classList.toggle('is-selected', node.dataset.key === key);
        });
    }

    // Initial load.
    refreshList();

    // ---------- Preview ----------
    const previewCard = qs('#datasetPreviewCard');
    const previewName = qs('#datasetPreviewName');
    const previewSummary = qs('#datasetPreviewSummary');
    const previewTable = qs('#datasetPreviewTable');
    const previewDelimiter = qs('#previewDelimiter');
    const previewSkipRows = qs('#previewSkipRows');
    const previewHasHeader = qs('#previewHasHeader');
    const loadIntoClassification = qs('#loadIntoClassificationButton');
    const loadIntoPrediction = qs('#loadIntoPredictionButton');
    const loadIntoNote = qs('#loadIntoNote');

    let currentKey = null;
    let currentRawText = null;
    let currentParsed = null;

    async function loadPreview(fileKey) {
        currentKey = fileKey;
        highlight(fileKey);
        previewName.textContent = fileKey;
        previewSummary.innerHTML = '';
        previewTable.querySelector('thead').innerHTML = '';
        previewTable.querySelector('tbody').innerHTML = '';
        loadIntoNote.className = 'form-note';
        loadIntoNote.textContent = 'Descargando…';
        loadIntoClassification.disabled = true;
        loadIntoPrediction.disabled = true;
        previewCard.hidden = false;
        try {
            currentRawText = await FILES.readFileAsText(fileKey);
            // Smart-default has_header: TXT in the notebook is headerless,
            // CSV usually has a header.
            previewHasHeader.checked = fileKey.toLowerCase().endsWith('.csv');
            reparse();
            loadIntoNote.classList.add('success');
            loadIntoNote.textContent = 'Listo. Ajustá los parámetros si hace falta y elegí destino.';
        } catch (error) {
            loadIntoNote.classList.add('error');
            loadIntoNote.textContent = error.message || 'Error al descargar.';
            previewCard.hidden = false;
        }
    }

    qs('#previewReparseButton').addEventListener('click', () => reparse());
    previewDelimiter.addEventListener('change', () => reparse());
    previewHasHeader.addEventListener('change', () => reparse());
    previewSkipRows.addEventListener('change', () => reparse());

    function reparse() {
        if (currentRawText == null) return;
        const delim = previewDelimiter.value === '\\t' ? '\t' : previewDelimiter.value;
        const parsed = PARSER.parseTabular(currentRawText, {
            delimiter: delim,
            skipRows: Number(previewSkipRows.value) || 0,
            hasHeader: previewHasHeader.checked,
            maxRows: null
        });
        currentParsed = parsed;
        STATE.datasets[currentKey] = {
            rows: parsed.rows,
            header: parsed.header,
            raw: currentRawText,
            parsedAt: new Date()
        };
        renderPreviewSummary(parsed);
        renderPreviewTable(parsed);
        loadIntoClassification.disabled = parsed.rows.length === 0;
        loadIntoPrediction.disabled = parsed.rows.length === 0;
    }

    function renderPreviewSummary(parsed) {
        const numericCols = (parsed.rows[0] || []).map(
            (_, idx) => PARSER.isNumericColumn(parsed.rows, idx)
        );
        const numericCount = numericCols.filter(Boolean).length;
        const cards = [
            { label: 'Filas', value: String(parsed.rows.length) },
            { label: 'Columnas', value: String(parsed.columnCount) },
            { label: 'Numéricas', value: String(numericCount) },
            { label: 'Delimiter', value: parsed.delimiter === '\t' ? 'tab' : `'${parsed.delimiter}'` }
        ];
        previewSummary.innerHTML = '';
        cards.forEach((card) => {
            const node = document.createElement('div');
            node.className = 'metric';
            node.innerHTML = `<p class="metric-label">${card.label}</p>` +
                             `<p class="metric-value muted">${card.value}</p>`;
            previewSummary.appendChild(node);
        });
    }

    function renderPreviewTable(parsed) {
        const thead = previewTable.querySelector('thead');
        const tbody = previewTable.querySelector('tbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';
        const headerCells = parsed.header
            || Array.from({ length: parsed.columnCount }, (_, idx) => `col_${idx}`);
        const headRow = document.createElement('tr');
        headerCells.forEach((label) => {
            const th = document.createElement('th');
            th.textContent = label;
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        const visibleRows = parsed.rows.slice(0, PREVIEW_MAX_ROWS);
        visibleRows.forEach((row) => {
            const tr = document.createElement('tr');
            row.forEach((cell) => {
                const td = document.createElement('td');
                td.textContent = cell == null ? '' :
                    (typeof cell === 'number' ? formatNumber(cell) : String(cell));
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        if (parsed.rows.length > visibleRows.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = parsed.columnCount;
            td.style.textAlign = 'center';
            td.style.color = 'var(--muted)';
            td.textContent = `… ${parsed.rows.length - visibleRows.length} fila(s) más, no mostradas.`;
            tr.appendChild(td);
            tbody.appendChild(tr);
        }
    }

    // ---------- Dispatch to downstream tabs ----------
    loadIntoClassification.addEventListener('click', () => {
        if (!currentParsed) return;
        STATE.classificationDataset = {
            fileKey: currentKey,
            header: currentParsed.header,
            rows: currentParsed.rows,
            columnCount: currentParsed.columnCount
        };
        document.dispatchEvent(
            new CustomEvent('sd:dataset-loaded', { detail: { tab: 'classification' } })
        );
        switchTab('classification');
        toast('Dataset cargado en Clasificación.', 'success');
    });

    loadIntoPrediction.addEventListener('click', () => {
        if (!currentParsed) return;
        STATE.predictionDataset = {
            fileKey: currentKey,
            header: currentParsed.header,
            rows: currentParsed.rows,
            columnCount: currentParsed.columnCount
        };
        document.dispatchEvent(
            new CustomEvent('sd:dataset-loaded', { detail: { tab: 'prediction' } })
        );
        switchTab('prediction');
        toast('Dataset cargado en Regresión Lineal.', 'success');
    });

    function switchTab(name) {
        const tab = document.querySelector(`.tab[data-tab="${name}"]`);
        if (tab) tab.click();
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    function formatNumber(value) {
        if (Number.isInteger(value)) return String(value);
        return Number(value).toFixed(3);
    }
});
