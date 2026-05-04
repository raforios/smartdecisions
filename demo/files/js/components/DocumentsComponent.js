import { BaseComponent } from './BaseComponent.js';

/**
 * DocumentsComponent — Grid de documentos/normativas con filtro por categoría.
 * Fuente configurable: JSON local o API.
 */
export class DocumentsComponent extends BaseComponent {
  /** @type {object} */
  #data = null;

  /** @type {string} */
  #activeFilter = 'Todos';

  async _loadData() {
    const source   = this._attr('source', 'json');
    const endpoint = this._attr('endpoint', '');
    const jsonPath = this._attr('json', 'config/documents.json');

    if (source === 'api' && endpoint) {
      this.#data = await this._dataService.fetchWithFallback(endpoint, jsonPath);
    } else {
      this.#data = await this._dataService.loadJson(jsonPath);
    }
  }

  _render() {
    const { categories = [], items = [] } = this.#data ?? {};

    this._el.innerHTML = `
      <div class="docs-filters" role="group" aria-label="Filtrar documentos">
        ${categories.map(cat => `
          <button type="button"
                  class="docs-filter-btn ${cat === 'Todos' ? 'docs-filter-btn--active' : ''}"
                  data-filter="${cat}">
            ${cat}
          </button>
        `).join('')}
      </div>
      <div class="grid-docs" data-docs-grid aria-live="polite" aria-relevant="additions removals">
        ${this.#renderItems(items, 'Todos')}
      </div>
    `;
  }

  _bindEvents() {
    this._el.querySelectorAll('[data-filter]').forEach(btn => {
      this._listen(btn, 'click', () => {
        this.#activeFilter = btn.dataset.filter;
        this.#applyFilter();

        // Update active state
        this._el.querySelectorAll('[data-filter]').forEach(b => {
          b.classList.toggle('docs-filter-btn--active', b.dataset.filter === this.#activeFilter);
        });
      });
    });
  }

  // ─── Private ──────────────────────────────────────────────────────────────

  #renderItems(items, filter) {
    const visible = filter === 'Todos'
      ? items
      : items.filter(item => item.type === filter);

    if (!visible.length) {
      return '<p class="docs-empty">No hay documentos en esta categoría.</p>';
    }

    return visible.map(doc => this.#renderCard(doc)).join('');
  }

  #renderCard({ id, title, type, date, href, description, featured }) {
    return `
      <article class="doc-item ${featured ? 'doc-item--featured' : ''}"
               data-doc-id="${id}">
        <div class="doc-item__header">
          <span class="tag tag--${type.toLowerCase()}">${type}</span>
          ${featured ? '<span class="tag tag--featured">Destacado</span>' : ''}
        </div>
        <h4 class="doc-item__title">${title}</h4>
        ${description ? `<p class="doc-item__desc">${description}</p>` : ''}
        <footer class="doc-item__footer">
          <time class="doc-item__date" datetime="${date}">${date}</time>
          <a href="${href}"
             class="doc-item__link"
             aria-label="Descargar ${title}"
             ${href !== '#' ? 'download' : ''}>
            <i class="fa-solid fa-download" aria-hidden="true"></i> Descargar
          </a>
        </footer>
      </article>
    `;
  }

  #applyFilter() {
    const grid = this._el.querySelector('[data-docs-grid]');
    if (!grid) return;
    grid.innerHTML = this.#renderItems(this.#data.items ?? [], this.#activeFilter);
  }
}
