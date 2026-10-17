'use strict';

/**
 * Principal — the application's welcome: who you are and when you last came
 * in, what your role may open, today's rates, where to configure, and (for
 * whoever runs the account) who else uses it and when they last came in.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_SHELL) return;
    const { API_URL } = window.SD_CONFIG;
    const shell = window.SD_SHELL;
    const icon = window.SD_ICONS.svg;
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

    /** The menu as a map: each top entry with what hangs from it. */
    function map() {
        qs('#homeMap').innerHTML = shell.menu().map((section) => section.items
            .filter((item) => item.href !== location.pathname)
            .map((item) => `<div class="sd-map-node">` +
                `<a class="sd-map-head" href="${item.href}">${icon(item.icon)}<span>${escape(item.label)}</span></a>` +
                (item.children.length ? `<div class="sd-map-children">${item.children.map((child) =>
                    `<a href="${child.href}">${escape(child.label)}</a>`).join('')}</div>` : '') +
                '</div>').join('')).join('');
    }

    function settings() {
        const links = shell.isEditor
            ? [['parametros/index.html', 'settings', 'Parámetros', 'Políticas, vendedores, prompts de la IA'],
               ['parametros/factores.html', 'rates', 'Factores externos', 'Tipo de cambio y factores que sigues'],
               ['cuenta.html', 'user', 'Mi cuenta', 'Tus datos y tu contraseña']]
            : [['cuenta.html', 'user', 'Mi cuenta', 'Tus datos y tu contraseña']];
        qs('#homeSettings').innerHTML = links.map(([target, name, title, line]) =>
            `<a class="sd-link" href="${target}">${icon(name)}<span><b>${title}</b>${line}</span></a>`).join('');
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

    async function users() {
        if (!shell.isEditor) return;
        const list = await window.SD_API.get(`${API_URL}/v1/users/company`).catch(() => null);
        if (!list) return;
        qs('#homeUsers').hidden = false;
        const inToday = list.filter((user) => isToday(user.last_login)).length;
        qs('#homeUsersNote').textContent =
            `${number(list.length)} usuarios; ${number(inToday)} entraron hoy.`;
        qs('#homeUsersTable tbody').innerHTML = list.map((user) =>
            `<tr><td>${escape(`${user.first_name} ${user.last_name}`)}</td><td>${escape(user.email)}</td>` +
            `<td>${ROLES[user.role] || escape(user.role)}</td>` +
            `<td>${when(user.last_login) || 'Sin registro aún'}</td>` +
            `<td class="numeric">${number(user.login_count)}</td>` +
            `<td><span class="sd-status ${user.status ? 'is-on' : 'is-off'}">` +
            `${user.status ? 'Activo' : 'Inactivo'}</span></td></tr>`).join('');
    }

    today();
    map();
    settings();
    me();
    rates();
    users();
});
