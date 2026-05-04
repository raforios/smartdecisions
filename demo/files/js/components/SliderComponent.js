import { BaseComponent } from './BaseComponent.js';

/**
 * SliderComponent — Carrusel de imágenes con autoplay y controles manuales.
 * Las diapositivas se cargan desde home-content.json.
 */
export class SliderComponent extends BaseComponent {
  /** @type {object[]} */
  #slides = [];

  /** @type {number} */
  #current = 0;

  /** @type {HTMLElement[]} */
  #slideEls = [];

  async _loadData() {
    const configPath = this._attr('config', 'config/home-content.json');
    const data = await this._dataService.loadJson(configPath);
    this.#slides = data.slider ?? [];
  }

  _render() {
    if (!this.#slides.length) return;

    this._el.innerHTML = `
      <div class="slider-container" role="region" aria-label="Galería de minerales" aria-roledescription="carrusel">
        ${this.#slides.map((slide, i) => this.#renderSlide(slide, i)).join('')}
        <button id="prevSlide" class="slide-nav slide-nav--prev"
                aria-label="Diapositiva anterior" type="button">❮</button>
        <button id="nextSlide" class="slide-nav slide-nav--next"
                aria-label="Siguiente diapositiva" type="button">❯</button>
        <div class="slide-dots" role="tablist" aria-label="Indicadores de diapositiva">
          ${this.#slides.map((_, i) => `
            <button role="tab"
                    aria-selected="${i === 0}"
                    aria-label="Ir a diapositiva ${i + 1}"
                    data-dot="${i}"
                    class="slide-dot ${i === 0 ? 'slide-dot--active' : ''}"
                    type="button">
            </button>
          `).join('')}
        </div>
      </div>
    `;

    this.#slideEls = Array.from(this._el.querySelectorAll('.slide'));
  }

  _bindEvents() {
    const prev = this._el.querySelector('#prevSlide');
    const next = this._el.querySelector('#nextSlide');

    if (prev) this._listen(prev, 'click', () => this.#goTo(this.#current - 1));
    if (next) this._listen(next, 'click', () => this.#goTo(this.#current + 1));

    // Dots navigation
    this._el.querySelectorAll('[data-dot]').forEach(dot => {
      this._listen(dot, 'click', () => this.#goTo(Number(dot.dataset.dot)));
    });

    // Keyboard accessibility
    this._listen(this._el, 'keydown', (e) => {
      if (e.key === 'ArrowLeft')  this.#goTo(this.#current - 1);
      if (e.key === 'ArrowRight') this.#goTo(this.#current + 1);
    });

    // Autoplay
    const interval = Number(this._attr('interval', '5000'));
    if (interval > 0) {
      this._interval(() => this.#goTo(this.#current + 1), interval);
    }
  }

  // ─── Private ──────────────────────────────────────────────────────────────

  #renderSlide(slide, index) {
    return `
      <div class="slide ${index === 0 ? 'active' : ''}"
           role="tabpanel"
           aria-label="Diapositiva ${index + 1} de ${this.#slides.length}"
           aria-hidden="${index !== 0}">
        <img src="${slide.image}" alt="${slide.alt}" loading="${index === 0 ? 'eager' : 'lazy'}">
        <div class="slide-caption">${slide.caption}</div>
      </div>
    `;
  }

  #goTo(index) {
    const total = this.#slideEls.length;
    const next  = ((index % total) + total) % total;

    this.#slideEls[this.#current].classList.remove('active');
    this.#slideEls[this.#current].setAttribute('aria-hidden', 'true');

    this.#slideEls[next].classList.add('active');
    this.#slideEls[next].setAttribute('aria-hidden', 'false');

    // Update dots
    this._el.querySelectorAll('[data-dot]').forEach((dot, i) => {
      const active = i === next;
      dot.classList.toggle('slide-dot--active', active);
      dot.setAttribute('aria-selected', String(active));
    });

    this.#current = next;
  }
}
