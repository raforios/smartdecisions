import { BaseComponent } from './BaseComponent.js';

const X_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">
  <path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z"/>
</svg>`;

/**
 * FooterComponent — Pie de página dinámico cargado desde social.json.
 */
export class FooterComponent extends BaseComponent {
  /** @type {object} */
  #footerData = null;

  async _loadData() {
    const configPath = this._attr('config', 'config/social.json');
    this.#footerData = await this._dataService.loadJson(configPath);
  }

  _render() {
    const { copyright, social = [], links = [] } = this.#footerData;
    const year = new Date().getFullYear();

    this._el.innerHTML = `
      <div class="tricolor-line" aria-hidden="true"></div>
      <footer class="footer" role="contentinfo">
        <div class="social-footer">
          <span>Encuéntranos en nuestras redes:</span>
          <nav class="social-icons" aria-label="Redes sociales">
            ${social.map(item => this.#renderSocialLink(item)).join('')}
          </nav>
        </div>
        ${links.length > 0 ? `
          <nav class="footer-links" aria-label="Enlaces del pie de página">
            ${links.map(l => `<a href="${l.href}">${l.label}</a>`).join('<span aria-hidden="true"> · </span>')}
          </nav>
        ` : ''}
        <p id="copyright-text">© ${year} ${copyright}</p>
      </footer>
    `;
  }

  // ─── Private ──────────────────────────────────────────────────────────────

  #renderSocialLink({ id, label, href, icon, type }) {
    const iconHtml = type === 'svg'
      ? X_SVG
      : `<i class="${icon}" aria-hidden="true"></i>`;

    return `
      <a href="${href}"
         target="_blank"
         rel="noopener noreferrer"
         aria-label="${label}"
         data-social="${id}">
        ${iconHtml}
      </a>
    `;
  }
}
