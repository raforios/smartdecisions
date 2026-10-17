'use strict';

/**
 * The frame every analysis page shares: dataset and period, the result
 * cache, which section is on view, the analysis menu, the reporting window
 * and the start-up that brings a returning user back to their screen.
 */
(function (A) {
    // Every amount column shows Bs, USD and USDT under one header.
    window.SD_MONEY.expandHeaders(document);
    if (!window.SD_AUTH.requireAuth()) return;

    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    const INGEST_URL = window.SD_CONFIG.API_URL;
    const ANALYTICS_URL = window.SD_CONFIG.API_URL;

    // The dataset id is persisted so a page reload / session refresh never forces
    // re-uploading the file: the data already lives in S3 + DynamoDB.
    const { DATASET_KEY, CACHE_KEY, VIEW_KEY, PERIOD_KEY } = A.STORE_KEYS;
    // One file per contract. Sales creates the dataset; these three attach to it.
    const COMPANION_PATHS = { cobros: 'collections', stock: 'stock',
                              visitas: 'visits', objetivos: 'objectives', compras: 'purchases' };
    const CONTRACT_LABELS = { ventas: 'Ventas', cobros: 'Cobros', stock: 'Stock',
                              visitas: 'Visitas', objetivos: 'Objetivos', compras: 'Compras' };
    const MAX_ISSUES_SHOWN = 200;
    const { cacheResult, cachedResult } = A;

    const state = {
        selectedFile: null,
        datasetId: sessionStorage.getItem(DATASET_KEY) || null,
        period: A.readStoredPeriod(),
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
    const analysisQuery = () => A.periodQuery(state.period);

    // One analysis can feed more than one view: the summary and the volume
    // source come from the same response, and both have to show when it was
    // computed. That is why the stamp is set on a list of nodes, not on one.
    const STAMP_IDS = {
        summary: ['stampSummary', 'stampVolume'],
        opportunities: ['stampOpportunities'],
        segmentation: ['stampSegmentation'],
        portfolio: ['stampPortfolio'],
        objectives: ['stampObjectives'],
        fx: ['stampFx'],
        receivables: ['stampReceivables'],
        stock: ['stampStock'],
        stockHistory: ['stampStockHistory'],
        purchases: ['stampPurchases']
    };

    function markStamp(kind, timestamp) {
        const time = new Date(timestamp).toLocaleTimeString('es-BO',
            { hour: '2-digit', minute: '2-digit' });
        (STAMP_IDS[kind] || []).forEach((id) => {
            const node = document.getElementById(id);
            if (node) node.textContent = `Calculado a las ${time}`;
        });
    }

    // The analysis sections are mutually exclusive views (tab-like): showing one
    // hides the others, so the page doesn't grow into a long vertical stack.
    // Each area page carries only its own sections; the others are skipped.
    const ANALYSIS_SECTIONS = ['stepDashboard', 'stepVolume', 'stepForecast',
        'stepSegmentation', 'stepOpportunities', 'stepPortfolio', 'stepReceivables',
        'stepStock', 'stepObjectives', 'stepFx', 'stepStockHistory', 'stepPurchases'];
    function showAnalysisView(sectionId, scroll = true) {
        ANALYSIS_SECTIONS.forEach((id) => {
            const section = document.getElementById(id);
            if (section) section.hidden = (id !== sectionId);
        });
        sessionStorage.setItem(VIEW_KEY, sectionId);
        resizeChartsIn(sectionId);
        // An option page shows only its view, already at the top.
        if (scroll && !document.body.dataset.analysis) {
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
            Object.values(A.chartRegistry).forEach((chart) => {
                if (chart && section.contains(chart.canvas)) chart.resize();
            });
        }, 0);
    }

    // Which cached analysis belongs to each section, so a reload lands the user
    // back where they were instead of on an empty screen.
    const VIEW_TO_KIND = {
        stepDashboard: 'summary',
        stepVolume: 'summary',
        stepOpportunities: 'opportunities',
        stepSegmentation: 'segmentation',
        stepForecast: 'forecast',
        stepReceivables: 'receivables',
        stepStock: 'stock',
        stepObjectives: 'objectives',
        stepFx: 'fx',
        stepStockHistory: 'stockHistory',
        stepPurchases: 'purchases'
    };

    function restoreLastView() {
        const sectionId = sessionStorage.getItem(VIEW_KEY);
        const kind = VIEW_TO_KIND[sectionId];
        // The last view may belong to another area's page.
        if (!kind || !document.getElementById(sectionId)) return;
        const cached = cachedResult(kind);
        if (!cached) return;
        if (kind === 'forecast') {
            A.restoreForecastControls(cached.payload.params);
            A.renderForecast(cached.payload.data, cached.payload.compare);
            showAnalysisView('stepForecast', false);
        } else {
            ANALYSES[kind].render(cached.payload, sectionId);
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
            render: (...args) => A.renderCommercialSummary(...args)
        },
        opportunities: {
            busy: 'Analizando…', running: 'Ejecutando el motor de oportunidades…',
            ready: 'Oportunidades listas.', failed: 'El motor falló.',
            // The engine takes ~30 s: opening the page reads the last stored run
            // of the dataset, and only a recalculation, a chosen period or a
            // dataset never analysed runs it again.
            fetch: (force) => {
                const run = () => window.SD_API.post(analysisUrl('run'));
                if (force || state.period.from || state.period.to) return run();
                return window.SD_API.get(`${ANALYTICS_URL}/v1/analytics/results/` +
                    `${encodeURIComponent(state.datasetId)}`).catch(run);
            },
            render: (...args) => A.renderOpportunities(...args)
        },
        segmentation: {
            busy: 'Segmentando…', running: 'Segmentando clientes…',
            ready: 'Segmentación lista.', failed: 'No se pudo segmentar.',
            fetch: () => window.SD_API.get(analysisUrl('segmentation')),
            render: (...args) => A.renderSegmentation(...args)
        },
        fx: {
            busy: 'Midiendo…', running: 'Midiendo el efecto del tipo de cambio…',
            ready: 'Efecto del tipo de cambio listo.',
            failed: 'No se pudo medir el efecto del tipo de cambio.',
            fetch: () => window.SD_API.get(fxUrl()),
            render: (...args) => A.renderFx(...args)
        },
        portfolio: {
            busy: 'Revisando…', running: 'Revisando la salud de la cartera…',
            ready: 'Salud de cartera lista.', failed: 'No se pudo revisar la cartera.',
            fetch: () => window.SD_API.get(analysisUrl('portfolio')),
            render: (...args) => A.renderPortfolio(...args)
        },
        objectives: {
            busy: 'Midiendo…', running: 'Midiendo el cumplimiento contra objetivo…',
            ready: 'Cumplimiento listo.',
            failed: 'No se pudo medir el cumplimiento.',
            fetch: () => window.SD_API.get(analysisUrl('objectives')),
            render: (...args) => A.renderObjectives(...args)
        },
        receivables: {
            busy: 'Calculando…', running: 'Leyendo la cartera por cobrar…',
            ready: 'Cuentas por cobrar listas.',
            failed: 'No se pudo calcular la cartera por cobrar.',
            fetch: () => window.SD_API.get(analysisUrl('receivables')),
            render: (...args) => A.renderReceivables(...args)
        },
        stock: {
            busy: 'Leyendo…', running: 'Leyendo el stock del día…',
            ready: 'Stock del día listo.', failed: 'No se pudo leer el stock.',
            fetch: () => window.SD_API.get(analysisUrl('stock')),
            render: (...args) => A.renderStock(...args)
        },
        stockHistory: {
            busy: 'Leyendo…', running: 'Leyendo las fotos del inventario…',
            ready: 'Evolución del inventario lista.',
            failed: 'No se pudo leer la evolución del inventario.',
            fetch: () => window.SD_API.get(analysisUrl('stock-history')),
            render: (...args) => A.renderStockHistory(...args)
        },
        purchases: {
            busy: 'Leyendo…', running: 'Leyendo las compras…',
            ready: 'Compras listas.', failed: 'No se pudieron leer las compras.',
            fetch: () => window.SD_API.get(analysisUrl('purchases')),
            render: (...args) => A.renderPurchases(...args)
        }
    };

    /**
     * The FX view always reads the file in bolivianos —it needs the original
     * amounts— and adds which dollar and the rate to simulate, if any.
     */
    function fxUrl() {
        const params = new URLSearchParams();
        if (state.period.from) params.set('date_from', state.period.from);
        if (state.period.to) params.set('date_to', state.period.to);
        params.set('source', qs('#fxSource').value);
        if (qs('#fxRate').value) params.set('rate', qs('#fxRate').value);
        return `${ANALYTICS_URL}/v1/analytics/fx-effect/` +
            `${encodeURIComponent(state.datasetId)}?${params.toString()}`;
    }

    function analysisUrl(kind) {
        return `${ANALYTICS_URL}/v1/analytics/${kind}/` +
            `${encodeURIComponent(state.datasetId)}${analysisQuery()}`;
    }

    /**
     * Shows an analysis, reusing the cached payload unless a recalculation is
     * explicitly requested. `trigger` is the button that shows the busy state.
     *
     * `view` overrides which section the renderer ends on. It exists because
     * one response can answer two questions: the commercial summary and the
     * volume source travel together, and asking for the second must not cost a
     * second call to the same endpoint.
     */
    async function openAnalysis(kind, trigger, force = false, view = null) {
        if (!state.datasetId) return;
        const analysis = ANALYSES[kind];
        if (!force) {
            const cached = cachedResult(kind);
            if (cached) {
                analysis.render(cached.payload, view);
                markStamp(kind, cached.at);
                return;
            }
        }
        const note = qs('#runNote');
        note.className = 'form-note';
        note.textContent = analysis.running;
        // An option page opens its analysis on load, with no button to busy.
        const done = trigger ? setButtonBusy(trigger, analysis.busy) : () => {};
        try {
            const payload = await analysis.fetch(force);
            cacheResult(kind, payload);
            analysis.render(payload, view);
            markStamp(kind, Date.now());
            // Opened by its page on load, the result on screen says it is ready.
            note.classList.add('success');
            note.textContent = trigger ? analysis.ready : '';
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || analysis.failed;
            toast(error.message || analysis.failed, 'error');
        } finally {
            done();
        }
    }

    /** Opens an analysis by the name its card or its page carries. */
    function openByName(kind, trigger) {
        if (kind === 'forecast') A.openForecast(trigger);
        else if (kind === 'volume') openAnalysis('summary', trigger, false, 'stepVolume');
        else openAnalysis(kind, trigger);
    }

    // The area pages that still list their analyses as cards.
    const menu = qs('#analysisMenu');
    if (menu) {
        menu.addEventListener('click', (event) => {
            const card = event.target.closest('.analysis-card');
            if (!card || card.disabled) return;
            openByName(card.dataset.analysis, card);
        });
    }

    // "↻ Recalcular" inside each result section: same analysis, fresh numbers.
    qsAll('[data-recalc]').forEach((button) => {
        button.addEventListener('click', () => openAnalysis(
            button.dataset.recalc, button, true, button.dataset.recalcView || null
        ));
    });

    // ---------- Reporting window ----------
    // Today's published rates, asked once to QUOTES, which owns them: the
    // legend under the period bar says what every total in dollars is at.
    let todayRates = null;

    async function loadTodayRates() {
        const today = new Date();
        const start = new Date(today.getTime() - 14 * 86400000);
        const iso = (day) => day.toISOString().slice(0, 10);
        const latest = async (currency) => {
            const answer = await window.SD_API.get(
                `${window.SD_CONFIG.API_URL}/v1/quotes/exchange-rates`,
                { currency, start: iso(start), end: iso(today) });
            const rates = (answer && answer.rates) || [];
            return rates.length ? rates[rates.length - 1].rate : null;
        };
        try {
            const [usd, usdt] = await Promise.all([latest('USD'), latest('USDT')]);
            todayRates = { usd, usdt: usdt || usd };
        } catch (error) {
            todayRates = null;
        }
        renderRatesLegend();
    }

    function renderRatesLegend() {
        const legend = qs('#ratesLegend');
        if (!legend) return;
        const from = state.period.from || '';
        const to = state.period.to || '';
        if (from && to && from.slice(0, 7) === to.slice(0, 7)) {
            legend.textContent = `Mes elegido (${A.formatDateMonth(from.slice(0, 7))}): ` +
                'los montos en USD y USDT están al tipo de cambio del último día de ese mes.';
            return;
        }
        const rates = todayRates
            ? ` (oficial Bs ${A.formatDecimal(todayRates.usd, 2)} · ` +
              `USDT Bs ${A.formatDecimal(todayRates.usdt, 2)})` : '';
        legend.textContent = `Totales en USD y USDT al tipo de cambio de hoy${rates}. ` +
            'Los gráficos por mes, al tipo del último día de cada mes.';
    }
    loadTodayRates();

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
        renderRatesLegend();

        qs('#periodNote').textContent = periodo.filtered
            ? `Mostrando ${A.formatDateRange(periodo.from_date, periodo.to_date)} · ` +
              `${A.formatInt(periodo.rows)} filas`
            : `Datos disponibles: ${A.formatDateRange(periodo.available_from,
                periodo.available_to)}`;
    }

    /**
     * Every `[data-chart-currency]` slot gets the same selector, so each chart
     * card carries its own control. They stay in sync, and changing one only
     * redraws the charts from the cached response: the amounts are all there.
     */
    const CHART_REDRAW = {
        receivables: (payload) => {
            A.renderAging(payload.aging || []);
            A.renderDueCalendar(payload.due_windows || [], payload.due_dates || []);
        },
        stock: (payload) => A.renderStockCharts(payload.products || []),
        stockHistory: (payload) => A.renderStockHistoryChart(payload.photos || []),
        summary: (payload) => A.renderSummaryCharts(payload),
        forecast: (payload) => A.renderForecast(payload.data, payload.compare),
        segmentation: (payload) => A.renderSegmentation(payload)
    };

    function mountChartCurrency() {
        const options = Object.entries(A.CHART_SYMBOLS).map(([code, label]) =>
            `<option value="${code}">${label}</option>`).join('');
        document.querySelectorAll('[data-chart-currency]').forEach((slot) => {
            slot.innerHTML = `<span>Moneda del gráfico</span><select>${options}</select>`;
            const select = slot.querySelector('select');
            select.value = A.chartCurrency;
            select.addEventListener('change', () => {
                A.chartCurrency = select.value;
                sessionStorage.setItem(A.CHART_CURRENCY_KEY, A.chartCurrency);
                document.querySelectorAll('[data-chart-currency] select')
                    .forEach((other) => { other.value = A.chartCurrency; });
                const kind = VIEW_TO_KIND[sessionStorage.getItem(VIEW_KEY)];
                const cached = cachedResult(kind);
                if (cached && cached.payload.available !== false && CHART_REDRAW[kind]) {
                    CHART_REDRAW[kind](cached.payload);
                }
            });
        });
    }
    mountChartCurrency();

    // The upload page has no reporting window.
    if (qs('#periodBar')) qs('#periodApply').addEventListener('click', () => {
        const from = qs('#periodFrom').value;
        const to = qs('#periodTo').value;
        if (from && to && from > to) {
            toast('La fecha "Desde" no puede ser posterior a "Hasta".', 'error');
            return;
        }
        setPeriod({ from: from || null, to: to || null });
        reopenCurrentAnalysis();
    });

    if (qs('#periodBar')) qs('#periodReset').addEventListener('click', () => {
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
        if (kind === 'forecast') A.loadForecast(trigger);
        else openAnalysis(kind, trigger, true);
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
                `${window.SD_CONFIG.API_URL}/v1/ingest/${state.datasetId}`
            );
            const isValid = status.status === 'validated';
            // Only Ventas shows the validation of the file that created the set.
            if (document.getElementById('stepValidation')) {
                A.renderIngestSummary(status.summary, status.status);
                qs('#stepValidation').hidden = false;
                qs('#validatedBlock').hidden = !isValid;
                qs('#errorsBlock').hidden = isValid;
                if (isValid) {
                    A.renderRejectedNotice(status.dataset_id, status.summary);
                } else {
                    A.renderIssues(status.issues || []);
                }
            }
            if (qs('#analysisArea')) qs('#analysisArea').hidden = !isValid;
            // An option page names its analysis; the others return to the last view.
            const own = document.body.dataset.analysis;
            if (own && isValid) openByName(own, null);
            else restoreLastView();
        } catch (error) {
            // The dataset is gone, or belongs to somebody else: forget it and
            // let the user start from the upload step instead of failing.
            setDataset(null);
        }
    }

    // ---------- Parameters not configured ----------
    // Every view judged with a policy says so while the account runs on the
    // service defaults, and points to where it is set (decision 7).
    const POLICY_PATHS = { commercial: 'commercial-policy', credit: 'credit-policy' };
    const POLICY_NAMES = { commercial: 'la política comercial', credit: 'la política de crédito' };
    const policySources = {};

    async function policyNotice(kind, sectionId, knownSource) {
        const section = document.getElementById(sectionId);
        if (!section) return;
        let source = knownSource;
        if (!source) {
            policySources[kind] = policySources[kind] || window.SD_API.get(
                `${ANALYTICS_URL}/v1/analytics/${POLICY_PATHS[kind]}`)
                .then((policy) => policy.source_code).catch(() => null);
            source = await policySources[kind];
        }
        let notice = section.querySelector(`.param-notice[data-policy="${kind}"]`);
        if (source !== 'DEFAULT') {
            if (notice) notice.remove();
            return;
        }
        if (!notice) {
            notice = document.createElement('p');
            notice.className = 'param-notice';
            notice.dataset.policy = kind;
            const head = section.querySelector('.section-head');
            if (head) head.after(notice); else section.prepend(notice);
        }
        notice.innerHTML = `Parámetro no configurado: este análisis usa ${POLICY_NAMES[kind]} ` +
            'por defecto del servicio. <a href="/parametros/index.html">Configúrala en ' +
            'Parámetros</a>.';
    }

    // Started once every analysis script has registered its renderers.
    document.addEventListener('DOMContentLoaded', () => {
        // The interpretation layer reads exactly what each analysis returned: the
        // cached payload is the backend's own response, so nothing is re-shaped for
        // it. The button only appears where SD_CONFIG.API_URL is configured.
        const AI_VIEWS = {
            stepDashboard: ['commercial_summary', 'summary'],
            stepVolume: ['volume_source', 'summary'],
            stepObjectives: ['objectives', 'objectives'],
            stepReceivables: ['receivables', 'receivables'],
            stepStock: ['stock', 'stock'],
            stepOpportunities: ['opportunities', 'opportunities'],
            stepSegmentation: ['segmentation', 'segmentation'],
            stepForecast: ['sales_forecast', 'forecast'],
            stepPortfolio: ['portfolio', 'portfolio'],
        stepFx: ['fx_effect', 'fx']
        };

        if (window.SD_AI) {
            Object.entries(AI_VIEWS).forEach(([sectionId, [viewId, kind]]) => {
                window.SD_AI.registerView(viewId, () => {
                    const cached = cachedResult(kind);
                    if (!cached) return null;
                    // Volume source shares the response with the summary, but
                    // explains its own block: sending the whole response would make
                    // the explanation talk about screens that are not on view.
                    return viewId === 'volume_source'
                        ? cached.payload.volume_source
                        : cached.payload;
                });
                const section = document.getElementById(sectionId);
                const head = section && section.querySelector('.section-head');
                if (head) window.SD_AI.mountExplain(head, viewId, head);
            });
        }

        if (state.datasetId) {
            restoreDataset();
        } else {
            // Same as Rutas: the account's latest validated upload, not an empty screen.
            window.SD_API.ensureDataset().then((datasetId) => {
                if (datasetId) { setDataset(datasetId); restoreDataset(); }
            });
        }
    });

    Object.assign(A, {
        ANALYTICS_URL, COMPANION_PATHS, CONTRACT_LABELS, INGEST_URL, MAX_ISSUES_SHOWN,
        cacheResult, cachedResult, openAnalysis, policyNotice, setDataset, showAnalysisView,
        showPeriodBar, state
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
