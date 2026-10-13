'use strict';

/**
 * What the analysis pages keep in the tab: the dataset, the reporting window
 * and the computed results. The summary of an area and each option page read
 * and write the same cache, so opening an option from its summary shows what
 * the summary already computed instead of asking for it again.
 */
(function (A) {
    const DATASET_KEY = 'sd_excel_dataset_id';
    const CACHE_KEY = 'sd_excel_results';
    const VIEW_KEY = 'sd_excel_view';
    const PERIOD_KEY = 'sd_excel_period';

    const datasetId = () => sessionStorage.getItem(DATASET_KEY) || null;

    function readStoredPeriod() {
        try {
            return JSON.parse(sessionStorage.getItem(PERIOD_KEY) || 'null') || {};
        } catch (parseError) {
            return {};
        }
    }

    /** The ?date_from=&date_to= suffix every analysis endpoint accepts. */
    function periodQuery(period) {
        const params = new URLSearchParams();
        if (period.from) params.set('date_from', period.from);
        if (period.to) params.set('date_to', period.to);
        const query = params.toString();
        return query ? `?${query}` : '';
    }

    // Analyses are expensive (the affinity engine takes ~30 s) and the session
    // can expire mid-review. Keeping the computed payloads in sessionStorage
    // means a reload — or a re-login in the same tab — restores exactly the
    // screen the user was reading, instead of forcing a re-run.
    function readCache() {
        try {
            const cache = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
            if (cache && cache.datasetId === datasetId()) return cache;
        } catch (parseError) {
            // A corrupt cache is not an error: it just means "nothing cached".
        }
        return { datasetId: datasetId(), results: {} };
    }

    function cacheResult(kind, payload) {
        const cache = readCache();
        cache.datasetId = datasetId();
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

    Object.assign(A, {
        STORE_KEYS: { DATASET_KEY, CACHE_KEY, VIEW_KEY, PERIOD_KEY },
        readStoredPeriod, periodQuery, cacheResult, cachedResult
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
