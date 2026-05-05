/**
 * ConfigService
 *
 * Loads and caches the parametric configuration for the event from
 * data/config.json. Centralising the load lets every page rely on the same
 * shape without duplicating fetch logic.
 */
export class ConfigService {
    static async load() {
        if (ConfigService._cache) return ConfigService._cache;
        const response = await fetch('data/config.json', { cache: 'no-cache' });
        if (!response.ok) {
            throw new Error(`No se pudo cargar data/config.json (HTTP ${response.status}).`);
        }
        ConfigService._cache = await response.json();
        return ConfigService._cache;
    }
}
