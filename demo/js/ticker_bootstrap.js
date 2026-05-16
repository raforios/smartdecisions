/**
 * Bootstrap del Ticker para páginas legacy que cargan js/script.js (no-module).
 *
 * Se importa como `<script type="module" src="js/ticker_bootstrap.js"></script>`
 * en cada HTML donde script.js renderiza el navbar. Espera a que script.js
 * monte `#mineral-ticker` (vía MutationObserver) y entonces arranca el módulo
 * compartido contra el endpoint público.
 */
import { MiningApiService } from './services/MiningApiService.js';
import { Ticker } from './components/Ticker.js';

const CONFIG_URL = 'data/config.json';

async function loadConfig() {
    try {
        const res = await fetch(CONFIG_URL, { cache: 'no-cache' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (err) {
        console.error('ticker_bootstrap: no se pudo leer config.json', err);
        return null;
    }
}

function waitForTickerElement() {
    return new Promise(resolve => {
        if (document.getElementById('mineral-ticker')) return resolve();
        const observer = new MutationObserver(() => {
            if (document.getElementById('mineral-ticker')) {
                observer.disconnect();
                resolve();
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    const config = await loadConfig();
    if (!config?.api) return;
    await waitForTickerElement();
    const miningApi = new MiningApiService(config.api);
    const ticker = new Ticker(miningApi, {
        refreshMs: config.api.tickerRefreshMs ?? 600_000,
        fallback: config.tickerPrecios || [],
    });
    ticker.start();
});
