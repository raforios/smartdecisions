/**
 * Registro de Participante.
 * POST /v1/mining-summit/participants
 *
 * El rol pertenece a la persona: se elige en el formulario (ya no se deriva de
 * la institución). Si se envía un eje y el rol no es "Sin rol", el backend
 * asienta al participante en un eje y mesa estables. Tras registrar se muestra
 * la credencial/sticker con QR (codifica el CI para el marcado de asistencia).
 */
import { Toast } from '../components/Toast.js';
import { renderQr, printCredential } from '../components/Credential.js?v=20260722c';
import { loadAvailability, buildAxisOptions, renderAvailabilityHint } from '../components/AxisPicker.js';
import { enhanceSelect } from '../components/SearchableSelect.js?v=20260722c';

// Roles de participante (value = código del backend, label = etiqueta en español).
// "Sin rol" (value vacío) registra a la persona sin aula hasta asignarle un rol.
const ROLE_OPTIONS = [
    ['', '— Sin rol (registrado sin aula) —'],
    ['PARTICIPANTE', 'Participante'],
    ['MODERADOR', 'Moderador'],
    ['VEEDOR', 'Veedor'],
    ['INVITADO', 'Invitado'],
    ['ORGANIZADOR', 'Organizador'],
    ['PRENSA', 'Prensa'],
    ['FACILITADOR', 'Facilitador'],
    ['SISTEMATIZADOR', 'Sistematizador'],
    ['COMUNICACION', 'Comunicación'],
    ['SISTEMAS', 'Sistemas']
].map(([value, label]) => `<option value="${value}">${label}</option>`).join('');

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
                            <input id="ci" name="ci" type="text" required minlength="4" maxlength="20" inputmode="text" pattern="[A-Za-z0-9\-]+" placeholder="Ej. 1234567 o 1234567-1A">
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
                        </div>
                        <div class="form-field form-field-wide">
                            <label for="role">Rol</label>
                            <select id="role" name="role">
                                ${ROLE_OPTIONS}
                            </select>
                            <div class="role-hint">El rol define su función; "Sin rol" queda registrado sin aula.</div>
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
                        <div class="form-field form-field-wide">
                            <label for="axis">Eje temático</label>
                            <select id="axis" name="axis">
                                <option value="">— Cargando disponibilidad… —</option>
                            </select>
                            <div id="axis-availability"></div>
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
        const axisSelect = container.querySelector('#axis');
        const axisHint = container.querySelector('#axis-availability');
        const resultBox = container.querySelector('#registro-result');

        await loadInstitutions(api, config, institutionSelect);

        async function refreshAvailability() {
            const availability = await loadAvailability(api, config);
            axisSelect.innerHTML = buildAxisOptions(availability, axisSelect.value);
            renderAvailabilityHint(axisHint, availability);
            return availability;
        }
        await refreshAvailability();

        // Combos con buscador (institución, eje, rol, departamento).
        enhanceSelect(institutionSelect, 'Buscar institución…');
        enhanceSelect(axisSelect, 'Buscar eje…');
        enhanceSelect(container.querySelector('#role'), 'Buscar rol…');
        enhanceSelect(container.querySelector('#department'), 'Buscar departamento…');

        resetBtn.addEventListener('click', () => {
            form.reset();
            refreshAvailability();
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
                await refreshAvailability();
            } catch (error) {
                Toast.danger(`No se pudo registrar: ${error.message}`);
                // The chosen axis may have just filled up; refresh and surface the
                // aulas/ejes that still have room.
                const availability = await refreshAvailability();
                renderAvailabilityHint(axisHint, availability, payload.axis);
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
                    <i class="fa-solid fa-download"></i> Descargar sticker (PNG)
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
