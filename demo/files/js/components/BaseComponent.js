/**
 * BaseComponent — Clase base abstracta para todos los componentes UI.
 * Principio: Template Method Pattern — define el ciclo de vida, subclases implementan render().
 *
 * Ciclo de vida:
 *   1. constructor(el, dataService, eventBus)
 *   2. init() → carga datos → render() → bindEvents()
 *   3. destroy() → limpieza
 */
export class BaseComponent {
  /** @type {HTMLElement} */
  _el;

  /** @type {import('../services/DataService.js').DataService} */
  _dataService;

  /** @type {import('../core/EventBus.js').EventBus} */
  _eventBus;

  /** @type {Function[]} Funciones cleanup registradas */
  #cleanupFns = [];

  /** @type {boolean} */
  #initialized = false;

  /**
   * @param {HTMLElement} el  Elemento DOM donde se monta el componente
   * @param {import('../services/DataService.js').DataService} dataService
   * @param {import('../core/EventBus.js').EventBus} eventBus
   */
  constructor(el, dataService, eventBus) {
    if (new.target === BaseComponent) {
      throw new Error('BaseComponent es una clase abstracta.');
    }
    this._el = el;
    this._dataService = dataService;
    this._eventBus = eventBus;
  }

  // ─── Lifecycle ─────────────────────────────────────────────────────────────

  /**
   * Inicializa el componente: carga datos y renderiza.
   * Debe ser llamado desde app.js después de instanciar.
   */
  async init() {
    if (this.#initialized) return;

    try {
      this._el.setAttribute('data-loading', 'true');
      await this._loadData();
      this._render();
      this._bindEvents();
      this._el.removeAttribute('data-loading');
      this.#initialized = true;
    } catch (error) {
      this._el.removeAttribute('data-loading');
      this._onError(error);
    }
  }

  /**
   * Destruye el componente: limpia eventos y DOM.
   */
  destroy() {
    this.#cleanupFns.forEach(fn => fn());
    this.#cleanupFns = [];
    this._el.innerHTML = '';
    this.#initialized = false;
  }

  // ─── Template Methods (subclases DEBEN implementar) ────────────────────────

  /**
   * Carga los datos necesarios para el componente.
   * @returns {Promise<void>}
   */
  async _loadData() {}

  /**
   * Genera y escribe el HTML del componente en `this._el`.
   */
  _render() {
    throw new Error(`${this.constructor.name} debe implementar _render()`);
  }

  /**
   * Enlaza eventos DOM después del render.
   */
  _bindEvents() {}

  // ─── Helpers protegidos ────────────────────────────────────────────────────

  /**
   * Registra un event listener y lo agrega al cleanup automático.
   * @param {EventTarget} target
   * @param {string} event
   * @param {Function} handler
   * @param {object} [options]
   */
  _listen(target, event, handler, options) {
    target.addEventListener(event, handler, options);
    this.#cleanupFns.push(() => target.removeEventListener(event, handler, options));
  }

  /**
   * Suscribe al EventBus y registra cleanup automático.
   * @param {string} event
   * @param {Function} handler
   */
  _subscribe(event, handler) {
    const unsub = this._eventBus.on(event, handler);
    this.#cleanupFns.push(unsub);
  }

  /**
   * Registra un setInterval con cleanup automático.
   * @param {Function} fn
   * @param {number} ms
   */
  _interval(fn, ms) {
    const id = setInterval(fn, ms);
    this.#cleanupFns.push(() => clearInterval(id));
    return id;
  }

  /**
   * Manejo de errores por defecto.
   * @param {Error} error
   */
  _onError(error) {
    console.error(`[${this.constructor.name}] Error:`, error);
    this._el.innerHTML = `<p class="component-error">No se pudo cargar este contenido.</p>`;
  }

  /**
   * Lee el atributo data- del elemento raíz.
   * @param {string} attr  Nombre sin 'data-'
   * @param {string} [defaultValue]
   */
  _attr(attr, defaultValue = '') {
    return this._el.dataset[attr] ?? defaultValue;
  }
}
