'use strict';

/**
 * Comercial › Clientes — who buys and who is leaving, and the way to the card
 * of each client.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const M = window.SD_MONEY;
    const O = window.SD_OVERVIEW;
    const { number } = O;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/analytics`;
    const qs = (selector) => document.querySelector(selector);

    const TITLES = { portfolio: 'Cartera de clientes', card: 'Ficha del cliente' };
    const paint = (name, ...rest) => O.paint(name, TITLES[name], ...rest);

    async function load() {
        O.loading(TITLES);
        const datasetId = await window.SD_API.ensureDataset();
        if (!datasetId) {
            qs('#areaTiles').hidden = true;
            qs('#areaEmpty').hidden = false;
            return;
        }
        const id = encodeURIComponent(datasetId);
        window.SD_API.get(`${BASE}/dashboard/${id}`).then((data) => {
            const clients = data.clients || {};
            paint('portfolio', `${number(clients.bought_this_month)} compraron`,
                `en el último mes. ${number(clients.at_risk)} en riesgo, ` +
                `${number(clients.new_clients)} nuevos y ${number(clients.lost)} perdidos.`);
        }).catch(() => paint('portfolio', '—', 'No se pudo leer la cartera.'));
        window.SD_API.get(`${BASE}/clients/${id}`).then((list) => {
            const clients = (list && list.clients) || [];
            const top = clients[0];
            paint('card', `${number(clients.length)} clientes`,
                top ? `El que más compró: ${top.name || top.client_id}, ` +
                    `Bs ${number(M.bob(top.amount))}. Busca cualquiera para ver su ficha.`
                    : 'Busca un cliente para ver su ficha.');
        }).catch(() => paint('card', '—', 'No se pudo leer la lista de clientes.'));
    }

    load();
});
