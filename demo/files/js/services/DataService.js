/**
 * DataService — Fuente única de datos (JSON local + API remota).
 * Principio: SRP (solo obtiene datos), DIP (los componentes dependen de esta abstracción).
 */
export class DataService {
  /** @type {string} */
  #apiBaseUrl;

  /** @type {number} */
  #timeout;

  /** @type {number} */
  #retries;

  /** @type {boolean} */
  #fallbackToJson;

  /** @type {Map<string, {data: *, timestamp: number}>} */
  #cache = new Map();

  #CACHE_TTL_MS = 60_000; // 1 minuto

  /**
   * @param {object} config
   * @param {string} config.apiBaseUrl
   * @param {number} config.timeout
   * @param {number} config.retries
   * @param {boolean} config.fallbackToJson
   */
  constructor({ apiBaseUrl = '', timeout = 8000, retries = 2, fallbackToJson = true } = {}) {
    this.#apiBaseUrl = apiBaseUrl;
    this.#timeout = timeout;
    this.#retries = retries;
    this.#fallbackToJson = fallbackToJson;
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  /**
   * Carga un archivo JSON local.
   * @param {string} path  Ruta relativa, ej. 'config/navigation.json'
   * @returns {Promise<*>}
   */
  async loadJson(path) {
    return this.#fetchWithCache(path, () => this.#fetchJson(path));
  }

  /**
   * Llama a un endpoint del API remoto.
   * @param {string} endpoint  Ruta relativa al baseUrl, ej. '/prices'
   * @param {object} [options] Opciones fetch adicionales
   * @returns {Promise<*>}
   */
  async fetchApi(endpoint, options = {}) {
    const url = `${this.#apiBaseUrl}${endpoint}`;
    return this.#fetchWithCache(url, () => this.#fetchWithRetry(url, options));
  }

  /**
   * Carga datos con fallback: intenta API → si falla, carga JSON local.
   * @param {string} endpoint
   * @param {string} jsonFallback  Ruta al JSON de respaldo
   * @returns {Promise<*>}
   */
  async fetchWithFallback(endpoint, jsonFallback) {
    try {
      return await this.fetchApi(endpoint);
    } catch (error) {
      console.warn(`[DataService] API no disponible (${endpoint}). Usando fallback: ${jsonFallback}`);
      return this.loadJson(jsonFallback);
    }
  }

  /** Limpia la caché completa. */
  clearCache() {
    this.#cache.clear();
  }

  // ─── Private helpers ───────────────────────────────────────────────────────

  async #fetchWithCache(key, fetcher) {
    const cached = this.#cache.get(key);
    const now = Date.now();

    if (cached && now - cached.timestamp < this.#CACHE_TTL_MS) {
      return cached.data;
    }

    const data = await fetcher();
    this.#cache.set(key, { data, timestamp: now });
    return data;
  }

  async #fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
      throw new Error(`[DataService] No se pudo cargar '${path}': HTTP ${response.status}`);
    }
    return response.json();
  }

  async #fetchWithRetry(url, options, attempt = 0) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.#timeout);

    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (attempt < this.#retries) {
        const delay = 500 * (attempt + 1);
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.#fetchWithRetry(url, options, attempt + 1);
      }

      throw error;
    }
  }
}
