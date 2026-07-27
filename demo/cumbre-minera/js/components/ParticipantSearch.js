/**
 * Buscador de participantes por nombre o CI (autocompletado). Trae todos los
 * participantes una vez (paginando el backend) y filtra en vivo. Al elegir uno
 * llama onPick(participant). Reusa los estilos .combo del CSS.
 */
export function mountParticipantSearch(inputEl, listEl, { api, config, onPick }) {
    let all = [];
    (async () => {
        try {
            const acc = [];
            let offset = null;
            for (let guard = 0; guard < 200; guard += 1) {
                const params = { limit: 100 };
                if (offset) params.last_evaluated_key = offset;
                const data = await api.get(config.miningSummit.participantsPath, params);
                acc.push(...(data.items || []));
                offset = data.last_evaluated_key || null;
                if (!offset) break;
            }
            all = acc;
        } catch (_) { /* búsqueda deshabilitada si falla la carga */ }
    })();

    const norm = (s) => String(s == null ? '' : s).toLowerCase()
        .normalize('NFD').replace(/[̀-ͯ]/g, '');

    function render(query) {
        const needle = norm(query.trim());
        if (!needle) { listEl.hidden = true; return; }
        const matches = all.filter(p =>
            norm(`${p.first_name || ''} ${p.last_name || ''} ${p.ci || ''}`).includes(needle)
        ).slice(0, 25);
        if (!matches.length) {
            listEl.innerHTML = '<div class="combo-empty">Sin resultados</div>';
        } else {
            listEl.innerHTML = matches.map(p =>
                `<div class="combo-option" data-ci="${escapeHtml(p.ci)}">
                    <strong>${escapeHtml(p.first_name)} ${escapeHtml(p.last_name)}</strong>
                    · CI ${escapeHtml(p.ci)}${p.institution_name
                        ? ` · <small>${escapeHtml(p.institution_name)}</small>` : ''}
                 </div>`).join('');
        }
        listEl.hidden = false;
    }

    inputEl.addEventListener('input', () => render(inputEl.value));
    inputEl.addEventListener('focus', () => render(inputEl.value));
    inputEl.addEventListener('blur', () => setTimeout(() => { listEl.hidden = true; }, 150));
    listEl.addEventListener('mousedown', (event) => {
        const opt = event.target.closest('.combo-option');
        if (!opt || !opt.dataset.ci) return;
        event.preventDefault();
        const participant = all.find(p => p.ci === opt.dataset.ci);
        listEl.hidden = true;
        inputEl.value = '';
        if (participant && onPick) onPick(participant);
    });
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
