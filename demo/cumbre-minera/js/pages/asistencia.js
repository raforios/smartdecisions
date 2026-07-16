/**
 * Registro de Asistencia (check-in por CI).
 *
 * Flujo:
 *   1. El operador escribe el CI y pulsa "Registrar asistencia".
 *   2. POST /v1/mining-summit/attendances con { ci }.
 *   3. Si el backend responde 400 indicando que el participante no existe y
 *      pide first_name/last_name, expandimos el formulario para captura
 *      "on-the-fly" y reintentamos.
 *   4. Si ya marcó hoy (409), informamos.
 */
import { Toast } from '../components/Toast.js';

export const AsistenciaPage = {
    render(container, { config, api }) {
        const departamentos = (config.departments || []).map(
            d => `<option value="${d}">${d}</option>`
        ).join('');

        container.innerHTML = `
            <div class="page-header">
                <div>
                    <h2>Registro de Asistencia</h2>
                    <div class="subtitle">Marca asistencia diaria por CI. Si no está registrado, se crea on-the-fly.</div>
                </div>
            </div>

            <div class="card">
                <h3><i class="fa-solid fa-clipboard-check" style="color:var(--oro)"></i> Check-in por CI</h3>
                <form id="asistencia-form">
                    <div class="form-grid">
                        <div class="form-field">
                            <label for="ci">Carnet de Identidad <span class="req">*</span></label>
                            <input id="ci" name="ci" type="text" required minlength="4" maxlength="20" inputmode="numeric" pattern="[0-9]+" placeholder="Ej. 1234567" autofocus>
                        </div>
                    </div>

                    <div id="qr-reader-wrap" class="qr-scan" hidden>
                        <div id="qr-reader"></div>
                        <button id="scan-close" class="btn btn-ghost" type="button">
                            <i class="fa-solid fa-xmark"></i> Cerrar cámara
                        </button>
                    </div>

                    <div id="onthefly" style="display:none; margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed var(--border);">
                        <div class="chip danger" style="margin-bottom: 0.75rem;">
                            <i class="fa-solid fa-circle-info"></i> Participante no registrado — completa los datos para crearlo.
                        </div>
                        <div class="form-grid">
                            <div class="form-field">
                                <label for="first_name">Nombre <span class="req">*</span></label>
                                <input id="first_name" name="first_name" type="text" maxlength="80">
                            </div>
                            <div class="form-field">
                                <label for="last_name">Apellido <span class="req">*</span></label>
                                <input id="last_name" name="last_name" type="text" maxlength="80">
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
                    </div>

                    <div class="form-actions">
                        <button id="submit-btn" class="btn btn-primary" type="submit">
                            <i class="fa-solid fa-check"></i> Registrar asistencia
                        </button>
                        <button id="scan-btn" class="btn btn-ghost" type="button">
                            <i class="fa-solid fa-qrcode"></i> Escanear QR
                        </button>
                        <button id="reset-btn" class="btn btn-ghost" type="button">
                            <i class="fa-solid fa-rotate-left"></i> Limpiar
                        </button>
                    </div>
                </form>

                <div id="last-result" style="margin-top: 1.25rem;"></div>
            </div>
        `;

        const form = container.querySelector('#asistencia-form');
        const onthefly = container.querySelector('#onthefly');
        const submitBtn = container.querySelector('#submit-btn');
        const resetBtn = container.querySelector('#reset-btn');
        const result = container.querySelector('#last-result');
        const ciInput = container.querySelector('#ci');
        const scanBtn = container.querySelector('#scan-btn');
        const readerWrap = container.querySelector('#qr-reader-wrap');
        const scanClose = container.querySelector('#scan-close');
        let qrScanner = null;

        async function stopScan() {
            readerWrap.hidden = true;
            if (!qrScanner) return;
            try { await qrScanner.stop(); qrScanner.clear(); } catch (_) { /* already stopped */ }
            qrScanner = null;
        }

        async function startScan() {
            if (typeof Html5Qrcode === 'undefined') {
                Toast.danger('El lector de QR no está disponible.');
                return;
            }
            readerWrap.hidden = false;
            qrScanner = new Html5Qrcode('qr-reader');
            try {
                await qrScanner.start(
                    { facingMode: 'environment' },
                    { fps: 10, qrbox: 220 },
                    async (decodedText) => {
                        await stopScan();
                        ciInput.value = extractCi(decodedText);
                        Toast.info(`QR leído: CI ${ciInput.value}. Marcando asistencia…`);
                        form.requestSubmit();
                    },
                    () => { /* ignore per-frame decode errors */ }
                );
            } catch (error) {
                Toast.danger(`No se pudo abrir la cámara: ${error}`);
                await stopScan();
            }
        }

        scanBtn.addEventListener('click', startScan);
        scanClose.addEventListener('click', stopScan);

        resetBtn.addEventListener('click', () => {
            form.reset();
            onthefly.style.display = 'none';
            result.innerHTML = '';
            stopScan();
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = readFormPayload(form, onthefly);
            if (!payload.ci) {
                Toast.danger('El CI es obligatorio.');
                return;
            }
            submitBtn.disabled = true;
            const original = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Marcando...';
            try {
                const saved = await api.post(
                    config.miningSummit.attendancesPath,
                    payload
                );
                Toast.success(`Asistencia registrada para CI ${saved.ci} el ${saved.attendance_date}.`);
                renderResult(result, saved);
                form.reset();
                onthefly.style.display = 'none';
            } catch (error) {
                if (error.status === 400 && /first_name and last_name/i.test(error.message)) {
                    onthefly.style.display = 'block';
                    Toast.info('Participante no registrado. Completa nombre y apellido para crearlo.');
                } else if (error.status === 409) {
                    Toast.info('Este CI ya tiene asistencia marcada hoy.');
                } else {
                    Toast.danger(`No se pudo marcar: ${error.message}`);
                }
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = original;
            }
        });
    }
};

/**
 * Extracts the CI from a scanned QR. The credential QR now encodes a JSON
 * object with the full participant data; older/plain QRs encode just the CI.
 * Either way we only need the CI to mark attendance.
 */
function extractCi(decodedText) {
    const raw = String(decodedText).trim();
    try {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.ci) return String(parsed.ci).trim();
    } catch (_) { /* not JSON: treat as a plain CI */ }
    return raw;
}

function readFormPayload(form, ontheflyEl) {
    const data = new FormData(form);
    const payload = {};
    const ontheflyVisible = ontheflyEl.style.display !== 'none';
    for (const [key, value] of data.entries()) {
        // Si el bloque on-the-fly no está visible, ignoramos sus campos vacíos.
        const isOnTheFlyField = ['first_name','last_name','email','phone','department'].includes(key);
        if (isOnTheFlyField && !ontheflyVisible) continue;
        const trimmed = String(value).trim();
        if (trimmed !== '') payload[key] = trimmed;
    }
    return payload;
}

function renderResult(container, attendance) {
    const created = attendance.participant_created
        ? '<span class="chip success">Participante creado on-the-fly</span>'
        : '<span class="chip">Participante existente</span>';
    container.innerHTML = `
        <div class="card" style="margin-bottom:0; border-top-color: var(--success);">
            <h3><i class="fa-solid fa-circle-check" style="color: var(--success)"></i> Asistencia confirmada</h3>
            <p><strong>CI:</strong> ${attendance.ci}</p>
            <p><strong>Fecha:</strong> ${attendance.attendance_date}</p>
            <p><strong>Hora:</strong> ${formatDateTime(attendance.attendance_at)}</p>
            <p><strong>Marcada por:</strong> ${attendance.marked_by}</p>
            <p>${created}</p>
        </div>
    `;
}

function formatDateTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-BO', { dateStyle: 'medium', timeStyle: 'short' });
}
