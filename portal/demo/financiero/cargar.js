'use strict';

/**
 * Cargar datos: the template goes up through FILES straight to the bucket
 * root —read once and removed, as in BINARIA's bulk loads— and FINANCE loads
 * it by its key. The loads, and every amount, can be reviewed here: a wrong
 * amount or date is corrected, an amount removed, a period emptied.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;

    const F = window.SD_FINANCE;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const escapeHtml = (text) => String(text ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;');
    const amount = (value) => Number(value).toLocaleString('es-BO',
        { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const state = { entries: [], fixing: null };

    // ---- Upload -----------------------------------------------------------
    qs('#fileInput').addEventListener('change', () => {
        qs('#uploadButton').disabled = !qs('#fileInput').files.length;
    });

    qs('#uploadButton').addEventListener('click', async () => {
        const file = qs('#fileInput').files[0];
        if (!file) return;
        const done = setButtonBusy(qs('#uploadButton'), 'Cargando…');
        try {
            const key = await window.SD_API.uploadToBucket(file, (ratio) => {
                qs('#uploadNote').textContent = `Subiendo… ${Math.round(ratio * 100)} %`;
            }, '');
            qs('#uploadNote').textContent = 'Validando y cargando…';
            showResult(await F.post('/loads/file', { flow: qs('#flowSelect').value, file_key: key }));
            qs('#uploadNote').textContent = '';
            await loadHistory();
        } catch (error) {
            qs('#uploadNote').textContent = '';
            toast(F.errorText(error, 'No se pudo cargar el archivo.'), 'error');
        } finally {
            done();
        }
    });

    function showResult(result) {
        const rejected = result.rejected || [];
        qs('#resultSummary').textContent = `Entraron ${result.accepted} cifra(s)` +
            (rejected.length ? `; ${rejected.length} fila(s) apartadas, con su motivo:` : '.');
        qs('#rejectedTable tbody').innerHTML = rejected.map((row) =>
            `<tr><td>${row.row}</td><td>${escapeHtml(F.errorText({ code: row.code }, row.code))}</td>` +
            `<td>${escapeHtml(row.value)}</td></tr>`).join('');
        qs('#rejectedBlock').hidden = !rejected.length;
        qs('#resultCard').hidden = false;
    }

    // ---- History ----------------------------------------------------------
    async function loadHistory() {
        const data = await F.get('/loads');
        qs('#loadsTable tbody').innerHTML = (data.loads || []).map((load) => {
            const [day, time] = load.created_at.split('T');
            const [year, month, date] = day.split('-');
            return `<tr><td>${date}/${month}/${year} ${time.slice(0, 5)}</td>` +
                `<td>${escapeHtml(load.user)}</td><td>${F.FLOW_LABELS[load.flow] || load.flow}</td>` +
                `<td>${F.CHANNEL_LABELS[load.channel] || load.channel}</td>` +
                `<td class="numeric">${load.accepted}</td><td class="numeric">${load.rejected}</td></tr>`;
        }).join('') || '<tr><td colspan="6">Todavía no hay cargas.</td></tr>';
    }

    // ---- Amounts ----------------------------------------------------------
    const filter = () => ({ periodicity: qs('#entriesPeriodicity').value,
                            date: qs('#entriesDate').value.trim() });

    async function loadEntries() {
        const { periodicity, date } = filter();
        const query = date ? { periodicity, date } : { periodicity };
        const data = await F.get('/entries', query);
        state.entries = data.entries || [];
        qs('#entriesNote').textContent = `${state.entries.length} monto(s).`;
        qs('#entriesTable tbody').innerHTML = state.entries.map((entry, index) =>
            `<tr><td>${entry.date}</td><td>${entry.account_code}</td>` +
            `<td class="numeric">${amount(entry.amount)}</td>` +
            `<td>${entry.taxes_included == null ? '' : (entry.taxes_included ? 'Sí' : 'No')}</td>` +
            `<td><button type="button" class="btn btn-ghost btn-small" data-fix="${index}">Corregir</button> ` +
            `<button type="button" class="btn btn-ghost btn-small" data-remove="${index}">Borrar</button></td></tr>`
        ).join('');
    }

    const target = (entry) => new URLSearchParams({
        periodicity: entry.periodicity, date: entry.date, account_code: entry.account_code
    }).toString();

    qs('#entriesTable').addEventListener('click', async (event) => {
        const fix = event.target.closest('[data-fix]');
        const remove = event.target.closest('[data-remove]');
        if (fix) {
            state.fixing = state.entries[Number(fix.dataset.fix)];
            qs('#fixTitle').textContent = `Corregir ${state.fixing.account_code} · ${state.fixing.date}`;
            qs('#fixDate').value = state.fixing.date;
            qs('#fixAmount').value = state.fixing.amount;
            qs('#fixForm').hidden = false;
        }
        if (remove) {
            try {
                await F.del(`/entries?${target(state.entries[Number(remove.dataset.remove)])}`);
                await loadEntries();
            } catch (error) {
                toast(F.errorText(error, 'No se pudo borrar el monto.'), 'error');
            }
        }
    });

    qs('#fixCancel').addEventListener('click', () => { qs('#fixForm').hidden = true; });
    qs('#fixForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const done = setButtonBusy(qs('#fixSave'), 'Guardando…');
        try {
            await F.patch(`/entries?${target(state.fixing)}`, {
                date: qs('#fixDate').value.trim(), amount: Number(qs('#fixAmount').value)
            });
            qs('#fixForm').hidden = true;
            await loadEntries();
        } catch (error) {
            toast(F.errorText(error, 'No se pudo corregir el monto.'), 'error');
        } finally {
            done();
        }
    });

    qs('#entriesShow').addEventListener('click', () => loadEntries().catch((error) =>
        toast(F.errorText(error, 'No se pudieron leer los montos.'), 'error')));

    // Emptying a period asks twice, on the page itself: it removes every
    // amount of that periodicity whose date starts with the one written.
    qs('#periodClear').addEventListener('click', () => {
        const { date } = filter();
        if (!date) {
            toast('Escribe la fecha del período que quieres vaciar.', 'error');
            return;
        }
        qs('#periodClearConfirm').hidden = false;
        qs('#entriesNote').textContent = `Se borrarán todos los montos de ${date}. ¿Seguro?`;
    });
    qs('#periodClearConfirm').addEventListener('click', async () => {
        const { periodicity, date } = filter();
        try {
            const result = await F.del(`/periods?${new URLSearchParams({ periodicity, date })}`);
            qs('#periodClearConfirm').hidden = true;
            toast(`Se borraron ${result.deleted} monto(s).`, 'success');
            // loadEntries writes the count back into the note, replacing the question.
            await loadEntries();
        } catch (error) {
            toast(F.errorText(error, 'No se pudo vaciar el período.'), 'error');
        }
    });

    loadHistory().catch((error) =>
        toast(F.errorText(error, 'No se pudo leer el historial de cargas.'), 'error'));
});
