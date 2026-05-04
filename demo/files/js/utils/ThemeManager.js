/**
 * ThemeManager — Gestiona el tema claro/oscuro del sitio.
 * Principio: SRP — solo maneja el tema.
 */
export class ThemeManager {
  #storageKey = 'mmm-theme';
  #eventBus;

  /**
   * @param {import('../core/EventBus.js').EventBus} eventBus
   */
  constructor(eventBus) {
    this.#eventBus = eventBus;
  }

  init() {
    const saved = localStorage.getItem(this.#storageKey);
    if (saved) {
      this.#apply(saved);
    }

    this.#eventBus.on('theme:toggle', () => this.toggle());
  }

  toggle() {
    const current = document.documentElement.getAttribute('data-theme') ?? 'light';
    const next    = current === 'dark' ? 'light' : 'dark';
    this.#apply(next);
    localStorage.setItem(this.#storageKey, next);
  }

  get isDark() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
  }

  // ─── Private ──────────────────────────────────────────────────────────────

  #apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    this.#eventBus.emit('theme:changed', { isDark: theme === 'dark', theme });
  }
}
