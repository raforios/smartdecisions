/**
 * Convierte un <select> nativo en un combo con buscador, sin perder el valor ni
 * el envío del formulario: el <select> original queda oculto como fuente del
 * valor (FormData lo lee por su name) y se le dispara 'change' al elegir. Las
 * opciones se leen EN VIVO al abrir, así funciona aunque el <select> se llene o
 * se reconstruya de forma asíncrona (p. ej. disponibilidad de ejes).
 */
export function enhanceSelect(selectEl, placeholder = 'Buscar…') {
    if (!selectEl || selectEl.dataset.enhanced) return;
    selectEl.dataset.enhanced = '1';
    selectEl.style.display = 'none';

    const wrap = document.createElement('div');
    wrap.className = 'combo';
    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.placeholder = placeholder;
    const list = document.createElement('div');
    list.className = 'combo-list';
    list.hidden = true;

    selectEl.parentNode.insertBefore(wrap, selectEl);
    wrap.appendChild(selectEl);
    wrap.appendChild(input);
    wrap.appendChild(list);

    const selectedText = () => {
        const opt = selectEl.options[selectEl.selectedIndex];
        return opt && opt.value ? opt.text : '';
    };
    input.value = selectedText();

    function render(filter) {
        const needle = (filter || '').trim().toLowerCase();
        const opts = Array.from(selectEl.options).filter(o => o.text.toLowerCase().includes(needle));
        if (!opts.length) {
            list.innerHTML = '<div class="combo-empty">Sin resultados</div>';
            return;
        }
        list.innerHTML = opts.map(o =>
            `<div class="combo-option" data-value="${o.value.replace(/"/g, '&quot;')}">${escapeHtml(o.text)}</div>`
        ).join('');
    }

    function open() {
        render('');
        list.hidden = false;
    }
    function close() {
        list.hidden = true;
        // Si lo escrito no coincide con nada, restaurar el texto seleccionado.
        input.value = selectedText();
    }

    input.addEventListener('focus', open);
    input.addEventListener('input', () => { list.hidden = false; render(input.value); });
    list.addEventListener('mousedown', (event) => {
        const opt = event.target.closest('.combo-option');
        if (!opt) return;
        event.preventDefault();
        selectEl.value = opt.dataset.value;
        input.value = opt.textContent;
        list.hidden = true;
        selectEl.dispatchEvent(new Event('change', { bubbles: true }));
    });
    input.addEventListener('blur', () => setTimeout(close, 120));

    // Si el form se resetea, sincronizar el texto mostrado.
    const formEl = selectEl.form;
    if (formEl) formEl.addEventListener('reset', () => setTimeout(() => { input.value = selectedText(); }, 0));
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
