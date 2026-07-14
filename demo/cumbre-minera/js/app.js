/**
 * app.js
 *
 * Bootstrap of the operator dashboard. Coordinates configuration, auth guard,
 * shell rendering and hash-based routing into the per-section page modules.
 */
import { ConfigService } from './services/ConfigService.js';
import { AuthService }   from './services/AuthService.js';
import { ApiService }    from './services/ApiService.js';
import { Header }        from './components/Header.js';
import { Sidebar }       from './components/Sidebar.js';
import { Footer }        from './components/Footer.js';
import { Toast }         from './components/Toast.js';

import { RegistroPage }     from './pages/registro.js';
import { AsistenciaPage }   from './pages/asistencia.js';
import { ReportesPage }     from './pages/reportes.js';
import { AsistenciasPage }  from './pages/asistencias.js';
import { EstadisticasPage } from './pages/estadisticas.js';
import { AdminInstitucionesPage } from './pages/admin-instituciones.js';
import { AdminAulasPage }         from './pages/admin-aulas.js';

const PAGE_FACTORIES = {
    registro:               RegistroPage,
    asistencia:             AsistenciaPage,
    reportes:               ReportesPage,
    asistencias:            AsistenciasPage,
    estadisticas:           EstadisticasPage,
    'admin-instituciones':  AdminInstitucionesPage,
    'admin-aulas':          AdminAulasPage
};

(async function bootstrap() {
    let config;
    try {
        config = await ConfigService.load();
    } catch (error) {
        document.getElementById('main-content').innerHTML =
            `<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i>
             <p>Error cargando configuración: ${error.message}</p></div>`;
        return;
    }

    Toast.configure({ timeoutMs: config.ui.toastTimeoutMs });

    const auth = new AuthService(config);
    auth.requireAuth(config.auth.loginPath);

    const api = new ApiService(
        config.endpoints.miningSummit,
        auth,
        () => window.location.replace(config.auth.loginPath)
    );

    document.title = `${config.event.fullName} | Panel de Operador`;

    // The access role (from the JWT) drives which sections are available.
    const role = auth.getUserRole();
    const allowedModules = Sidebar.allowedItems(config, role).map(item => item.module);
    const defaultModule = allowedModules[0] || config.menu[0].module;

    // Render shell
    document.getElementById('topbar').innerHTML = Header.render(config, auth.getUserEmail());
    document.getElementById('sidebar').innerHTML = Sidebar.render(config, role);
    document.getElementById('footer-container').innerHTML = Footer.render(config);

    Header.initInteractions({
        onLogout: () => {
            auth.logout();
            window.location.replace(config.auth.loginPath);
        }
    });
    const sidebarEl = document.getElementById('sidebar');
    const menuToggle = document.getElementById('menu-toggle');
    const sidebarBackdrop = document.getElementById('sidebar-backdrop');
    const closeSidebar = () => {
        sidebarEl.classList.remove('open');
        sidebarBackdrop.classList.remove('show');
    };
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebarEl.classList.toggle('open');
            sidebarBackdrop.classList.toggle('show');
        });
    }
    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', closeSidebar);
    }

    Sidebar.initInteractions({
        onSelect: ({ module }) => {
            window.location.hash = module;
            closeSidebar();
        }
    });

    const ctx = { config, api, auth };

    function navigateToHash() {
        let requested = window.location.hash.replace('#', '') || defaultModule;
        // Enforce role-based access: silently fall back to the first allowed
        // section if the hash points to a module the role cannot use.
        if (!allowedModules.includes(requested)) {
            requested = defaultModule;
            window.location.hash = requested;
        }
        const Page = PAGE_FACTORIES[requested];
        const main = document.getElementById('main-content');
        if (!Page) {
            main.innerHTML = `<div class="empty-state">
                <i class="fa-solid fa-circle-question"></i>
                <p>Sección desconocida: ${requested}</p></div>`;
            return;
        }
        Sidebar.setActive(requested);
        main.innerHTML = '<div class="loading"><div class="spinner"></div> Cargando...</div>';
        try {
            Page.render(main, ctx);
        } catch (error) {
            main.innerHTML = `<div class="empty-state">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>Error renderizando la sección: ${error.message}</p></div>`;
        }
    }

    window.addEventListener('hashchange', navigateToHash);
    navigateToHash();
})();
