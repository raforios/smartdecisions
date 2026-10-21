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
    async function lastTwo(currency) {
        const end = new Date();
        const start = new Date(end.getTime() - 14 * 86400000);
        const iso = (day) => day.toISOString().slice(0, 10);
        const answer = await window.SD_API.get(`${API_URL}/v1/quotes/exchange-rates`,
            { currency, start: iso(start), end: iso(end) });
        const rates = (answer && answer.rates) || [];
        return rates.slice(-2);
    }

    async function rates() {
        const card = qs('#homeRates');
        // Only the ADMIN manages the rates; for the rest the card is a reading.
        if (shell.role === 'ADMIN') card.setAttribute('href', 'admin/tipo-cambio.html');
        else card.removeAttribute('href');
        try {
            const [usd, usdt] = await Promise.all([lastTwo('USD'), lastTwo('USDT')]);
            const line = (pair) => {
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
                `<span>Brecha<b>${number(gap, 2)} %</b></span></div>`;
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

    /** The ADMIN's card: services up, tables active, and what is wrong first. */
    async function health() {
        if (shell.role !== 'ADMIN' || !window.SD_HEALTH) return;
        qs('#homeTop').classList.add('sd-grid-half');
        qs('#homeHealth').hidden = false;
        const results = await window.SD_HEALTH.check();
        const totals = window.SD_HEALTH.summarize(results);
        qs('#homeHealthValue').textContent = `${totals.up} de ${totals.services} servicios responden`;
        qs('#homeHealthTables').textContent = window.SD_HEALTH.tablesLine(totals);
        const problems = results.flatMap((item) => [
            ...(item.up ? [] : [[item.label, 'No responde']]),
            ...((item.tables && item.tables.tables) || []).filter((table) => table.status !== 'ACTIVE')
                .map((table) => [item.label,
                    `${table.name}: ${window.SD_HEALTH.stateLabel(table.status)}`])
        ]);
        qs('#homeHealthProblems').innerHTML = problems.slice(0, 4).map(([label, what]) =>
            `<div class="sd-list-row"><span>${escape(label)}</span><b class="is-bad">${escape(what)}</b></div>`)
            .join('');
        const note = qs('#homeHealthNote');
        note.className = `sd-stat-note ${problems.length ? 'is-bad' : 'is-good'}`;
        note.textContent = problems.length
            ? `${problems.length} problema(s): abre Salud para el detalle.`
            : 'Todo responde.';
    }

    today();
    me();
    rates();
    users();
    health();
});
