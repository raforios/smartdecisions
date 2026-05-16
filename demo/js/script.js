/**
 * MINISTERIO DE MINERÍA Y METALURGIA - ARQUITECTURA CMS (VANILLA JS - SINGLE FILE)
 */

// ==========================================
// 1. SIMULACIÓN DE BASE DE DATOS (JSON INTERNO)
// ==========================================
const apiData = {
    institucion: {
        nombreCorto: "MINISTERIO DE",
        nombreLargo: "MINERÍA Y METALURGIA",
        logo: "img/cropped-escudo.png"
    },
    menu: [
        { titulo: "Inicio", url: "index.html" },
        { titulo: "Ministerio", url: "institucional.html" },
        { titulo: "Documentación", url: "documentacion.html" }
    ],
    redes: [
        { nombre: "LinkedIn", icono: "fa-brands fa-linkedin", url: "https://www.linkedin.com/company/ministerio-de-minería-y-metalurgia-de-bolivia/posts/?feedView=all" },
        { nombre: "YouTube", icono: "fa-brands fa-youtube", url: "https://www.youtube.com/channel/UC3avDHxuYOiv56hspVueXrg" },
        { nombre: "Instagram", icono: "fa-brands fa-instagram", url: "https://www.instagram.com/ministeriodemineriabolivia/" },
        { nombre: "TikTok", icono: "fa-brands fa-tiktok", url: "https://www.tiktok.com/@ministeriodemineria" },
        { nombre: "X", svg: true, url: "https://x.com/minmineriabo" },
        { nombre: "Facebook", icono: "fa-brands fa-facebook", url: "https://www.facebook.com/minmineriabol" }
    ],
    cotizaciones: [
        { name: "ORO", price: "2,150.40", trend: "+1.2%", status: "up" },
        { name: "PLATA", price: "24.30", trend: "-0.5%", status: "down" },
        { name: "ESTAÑO", price: "27,450.00", trend: "+0.8%", status: "up" },
        { name: "ZINC", price: "2,540.00", trend: "+2.1%", status: "up" },
        { name: "LITIO (LCE)", price: "13,500.00", trend: "-1.4%", status: "down" },
        { name: "HIERRO", price: "915.00", trend: "+0.5%", status: "up" }
    ],
    // NUEVO: Información de Contacto Global
    contacto: {
        oficinaCentral: "Av. Mariscal Santa Cruz, Edificio Centro de Comunicaciones Piso 14.",
        oficinaPiso2: "Av. Mariscal Santa Cruz, Edificio Centro de Comunicaciones Piso 2.",
        oficinaArce: "Av. Arce, Pasaje Pinilla.",
        telefono: "2312784",
        mapaEmbed: "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3825.437152016335!2d-68.13624382512613!3d-16.49692488424564!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x915f207038bb1dd1%3A0x673dbb608882b544!2sEdificio%20Centro%20de%20Comunicaciones%20La%20Paz!5e0!3m2!1ses!2sbo!4v1709900000000!5m2!1ses!2sbo",
        mapaLink: "https://maps.google.com"
    },
    noticias: [
        { tipo: "Notas de Prensa", icono: "fa-solid fa-newspaper", extracto: "Ministerio expone portafolio de inversiones en la convención minera internacional...", accion: "Leer más" },
        { tipo: "Comunicados", icono: "fa-solid fa-bullhorn", extracto: "Actualización de normativas de exportación para optimización aduanera.", accion: "Ver archivo" },
        { tipo: "Fotografías", icono: "fa-solid fa-camera", extracto: "Galería oficial de inspecciones técnicas y reuniones corporativas.", accion: "Ver galería" },
        { tipo: "Artículos Técnicos", icono: "fa-solid fa-file-lines", extracto: "El rol del Zinc boliviano en la cadena de suministros global.", accion: "Descargar" }
    ],
    slider: [
        { img: "img/mineral1.jpg", title: "LITIO Y EVAPORÍTICOS", desc: "El epicentro de la transición energética global." },
        { img: "img/mineral2.jpg", title: "ORO Y PLATA", desc: "Potencial geológico con tecnología metalúrgica de punta." },
        { img: "img/mineral3.jpg", title: "ESTAÑO Y ZINC", desc: "Fortaleciendo la cadena de suministros industriales." },
        { img: "img/mineral4.jpg", title: "HIERRO Y SIDERURGIA", desc: "Impulsando la industria metalúrgica para el mercado internacional." }
    ],
    documentos: [
        { titulo: "Reglamento General de Minería 2026", tipo: "PDF", fecha: "10/03/2026" },
        { titulo: "Manual de Exportación de Concentrados", tipo: "DOC", fecha: "05/03/2026" },
        { titulo: "Ley de Fomento Metalúrgico", tipo: "LEY", fecha: "20/02/2026" }
    ],
    entidades: [
        { nombre: "VINTO", url: "https://vinto.gob.bo/" },
        { nombre: "COMIBOL", url: "https://www.comibol.gob.bo/" },
        { nombre: "AJAM", url: "https://www.autoridadminera.gob.bo/" },
        { nombre: "ESM", url: "https://esm.gob.bo/" },
        { nombre: "SERGEOMIN", url: "https://www.sergeomin.gob.bo/" },
        { nombre: "SENARECOM", url: "https://www.senarecom.gob.bo/" },
        { nombre: "FOFIM", url: "https://www.fofim.gob.bo/" }
    ]
};

// ==========================================
// 2. MOTORES DE RENDERIZADO (DRY / UI)
// ==========================================

function renderSharedComponents() {
    const navCont = document.getElementById('navbar-container');
    const footCont = document.getElementById('footer-container');

    if (navCont) {
        const menuHtml = apiData.menu.map(m => `<li><a href="${m.url}">${m.titulo}</a></li>`).join('');
        // El ticker se hidrata en runtime desde js/ticker_bootstrap.js (módulo
        // ES que consume el endpoint público /reports/daily). Mantenemos un
        // placeholder visible hasta que llegue la primera respuesta.
        const tickerPlaceholder = `<div class="ticker-item is-fallback"><span>Cargando cotizaciones…</span></div>`;

        navCont.innerHTML = `
            <nav class="navbar">
                <div class="nav-container">
                    <div class="brand">
                        <img src="${apiData.institucion.logo}" alt="Escudo" class="escudo-img">
                        <div class="logo-text">
                            <span class="logo-min">${apiData.institucion.nombreCorto}</span>
                            <span class="logo-main">${apiData.institucion.nombreLargo}</span>
                        </div>
                    </div>
                    <ul class="nav-links">
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

    if (footCont) {
        const socialHtml = apiData.redes.map(r => {
            if (r.svg) return `<a href="${r.url}" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16"><path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z"/></svg></a>`;
            return `<a href="${r.url}" target="_blank"><i class="${r.icono}"></i></a>`;
        }).join('');

        // INYECCIÓN DEL BLOQUE DE CONTACTO GLOBAL + FOOTER
        footCont.innerHTML = `
            <section class="contacto-section container" style="margin-bottom: 2rem; margin-top: 4rem;">
                <div class="contacto-info">
                    <h2 class="section-title">Contacto Institucional</h2>
                    <div class="contact-item">
                        <i class="fa-solid fa-building"></i>
                        <div><strong>Oficina Central - MMM</strong><br>${apiData.contacto.oficinaCentral}</div>
                    </div>
                    <div class="contact-item">
                        <i class="fa-solid fa-building"></i>
                        <div><strong>Oficina Piso 2 - MMM</strong><br>${apiData.contacto.oficinaPiso2}</div>
                    </div>
                    <div class="contact-item">
                        <i class="fa-solid fa-location-dot"></i>
                        <div><strong>Oficina Av. Arce - MMM</strong><br>${apiData.contacto.oficinaArce}</div>
                    </div>
                    <div class="contact-item">
                        <i class="fa-solid fa-phone"></i>
                        <div><strong>Teléfono:</strong> ${apiData.contacto.telefono}</div>
                    </div>
                </div>
                <div class="contacto-mapa">
                    <iframe src="${apiData.contacto.mapaEmbed}" width="100%" height="300" style="border:0; border-radius: 8px;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                    <a href="${apiData.contacto.mapaLink}" target="_blank" class="map-link">Ver todas las ubicaciones en Google Maps <i class="fa-solid fa-arrow-right"></i></a>
                </div>
            </section>

            <div class="tricolor-line"></div>
            <footer class="footer">
                <div class="social-footer">
                    <span>Encuéntranos en nuestras redes:</span>
                    <div class="social-icons">${socialHtml}</div>
                </div>
                <p>© ${new Date().getFullYear()} ${apiData.institucion.nombreCorto} ${apiData.institucion.nombreLargo} | Estado Plurinacional de Bolivia</p>
            </footer>
        `;
    }
}

function renderContentBlocks() {
    const contNoticias = document.getElementById('cms-noticias');
    if (contNoticias) {
        contNoticias.innerHTML = apiData.noticias.map(n => `
            <div class="prensa-item">
                <h3 style="color: var(--oro);"><i class="${n.icono}"></i> ${n.tipo}</h3>
                <p style="font-size: 0.9rem; margin-top: 10px;">${n.extracto}</p>
                <a href="#" style="font-size: 0.8rem; font-weight: bold; color: var(--negro);">${n.accion} ➔</a>
            </div>
        `).join('');
    }

    const contSlider = document.getElementById('cms-slider');
    if (contSlider) {
        let slidesHtml = apiData.slider.map((s, index) => `
            <div class="slide ${index === 0 ? 'active' : ''}">
                <img src="${s.img}" alt="${s.title}" onerror="this.src='https://images.unsplash.com/photo-1590001158193-798d36136701?q=80&w=1200'">
                <div class="slide-caption"><strong>${s.title}:</strong> ${s.desc}</div>
            </div>
        `).join('');
        contSlider.innerHTML = slidesHtml + `<button id="prevSlide" class="slide-nav">❮</button><button id="nextSlide" class="slide-nav">❯</button>`;
    }

    const contDocs = document.getElementById('docs-container');
    if (contDocs) {
        contDocs.innerHTML = apiData.documentos.map(d => `
            <div class="doc-item">
                <span class="tag">${d.tipo}</span>
                <h4 style="margin:10px 0">${d.titulo}</h4>
                <p style="font-size:0.8rem; color:gray">Publicado: ${d.fecha}</p>
                <a href="#" style="color:var(--oro); text-decoration:none; font-weight:600">⬇ Descargar</a>
            </div>
        `).join('');
    }

    const contEntidades = document.getElementById('cms-entidades');
    if (contEntidades) {
        contEntidades.innerHTML = apiData.entidades.map(e => `
            <a href="${e.url}" target="_blank" class="entidad-card">${e.nombre} <i class="fa-solid fa-arrow-up-right-from-square"></i></a>
        `).join('');
    }

    const yt = document.getElementById('yt-content');
    const fb = document.getElementById('fb-content');
    if(yt) yt.innerHTML = `<div style="background:#000; height:150px; border-radius:8px; display:flex; align-items:center; justify-content:center; color:white">Video Institucional</div>`;
    if(fb) fb.innerHTML = `<p style="font-size:0.9rem"><strong>@MineriaBolivia:</strong> Actualización de normativas mineras en curso...</p>`;
}

// ==========================================
// 3. ANIMACIONES Y LÓGICA (HERO, TABS, CHART)
// ==========================================

let dots = [], canvas, ctx;
function initHeroAnimation() {
    canvas = document.getElementById('hero-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
    dots = [];
    for (let i = 0; i < 70; i++) {
        dots.push({ x: Math.random() * canvas.width, y: Math.random() * canvas.height, vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4 });
    }
}

function animateHero() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(201, 167, 81, 0.6)"; ctx.strokeStyle = "rgba(201, 167, 81, 0.15)";
    dots.forEach((p, i) => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
        ctx.beginPath(); ctx.arc(p.x, p.y, 2, 0, Math.PI * 2); ctx.fill();
        for (let j = i + 1; j < dots.length; j++) {
            let p2 = dots[j];
            if (Math.hypot(p.x - p2.x, p.y - p2.y) < 120) {
                ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
            }
        }
    });
    requestAnimationFrame(animateHero);
}

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    if (tabBtns.length === 0) return;
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.getAttribute('data-target')).classList.add('active');
        });
    });
}

// ==========================================
// 4. INICIALIZACIÓN GLOBAL
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    renderSharedComponents();

    setTimeout(() => {
        renderContentBlocks();
        initHeroAnimation();
        if(canvas) animateHero();
        initTabs();

        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.onclick = () => {
                const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                themeToggle.innerText = newTheme === 'dark' ? '☀️' : '🌙';
                localStorage.setItem('theme', newTheme);
                if(document.getElementById('lme-chart')) location.reload(); 
            };
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {
                document.documentElement.setAttribute('data-theme', savedTheme);
                themeToggle.innerText = savedTheme === 'dark' ? '☀️' : '🌙';
            }
        }

        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        function showSlide(index) {
            if (slides.length === 0) return;
            slides.forEach(s => s.classList.remove('active'));
            currentSlide = index >= slides.length ? 0 : (index < 0 ? slides.length - 1 : index);
            slides[currentSlide].classList.add('active');
        }
        if(document.getElementById('nextSlide')) document.getElementById('nextSlide').onclick = () => showSlide(++currentSlide);
        if(document.getElementById('prevSlide')) document.getElementById('prevSlide').onclick = () => showSlide(--currentSlide);
        if (slides.length > 0) setInterval(() => showSlide(++currentSlide), 5000);

    }, 50); 
});

window.onresize = initHeroAnimation;
