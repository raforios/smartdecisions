/**
 * Registro de Participante.
 * POST /v1/mining-summit/participants
 * El backend registra automáticamente la primera asistencia del día.
 */
import { Toast } from '../components/Toast.js';

export const RegistroPage = {
    render(container, { config, api }) {
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
                        <div class="form-field">
                            <label for="email">Correo electrónico</label>
                            <input id="email" name="email" type="email" maxlength="120">
                        </div>
                        <div class="form-field">
                            <label for="phone">Celular</label>
                            <input id="phone" name="phone" type="tel" maxlength="30">
                        </div>
                        <div class="form-field">
                            <label for="department">Departamento de Procedencia</label>
                            <select id="department" name="department">
                                <option value="">— Seleccionar —</option>
                                ${departamentos}
                            </select>
                        </div>
                        <div class="form-field">
                            <label for="company">Empresa</label>
                            <input id="company" name="company" type="text" maxlength="120">
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
        `;

        const form = container.querySelector('#registro-form');
        const submitBtn = container.querySelector('#submit-btn');
        const resetBtn = container.querySelector('#reset-btn');

        resetBtn.addEventListener('click', () => form.reset());

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
                const saved = await api.post(
                    config.miningSummit.participantsPath,
                    payload
                );
                Toast.success(
                    `Participante registrado: ${saved.first_name} ${saved.last_name} (CI ${saved.ci}).`
                );
                form.reset();
            } catch (error) {
                Toast.danger(`No se pudo registrar: ${error.message}`);
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = original;
            }
        });
    }
};

function readFormPayload(form) {
    const data = new FormData(form);
    const payload = {};
    for (const [key, value] of data.entries()) {
        const trimmed = String(value).trim();
        if (trimmed !== '') payload[key] = trimmed;
    }
    return payload;
}
