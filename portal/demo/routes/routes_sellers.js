'use strict';

/**
 * Rutas — "Vendedores": who each seller of the files is in the system.
 *
 * The sales file names a seller the way the ERP exports it ("Ana", "V-017");
 * the phone signs in with an email. Plans are made from the file's portfolio,
 * so without this link a seller's phone never sees their own plan and the
 * comparison cannot tell their run from anybody else's. INGEST owns the
 * master; the loads add new sellers on their own, and this screen only links.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_SHELL.forClient) return;
    const { qs, toast } = window.SD_UI;
    const T = window.SD_TRACK;

    const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    const state = { sellers: [] };

    async function load() {
        T.note(qs('#sellersNote'), 'Consultando…');
        try {
            const data = await T.sellers.list();
            state.sellers = data.sellers || [];
            qs('#sellersSummary').innerHTML =
                metric('Vendedores', String(data.total)) +
                metric('Con usuario', String(data.linked)) +
                metric('Sin usuario', String(data.total - data.linked));
            paintPage();
            T.note(qs('#sellersNote'), state.sellers.length ? ''
                : 'Todavía no hay vendedores: aparecen al cargar un archivo de ventas con la ' +
                  'columna Vendedor.');
        } catch (error) {
            T.note(qs('#sellersNote'), T.errorText(error, 'No se pudieron leer los vendedores.'),
                   'error');
        }
    }

    function metric(label, value) {
        return `<div class="metric"><p class="metric-label">${T.escapeHtml(label)}</p>` +
               `<p class="metric-value">${T.escapeHtml(value)}</p></div>`;
    }

    // Draws every row; the common pager (js/ui.js) shows ten at a time.
    function paintPage() {
        const rows = state.sellers;

        const tbody = qs('#sellersTable tbody');
        tbody.innerHTML = rows.map((seller) =>
            `<tr data-id="${T.escapeHtml(seller.id)}">` +
            `<td>${T.escapeHtml(seller.name || seller.id)}</td>` +
            `<td><input type="email" class="seller-email" maxlength="100" ` +
            `value="${T.escapeHtml(seller.user_email || '')}" placeholder="correo@empresa.com"></td>` +
            `<td><button type="button" class="btn-icon is-save" data-tip="Guardar" aria-label="Guardar" data-save>${window.SD_ICONS.svg('check')}</button></td>` +
            '</tr>').join('');
    }

    qs('#sellersTable').addEventListener('click', async (event) => {
        const button = event.target.closest('[data-save]');
        if (!button) return;
        const row = button.closest('tr');
        const email = row.querySelector('.seller-email').value.trim();
        if (email && !EMAIL.test(email)) {
            T.note(qs('#sellersNote'), 'Ese correo no es válido.', 'error');
            return;
        }
        button.disabled = true;
        try {
            // An empty email unlinks: the seller keeps their plans, their phone stops seeing them.
            await T.sellers.link(row.dataset.id, { user_email: email || null });
            toast(email ? 'Vendedor vinculado.' : 'Vendedor desvinculado.', 'success');
            await load();
        } catch (error) {
            T.note(qs('#sellersNote'), T.errorText(error, 'No se pudo guardar.'), 'error');
        } finally {
            button.disabled = false;
        }
    });

    qs('#sellersRefresh').addEventListener('click', load);

    let loaded = false;
    T.onShow('sellers', () => { if (!loaded) { loaded = true; load(); } });
});
