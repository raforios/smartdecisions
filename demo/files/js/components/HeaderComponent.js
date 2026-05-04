import { BaseComponent } from './BaseComponent.js';

/**
 * HeaderComponent — Navbar dinámico cargado desde navigation.json.
 * Incluye: logo, menú con submenús, botón BI destacado, toggle de tema.
 */
export class HeaderComponent extends BaseComponent {
  /** @type {object} */
  #navData = null;

  async _loadData() {
    const configPath = this._attr('config', 'config/navigation.json');
    this.#navData = await this._dataService.loadJson(configPath);
  }

  _render() {
    const { brand, items = [], actions = [] } = this.#navData;

    this._el.innerHTML = `
      <nav class="navbar" role="navigation" aria-label="Navegación principal">
        <div class="nav-container">
          ${this.#renderBrand(brand)}
          <button class="nav-burger" aria-label="Abrir menú" aria-expanded="false" data-burger>
            <span></span><span></span><span></span>
          </button>
          <ul class="nav-links" role="list" data-nav-menu>
            ${items.map(item => this.#renderNavItem(item)).join('')}
            ${actions.map(action => this.#renderAction(action)).join('')}
          </ul>
        </div>
      </nav>
    `;

    this.#markActiveLink();
  }

  _bindEvents() {
    // ── Burger menú (mobile) ──────────────────────────────────────────────
    const burger = this._el.querySelector('[data-burger]');
    const menu   = this._el.querySelector('[data-nav-menu]');

    if (burger && menu) {
      this._listen(burger, 'click', () => {
        const isOpen = menu.classList.toggle('nav-links--open');
        burger.setAttribute('aria-expanded', String(isOpen));
      });
    }

    // ── Submenús hover / focus ────────────────────────────────────────────
    this._el.querySelectorAll('.has-submenu').forEach(item => {
      const toggle = item.querySelector('.nav-submenu-toggle');
      const sub    = item.querySelector('.nav-submenu');
      if (!toggle || !sub) return;

      this._listen(toggle, 'click', (e) => {
        e.preventDefault();
        const isOpen = item.classList.toggle('submenu-open');
        toggle.setAttribute('aria-expanded', String(isOpen));
      });
    });

    // ── Cerrar submenús al hacer click fuera ─────────────────────────────
    this._listen(document, 'click', (e) => {
      if (!this._el.contains(e.target)) {
        this._el.querySelectorAll('.submenu-open').forEach(el => {
          el.classList.remove('submenu-open');
        });
      }
    });

    // ── Theme toggle ──────────────────────────────────────────────────────
    const themeBtn = this._el.querySelector('[data-theme-toggle]');
    if (themeBtn) {
      this._listen(themeBtn, 'click', () => {
        this._eventBus.emit('theme:toggle');
      });

      this._subscribe('theme:changed', ({ isDark }) => {
        themeBtn.textContent = isDark ? '☀️' : '🌙';
        themeBtn.setAttribute('aria-label', isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
      });
    }
  }

  // ─── Private render helpers ───────────────────────────────────────────────

  #renderBrand(brand) {
    return `
      <a class="brand" href="index.html" aria-label="${brand.line2}">
        <img src="${brand.logo}" alt="${brand.logoAlt}" class="escudo-img" loading="eager">
        <div class="logo-text">
          <span class="logo-min">${brand.line1}</span>
          <span class="logo-main">${brand.line2}</span>
        </div>
      </a>
    `;
  }

  #renderNavItem(item) {
    const hasChildren = item.children?.length > 0;
    const activeClass = this.#isActive(item.href) ? ' aria-current="page"' : '';

    if (hasChildren) {
      return `
        <li class="has-submenu" role="none">
          <button class="nav-submenu-toggle" aria-haspopup="true" aria-expanded="false">
            ${item.label} <span class="submenu-arrow" aria-hidden="true">▾</span>
          </button>
          <ul class="nav-submenu" role="menu">
            ${item.children.map(child => `
              <li role="none">
                <a href="${child.href}" role="menuitem">${child.label}</a>
              </li>
            `).join('')}
          </ul>
        </li>
      `;
    }

    return `
      <li role="none">
        <a href="${item.href}"
           ${item.highlight ? 'class="btn-bi"' : ''}
           ${activeClass}
           role="menuitem">
          ${item.label}
        </a>
      </li>
    `;
  }

  #renderAction(action) {
    if (action.type === 'theme') {
      return `
        <li role="none">
          <button class="theme-btn"
                  data-theme-toggle
                  aria-label="Cambiar tema"
                  type="button">
            ${action.icon}
          </button>
        </li>
      `;
    }
    return '';
  }

  #isActive(href) {
    return window.location.pathname.endsWith(href) ||
           window.location.href.includes(href);
  }

  #markActiveLink() {
    this._el.querySelectorAll('a[href]').forEach(link => {
      if (this.#isActive(link.getAttribute('href'))) {
        link.setAttribute('aria-current', 'page');
        link.classList.add('nav-link--active');
      }
    });
  }
}
