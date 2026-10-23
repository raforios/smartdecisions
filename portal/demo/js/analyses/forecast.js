'use strict';

/**
 * Pronóstico de demanda: the projection and its method.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    // ---------- Forecast ----------
    qs('#forecastRun').addEventListener('click', () => loadForecast());

    function openForecast(card) {
        if (!A.state.datasetId) return;
        A.showAnalysisView('stepForecast');
        // Reuse the last projection (with the controls the user had chosen)
        // instead of recomputing it every time the card is clicked.
        const cached = A.cachedResult('forecast');
        if (cached) {
            restoreForecastControls(cached.payload.params);
            renderForecast(cached.payload.data, cached.payload.compare);
            qs('#forecastNote').textContent =
                `Método: ${A.FORECAST_METHODS[cached.payload.data.method] || ''} · ` +
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
        if (!A.state.datasetId) return;
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
            if (A.state.period.from) params.date_from = A.state.period.from;
            if (A.state.period.to) params.date_to = A.state.period.to;
            // Both methods, always: seeing them apart tells you what one model
            // says; seeing them together tells you how much the answer depends
            // on the model, which is the useful question. Where the two lines
            // separate is where the projection stops being solid.
            const url =
                `${A.ANALYTICS_URL}/v1/commercial/forecast/${encodeURIComponent(A.state.datasetId)}`;
            const [primary, secondary] = await Promise.all([
                window.SD_API.get(url, params),
                window.SD_API.get(url, { ...params, method: A.otherMethod(params.method) })
                    .catch(() => null)
            ]);
            A.cacheResult('forecast', { data: primary, compare: secondary, params });
            renderForecast(primary, secondary);
            note.textContent = secondary
                ? `Comparando ${A.FORECAST_METHODS[primary.method]} contra ` +
                  `${A.FORECAST_METHODS[secondary.method]} · ` +
                  `${primary.months_ahead} meses proyectados.`
                : `Método: ${A.FORECAST_METHODS[primary.method] || ''} · ` +
                  `${primary.months_ahead} meses proyectados.`;
        } catch (error) {
            note.classList.add('error');
            note.textContent = error.message || 'No se pudo calcular el pronóstico.';
            toast(error.message || 'Error en el pronóstico.', 'error');
        } finally {
            done();
        }
    }

    function renderForecast(data, compare) {
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
            const total = A.formatCurrency(serie.total_forecast);
            const other = compare && (compare.series || [])
                .find((item) => (item.name || '') === (serie.name || ''));
            // Two totals side by side answer "how much does the method change
            // the number", which is the reason for showing both at all.
            const gap = other && serie.total_forecast
                ? ` · el otro método proyecta ${A.formatCurrency(other.total_forecast)}`
                : '';
            card.innerHTML = `<h3 class="chart-title">${A.escapeHtml(serie.name || 'Total')} ` +
                `<span class="chart-sub">· proyección ${A.escapeHtml(total)}` +
                `${A.escapeHtml(gap)}</span></h3>` +
                `<canvas id="forecast_${index}"></canvas>`;
            container.appendChild(card);

            const hist = serie.history || [];
            const fore = serie.forecast || [];
            // The same series computed with the other method, matched by name so
            // a grouped forecast lines each group up with its own counterpart.
            const twin = compare && (compare.series || [])
                .find((other) => (other.name || '') === (serie.name || ''));
            // Continuous x-axis: historical months then projected months. The
            // forecast line starts from the last historical point for continuity.
            const labels = hist.map((p) => p.month).concat(fore.map((p) => p.month));
            // Each point is {bob, usd, usdt}: the chart draws the currency
            // its selector names, never the object itself.
            const histData = hist.map((p) => A.chartAmount(p.amount)).concat(fore.map(() => null));
            const foreData = hist.map((p, i) => (i === hist.length - 1 ? A.chartAmount(p.amount) : null))
                .concat(fore.map((p) => A.chartAmount(p.amount)));
            const twinData = twin
                ? hist.map((p, i) => (i === hist.length - 1 ? A.chartAmount(p.amount) : null))
                    .concat((twin.forecast || []).map((p) => A.chartAmount(p.amount)))
                : null;
            A.makeChart(`forecast_${index}`, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        { label: 'Histórico', data: histData, borderColor: A.BRAND[0],
                          backgroundColor: 'rgba(13,30,76,0.08)', fill: true, tension: 0.3 },
                        { label: A.FORECAST_METHODS[data.method] || 'Pronóstico',
                          data: foreData, borderColor: A.BRAND[1],
                          borderDash: [6, 4], tension: 0.3 },
                        ...(twinData ? [{
                            label: A.FORECAST_METHODS[compare.method] || 'Alternativa',
                            data: twinData, borderColor: '#12796f',
                            borderDash: [2, 3], tension: 0.3, pointRadius: 2
                        }] : [])
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: true, position: 'bottom' },
                        tooltip: { callbacks: { label: (ctx) => ctx.parsed.y == null ? ''
                            : `${ctx.dataset.label}: ${A.chartSymbol()} ` +
                              `${A.formatDecimal(ctx.parsed.y, 0)}` } }
                    }
                }
            });
        });
    }

    Object.assign(A, {
        loadForecast, openForecast, renderForecast, restoreForecastControls
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
