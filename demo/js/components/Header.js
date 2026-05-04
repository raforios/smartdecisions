export class Header {
    static render(data) {
        const menuHtml = data.menuPrincipal.map(m => `<li><a href="${m.url}">${m.titulo}</a></li>`).join('');
        const tickerHtml = data.tickerPrecios.map(p => `<div class="ticker-item"><span>${p.name}</span><span>$${p.price}</span><span class="${p.status}">${p.trend} ${p.status === 'up' ? '▲' : '▼'}</span></div>`).join('');

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
                <div class="ticker" id="mineral-ticker">${tickerHtml}${tickerHtml}</div>
                <a href="mercados.html" class="mercados-btn"><i class="fa-solid fa-chart-line" style="margin-right: 8px;"></i> Bolsa de Londres (LME)</a>
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
