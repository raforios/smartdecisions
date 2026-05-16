export class Header {
    static render(data) {
        const menuHtml = data.menuPrincipal.map(m => `<li><a href="${m.url}">${m.titulo}</a></li>`).join('');
        // Inicialmente vacío — Ticker.js lo poblará desde el endpoint público.
        // Mientras la API responde, mostramos un skeleton tenue.
        const tickerPlaceholder = `<div class="ticker-item is-fallback"><span>Cargando cotizaciones…</span></div>`;

        return `
            <nav class="navbar">
                <div class="nav-container">
                    <div class="brand">
                        <img src="${data.institucion.logo}" alt="Escudo" class="escudo-img">
                        <div class="logo-text">
                            <span class="logo-min">${data.institucion.nombreCorto}</span>
                            <span class="logo-main">${data.institucion.nombreLargo}</span>
                        </div>
                    </div>

                    <div class="hamburger" id="mobile-menu-btn">
                        <span></span><span></span><span></span>
                    </div>

                    <ul class="nav-links" id="nav-links-container">
                        ${menuHtml}
                        <li><a href="#" class="btn-bi">Portal BI</a></li>
                        <li><button id="theme-toggle" class="theme-btn">🌙</button></li>
                    </ul>
                </div>
            </nav>
            <div class="ticker-wrap">
                <div class="ticker" id="mineral-ticker">${tickerPlaceholder}</div>
                <a href="mercados.html" class="mercados-btn"><i class="fa-solid fa-chart-line" style="margin-right: 8px;"></i> Ver detalle</a>
            </div>
        `;
    }

    static initInteractions() {
        const hamburger = document.getElementById('mobile-menu-btn');
        const navLinks = document.getElementById('nav-links-container');

        if (hamburger && navLinks) {
            hamburger.addEventListener('click', () => {
                hamburger.classList.toggle('active');
                navLinks.classList.toggle('active');
            });
        }
    }
}
