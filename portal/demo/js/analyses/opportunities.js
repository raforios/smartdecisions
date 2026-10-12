'use strict';

/**
 * Oportunidades de venta: what to offer to each client, by product.
 */
(function (A) {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, qsAll, toast, setButtonBusy } = window.SD_UI;

    function renderOpportunities(response) {
        A.state.opportunities = response.opportunities || [];
        const insight = deriveInsight(response.summary, A.state.opportunities);
        renderOpportunityHeadline(insight);
        renderOpportunitySummary(response.summary, insight);
        renderProductOpportunities();
        A.showAnalysisView('stepOpportunities');
    }

    // Aggregates the raw opportunities into the plain-language story the manager
    // needs: how much, where, and which categories to push first.
    function deriveInsight(summary, opportunities) {
        const byCategory = new Map();
        opportunities.forEach((opp) => {
            const name = opp.recommended_product_name || opp.recommended_product_id || '—';
            const entry = byCategory.get(name) || { name, value: 0, count: 0 };
            entry.value = window.SD_MONEY.add(entry.value, opp.expected_drop_size_amount);
            entry.count += 1;
            byCategory.set(name, entry);
        });
        const ranking = [...byCategory.values()].sort((a, b) =>
            window.SD_MONEY.bob(b.value) - window.SD_MONEY.bob(a.value));
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
        const count = A.formatInt(insight.count);
        const pdvs = A.formatInt(insight.pdvs);
        const valueText = insight.totalValue == null ? null : A.formatCurrency(insight.totalValue);
        const lead = valueText
            ? `Detectamos <strong>${count} acciones de venta</strong> en <strong>${pdvs} ` +
              `puntos de venta</strong>, con una venta potencial de <strong>${valueText}</strong>.`
            : `Detectamos <strong>${count} acciones de venta</strong> en <strong>${pdvs} ` +
              'puntos de venta</strong>.';
        const top = insight.topCategory
            ? ` La mayor oportunidad está en <strong>${A.escapeHtml(insight.topCategory.name)}</strong>.`
            : '';
        const chips = insight.top3.map((cat, index) =>
            `<span class="insight-chip"><span class="chip-rank">${index + 1}</span> ` +
            `${A.escapeHtml(cat.name)} · <strong>${A.formatCurrency(cat.value)}</strong></span>`
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
                label: 'Acciones sugeridas', value: A.formatInt(summary.total_opportunities || 0),
                variant: 'accent', hint: 'Recomendaciones de venta cruzada'
            },
            {
                label: 'Puntos de venta',
                value: A.formatInt(summary.total_pos_with_opportunities || 0),
                hint: 'Con al menos una recomendación'
            },
            {
                label: 'Venta potencial',
                value: '—',
                valueHtml: totalValue == null ? '' : window.SD_MONEY.card(totalValue),
                variant: totalValue == null ? '' : 'success',
                hint: totalValue == null ? 'Faltan precios en el archivo.' : 'Impacto esperado'
            },
            {
                label: 'Categoría estrella',
                value: insight.topCategory ? insight.topCategory.name : '—',
                hint: 'Mayor venta potencial'
            }
        ];
        const container = qs('#opportunitySummary');
        container.innerHTML = '';
        cards.forEach((card) => container.appendChild(A.metricCard(card)));
        A.arrangeMetrics(container);
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
            group.total = window.SD_MONEY.add(group.total, opp.expected_drop_size_amount);
            group.stores.push(opp);
            byProduct.set(key, group);
        });
        const groups = [...byProduct.values()];
        const bob = window.SD_MONEY.bob;
        groups.forEach((g) => g.stores.sort((a, b) =>
            bob(b.expected_drop_size_amount) - bob(a.expected_drop_size_amount)));
        return groups.sort((a, b) => bob(b.total) - bob(a.total));
    }

    function renderProductOpportunities() {
        const tbody = qs('#opportunitiesTable tbody');
        tbody.innerHTML = '';
        const filterText = qs('#pdvFilter').value.trim().toLowerCase();
        let groups = groupOpportunitiesByProduct(A.state.opportunities);
        if (filterText) {
            groups = groups.filter((g) => g.product.toLowerCase().includes(filterText));
        }
        qs('#filterCount').textContent =
            `${A.formatInt(groups.length)} producto(s) · ` +
            `${A.formatInt(A.state.opportunities.length)} acciones en total`;

        if (groups.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sin oportunidades para ese filtro.</td></tr>';
            return;
        }
        groups.forEach((group, index) => {
            const row = document.createElement('tr');
            row.className = 'product-row';
            row.innerHTML =
                `<td><button type="button" class="expand-btn" data-idx="${index}">▸</button>
                    <strong>${A.escapeHtml(group.product)}</strong></td>
                 <td class="numeric">${A.formatInt(group.stores.length)}</td>
                 ${window.SD_MONEY.cells(group.total, 2, 'strong')}
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
                    <td>${A.escapeHtml(store)}</td>
                    <td class="based-on">porque compra ${A.escapeHtml(based)}</td>
                    <td class="numeric">${A.formatPercent(opp.confidence)}</td>
                    ${window.SD_MONEY.cells(opp.expected_drop_size_amount, 2, 'strong')}
                </tr>`;
            }).join('');
            detail.innerHTML = `<td colspan="6" class="detail-cell">
                <table class="data-table detail-table"><thead><tr>
                    <th>Comercio</th><th>Motivo</th>
                    <th class="numeric">Probabilidad</th>
                    <th class="numeric" data-money>Venta potencial</th>
                </tr></thead><tbody>${inner}</tbody></table>
                ${group.stores.length > 50 ? `<p class="based-on" style="margin:.5rem 0 0">` +
                    `Mostrando 50 de ${A.formatInt(group.stores.length)} comercios.</p>` : ''}
            </td>`;
            tbody.appendChild(detail);
            window.SD_MONEY.expandHeaders(detail);

            row.querySelector('.expand-btn').addEventListener('click', (ev) => {
                detail.hidden = !detail.hidden;
                ev.currentTarget.textContent = detail.hidden ? '▸' : '▾';
            });
        });
    }

    Object.assign(A, {
        renderOpportunities
    });
})(window.SD_ANALYSIS = window.SD_ANALYSIS || {});
