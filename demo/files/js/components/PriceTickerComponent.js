import { BaseComponent } from './BaseComponent.js';

/**
 * PriceTickerComponent — Ticker animado de cotizaciones de minerales.
 * Fuente configurable: 'api' (con fallback JSON) o 'json' (solo archivo local).
 */
export class PriceTickerComponent extends BaseComponent {
  /** @type {object[]} */
  #minerals = [];

  async _loadData() {
    const source      = this._attr('source', 'json');
    const endpoint    = this._attr('endpoint', '/prices');
    const jsonFallback = this._attr('jsonFallback', 'config/minerals.json');

    let rawData;

    if (source === 'api') {
      rawData = await this._dataService.fetchWithFallback(endpoint, jsonFallback);
    } else {
      rawData = await this._dataService.loadJson(jsonFallback);
    }

    this.#minerals = this.#normalizeData(rawData);
  }

  _render() {
    if (!this.#minerals.length) return;

    const items = [...this.#minerals, ...this.#minerals]; // duplicar para loop infinito
    const itemsHtml = items.map(m => this.#renderItem(m)).join('');

    this._el.innerHTML = `
      <div class="ticker-wrap" role="marquee" aria-label="Cotizaciones minerales">
        <div class="ticker" id="mineral-ticker" aria-live="off">
          ${itemsHtml}
        </div>
        <a href="mercados.html" class="mercados-btn" aria-label="Ver Bolsa de Londres">
          <i class="fa-solid fa-chart-line" aria-hidden="true"></i>
          Bolsa de Londres (LME)
        </a>
      </div>
    `;
  }

  // ─── Private ──────────────────────────────────────────────────────────────

  #renderItem({ name, price, unit, trend, up }) {
    const dirClass = up ? 'up' : 'down';
    const arrow    = up ? '▲' : '▼';
    return `
      <div class="ticker-item" role="text" aria-label="${name}: ${price} ${unit}, ${trend}">
        <span class="ticker-name">${name}</span>
        <span class="ticker-price">$${price}</span>
        <span class="ticker-unit">${unit}</span>
        <span class="${dirClass}" aria-hidden="true">${trend} ${arrow}</span>
      </div>
    `;
  }

  /**
   * Normaliza la respuesta del API o del JSON local a un formato único.
   * @param {object} raw
   * @returns {object[]}
   */
  #normalizeData(raw) {
    // Formato JSON local: { minerals: [...] }
    if (Array.isArray(raw?.minerals)) {
      return raw.minerals;
    }

    // Formato API: [ { name, price_low, price_high, mineral: { name } } ]
    if (Array.isArray(raw)) {
      return raw.map(item => ({
        name:  item.mineral?.name ?? item.name ?? 'MINERAL',
        price: this.#formatPrice(item.price_low ?? item.price ?? 0),
        unit:  item.mineral?.unit ?? item.unit ?? 'USD/TM',
        trend: '+0.0%',
        up:    true,
      }));
    }

    return [];
  }

  #formatPrice(value) {
    return Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
}
