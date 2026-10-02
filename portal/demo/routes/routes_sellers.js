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
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast } = window.SD_UI;
    const T = window.SD_TRACK;

    const ROWS_PER_PAGE = 10;
    const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    const state = { sellers: [], page: 0 };

    async function load() {
        T.note(qs('#sellersNote'), 'Consultando…');
        try {
            const data = await T.sellers.list();
            state.sellers = data.sellers || [];
            qs('#sellersSummary').innerHTML =
                metric('Vendedores', String(data.total)) +
                metric('Con usuario', String(data.linked)) +
                metric('Sin usuario', String(data.total - data.linked));
            paintPage(state.page);
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

    // Ten rows per page with invisible filler, like every table of the portal.
    function paintPage(page) {
        const rows = state.sellers;
        const pages = Math.max(1, Math.ceil(rows.length / ROWS_PER_PAGE));
        state.page = Math.min(Math.max(page, 0), pages - 1);
        const slice = rows.slice(state.page * ROWS_PER_PAGE, (state.page + 1) * ROWS_PER_PAGE);

        const tbody = qs('#sellersTable tbody');
        tbody.innerHTML = slice.map((seller) =>
            `<tr data-id="${T.escapeHtml(seller.id)}">` +
            `<td>${T.escapeHtml(seller.name || seller.id)}</td>` +
            `<td><input type="email" class="seller-email" maxlength="100" ` +
            `value="${T.escapeHtml(seller.user_email || '')}" placeholder="correo@empresa.com"></td>` +
            '<td><button type="button" class="btn btn-ghost btn-small" data-save>Guardar</button></td>' +
            '</tr>').join('');
        if (rows.length > ROWS_PER_PAGE) {
            tbody.innerHTML += '<tr class="row-filler"><td colspan="3">&nbsp;</td></tr>'
                .repeat(ROWS_PER_PAGE - slice.length);
        }
        qs('#sellersCount').textContent = rows.length === 1 ? '1 vendedor' : `${rows.length} vendedores`;
        qs('#sellersPage').textContent = `${state.page + 1} / ${pages}`;
        qs('#sellersPrev').disabled = state.page === 0;
        qs('#sellersNext').disabled = state.page >= pages - 1;
        qs('#sellersPager').hidden = rows.length <= ROWS_PER_PAGE;
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
    qs('#sellersPrev').addEventListener('click', () => paintPage(state.page - 1));
    qs('#sellersNext').addEventListener('click', () => paintPage(state.page + 1));

    let loaded = false;
    T.onShow('sellers', () => { if (!loaded) { loaded = true; load(); } });
});
