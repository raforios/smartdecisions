'use strict';

/**
 * The pieces of an area's summary (level 1): one block per option with its
 * figure, a line and an optional small visual. Each analysis is asked once
 * and kept in the cache the option pages read (analyses/store.js), so opening
 * an option from its summary shows it at once.
 */
(function overviewModule() {
    const A = window.SD_ANALYSIS;
    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

    const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const number = (value, decimals = 0) => (value == null || isNaN(value) ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
    const signed = (value) => `${value > 0 ? '+' : ''}${number(value, 1)} %`;
    const day = (iso) => {
        const [year, month, date] = String(iso || '').split('-');
        return MONTHS[Number(month) - 1] ? `${Number(date)} de ${MONTHS[Number(month) - 1]} de ${year}` : '';
    };
    const kpi = (kpis, code) => ((kpis || []).find((card) => card.metric_code === code) || {}).value;
    const tile = (name) => document.querySelector(`[data-tile="${name}"]`);

    /** Title, figure, one line and an optional small visual. */
    function paint(name, title, value, line, visual = '') {
        tile(name).innerHTML = `<p class="sd-tile-title">${title}</p>` +
            `<p class="sd-tile-value">${value}</p><p class="sd-tile-line">${line}</p>` +
            (visual ? `<div class="sd-tile-visual">${visual}</div>` : '');
    }

    /** A bar split in shares, with its legend under it: [label, percent, colour]. */
    function shares(parts) {
        return `<div class="sd-bar">${parts.map(([, share, color]) =>
            `<span style="width:${Math.max(share, 0)}%;background:${color}"></span>`).join('')}</div>` +
            `<div class="sd-bar-legend">${parts.map(([label, share, color]) =>
                `<span><i style="background:${color}"></i>${label} ${number(share, 1)} %</span>`).join('')}</div>`;
    }

    function progress(percent) {
        return `<div class="sd-progress"><span style="width:${Math.min(Math.max(percent, 0), 100)}%">` +
            '</span></div>';
    }

    /** Grey bars under each block's title until its figure arrives. */
    function loading(titles) {
        document.querySelectorAll('[data-tile]').forEach((node) => {
            node.innerHTML = `<p class="sd-tile-title">${titles[node.dataset.tile] || ''}</p>` +
                '<span class="sd-skeleton is-big"></span><span class="sd-skeleton"></span>';
        });
    }

    /** One analysis: the cached answer, or a fresh one that is then cached. */
    function analysis(kind, path, render, onFail) {
        const cached = A.cachedResult(kind);
        if (cached) {
            render(cached.payload);
            return;
        }
        window.SD_API.get(path).then((payload) => {
            A.cacheResult(kind, payload);
            render(payload);
        }).catch(onFail);
    }

    window.SD_OVERVIEW = { token, number, signed, day, kpi, tile, paint, shares, progress, loading, analysis };
})();
