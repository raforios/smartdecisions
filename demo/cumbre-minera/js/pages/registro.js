/**
 * Registro de Participante.
 * POST /v1/mining-summit/participants
 *
 * Al elegir una institución se envía institution_id: el backend deriva el rol
 * y (para roles FIJO) asienta al participante en un eje y mesa estables. Tras
 * registrar se muestra una credencial imprimible con QR (codifica el CI para
 * el marcado de asistencia).
 */
import { Toast } from '../components/Toast.js';
import { renderQr, printCredential } from '../components/Credential.js';

export const RegistroPage = {
    async render(container, { config, api }) {
        const departamentos = (config.departments || []).map(
            d => `<option value="${d}">${d}</option>`
        ).join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Registro de Participantes</h2>
                    <div class="subtitle">Crea un participante nuevo. La primera asistencia se registra automáticamente.</div>
                </div>
            </div>

            <div class="card">
                <h3><i class="fa-solid fa-user-plus" style="color:var(--oro)"></i> Datos del participante</h3>
                <form id="registro-form">
                    <div class="form-grid">
                        <div class="form-field">
                            <label for="ci">Carnet de Identidad <span class="req">*</span></label>
                            <input id="ci" name="ci" type="text" required minlength="4" maxlength="20" inputmode="numeric" pattern="[0-9]+" placeholder="Ej. 1234567">
                        </div>
                        <div class="form-field">
                            <label for="first_name">Nombre <span class="req">*</span></label>
                            <input id="first_name" name="first_name" type="text" required minlength="1" maxlength="80">
                        </div>
                        <div class="form-field">
                            <label for="last_name">Apellido <span class="req">*</span></label>
                            <input id="last_name" name="last_name" type="text" required minlength="1" maxlength="80">
                        </div>
                        <div class="form-field form-field-wide">
                            <label for="institution_id">Institución / Organización</label>
                            <select id="institution_id" name="institution_id">
                                <option value="">— Cargando instituciones… —</option>
                            </select>
                            <div id="role-hint" class="role-hint"></div>
                        </div>
                        <div class="form-field">
                            <label for="email">Correo electrónico</label>
                            <input id="email" name="email" type="email" maxlength="120">
                        </div>
                        <div class="form-field">
                            <label for="phone">Celular</label>
                            <input id="phone" name="phone" type="tel" maxlength="30">
                        </div>
                        <div class="form-field">
                            <label for="department">Departamento</label>
                            <select id="department" name="department">
                                <option value="">— Seleccionar —</option>
                                ${departamentos}
                            </select>
                        </div>
                    </div>
                    <div class="form-actions">
                        <button id="submit-btn" class="btn btn-primary" type="submit">
                            <i class="fa-solid fa-floppy-disk"></i> Registrar y marcar asistencia
                        </button>
                        <button id="reset-btn" class="btn btn-ghost" type="button">
                            <i class="fa-solid fa-rotate-left"></i> Limpiar
                        </button>
                    </div>
                </form>
            </div>

            <div id="registro-result"></div>
        `;

        const form = container.querySelector('#registro-form');
        const submitBtn = container.querySelector('#submit-btn');
        const resetBtn = container.querySelector('#reset-btn');
        const institutionSelect = container.querySelector('#institution_id');
        const roleHint = container.querySelector('#role-hint');
        const resultBox = container.querySelector('#registro-result');

        const institutions = await loadInstitutions(api, config, institutionSelect);

        institutionSelect.addEventListener('change', () => {
            renderRoleHint(roleHint, institutions.get(institutionSelect.value));
        });

        resetBtn.addEventListener('click', () => {
            form.reset();
            roleHint.innerHTML = '';
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = readFormPayload(form);
            if (!payload.ci || !payload.first_name || !payload.last_name) {
                Toast.danger('Nombre, apellido y CI son obligatorios.');
                return;
            }
            submitBtn.disabled = true;
            const original = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Guardando...';
            try {
                const saved = await api.post(config.miningSummit.participantsPath, payload);
                Toast.success(
                    `Participante registrado: ${saved.first_name} ${saved.last_name} (CI ${saved.ci}).`
                );
                renderCredential(resultBox, saved);
                form.reset();
                roleHint.innerHTML = '';
            } catch (error) {
                Toast.danger(`No se pudo registrar: ${error.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = original;
            }
        });
    }
};

async function loadInstitutions(api, config, selectEl) {
    const byId = new Map();
    try {
        const response = await api.get(config.miningSummit.institutionsPath);
        const items = (response && response.items) || [];
        items.forEach(item => byId.set(item.id, item));
        selectEl.innerHTML = buildInstitutionOptions(items);
    } catch (error) {
        selectEl.innerHTML = '<option value="">— No se pudo cargar el catálogo —</option>';
        Toast.danger(`Instituciones: ${error.message}`);
    }
    return byId;
}

function buildInstitutionOptions(items) {
    const groups = new Map();
    items.forEach(item => {
        if (!groups.has(item.category)) groups.set(item.category, []);
        groups.get(item.category).push(item);
    });
    let html = '<option value="">— Sin institución (asistencia libre) —</option>';
    for (const [category, list] of groups) {
        const options = list.map(
            item => `<option value="${item.id}">${escapeHtml(item.name)}</option>`
        ).join('');
        html += `<optgroup label="${escapeHtml(category)}">${options}</optgroup>`;
    }
    return html;
}

function renderRoleHint(hintEl, institution) {
    if (!institution) {
        hintEl.innerHTML = '';
        return;
    }
    const seated = institution.assignment_type === 'FIJO';
    const icon = seated ? 'fa-chair' : 'fa-people-arrows';
    const seatText = seated
        ? 'Asiento fijo: se le asignará un eje y una mesa.'
        : 'Asistencia rotativa: sin mesa fija.';
    hintEl.innerHTML = `
        <i class="fa-solid ${icon}" style="color:var(--oro)"></i>
        Rol: <strong>${institution.role}</strong> · ${seatText}
    `;
}

function renderCredential(resultBox, participant) {
    const seated = participant.mesa_code;
    const seatBlock = seated
        ? `<div class="cred-seat-fixed">
                <div class="cred-eje">${escapeHtml(participant.axis_label || participant.axis || '')}</div>
                <div class="cred-aula"><span>Aula</span> ${escapeHtml(participant.mesa_code)}</div>
           </div>`
        : `<div class="cred-seat cred-seat-rotating">
                <span>Asistencia rotativa</span> — sin mesa fija
           </div>`;

    resultBox.innerHTML = `
        <div class="card credential" id="credential">
            <div class="credential-head">
                <img src="assets/logo_oficial.png" alt="Cumbre Minera" class="cred-logo">
                <div>
                    <div class="cred-title">Cumbre Minera 2026</div>
                    <div class="cred-sub">Credencial de Participante</div>
                </div>
            </div>
            <div class="credential-body">
                <div class="cred-info">
                    <div class="cred-name">${escapeHtml(participant.first_name)} ${escapeHtml(participant.last_name)}</div>
                    <div class="cred-line"><span>CI</span> ${escapeHtml(participant.ci)}</div>
                    ${participant.institution_name
                        ? `<div class="cred-line"><span>Institución</span> ${escapeHtml(participant.institution_name)}</div>`
                        : ''}
                    ${participant.role
                        ? `<div class="cred-line"><span>Rol</span> ${escapeHtml(participant.role)}</div>`
                        : ''}
                    ${seatBlock}
                </div>
                <div class="cred-qr">
                    <canvas id="cred-qr-canvas"></canvas>
                    <div class="cred-qr-caption">Escanea para asistencia</div>
                </div>
            </div>
            <div class="form-actions">
                <button id="print-credential" class="btn btn-primary" type="button">
                    <i class="fa-solid fa-print"></i> Imprimir credencial
                </button>
            </div>
        </div>
    `;

    const canvas = resultBox.querySelector('#cred-qr-canvas');
    renderQr(canvas, participant);
    resultBox.querySelector('#print-credential')
        .addEventListener('click', () => printCredential(participant));
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function readFormPayload(form) {
    const data = new FormData(form);
    const payload = {};
    for (const [key, value] of data.entries()) {
        const trimmed = String(value).trim();
        if (trimmed !== '') payload[key] = trimmed;
    }
    return payload;
}

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
