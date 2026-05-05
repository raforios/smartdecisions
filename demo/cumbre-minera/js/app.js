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

const PAGE_FACTORIES = {
    registro:     RegistroPage,
    asistencia:   AsistenciaPage,
    reportes:     ReportesPage,
    asistencias:  AsistenciasPage,
    estadisticas: EstadisticasPage
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

    // Render shell
    document.getElementById('topbar').innerHTML = Header.render(config, auth.getUserEmail());
    document.getElementById('sidebar').innerHTML = Sidebar.render(config);
    document.getElementById('footer-container').innerHTML = Footer.render(config);

    Header.initInteractions({
        onLogout: () => {
            auth.logout();
            window.location.replace(config.auth.loginPath);
        }
    });
    Sidebar.initInteractions({
        onSelect: ({ module }) => {
            window.location.hash = module;
        }
    });

    const ctx = { config, api, auth };

    function navigateToHash() {
        const requested = window.location.hash.replace('#', '') || config.menu[0].module;
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
