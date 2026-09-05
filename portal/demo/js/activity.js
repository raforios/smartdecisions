'use strict';

/**
 * "Tu actividad" — what this account already has.
 *
 * The home page used to open on three empty module cards, which reads like a
 * brochure. An account that has uploaded data and run an analysis should see
 * that on entry: it is the difference between a demo and a product somebody
 * pays for every month.
 *
 * Both services answer only with the caller's own rows — the owner is part of
 * the query — so this panel cannot surface another client's history.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH || !window.SD_AUTH.getToken()) return;

    const { qs } = window.SD_UI;
    const card = qs('#activityCard');
    if (!card) return;

    const INGEST_URL = window.SD_CONFIG.INGEST_URL;
    const ANALYTICS_URL = window.SD_CONFIG.ANALYTICS_URL;
    const DATASET_KEY = 'sd_excel_dataset_id';

    const STATUS_LABELS = {
        validated: 'Validado',
        failed: 'Con errores',
        completed: 'Completado'
    };

    function number(value) {
        return Number(value || 0).toLocaleString('es-BO');
    }

    /**
     * Renders a timestamp as "hace N días" — for a history panel, how long ago
     * is the question, not the exact instant.
     */
    function elapsed(iso) {
        const then = new Date(iso);
        if (Number.isNaN(then.getTime())) return '';
        const days = Math.floor((Date.now() - then.getTime()) / 86400000);
        if (days <= 0) return 'hoy';
        if (days === 1) return 'ayer';
        if (days < 30) return `hace ${days} días`;
        const months = Math.round(days / 30);
        return months === 1 ? 'hace un mes' : `hace ${months} meses`;
    }

    function tile(title, when, rows, action) {
        const items = rows
            .map(([label, value]) => `
                <div class="tile-row">
                    <span class="tile-label">${label}</span>
                    <span class="tile-value">${value}</span>
                </div>`)
            .join('');
        return `
            <article class="activity-tile">
                <header class="tile-head">
                    <h3>${title}</h3>
                    <span class="tile-when">${when}</span>
                </header>
                ${items}
                ${action || ''}
            </article>`;
    }

    function emptyTile(title, text, action) {
        return `
            <article class="activity-tile activity-tile-empty">
                <header class="tile-head"><h3>${title}</h3></header>
                <p class="tile-empty-text">${text}</p>
                ${action || ''}
            </article>`;
    }

    async function load() {
        // Each service is asked for one row: the panel shows the latest, and
        // pulling forty to display one would be paid for on every page load.
        const [datasets, runs] = await Promise.all([
            window.SD_API.get(`${INGEST_URL}/v1/ingest/datasets`, { limit: 1 })
                .catch(() => null),
            window.SD_API.get(`${ANALYTICS_URL}/v1/analytics/runs`, { limit: 1 })
                .catch(() => null)
        ]);

        const lastDataset = datasets && datasets.datasets && datasets.datasets[0];
        const lastRun = runs && runs.runs && runs.runs[0];

        // Nothing to show and nothing to hide: a brand-new account keeps the
        // clean home it had before.
        if (!lastDataset && !lastRun) return;

        const tiles = [];

        if (lastDataset) {
            // Re-seed the dataset the modules read, so a returning user lands
            // able to work instead of being asked to upload the same file again.
            sessionStorage.setItem(DATASET_KEY, lastDataset.dataset_id);
            const period = (lastDataset.date_range_start && lastDataset.date_range_end)
                ? `${lastDataset.date_range_start} → ${lastDataset.date_range_end}`
                : '—';
            tiles.push(tile(
                'Tu última carga',
                elapsed(lastDataset.created_at),
                [
                    ['Estado', STATUS_LABELS[lastDataset.status] || lastDataset.status],
                    ['Filas válidas', number(lastDataset.valid_rows)],
                    ['Puntos de venta', number(lastDataset.unique_points_of_sale)],
                    ['Productos', number(lastDataset.unique_products)],
                    ['Período', period]
                ],
                '<a class="tile-action" href="excel/index.html">Ver el análisis →</a>'
            ));
        } else {
            tiles.push(emptyTile(
                'Tu última carga',
                'Todavía no subiste un archivo de ventas.',
                '<a class="tile-action" href="excel/index.html">Subir el primero →</a>'
            ));
        }

        if (lastRun) {
            tiles.push(tile(
                'Tu último análisis',
                elapsed(lastRun.created_at),
                [
                    ['Estado', STATUS_LABELS[lastRun.status] || lastRun.status],
                    ['Oportunidades', number(lastRun.total_opportunities)],
                    ['Puntos de venta con oportunidad',
                     number(lastRun.total_pos_with_opportunities)],
                    ['Valor esperado',
                     lastRun.total_expected_value === null
                         ? '—'
                         : `Bs ${number(Math.round(lastRun.total_expected_value))}`]
                ],
                '<a class="tile-action" href="excel/index.html">Abrir oportunidades →</a>'
            ));
        } else {
            tiles.push(emptyTile(
                'Tu último análisis',
                'Sube un archivo y el análisis comercial se corre sobre él.',
                '<a class="tile-action" href="excel/index.html">Ir al módulo →</a>'
            ));
        }

        qs('#activityGrid').innerHTML = tiles.join('');
        qs('#activityMeta').textContent = window.SD_AUTH.getEmail() || '';
        card.hidden = false;
    }

    load().catch(() => {
        // The panel is a courtesy: if a service is unreachable the modules must
        // still be usable, so it stays hidden instead of blocking the page.
    });
});
