/**
 * Header (top bar) for the operator dashboard.
 * Reusable across pages; reads parametric branding from config.event.
 */
export class Header {
    static render(config, currentUser) {
        const event = config.event;
        return `
            <div class="topbar-left">
                <button id="menu-toggle" class="icon-btn menu-toggle" title="Menú" aria-label="Menú">
                    <i class="fa-solid fa-bars"></i>
                </button>
                <div class="topbar-brand">
                    <img src="${event.logo}" alt="Logo">
                    <div class="brand-text">
                        <span class="brand-short">${event.shortName}</span>
                        <span class="brand-long">${event.longName}</span>
                    </div>
                </div>
            </div>
            <div class="topbar-actions">
                <span class="topbar-user" title="Operador autenticado">
                    <i class="fa-solid fa-user-shield"></i>
                    <span class="user-email">${currentUser || 'operador'}</span>
                </span>
                <button id="theme-toggle" class="icon-btn" title="Cambiar tema">
                    <i class="fa-solid fa-moon"></i>
                </button>
                <button id="logout-btn" class="icon-btn" title="Cerrar sesión">
                    <i class="fa-solid fa-right-from-bracket"></i>
                </button>
            </div>
        `;
    }

    static initInteractions({ onLogout }) {
        const themeBtn = document.getElementById('theme-toggle');
        if (themeBtn) {
            const saved = localStorage.getItem('cumbre_theme') || 'light';
            document.documentElement.setAttribute('data-theme', saved);
            themeBtn.innerHTML = saved === 'dark'
                ? '<i class="fa-solid fa-sun"></i>'
                : '<i class="fa-solid fa-moon"></i>';
            themeBtn.addEventListener('click', () => {
                const next = document.documentElement.getAttribute('data-theme') === 'dark'
                    ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem('cumbre_theme', next);
                themeBtn.innerHTML = next === 'dark'
                    ? '<i class="fa-solid fa-sun"></i>'
                    : '<i class="fa-solid fa-moon"></i>';
            });
        }

        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn && onLogout) {
            logoutBtn.addEventListener('click', () => onLogout());
        }
    }
}
