'use strict';

/**
 * Mi cuenta — the signed-in user's data and the change of their own password.
 * AUTH answers a refusal with a code; the wording lives here.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { API_URL } = window.SD_CONFIG;
    const { qs, qsAll, toast, setButtonBusy, revealToggle } = window.SD_UI;

    const ROLES = { MANAGER: 'Gerente', REQUESTER: 'Consulta', ADMIN: 'Administrador', SELLER: 'Vendedor' };
    const ERRORS = {
        WRONG_PASSWORD: 'La contraseña actual no es correcta.',
        SAME_PASSWORD: 'La contraseña nueva tiene que ser distinta de la actual.'
    };
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const moment = (iso) => (iso ? new Date(iso).toLocaleString('es-BO',
        { dateStyle: 'long', timeStyle: 'short' }) : 'Sin registro aún');

    async function load() {
        const profile = await window.SD_API.get(`${API_URL}/v1/users/me`).catch(() => null);
        if (!profile) {
            qs('#accountData').innerHTML = '<p class="sd-empty">No se pudieron leer tus datos.</p>';
            return;
        }
        qs('#accountData').innerHTML = [
            ['Nombre', `${profile.first_name} ${profile.last_name}`],
            ['Correo', profile.email],
            ['Rol', ROLES[profile.role] || profile.role],
            ['Empresa', profile.client || '—'],
            ['Esta sesión', moment(profile.last_login)],
            ['Sesión anterior', moment(profile.previous_login)],
            ['Sesiones registradas', String(profile.login_count || 0)]
        ].map(([label, value]) => `<div class="sd-list-row"><span>${label}</span>` +
            `<b>${escape(value)}</b></div>`).join('');
    }

    // An eye on each field, to check what was typed before changing it.
    const hideAll = qsAll('#passwordForm [data-reveal]').map((button) =>
        revealToggle(button.previousElementSibling, button));

    function say(text, kind) {
        const note = qs('#passwordNote');
        note.className = `form-note${kind ? ` ${kind}` : ''}`;
        note.textContent = text;
    }

    qs('#passwordForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        const current = qs('#passwordCurrent').value;
        const fresh = qs('#passwordNew').value;
        if (!current || fresh.length < 8) {
            say('Escribe la contraseña actual y una nueva de 8 caracteres o más.', 'error');
            return;
        }
        if (fresh !== qs('#passwordRepeat').value) {
            say('La contraseña nueva no coincide con la repetida.', 'error');
            return;
        }
        const done = setButtonBusy(qs('#passwordSave'), 'Cambiando…');
        try {
            await window.SD_API.post(`${API_URL}/v1/users/me/password`,
                { current_password: current, new_password: fresh });
            qs('#passwordForm').reset();
            hideAll.forEach((hide) => hide());
            say('Contraseña cambiada. La usarás desde tu próxima sesión.', 'success');
            toast('Contraseña cambiada.', 'success');
        } catch (error) {
            say(ERRORS[error.code] || error.message || 'No se pudo cambiar la contraseña.', 'error');
        } finally {
            done();
        }
    });

    load();
});
