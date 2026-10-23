'use strict';

/**
 * Principal — the application's welcome: who you are and when you last came
 * in, today's rates and, for whoever runs the account, who else uses it and
 * when they last came in. What a role may open is the menu's job (Rafael,
 * 21-oct: repeating it here only took space).
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_SHELL) return;
    const { API_URL } = window.SD_CONFIG;
    const shell = window.SD_SHELL;
    const qs = (selector) => document.querySelector(selector);

    const ROLES = { MANAGER: 'Gerente', REQUESTER: 'Consulta', ADMIN: 'Administrador', SELLER: 'Vendedor' };
    const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
        'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const number = (value, decimals = 0) => (value == null ? '—'
        : Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals }));

    /** "12 de octubre a las 18:30", in the browser's time. */
    function when(iso) {
        if (!iso) return null;
        const moment = new Date(iso);
        const time = moment.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
        return `${moment.getDate()} de ${MONTHS[moment.getMonth()]} a las ${time}`;
    }
    const isToday = (iso) => iso && new Date(iso).toDateString() === new Date().toDateString();

    function today() {
        const now = new Date();
        qs('#homeToday').textContent = `${now.getDate()} de ${MONTHS[now.getMonth()]} de ${now.getFullYear()}`;
    }

    async function me() {
        const profile = await window.SD_API.get(`${API_URL}/v1/users/me`).catch(() => null);
        if (!profile) return;
        qs('#homeHello').textContent = `Hola, ${profile.first_name}`;
        const last = when(profile.previous_login);
        qs('#homeLast').textContent = last
            ? `Tu última sesión fue el ${last}. Entras como ${ROLES[profile.role] || profile.role}.`
            : `Es tu primera sesión registrada. Entras como ${ROLES[profile.role] || profile.role}.`;
    }

    /** The last published rate of a currency and the one before it. */
    // The week the chart shows (Rafael, 21-oct: the last week of the rate).
    const WEEK_POINTS = 7;

    /** The last published rates of a currency, oldest first: enough for a week. */
    async function recentRates(currency) {
        const end = new Date();
        const start = new Date(end.getTime() - 14 * 86400000);
        const iso = (day) => day.toISOString().slice(0, 10);
        const answer = await window.SD_API.get(`${API_URL}/v1/quotes/exchange-rates`,
            { currency, start: iso(start), end: iso(end) });
        const rates = (answer && answer.rates) || [];
        return rates.slice(-WEEK_POINTS);
    }

    /** The official dollar and USDT of the week, drawn on the dark card. */
    function weekChart(canvas, usd, usdt) {
        if (!window.Chart || !usd.length) return;
        const dayLabel = (rate) => {
            const [, month, day] = String(rate.date).slice(0, 10).split('-');
            return `${Number(day)}/${Number(month)}`;
        };
        const byDate = new Map(usdt.map((rate) => [String(rate.date).slice(0, 10), rate.rate]));
        const light = 'rgba(214, 222, 236, 0.85)';
        new window.Chart(canvas, {
            type: 'line',
            data: {
                labels: usd.map(dayLabel),
                datasets: [
                    { label: 'Dólar oficial', data: usd.map((rate) => rate.rate),
                      borderColor: '#ffffff', backgroundColor: '#ffffff', tension: 0.3, pointRadius: 2 },
                    { label: 'USDT', data: usd.map((rate) => byDate.get(String(rate.date).slice(0, 10)) ?? null),
                      borderColor: '#4fd1c5', backgroundColor: '#4fd1c5', tension: 0.3, pointRadius: 2,
                      spanGaps: true }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: light, boxWidth: 10 } },
                    tooltip: { callbacks: { label: (item) => `${item.dataset.label}: Bs ${number(item.raw, 2)}` } } },
                scales: {
                    x: { ticks: { color: light }, grid: { display: false } },
                    y: { ticks: { color: light, callback: (value) => number(value, 2) },
                         grid: { color: 'rgba(255, 255, 255, 0.08)' } }
                }
            }
        });
    }

    async function rates() {
        const card = qs('#homeRates');
        // Only the ADMIN manages the rates; for the rest the card is a reading.
        if (shell.role === 'ADMIN') card.setAttribute('href', 'admin/tipo-cambio.html');
        else card.removeAttribute('href');
        try {
            const [usd, usdt] = await Promise.all([recentRates('USD'), recentRates('USDT')]);
            const line = (rates) => {
                const pair = rates.slice(-2);
                const [before, now] = pair.length > 1 ? pair : [null, pair[0]];
                if (!now) return '—';
                const change = before ? now.rate - before.rate : null;
                return `Bs ${number(now.rate, 2)}` + (change ? ` (${change > 0 ? '+' : ''}${number(change, 2)})` : '');
            };
            const official = usd[usd.length - 1];
            const parallel = usdt[usdt.length - 1];
            const gap = official && parallel ? 100 * (parallel.rate / official.rate - 1) : null;
            card.innerHTML = '<p class="sd-hero-label">Cotizaciones del día</p>' +
                `<p class="sd-hero-value">Bs ${number(official && official.rate, 2)}</p>` +
                `<div class="sd-hero-other"><span>Dólar oficial<b>${line(usd)}</b></span>` +
                `<span>USDT<b>${line(usdt)}</b></span>` +
                `<span>Brecha<b>${number(gap, 2)} %</b></span></div>` +
                '<div class="sd-hero-chart"><canvas id="homeRatesChart"></canvas></div>';
            weekChart(qs('#homeRatesChart'), usd, usdt);
        } catch (error) {
            card.innerHTML = '<p class="sd-hero-label">Cotizaciones del día</p>' +
                '<p class="sd-hero-other">No se pudieron leer las cotizaciones.</p>';
        }
    }

    /**
     * The manager, the users of their company; the ADMIN, every registered
     * user, latest sign-in first, with the way into the users screen.
     */
    async function users() {
        if (!shell.isEditor) return;
        const admin = shell.role === 'ADMIN';
        const url = admin ? `${API_URL}/v1/users/` : `${API_URL}/v1/users/company`;
        const list = await window.SD_API.get(url).catch(() => null);
        if (!list) return;
        if (admin) {
            qs('#homeUsersTitle').textContent = 'Usuarios registrados';
            qs('#homeUsersManage').hidden = false;
            qs('#homeUsersCompany').hidden = false;
            list.sort((left, right) => String(right.last_login || '').localeCompare(String(left.last_login || '')));
        }
        qs('#homeUsers').hidden = false;
        const inToday = list.filter((user) => isToday(user.last_login)).length;
        const companies = new Set(list.map((user) => user.client).filter(Boolean)).size;
        qs('#homeUsersNote').textContent = admin
            ? `${number(list.length)} usuarios de ${number(companies)} empresas; ${number(inToday)} entraron hoy.`
            : `${number(list.length)} usuarios; ${number(inToday)} entraron hoy.`;
        qs('#homeUsersTable tbody').innerHTML = list.map((user) =>
            (admin ? `<tr><td>${escape(user.client || 'Sin empresa')}</td>` : '<tr>') +
            `<td>${escape(`${user.first_name} ${user.last_name}`)}</td><td>${escape(user.email)}</td>` +
            `<td>${ROLES[user.role] || escape(user.role)}</td>` +
            `<td>${when(user.last_login) || 'Sin registro aún'}</td>` +
            `<td class="numeric">${number(user.login_count)}</td>` +
            `<td><span class="sd-status ${user.status ? 'is-on' : 'is-off'}">` +
            `${user.status ? 'Activo' : 'Inactivo'}</span></td></tr>`).join('');
    }

    /**
     * The ADMIN's card: every service by name with its light and how long it
     * took, base services first, so a glance says which one is down.
     */
    async function health() {
        if (shell.role !== 'ADMIN' || !window.SD_HEALTH) return;
        qs('#homeTop').classList.add('sd-grid-half');
        qs('#homeHealth').hidden = false;
        const results = await window.SD_HEALTH.check();
        const totals = window.SD_HEALTH.summarize(results);
        const tableTrouble = (item) => Boolean(item.tables && !item.tables.healthy);
        qs('#homeHealthValue').textContent = `${totals.up} de ${totals.services} responden`;
        qs('#homeHealthGrid').innerHTML = results.map((item) => {
            const state = !item.up ? 'is-down' : (tableTrouble(item) ? 'is-warn' : 'is-up');
            const title = !item.up ? 'No responde'
                : (tableTrouble(item) ? 'Una tabla no está activa' : 'Responde');
            return `<span class="sd-health-chip ${state}" title="${title}">` +
                `<i aria-hidden="true"></i><b>${escape(item.label)}</b>` +
                `<small>${item.ms == null ? '—' : `${number(item.ms)} ms`}</small></span>`;
        }).join('');
        qs('#homeHealthTables').textContent = window.SD_HEALTH.tablesLine(totals);
        const down = results.filter((item) => !item.up || tableTrouble(item)).length;
        const note = qs('#homeHealthNote');
        note.className = `sd-stat-note ${down ? 'is-bad' : 'is-good'}`;
        note.textContent = down ? `${down} con problemas: abre Salud para el detalle.` : 'Todo responde.';
    }

    /** The ADMIN's last hours: the chart and the newest failures. */
    async function events() {
        if (shell.role !== 'ADMIN' || !window.SD_EVENTS || !window.Chart) return;
        qs('#homeEvents').hidden = false;
        try {
            const activity = await window.SD_EVENTS.load(12);
            const totals = window.SD_EVENTS.totals(activity);
            const errors = totals.clientErrors + totals.serverErrors;
            qs('#homeEventsNote').textContent = `${number(totals.calls)} llamadas; ` +
                `${number(errors)} con error`;
            window.SD_EVENTS.chart(qs('#homeEventsChart'), activity);
            const latest = activity.latest_errors.slice(0, 5);
            qs('#homeEventsErrors').innerHTML = latest.length
                ? latest.map((call) => `<div class="sd-list-row"><span>${window.SD_EVENTS.when(call.timestamp)} · ` +
                    `${escape(call.microservice)} <code>${escape(call.endpoint || '')}</code></span>` +
                    `<b class="is-bad">${call.status_code}</b></div>`).join('')
                : '<p class="sd-stat-note is-good">Sin errores en las últimas 12 horas.</p>';
        } catch (error) {
            qs('#homeEventsNote').textContent = 'No se pudieron leer los eventos.';
        }
    }

    today();
    me();
    rates();
    users();
    health();
    events();
});
