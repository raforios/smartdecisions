/**
 * Ticker — top navbar marquee fed from the public daily mineral report.
 *
 * Mounts itself into an existing `<div id="mineral-ticker">` element rendered
 * by the Header. Falls back to the hardcoded ticker list in config when the
 * API is unreachable so the bar never disappears.
 */
export class Ticker {
    constructor(miningApi, options = {}) {
        this.api = miningApi;
        this.refreshMs = options.refreshMs ?? 600_000;
        this.fallback = options.fallback || [];
        this._timer = null;
    }

    /**
     * Renders the ticker once and schedules periodic refreshes. Safe to call
     * on pages without the ticker element — it just no-ops.
     */
    async start() {
        if (!document.getElementById('mineral-ticker')) return;
        await this.refresh();
        this._timer = setInterval(() => this.refresh().catch(() => {}),
            this.refreshMs);
    }

    stop() {
        if (this._timer) {
            clearInterval(this._timer);
            this._timer = null;
        }
    }

    async refresh() {
        const today = new Date().toISOString().slice(0, 10);
        const payload = await this.api.getDailyReport(today);
        const rows = payload?.rows?.length ? this._toTickerItems(payload.rows) : this.fallback;
        this._render(rows);
    }

    _toTickerItems(rows) {
        return rows.map(r => {
            const change = Number(r.change_pct) || 0;
            const status = change >= 0 ? 'up' : 'down';
            const trend = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
            const price = this._formatPrice(r.price_low);
            const unit = r.unit ? ` / ${r.unit}` : '';
            return {
                name: r.mineral.toUpperCase(),
                price: `${price}${unit}`,
                trend,
                status,
                fallback: !!r.is_fallback,
            };
        });
    }

    _formatPrice(value) {
        const v = Number(value);
        if (!Number.isFinite(v)) return '—';
        if (Math.abs(v - Math.round(v)) < 1e-9) {
            return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
        }
        return v.toLocaleString('en-US', {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }

    _render(items) {
        const target = document.getElementById('mineral-ticker');
        if (!target) return;
        const html = items.map(p => `
            <div class="ticker-item ${p.fallback ? 'is-fallback' : ''}">
                <span>${p.name}</span>
                <span>$${p.price}</span>
                <span class="${p.status}">${p.trend} ${p.status === 'up' ? '▲' : '▼'}</span>
            </div>
        `).join('');
        // Duplicate the strip so the CSS marquee loops seamlessly.
        target.innerHTML = html + html;
    }
}
