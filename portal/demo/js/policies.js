'use strict';

/**
 * Parámetros — the two policies the analyses are judged with: the commercial
 * one (objectives and the exchange-rate effect) and the credit one
 * (receivables). Each is shown as it is in force —ANALYTICS fills what the
 * account did not set with its defaults— and can be edited here. Saving
 * answers with the resolved policy, so what shows is always what the numbers
 * are computed with.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const BASE = `${window.SD_CONFIG.API_URL}/v1/analytics`;

    const SOURCE_LABELS = {
        CLIENT: 'Configurada por tu empresa',
        DEFAULT: 'Valores por defecto: todavía no la configuraste'
    };

    // Fractions travel as 0..1; people write percentages.
    const toPercent = (value) => (value == null ? '' : String(+(Number(value) * 100).toFixed(4)));
    const fromPercent = (text) => (text.trim() === '' ? null : Number(text) / 100);
    const toNumber = (text) => (text.trim() === '' ? null : Number(text));
    const toList = (values, format) => (values || []).map(format).join('; ');
    const fromList = (text, parse) => (text.trim() === ''
        ? null : text.split(';').map((part) => parse(part.trim())));
    // "PLATINIUM: 20; ORO: 15" <-> {PLATINIUM: 20, ORO: 15}
    const toPairs = (map, format) => Object.entries(map || {})
        .map(([key, value]) => `${key}: ${format(value)}`).join('; ');
    function fromPairs(text, parse) {
        if (text.trim() === '') return null;
        const result = {};
        text.split(';').forEach((part) => {
            const [key, value] = part.split(':').map((piece) => (piece || '').trim());
            if (key && value) result[key] = parse(value);
        });
        return result;
    }

    // One row per field: label, how to show it, how to read it back, a hint.
    const COMMERCIAL = [
        ['yellow_from', 'Amarillo desde (% de cumplimiento)', toPercent, fromPercent, 'Ej.: 70'],
        ['green_from', 'Verde desde (% de cumplimiento)', toPercent, fromPercent, 'Ej.: 90'],
        ['bs_per_point', 'Bs por punto', (v) => (v == null ? '' : String(v)), toNumber, ''],
        ['points_per_cluster', 'Bs por punto, por cluster',
         (v) => toPairs(v, String), (t) => fromPairs(t, Number), 'PLATINIUM: 20; ORO: 15'],
        ['usd_cost_share', 'Parte del costo comprada en dólares (%)', toPercent, fromPercent,
         '100 si importas todo'],
        ['usd_cost_share_by_category', 'Parte en dólares por categoría (%)',
         (v) => toPairs(v, toPercent), (t) => fromPairs(t, (x) => Number(x) / 100),
         'FILM STRETCH: 100; POTE: 40']
    ];
    const CREDIT = [
        ['aging_buckets', 'Tramos de antigüedad (días)', (v) => toList(v, String),
         (t) => fromList(t, Number), '0; 30; 60; 90'],
        ['loss_rates', 'Pérdida esperada por tramo (%)', (v) => toList(v, toPercent),
         (t) => fromList(t, (x) => Number(x) / 100), 'Uno por tramo: 1; 5; 20; 50'],
        ['financial_rate_daily', 'Tasa financiera diaria (%)', toPercent, fromPercent, ''],
        ['delinquent_days', 'Moroso desde (días)', (v) => (v == null ? '' : String(v)),
         toNumber, ''],
        ['default_term_days', 'Plazo por defecto (días)', (v) => (v == null ? '' : String(v)),
         toNumber, '']
    ];

    function paint(tableId, fields, policy) {
        qs(`#${tableId} tbody`).innerHTML = fields.map(([key, label, show, , hint]) =>
            `<tr><td>${label}</td><td><input type="text" data-field="${key}" ` +
            `value="${show(policy[key]).replaceAll('"', '&quot;')}" placeholder="${hint}"></td></tr>`
        ).join('');
    }

    function read(tableId, fields) {
        const body = {};
        fields.forEach(([key, , , parse]) => {
            const value = parse(qs(`#${tableId} [data-field="${key}"]`).value);
            if (value !== null) body[key] = value;
        });
        return body;
    }

    const POLICIES = {
        commercial: { path: 'commercial-policy', table: 'commercialPolicyTable',
                      source: 'commercialPolicySource', fields: COMMERCIAL },
        credit: { path: 'credit-policy', table: 'creditPolicyTable',
                  source: 'creditPolicySource', fields: CREDIT }
    };

    function show(kind, policy) {
        const { table, source, fields } = POLICIES[kind];
        paint(table, fields, policy);
        const badge = qs(`#${source}`);
        badge.textContent = SOURCE_LABELS[policy.source_code] || '';
        badge.className = `policy-source ${policy.source_code === 'CLIENT' ? 'is-set' : 'is-default'}`;
    }

    async function load() {
        const note = qs('#policiesNote');
        try {
            const [commercial, credit] = await Promise.all(Object.values(POLICIES).map(
                ({ path }) => window.SD_API.get(`${BASE}/${path}`)));
            show('commercial', commercial);
            show('credit', credit);
            note.textContent = '';
        } catch (error) {
            note.className = 'form-note error';
            note.textContent = (error && error.message) || 'No se pudieron leer las políticas.';
        }
    }

    async function save(kind, button) {
        const { path, table, fields } = POLICIES[kind];
        const note = qs('#policiesNote');
        const done = setButtonBusy(button, 'Guardando…');
        try {
            show(kind, await window.SD_API.put(`${BASE}/${path}`, read(table, fields)));
            // The analyses cached with the old policy no longer describe it.
            sessionStorage.removeItem('sd_excel_results');
            note.className = 'form-note success';
            note.textContent = 'Política guardada. Los análisis se recalculan con ella.';
            toast('Política guardada.', 'success');
        } catch (error) {
            note.className = 'form-note error';
            note.textContent = (error && error.message) || 'No se pudo guardar la política.';
        } finally {
            done();
        }
    }

    qs('#commercialPolicySave').addEventListener('click',
        (event) => save('commercial', event.currentTarget));
    qs('#creditPolicySave').addEventListener('click',
        (event) => save('credit', event.currentTarget));
    load();
});
