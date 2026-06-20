'use strict';

/**
 * Playground shell — wires the page-level concerns shared across the three
 * tabs (Datasets, Classification, Linear Regression):
 *   - Auth guard + logout
 *   - Tab switching
 *   - A small client for the FILES service (upload / list / read)
 *   - A permissive CSV/TXT parser (auto-detects delimiter, casts numbers)
 *   - Shared in-memory state (datasets cache + the currently selected
 *     payload for each downstream tab)
 *
 * Per-tab modules attach themselves to `window.SD_PLAYGROUND_*` and read
 * from `window.SD_PLAYGROUND_STATE`.
 */
(function () {

    // ---------- Auth + tabs ----------
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.SD_AUTH.requireAuth()) return;
        const { qs, qsAll } = window.SD_UI;
        qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
        qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());

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
                document.dispatchEvent(
                    new CustomEvent('sd:tab-changed', { detail: { tab: target } })
                );
            });
        });
    });

    // ---------- Shared state ----------
    window.SD_PLAYGROUND_STATE = {
        // file_key (S3) → { rows: number[][], header: string[]|null, raw: string,
        //                   parsedAt: Date }
        datasets: {},
        // The dataset object currently selected on each downstream tab.
        // Shape: { fileKey, rows, header, options }
        classificationDataset: null,
        predictionDataset: null
    };

    // ---------- FILES client ----------
    const FILES_URL = window.SD_CONFIG.FILES_URL.replace(/\/$/, '');
    const BUCKET = 'ml-data-file-handler';

    function _bearer() {
        return `Bearer ${window.SD_AUTH.getToken()}`;
    }

    async function uploadFile(file, filePath = '') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('bucket_name', BUCKET);
        formData.append('file_path', filePath);
        const url = `${FILES_URL}/v1/s3/upload`;
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Authorization': _bearer() },
            body: formData
        });
        return _handleJSON(response, 'upload');
    }

    async function listFiles(prefix = '') {
        const url = `${FILES_URL}/v1/s3/list-files`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': _bearer(),
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ bucket_name: BUCKET, prefix })
        });
        return _handleJSON(response, 'list-files');
    }

    async function readFileAsText(fileKey) {
        // FILES /v1/s3/read/{bucket}/{file_key} expects the key without
        // leading slash; encode each segment so that paths like
        // "ingest/ventas_demo.xlsx" survive intact.
        const safeKey = fileKey.split('/').map(encodeURIComponent).join('/');
        const url = `${FILES_URL}/v1/s3/read/${BUCKET}/${safeKey}`;
        const response = await fetch(url, {
            method: 'GET',
            headers: { 'Authorization': _bearer() }
        });
        if (response.status === 401) {
            window.SD_AUTH.clearSession();
            window.location.href = window.SD_CONFIG.LOGIN_PATH;
            throw new Error('Sesión expirada.');
        }
        if (!response.ok) {
            let detail = '';
            try { detail = (await response.json()).detail || ''; } catch (_) {}
            throw new Error(detail || `FILES read failed (${response.status}).`);
        }
        // FILES may wrap CSV/TXT inside a JSON envelope with a 'content' field,
        // or return the raw text directly. Tolerate both.
        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        if (contentType.includes('application/json')) {
            const payload = await response.json();
            if (typeof payload === 'string') return payload;
            return payload.content || payload.data || payload.body || JSON.stringify(payload);
        }
        return await response.text();
    }

    async function _handleJSON(response, opName) {
        if (response.status === 401) {
            window.SD_AUTH.clearSession();
            window.location.href = window.SD_CONFIG.LOGIN_PATH;
            throw new Error('Sesión expirada.');
        }
        let payload = null;
        try { payload = await response.json(); } catch (_) {}
        if (!response.ok) {
            const detail = payload && (payload.detail || payload.message);
            throw new Error(detail || `FILES ${opName} failed (${response.status}).`);
        }
        return payload;
    }

    window.SD_PLAYGROUND_FILES = {
        BUCKET,
        uploadFile,
        listFiles,
        readFileAsText
    };

    // ---------- CSV / TXT parser ----------
    /**
     * Parses the raw text content of a CSV/TXT into a uniform shape:
     *   { delimiter, header, rows, columnCount }
     *
     * Options:
     *   - delimiter: 'auto' | ',' | ';' | '\t'
     *   - skipRows: number of leading rows to drop (used before reading header)
     *   - hasHeader: when true, the first non-skipped row becomes the header
     *   - maxRows: stop after this many data rows (preview only)
     */
    function parseTabular(text, options) {
        const opts = Object.assign(
            { delimiter: 'auto', skipRows: 0, hasHeader: false, maxRows: null },
            options || {}
        );
        const rawLines = text.split(/\r?\n/).filter((line) => line.length > 0);
        const lines = rawLines.slice(Math.max(0, opts.skipRows));
        if (lines.length === 0) {
            return { delimiter: ',', header: null, rows: [], columnCount: 0 };
        }
        let delimiter = opts.delimiter;
        if (delimiter === 'auto') {
            const sample = lines.slice(0, 5).join('\n');
            const candidates = [',', ';', '\t', '|'];
            delimiter = candidates.reduce((best, cand) =>
                (sample.split(cand).length > sample.split(best).length ? cand : best)
            , ',');
        }

        const splitLine = (line) => line.split(delimiter).map((cell) => cell.trim());

        let header = null;
        let dataStart = 0;
        if (opts.hasHeader) {
            header = splitLine(lines[0]);
            dataStart = 1;
        }

        const rows = [];
        for (let i = dataStart; i < lines.length; i++) {
            if (opts.maxRows && rows.length >= opts.maxRows) break;
            const cells = splitLine(lines[i]).map(_castCell);
            rows.push(cells);
        }
        const columnCount = rows[0] ? rows[0].length : (header ? header.length : 0);
        return { delimiter, header, rows, columnCount };
    }

    function _castCell(value) {
        if (value === '') return null;
        const asNumber = Number(value);
        if (!Number.isNaN(asNumber) && /^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$/.test(value)) {
            return asNumber;
        }
        return value;
    }

    function isNumericColumn(rows, columnIndex) {
        if (rows.length === 0) return false;
        let numericCount = 0;
        const sample = rows.slice(0, Math.min(rows.length, 100));
        for (const row of sample) {
            const value = row[columnIndex];
            if (value == null) continue;
            if (typeof value === 'number' && !Number.isNaN(value)) numericCount++;
        }
        return numericCount >= sample.length * 0.8;
    }

    window.SD_PLAYGROUND_PARSER = {
        parseTabular,
        isNumericColumn
    };

    // ---------- Chart.js dark defaults ----------
    document.addEventListener('DOMContentLoaded', () => {
        if (typeof window.Chart === 'undefined') return;
        window.Chart.defaults.color = '#0d1e4c';
        window.Chart.defaults.borderColor = '#e3dccc';
        window.Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
    });
})();
