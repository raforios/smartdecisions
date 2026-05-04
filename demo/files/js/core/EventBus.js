/**
 * EventBus — Pub/Sub para comunicación entre componentes.
 * Principio: Open/Closed (extender sin modificar) + SRP (solo maneja eventos).
 */
export class EventBus {
  /** @type {Map<string, Set<Function>>} */
  #handlers = new Map();

  /**
   * Suscribe un callback a un evento.
   * @param {string} event
   * @param {Function} handler
   * @returns {Function} Función para cancelar la suscripción (unsubscribe)
   */
  on(event, handler) {
    if (!this.#handlers.has(event)) {
      this.#handlers.set(event, new Set());
    }
    this.#handlers.get(event).add(handler);

    return () => this.off(event, handler);
  }

  /**
   * Desuscribe un callback de un evento.
   * @param {string} event
   * @param {Function} handler
   */
  off(event, handler) {
    this.#handlers.get(event)?.delete(handler);
  }

  /**
   * Emite un evento con datos opcionales.
   * @param {string} event
   * @param {*} data
   */
  emit(event, data) {
    this.#handlers.get(event)?.forEach(handler => {
      try {
        handler(data);
      } catch (error) {
        console.error(`[EventBus] Error en handler de '${event}':`, error);
      }
    });
  }

  /**
   * Suscripción de un solo disparo (se cancela automáticamente).
   * @param {string} event
   * @param {Function} handler
   */
  once(event, handler) {
    const wrapper = (data) => {
      handler(data);
      this.off(event, wrapper);
    };
    this.on(event, wrapper);
  }
}

/** Instancia global singleton */
export const eventBus = new EventBus();
