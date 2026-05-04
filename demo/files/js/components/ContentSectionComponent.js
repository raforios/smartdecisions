import { BaseComponent } from './BaseComponent.js';

/**
 * ContentSectionComponent — Renderizador genérico de secciones de contenido.
 * Lee el tipo de sección (entidades, comunicacion, contacto, etc.) desde
 * el atributo data-section y renderiza el contenido correspondiente del JSON.
 */
export class ContentSectionComponent extends BaseComponent {
  /** @type {object} */
  #sectionData = null;

  /** @type {string} */
  #sectionKey = '';

  async _loadData() {
    this.#sectionKey = this._attr('section');
    if (!this.#sectionKey) {
      throw new Error('ContentSectionComponent requiere data-section="<key>"');
    }

    const configPath = this._attr('config', 'config/home-content.json');
    const allData = await this._dataService.loadJson(configPath);
    this.#sectionData = allData[this.#sectionKey];

    if (!this.#sectionData) {
      throw new Error(`Sección '${this.#sectionKey}' no encontrada en ${configPath}`);
    }
  }

  _render() {
    const renderer = this.#getRenderer();
    this._el.innerHTML = renderer(this.#sectionData);
  }

  // ─── Private: renderer dispatch ──────────────────────────────────────────

  #getRenderer() {
    const renderers = {
      entidades:    (d) => this.#renderEntidades(d),
      contacto:     (d) => this.#renderContacto(d),
      comunicacion: (d) => this.#renderComunicacion(d),
    };

    return renderers[this.#sectionKey]
      ?? ((d) => `<p>Sección '${this.#sectionKey}' sin renderer definido.</p>`);
  }

  #renderEntidades({ title, items }) {
    return `
      <section class="section" id="entidades">
        <h2 class="section-title">${title}</h2>
        <div class="grid-entidades">
          ${items.map(({ name, href, external }) => `
            <a href="${href}"
               ${external ? 'target="_blank" rel="noopener noreferrer"' : ''}
               class="entidad-card">
              ${name}
              ${external ? '<i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i>' : ''}
            </a>
          `).join('')}
        </div>
      </section>
    `;
  }

  #renderContacto({ title, addresses, mapEmbed }) {
    return `
      <section class="section contacto-section" id="contacto">
        <div class="contacto-info">
          <h2 class="section-title">${title}</h2>
          ${addresses.map(({ icon, title: t, detail }) => `
            <div class="contact-item">
              <i class="fa-solid ${icon}" aria-hidden="true"></i>
              <div>
                <strong>${t}:</strong><br>${detail}
              </div>
            </div>
          `).join('')}
        </div>
        <div class="contacto-mapa">
          <iframe
            src="${mapEmbed}"
            width="100%" height="300"
            style="border:0; border-radius:8px;"
            allowfullscreen loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"
            title="Mapa de ubicación del ministerio">
          </iframe>
          <a href="https://maps.google.com" target="_blank" rel="noopener noreferrer" class="map-link">
            Ver todas las ubicaciones en Google Maps
            <i class="fa-solid fa-arrow-right" aria-hidden="true"></i>
          </a>
        </div>
      </section>
    `;
  }

  #renderComunicacion({ title, items }) {
    return `
      <section class="section container" id="comunicacion">
        <h2 class="section-title">${title}</h2>
        <div class="comunicacion-layout">
          <div class="prensa-grid">
            ${items.map(({ title: t, icon, excerpt, href, linkLabel }) => `
              <div class="prensa-item">
                <h3 style="color:var(--oro)">
                  <i class="fa-solid ${icon}" aria-hidden="true"></i> ${t}
                </h3>
                <p style="font-size:.9rem; margin-top:10px">${excerpt}</p>
                <a href="${href}"
                   style="font-size:.8rem; font-weight:bold; color:var(--negro)">
                  ${linkLabel} ➔
                </a>
              </div>
            `).join('')}
          </div>
          <div class="social-feeds-sidebar">
            <div class="feed-card" style="min-height:200px; margin-bottom:1rem">
              <h3 style="font-size:1.1rem">
                <i class="fa-brands fa-youtube" style="color:red" aria-hidden="true"></i>
                Canal Oficial
              </h3>
            </div>
            <div class="feed-card" style="min-height:200px">
              <h3 style="font-size:1.1rem">
                <i class="fa-brands fa-facebook" style="color:#1877F2" aria-hidden="true"></i>
                Facebook
              </h3>
            </div>
          </div>
        </div>
      </section>
    `;
  }
}
