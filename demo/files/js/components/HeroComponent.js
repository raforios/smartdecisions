import { BaseComponent } from './BaseComponent.js';

/**
 * HeroComponent — Sección hero con animación de canvas de partículas
 * y contenido cargado dinámicamente desde JSON.
 */
export class HeroComponent extends BaseComponent {
  /** @type {object} */
  #heroData = null;

  /** @type {HTMLCanvasElement} */
  #canvas = null;

  /** @type {CanvasRenderingContext2D} */
  #ctx = null;

  /** @type {object[]} Puntos animados */
  #dots = [];

  /** @type {number} requestAnimationFrame ID */
  #rafId = null;

  async _loadData() {
    const configPath = this._attr('config', 'config/home-content.json');
    const data = await this._dataService.loadJson(configPath);
    this.#heroData = data.hero;
  }

  _render() {
    const { title, subtitle, cta } = this.#heroData ?? {
      title:    'Ministerio de Minería y Metalurgia',
      subtitle: '',
      cta:      null,
    };

    const heightStyle = this._attr('height', '75vh');
    this._el.style.cssText += `height:${heightStyle}; min-height:350px;`;
    this._el.setAttribute('role', 'banner');

    this._el.innerHTML = `
      <canvas id="hero-canvas" aria-hidden="true"></canvas>
      <div class="hero-content">
        <h1 class="hero-title">${title}</h1>
        <p>${subtitle}</p>
        <div class="hero-divider" aria-hidden="true"></div>
        ${cta ? `<a href="${cta.href}" class="hero-cta">${cta.label}</a>` : ''}
      </div>
    `;
  }

  _bindEvents() {
    this.#canvas = this._el.querySelector('#hero-canvas');
    if (!this.#canvas) return;

    this.#ctx = this.#canvas.getContext('2d');
    this.#resize();
    this.#animate();

    this._listen(window, 'resize', () => this.#resize());
  }

  destroy() {
    if (this.#rafId) {
      cancelAnimationFrame(this.#rafId);
      this.#rafId = null;
    }
    super.destroy();
  }

  // ─── Canvas animation ────────────────────────────────────────────────────

  #resize() {
    const parent = this._el;
    this.#canvas.width  = parent.clientWidth;
    this.#canvas.height = parent.clientHeight;
    this.#initDots();
  }

  #initDots() {
    const COUNT = 70;
    this.#dots = Array.from({ length: COUNT }, () => ({
      x:  Math.random() * this.#canvas.width,
      y:  Math.random() * this.#canvas.height,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
    }));
  }

  #animate() {
    const { width, height } = this.#canvas;
    this.#ctx.clearRect(0, 0, width, height);

    const dotColor  = 'rgba(201, 167, 81, 0.7)';
    const lineColor = 'rgba(201, 167, 81, 0.15)';
    const CONNECT_DIST = 120;

    this.#ctx.fillStyle  = dotColor;
    this.#ctx.strokeStyle = lineColor;

    this.#dots.forEach((p, i) => {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0 || p.x > width)  p.vx *= -1;
      if (p.y < 0 || p.y > height) p.vy *= -1;

      this.#ctx.beginPath();
      this.#ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
      this.#ctx.fill();

      for (let j = i + 1; j < this.#dots.length; j++) {
        const q    = this.#dots[j];
        const dist = Math.hypot(p.x - q.x, p.y - q.y);
        if (dist < CONNECT_DIST) {
          this.#ctx.beginPath();
          this.#ctx.moveTo(p.x, p.y);
          this.#ctx.lineTo(q.x, q.y);
          this.#ctx.stroke();
        }
      }
    });

    this.#rafId = requestAnimationFrame(() => this.#animate());
  }
}
