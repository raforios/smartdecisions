'use strict';

/**
 * Administración — the users of the platform, of every company (ADMIN only).
 *
 * AUTH already has the whole CRUD: the list, the sign-up, the edit and the
 * delete. Its sign-up creates a REQUESTER without a company, so creating a
 * user is two calls: the sign-up, then the edit that sets role and company.
 * A company is the `client` every service keys its data by.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated() || !window.SD_CONFIG.API_URL) return;
    const { qs, toast, setButtonBusy, revealToggle } = window.SD_UI;
    const icon = window.SD_ICONS.svg;
    const API = window.SD_API;
    const USERS = `${window.SD_CONFIG.API_URL}/v1/users`;
    const SIGNUP = `${window.SD_CONFIG.API_URL}/v1/auth/signup`;
    const SELF = window.SD_AUTH.getEmail();
    const NEW_COMPANY = '__new__';

    // The roles SmartDecisions hands out; any other one is shown as it is.
    const ROLES = { MANAGER: 'Gerente', REQUESTER: 'Consulta', SELLER: 'Vendedor', ADMIN: 'Administrador' };
    const roleLabel = (code) => ROLES[code] || code;
    const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const when = (iso) => {
        if (!iso) return 'Sin registro aún';
        const moment = new Date(iso);
        const time = moment.toLocaleTimeString('es-BO', { hour: '2-digit', minute: '2-digit' });
        return `${moment.getDate()} ${MONTHS[moment.getMonth()]} ${moment.getFullYear()}, ${time}`;
    };
    const escape = (text) => String(text == null ? '' : text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');

    const state = { users: [], editing: null, formCompanies: null, fromTable: false };
    // The eye beside the password, as in the sign-in; it hides again on every open.
    const hidePassword = revealToggle(qs('#userPassword'), qs('#userPasswordReveal'));
    const note = (text, kind) => {
        const element = qs('#usersNote');
        element.className = `form-note${kind ? ` ${kind}` : ''}`;
        element.textContent = text || '';
    };
    const companies = () => [...new Set(state.users.map((user) => user.client).filter(Boolean))]
        .sort((left, right) => left.localeCompare(right));

    /** What AUTH answered, in words: it sends English sentences, not codes. */
    function failure(error, fallback) {
        const code = error && (error.code || error.message);
        if (code === 'COMPANY_NOT_FOUND') return 'Esa empresa no existe: créala en Empresas.';
        if (code === 'COMPANY_INACTIVE') return 'Esa empresa está inactiva.';
        if (error && error.status === 409) return 'Ese correo ya está registrado.';
        if (error && error.status === 404) return 'El usuario ya no existe.';
        if (error && error.status === 422) return 'Revisa los datos: nombre y apellido de 3 a 30 letras, contraseña de 8 o más.';
        if (error && error.status === 403) return 'Sólo el Administrador administra los usuarios.';
        return fallback;
    }

    /**
     * The companies a user may be given: the active ones of AUTH's table
     * (Rafael, 21-oct). Until AUTH serves them, the clients users already
     * have, and a new one may still be typed.
     */
    async function loadCompanies() {
        try {
            const list = await API.get(`${window.SD_CONFIG.API_URL}/v1/auth/companies`);
            state.formCompanies = list.filter((company) => company.active).map((company) => company.name);
            state.fromTable = true;
        } catch (error) {
            state.formCompanies = null;
            state.fromTable = false;
        }
    }

    async function load() {
        try {
            [state.users] = await Promise.all([API.get(`${USERS}/`), loadCompanies()]);
            fillCompanyFilter();
            // The form offers the existing companies: it opens once they are known.
            qs('#userNew').disabled = false;
            paint();
            note('');
        } catch (error) {
            note(failure(error, 'No se pudieron leer los usuarios.'), 'error');
        }
    }

    function fillCompanyFilter() {
        const select = qs('#usersCompany');
        const chosen = select.value;
        select.innerHTML = '<option value="">Todas</option>' +
            companies().map((name) => `<option>${escape(name)}</option>`).join('') +
            '<option value="-">Sin empresa</option>';
        select.value = chosen;
    }

    function visible() {
        const text = qs('#usersSearch').value.trim().toLowerCase();
        const company = qs('#usersCompany').value;
        return state.users
            .filter((user) => !company || (company === '-' ? !user.client : user.client === company))
            .filter((user) => !text || `${user.first_name} ${user.last_name} ${user.email}`
                .toLowerCase().includes(text))
            .sort((left, right) => (left.client || '').localeCompare(right.client || '') ||
                roleLabel(left.role).localeCompare(roleLabel(right.role)) ||
                left.email.localeCompare(right.email));
    }

    /** Every matching user; the common pager (js/ui.js) shows ten at a time. */
    function paint() {
        const rows = visible();
        qs('#usersCount').textContent =
            `${rows.length} de ${state.users.length} usuarios; ${companies().length} empresas.`;
        const tbody = qs('#usersTable tbody');
        tbody.innerHTML = rows.map((user) => `
            <tr>
                <td>${escape(user.client || 'Sin empresa')}</td>
                <td><b>${escape(`${user.first_name} ${user.last_name}`)}</b><br>${escape(user.email)}</td>
                <td>${escape(roleLabel(user.role))}</td>
                <td>${when(user.last_login)}</td>
                <td><span class="sd-status ${user.status ? 'is-on' : 'is-off'}">
                    ${user.status ? 'Activo' : 'Inactivo'}</span></td>
                <td class="row-actions">
                    <button type="button" class="btn-icon" data-tip="Editar" aria-label="Editar"
                            data-edit="${escape(user.email)}">${icon('edit')}</button>
                    ${user.email === SELF ? '' : `<button type="button" class="btn-icon is-delete" data-tip="Eliminar"
                            aria-label="Eliminar" data-delete="${escape(user.email)}">${icon('trash')}</button>`}
                </td>
            </tr>`).join('');
    }

    /** The form, empty for a new user or filled with the one being edited. */
    function openForm(user) {
        state.editing = user || null;
        const creating = !user;
        qs('#userFormTitle').textContent = creating ? 'Nuevo usuario' : `Editar ${user.email}`;
        qs('#userEmailField').hidden = !creating;
        qs('#userEmail').value = '';
        qs('#userFirstName').value = creating ? '' : user.first_name;
        qs('#userLastName').value = creating ? '' : user.last_name;
        qs('#userPassword').value = '';
        hidePassword();
        qs('#userPasswordLabel').textContent = creating
            ? 'Contraseña inicial (8 o más caracteres)'
            : 'Contraseña nueva (déjala vacía para no cambiarla)';
        // Nobody switches their own account off from here.
        qs('#userStatusField').hidden = creating || user.email === SELF;
        qs('#userStatus').value = creating ? 'true' : String(user.status);

        const roles = Object.keys(ROLES);
        if (user && !roles.includes(user.role)) roles.push(user.role);
        qs('#userRole').innerHTML = roles.map((code) =>
            `<option value="${code}">${escape(roleLabel(code))}</option>`).join('');
        qs('#userRole').value = creating ? 'MANAGER' : user.role;

        const offered = state.fromTable ? state.formCompanies.slice() : companies();
        if (user && user.client && !offered.includes(user.client)) offered.push(user.client);
        qs('#userCompany').innerHTML = offered.map((name) =>
            `<option>${escape(name)}</option>`).join('') +
            (state.fromTable ? '' : `<option value="${NEW_COMPANY}">Otra empresa…</option>`);
        qs('#userCompany').value = (user && user.client) || (offered[0] ? offered[0] : NEW_COMPANY);
        qs('#userNewCompany').value = '';
        syncCompany();

        qs('#userForm').hidden = false;
        qs(creating ? '#userEmail' : '#userFirstName').focus();
    }

    /** The ADMIN runs the platform and has no company; the rest belong to one. */
    function syncCompany() {
        const admin = qs('#userRole').value === 'ADMIN';
        qs('#userCompanyField').hidden = admin;
        qs('#userNewCompanyField').hidden = admin || qs('#userCompany').value !== NEW_COMPANY;
    }

    function closeForm() {
        state.editing = null;
        qs('#userForm').hidden = true;
        qs('#usersTable').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /** The fields AUTH's edit takes, and only those that say something. */
    function changes() {
        const role = qs('#userRole').value;
        const body = {
            first_name: qs('#userFirstName').value.trim(),
            last_name: qs('#userLastName').value.trim(),
            role
        };
        if (role !== 'ADMIN') {
            const picked = qs('#userCompany').value;
            body.client = picked === NEW_COMPANY ? qs('#userNewCompany').value.trim() : picked;
        }
        const password = qs('#userPassword').value;
        if (password) body.password = password;
        if (state.editing && state.editing.email !== SELF) body.status = qs('#userStatus').value === 'true';
        return body;
    }

    /** What the browser can tell before asking AUTH. */
    function invalid(body, creating) {
        if (creating && !qs('#userEmail').checkValidity()) return 'Escribe un correo válido.';
        if (creating && !qs('#userEmail').value.trim()) return 'Escribe el correo.';
        if (body.first_name.length < 3 || body.last_name.length < 3) return 'Nombre y apellido, de 3 letras o más.';
        if (body.role !== 'ADMIN' && (!body.client || body.client.length < 3)) return 'Elige o escribe la empresa.';
        if (creating && !body.password) return 'Escribe la contraseña inicial.';
        if (body.password && body.password.length < 8) return 'La contraseña lleva 8 caracteres o más.';
        return null;
    }

    async function save(button) {
        const creating = !state.editing;
        const body = changes();
        const problem = invalid(body, creating);
        if (problem) { note(problem, 'error'); return; }
        const done = setButtonBusy(button, 'Guardando…');
        const email = creating ? qs('#userEmail').value.trim().toLowerCase() : state.editing.email;
        try {
            if (creating) {
                await API.post(SIGNUP, { email, first_name: body.first_name,
                    last_name: body.last_name, password: body.password });
                delete body.password;
            }
            try {
                await API.patch(`${USERS}/${encodeURIComponent(email)}`, body);
            } catch (error) {
                // The account exists already: say what is missing instead of hiding it.
                if (creating) {
                    note(`${email} se creó, pero sin su rol ni su empresa: edítalo para asignarlos.`, 'error');
                    closeForm();
                    await load();
                    return;
                }
                throw error;
            }
            toast(creating ? `Usuario ${email} creado.` : `Usuario ${email} actualizado.`, 'success');
            closeForm();
            await load();
        } catch (error) {
            note(failure(error, 'No se pudo guardar el usuario.'), 'error');
        } finally {
            done();
        }
    }

    /** First click asks, the second deletes: no browser dialogs in the portal. */
    async function remove(button) {
        const email = button.dataset.delete;
        if (button.dataset.confirm !== '1') {
            button.dataset.confirm = '1';
            button.dataset.tip = 'Confirmar eliminación';
            button.setAttribute('aria-label', 'Confirmar eliminación');
            button.classList.add('is-danger');
            note(`Eliminar ${email} no se puede deshacer; para quitarle el acceso sin borrarlo, edítalo y déjalo inactivo.`);
            return;
        }
        const done = setButtonBusy(button);
        try {
            await API.del(`${USERS}/${encodeURIComponent(email)}`);
            toast(`Usuario ${email} eliminado.`, 'success');
            note('');
            await load();
        } catch (error) {
            note(failure(error, 'No se pudo eliminar el usuario.'), 'error');
            done();
        }
    }

    qs('#usersSearch').addEventListener('input', () => paint());
    qs('#usersCompany').addEventListener('change', () => paint());
    qs('#userNew').addEventListener('click', () => { note(''); openForm(null); });
    qs('#userRole').addEventListener('change', syncCompany);
    qs('#userCompany').addEventListener('change', syncCompany);
    qs('#userCancel').addEventListener('click', closeForm);
    qs('#userSave').addEventListener('click', (event) => save(event.currentTarget));
    qs('#usersTable').addEventListener('click', (event) => {
        const edit = event.target.closest('[data-edit]');
        if (edit) {
            note('');
            openForm(state.users.find((user) => user.email === edit.dataset.edit));
            return;
        }
        const del = event.target.closest('[data-delete]');
        if (del) remove(del);
    });

    load();
});
