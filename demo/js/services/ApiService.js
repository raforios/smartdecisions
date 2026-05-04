export class ApiService {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async get(endpoint) {
        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`);
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`Error al obtener datos de ${endpoint}:`, error);
            return null;
        }
    }

    async getConfig() {
        return await this.get('data/config.json');
    }
}
