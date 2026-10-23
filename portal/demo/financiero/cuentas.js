'use strict';

/**
 * Análisis Financiero › Catálogo de cuentas — the one chart of accounts, the
 * same for every company (contract, 15-oct). The manager reads it; the ADMIN,
 * who opens it from Administración, also adds, renames and removes accounts.
 * FINANCE enforces the same rule: only the ADMIN may change it.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const F = window.SD_FINANCE;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const icon = window.SD_ICONS.svg;
    const admin = window.SD_SHELL && window.SD_SHELL.role === 'ADMIN';
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');

    // The six types of the Bolivian chart, by the digit FINANCE sends.
    const TYPES = { 1: 'Activo', 2: 'Pasivo', 3: 'Patrimonio', 4: 'Ingresos', 5: 'Costos', 6: 'Gastos' };
    // Only sales (4) and purchases (5) carry the invoice mark.
    const INVOICEABLE = ['4', '5'];
    // Numbers joined by dots, the first one the type: what FINANCE accepts.
    const CODE_PATTERN = /^[1-6](\.\d+)*$/;

    const state = { accounts: [], renaming: null };
    const note = (text, kind) => {
        const element = qs('#accountsNote');
        element.className = `form-note${kind ? ` ${kind}` : ''}`;
        element.textContent = text || '';
    };
    const groups = () => state.accounts.filter((account) => !account.group_code);

    function marks(account) {
        const list = [];
        if (account.subtracts) list.push('Resta');
        if (account.invoiced === true) list.push('Con factura');
        if (account.invoiced === false) list.push('Sin factura');
        return list.join(' · ');
    }

    async function load() {
        try {
            const data = await F.get('/accounts');
            state.accounts = data.accounts || [];
            paint();
            note('');
            qs('#accountNew').disabled = false;
            qs('#accountsDownload').disabled = false;
        } catch (error) {
            note(F.errorText(error, 'No se pudo leer el catálogo.'), 'error');
        }
    }

    function visible() {
        const text = qs('#accountsSearch').value.trim().toLowerCase();
        const type = qs('#accountsType').value;
        return state.accounts
            .filter((account) => !type || account.account_type === type)
            .filter((account) => !text ||
                `${account.account_code} ${account.name}`.toLowerCase().includes(text));
    }

    /** Groups in bold and their accounts indented under them, in code order. */
    function paint() {
        const rows = visible();
        qs('#accountsCount').textContent =
            `${rows.length} de ${state.accounts.length}: ${groups().length} grupos y ` +
            `${state.accounts.length - groups().length} cuentas.`;
        qs('#accountsTable tbody').innerHTML = rows.map((account) => {
            const group = !account.group_code;
            const actions = admin ? `<td class="row-actions">
                <button type="button" class="btn-icon" data-tip="Cambiar el nombre" aria-label="Cambiar el nombre"
                        data-rename="${escape(account.account_code)}">${icon('edit')}</button>
                <button type="button" class="btn-icon is-delete" data-tip="Quitar del catálogo"
                        aria-label="Quitar del catálogo" data-remove="${escape(account.account_code)}">${icon('trash')}</button>
            </td>` : '';
            return `<tr class="${group ? 'account-group' : 'account-row'}">` +
                `<td><code>${escape(account.account_code)}</code></td>` +
                `<td>${group ? `<b>${escape(account.name)}</b>` : escape(account.name)}</td>` +
                `<td>${TYPES[account.account_type] || escape(account.account_type)}</td>` +
                `<td>${marks(account)}</td>${actions}</tr>`;
        }).join('');
    }

    // ---------- ADMIN: add, rename, remove ----------

    function fillGroups() {
        const type = qs('#accountTypeInput').value;
        qs('#accountGroup').innerHTML = '<option value="">Es un grupo (sin grupo arriba)</option>' +
            groups().filter((group) => group.account_type === type).map((group) =>
                `<option value="${escape(group.account_code)}">${escape(group.account_code)} · ` +
                `${escape(group.name)}</option>`).join('');
        qs('#accountInvoicedField').hidden = !INVOICEABLE.includes(type);
        if (!INVOICEABLE.includes(type)) qs('#accountInvoiced').value = '';
    }

    function openForm(account) {
        state.renaming = account || null;
        const creating = !account;
        qs('#accountFormTitle').textContent = creating ? 'Nueva cuenta'
            : `Cambiar el nombre de ${account.account_code}`;
        qs('#accountCodeField').hidden = !creating;
        qs('#accountNewFields').hidden = !creating;
        qs('#accountCode').value = '';
        qs('#accountName').value = creating ? '' : account.name;
        qs('#accountSubtracts').checked = false;
        qs('#accountTypeInput').value = '1';
        fillGroups();
        qs('#accountForm').hidden = false;
        qs(creating ? '#accountCode' : '#accountName').focus();
    }

    function closeForm() {
        state.renaming = null;
        qs('#accountForm').hidden = true;
        qs('#accountsTable').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function save(button) {
        const name = qs('#accountName').value.trim();
        if (!name) { note('Escribe el nombre.', 'error'); return; }
        const done = setButtonBusy(button, 'Guardando…');
        try {
            if (state.renaming) {
                await F.patch(`/accounts/${encodeURIComponent(state.renaming.account_code)}`, { name });
                toast(`Cuenta ${state.renaming.account_code} renombrada.`, 'success');
            } else {
                const code = qs('#accountCode').value.trim();
                if (!CODE_PATTERN.test(code)) {
                    note(F.errorText({ code: 'INVALID_ACCOUNT_CODE' }), 'error');
                    return;
                }
                const invoiced = qs('#accountInvoiced').value;
                await F.post('/accounts', {
                    account_code: code,
                    name,
                    account_type: qs('#accountTypeInput').value,
                    group_code: qs('#accountGroup').value || null,
                    subtracts: qs('#accountSubtracts').checked,
                    invoiced: invoiced === '' ? null : invoiced === 'true'
                });
                toast(`Cuenta ${code} agregada.`, 'success');
            }
            closeForm();
            await load();
        } catch (error) {
            note(F.errorText(error, 'No se pudo guardar la cuenta.'), 'error');
        } finally {
            done();
        }
    }

    /** First click asks, the second removes: no browser dialogs in the portal. */
    async function remove(button) {
        const code = button.dataset.remove;
        if (button.dataset.confirm !== '1') {
            button.dataset.confirm = '1';
            button.dataset.tip = 'Confirmar';
            button.classList.add('is-danger');
            note(`Quitar ${code} no se puede deshacer. Una cuenta con montos cargados no se quita.`);
            return;
        }
        const done = setButtonBusy(button);
        try {
            await F.del(`/accounts/${encodeURIComponent(code)}`);
            toast(`Cuenta ${code} quitada del catálogo.`, 'success');
            note('');
            await load();
        } catch (error) {
            note(F.errorText(error, 'No se pudo quitar la cuenta.'), 'error');
            done();
        }
    }

    /**
     * The whole catalog as a CSV Excel opens as it is: semicolons, which the
     * Spanish Excel expects, and the UTF-8 mark so the accents survive.
     */
    function download() {
        const cell = (value) => `"${String(value == null ? '' : value).replaceAll('"', '""')}"`;
        const invoice = (account) => (account.invoiced === true ? 'Con factura'
            : (account.invoiced === false ? 'Sin factura' : ''));
        const lines = [['Código', 'Nombre', 'Tipo', 'Grupo', 'Resta', 'Factura']].concat(
            state.accounts.map((account) => [account.account_code, account.name,
                TYPES[account.account_type] || account.account_type, account.group_code || '',
                account.subtracts ? 'Sí' : '', invoice(account)]));
        const csv = '\ufeff' + lines.map((line) => line.map(cell).join(';')).join('\r\n');
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        link.download = `catalogo_cuentas_${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }

    qs('#accountsType').innerHTML = '<option value="">Todos</option>' + Object.entries(TYPES)
        .map(([digit, label]) => `<option value="${digit}">${label}</option>`).join('');
    qs('#accountsSearch').addEventListener('input', paint);
    qs('#accountsType').addEventListener('change', paint);
    qs('#accountsDownload').addEventListener('click', download);

    if (admin) {
        qs('#accountNew').hidden = false;
        qs('#accountsActions').hidden = false;
        qs('#accountTypeInput').innerHTML = Object.entries(TYPES)
            .map(([digit, label]) => `<option value="${digit}">${digit} · ${label}</option>`).join('');
        qs('#accountTypeInput').addEventListener('change', fillGroups);
        // The first number of the code is the type: picked for the ADMIN.
        // Only numbers and dots get in (Rafael, 22-oct): a comma or a letter
        // is refused as it is typed or pasted, never dropped or merged
        // ("6,6,8" must not become "668"). FINANCE refuses it anyway.
        qs('#accountCode').addEventListener('beforeinput', (event) => {
            if (event.data && /[^0-9.]/.test(event.data)) {
                event.preventDefault();
                note('El código sólo lleva números y puntos, por ejemplo 6.1.20.', 'error');
            }
        });
        // The group is picked the same way (Rafael, 23-oct): the longest group
        // whose code starts the typed one, so 6.1.98 lands in 6.1 and is never
        // left as a stray top-level group by mistake.
        qs('#accountCode').addEventListener('input', () => {
            const code = qs('#accountCode').value.trim();
            const digit = code.charAt(0);
            if (TYPES[digit] && qs('#accountTypeInput').value !== digit) {
                qs('#accountTypeInput').value = digit;
                fillGroups();
            }
            const parent = [...qs('#accountGroup').options].map((option) => option.value)
                .filter((group) => group && code.startsWith(`${group}.`))
                .sort((a, b) => b.length - a.length)[0];
            qs('#accountGroup').value = parent || '';
        });
        qs('#accountNew').addEventListener('click', () => { note(''); openForm(null); });
        qs('#accountCancel').addEventListener('click', closeForm);
        qs('#accountSave').addEventListener('click', (event) => save(event.currentTarget));
        qs('#accountsTable').addEventListener('click', (event) => {
            const rename = event.target.closest('[data-rename]');
            if (rename) {
                note('');
                openForm(state.accounts.find((account) => account.account_code === rename.dataset.rename));
                return;
            }
            const del = event.target.closest('[data-remove]');
            if (del) remove(del);
        });
    }

    load();
});
