/**
 * EntityPanel — config-driven CRUD UI for one CMS entity.
 *
 * Built around the layout in admin/index.html (panel host + shared
 * modal). The panel reads its behavior from one of the ENTITY_CONFIGS
 * entries; the modal form is generated from the `fields` list.
 *
 * File fields are special: their value lives on the browser as a File
 * object until the user clicks Save, at which point the panel uploads
 * to FilesService and writes the resulting bucket/key onto the payload
 * under `${refName}_s3_bucket` / `${refName}_s3_key`.
 */
export class EntityPanel {
    constructor({ entity, config, cmsAdmin, files }) {
        this.entity = entity;
        this.config = config;
        this.cmsAdmin = cmsAdmin;
        this.files = files;
        this.items = [];
        this.modal = new ItemModal({
            host: document.getElementById('modal-host'),
            titleEl: document.getElementById('modal-title'),
            formEl: document.getElementById('modal-form'),
            errorEl: document.getElementById('modal-error'),
            closeBtn: document.getElementById('modal-close'),
            cancelBtn: document.getElementById('modal-cancel'),
            saveBtn: document.getElementById('modal-save'),
            files,
        });
    }

    async mount(hostEl, titleEl, newBtn) {
        titleEl.textContent = this.config.title;
        hostEl.innerHTML = '<p class="panel-loading">Cargando…</p>';
        newBtn.onclick = () => this._openCreate();
        try {
            const data = await this.cmsAdmin[this.config.service.list]();
            this.items = data?.items || [];
            this._renderTable(hostEl);
        } catch (err) {
            hostEl.innerHTML = `<p class="form-error">${err.message}</p>`;
        }
    }

    _renderTable(hostEl) {
        if (!this.items.length) {
            hostEl.innerHTML = '<p class="panel-empty">Sin items todavía. Crea uno con “Nuevo”.</p>';
            return;
        }
        const headers = this.config.columns
            .map(c => `<th>${c.label}</th>`).join('');
        const rows = this.items.map(item => {
            const cells = this.config.columns
                .map(c => `<td>${_formatCell(item[c.key], c.type)}</td>`)
                .join('');
            return `
                <tr data-id="${item.id}">
                    ${cells}
                    <td class="row-actions">
                        <button class="ghost edit-btn"><i class="fa-solid fa-pen"></i></button>
                        <button class="ghost danger delete-btn"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        }).join('');
        hostEl.innerHTML = `
            <table class="admin-table">
                <thead><tr>${headers}<th></th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
        hostEl.querySelectorAll('.edit-btn').forEach(btn => {
            btn.onclick = () => this._openEdit(btn.closest('tr').dataset.id);
        });
        hostEl.querySelectorAll('.delete-btn').forEach(btn => {
            btn.onclick = () => this._delete(btn.closest('tr').dataset.id);
        });
    }

    async _openCreate() {
        const defaults = Object.fromEntries(
            this.config.fields
                .filter(f => f.default !== undefined)
                .map(f => [f.name, f.default]),
        );
        await this.modal.open({
            title: `Crear ${this.config.title.slice(0, -1).toLowerCase()}`,
            fields: this.config.fields,
            values: defaults,
            subPath: this.config.subPath,
            onSubmit: payload => this.cmsAdmin[this.config.service.create](payload),
        });
        this._refresh();
    }

    async _openEdit(id) {
        const item = this.items.find(i => i.id === id);
        await this.modal.open({
            title: `Editar ${this.config.title.slice(0, -1).toLowerCase()}`,
            fields: this.config.fields,
            values: item,
            subPath: this.config.subPath,
            onSubmit: payload => this.cmsAdmin[this.config.service.update](id, payload),
        });
        this._refresh();
    }

    async _delete(id) {
        const item = this.items.find(i => i.id === id);
        const label = item?.title || item?.name || id;
        if (!confirm(`¿Eliminar “${label}”?`)) return;
        try {
            await this.cmsAdmin[this.config.service.delete](id);
            this._refresh();
        } catch (err) {
            alert(err.message);
        }
    }

    _refresh() {
        const hostEl = document.getElementById('panel-host');
        const titleEl = document.getElementById('panel-title');
        const newBtn = document.getElementById('new-item-btn');
        this.mount(hostEl, titleEl, newBtn);
    }
}


// ---------- Modal ----------

class ItemModal {
    constructor(refs) {
        this.refs = refs;
        this.refs.closeBtn.onclick = () => this._close();
        this.refs.cancelBtn.onclick = () => this._close();
        this.refs.host.querySelector('.modal-backdrop')
            .addEventListener('click', () => this._close());
    }

    open({ title, fields, values = {}, subPath, onSubmit }) {
        this.refs.titleEl.textContent = title;
        this.refs.errorEl.hidden = true;
        this.refs.formEl.innerHTML = fields
            .map(f => _renderField(f, values[f.name])).join('');
        this.refs.host.hidden = false;
        return new Promise(resolve => {
            this.refs.saveBtn.onclick = async () => {
                this.refs.saveBtn.disabled = true;
                this.refs.errorEl.hidden = true;
                try {
                    const payload = await _collectPayload(this.refs.formEl, fields,
                        this.refs.files, subPath);
                    await onSubmit(payload);
                    this._close();
                    resolve(true);
                } catch (err) {
                    this.refs.errorEl.textContent = err.message;
                    this.refs.errorEl.hidden = false;
                } finally {
                    this.refs.saveBtn.disabled = false;
                }
            };
            this._resolveCurrent = resolve;
        });
    }

    _close() {
        this.refs.host.hidden = true;
        if (this._resolveCurrent) this._resolveCurrent(false);
        this._resolveCurrent = null;
    }
}


// ---------- Field rendering + payload assembly ----------

function _renderField(field, currentValue) {
    const id = `field-${field.name}`;
    const required = field.required ? 'required' : '';
    const placeholder = field.placeholder
        ? `placeholder="${_escape(field.placeholder)}"` : '';
    const max = field.maxLength ? `maxlength="${field.maxLength}"` : '';

    if (field.type === 'textarea') {
        return `
            <label class="form-field" for="${id}">
                <span>${field.label}</span>
                <textarea id="${id}" name="${field.name}" rows="4" ${max} ${required}>${
                    _escape(currentValue ?? '')}</textarea>
            </label>`;
    }
    if (field.type === 'select') {
        const opts = field.options.map(o => {
            const value = typeof o === 'string' ? o : o.value;
            const label = typeof o === 'string' ? o : o.label;
            const selected = currentValue === value ? 'selected' : '';
            return `<option value="${_escape(value)}" ${selected}>${
                _escape(label)}</option>`;
        }).join('');
        return `
            <label class="form-field" for="${id}">
                <span>${field.label}</span>
                <select id="${id}" name="${field.name}" ${required}>${opts}</select>
            </label>`;
    }
    if (field.type === 'checkbox') {
        const checked = currentValue ? 'checked' : '';
        return `
            <label class="form-field form-field-inline" for="${id}">
                <input type="checkbox" id="${id}" name="${field.name}" ${checked}>
                <span>${field.label}</span>
            </label>`;
    }
    if (field.type === 'file') {
        const bucket = currentValue && typeof currentValue === 'object'
            ? null
            : `<small class="file-current">Actual: ${_escape(currentValue || '—')}</small>`;
        return `
            <label class="form-field" for="${id}">
                <span>${field.label}</span>
                <input type="file" id="${id}" name="${field.name}" ${
                    field.accept ? `accept="${field.accept}"` : ''}>
                ${bucket || ''}
            </label>`;
    }
    const inputType = ({
        number: 'number', date: 'date', datetime: 'datetime-local',
    })[field.type] || 'text';
    const value = _formatInputValue(currentValue, field.type);
    return `
        <label class="form-field" for="${id}">
            <span>${field.label}</span>
            <input id="${id}" name="${field.name}" type="${inputType}"
                   value="${_escape(value)}" ${placeholder} ${max} ${required}>
        </label>`;
}

async function _collectPayload(formEl, fields, filesService, subPath) {
    const data = new FormData(formEl);
    const payload = {};
    for (const field of fields) {
        if (field.type === 'file') {
            const input = formEl.querySelector(`[name="${field.name}"]`);
            const file = input?.files?.[0];
            if (file) {
                const { bucket, key } = await filesService.upload(file, subPath);
                payload[`${field.refName}_s3_bucket`] = bucket;
                payload[`${field.refName}_s3_key`] = key;
            }
            continue;
        }
        if (field.type === 'checkbox') {
            payload[field.name] = formEl
                .querySelector(`[name="${field.name}"]`).checked;
            continue;
        }
        const raw = data.get(field.name);
        if (raw === null || raw === '') continue;
        if (field.type === 'number') {
            payload[field.name] = Number(raw);
        } else if (field.type === 'datetime') {
            // <input type="datetime-local"> emits "YYYY-MM-DDTHH:mm";
            // the backend Pydantic schema parses ISO 8601 just fine.
            payload[field.name] = raw;
        } else {
            payload[field.name] = raw;
        }
    }
    return payload;
}

function _formatCell(value, kind) {
    if (value === null || value === undefined || value === '') return '—';
    if (kind === 'bool') return value ? '✓' : '✗';
    if (kind === 'datetime') {
        const d = new Date(value);
        if (Number.isNaN(d.getTime())) return _escape(String(value));
        return d.toLocaleString('es-BO',
            { dateStyle: 'short', timeStyle: 'short' });
    }
    return _escape(String(value));
}

function _formatInputValue(value, kind) {
    if (value === null || value === undefined) return '';
    if (kind === 'datetime') {
        // Trim the timezone suffix so <input type="datetime-local"> accepts it.
        return String(value).slice(0, 16);
    }
    if (kind === 'date') {
        return String(value).slice(0, 10);
    }
    return value;
}

function _escape(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}
