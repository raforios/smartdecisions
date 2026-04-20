/**
 * MINISTERIO DE MINERÍA Y METALURGIA - SCRIPT PRINCIPAL
 */

// 1. INYECCIÓN DINÁMICA DE NAVBAR Y FOOTER
function loadSharedComponents() {
    const navbarContainer = document.getElementById('navbar-container');
    const footerContainer = document.getElementById('footer-container');

    if (navbarContainer) {
        navbarContainer.innerHTML = `
            <nav class="navbar">
                <div class="nav-container">
                    <div class="brand">
                        <img src="img/cropped-escudo.png" alt="Escudo de Bolivia" class="escudo-img">
                        <div class="logo-text">
                            <span class="logo-min">MINISTERIO DE</span>
                            <span class="logo-main">MINERÍA Y METALURGIA</span>
                        </div>
                    </div>
                    <ul class="nav-links">
                        <li><a href="index.html">Inicio</a></li>
                        <li><a href="institucional.html">Ministerio</a></li>
                        <li><a href="documentacion.html">Documentación</a></li>
                        <li><a href="#" class="btn-bi">Portal BI</a></li>
                        <li><button id="theme-toggle" class="theme-btn">🌙</button></li>
                    </ul>
                </div>
            </nav>
            <div class="ticker-wrap">
                <div class="ticker" id="mineral-ticker"></div>
                <a href="mercados.html" class="mercados-btn"><i class="fa-solid fa-chart-line" style="margin-right: 8px;"></i> Bolsa de Londres (LME)</a>
            </div>
        `;
    }

    if (footerContainer) {
        footerContainer.innerHTML = `
            <div class="tricolor-line"></div>
            <footer class="footer">
                <div class="social-footer">
                    <span>Encuéntranos en nuestras redes:</span>
                    <div class="social-icons">
                        <a href="https://www.linkedin.com/company/ministerio-de-miner%C3%ADa-y-metalurgia-de-bolivia/posts/?feedView=all" target="_blank"><i class="fa-brands fa-linkedin"></i></a>
                        <a href="https://www.youtube.com/channel/UC3avDHxuYOiv56hspVueXrg" target="_blank"><i class="fa-brands fa-youtube"></i></a>
                        <a href="https://www.instagram.com/ministeriodemineriabolivia/" target="_blank"><i class="fa-brands fa-instagram"></i></a>
                        <a href="https://www.tiktok.com/@ministeriodemineria" target="_blank"><i class="fa-brands fa-tiktok"></i></a>
                        <a href="https://x.com/minmineriabo" target="_blank">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16">
                              <path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z"/>
                            </svg>
                        </a>
                        <a href="https://www.facebook.com/minmineriabol" target="_blank"><i class="fa-brands fa-facebook"></i></a>
                    </div>
                </div>
                <p id="copyright-text">© ${new Date().getFullYear()} Ministerio de Minería y Metalurgia | Estado Plurinacional de Bolivia</p>
            </footer>
        `;
    }
}

// 2. TICKER DE PRECIOS
function loadPriceTicker() {
    const ticker = document.getElementById('mineral-ticker');
    if(!ticker) return;

    const prices = [
        { name: "ORO", price: "2,150.40", trend: "+1.2%", status: "up" },
        { name: "PLATA", price: "24.30", trend: "-0.5%", status: "down" },
        { name: "ESTAÑO", price: "27,450.00", trend: "+0.8%", status: "up" },
        { name: "ZINC", price: "2,540.00", trend: "+2.1%", status: "up" },
        { name: "LITIO (LCE)", price: "13,500.00", trend: "-1.4%", status: "down" },
        { name: "HIERRO", price: "915.00", trend: "+0.5%", status: "up" }
    ];

    const content = prices.map(p => `
        <div class="ticker-item"><span>${p.name}</span><span>$${p.price}</span><span class="${p.status}">${p.trend} ${p.status === 'up' ? '▲' : '▼'}</span></div>
    `).join('');
    ticker.innerHTML = content + content;
}

// 3. ANIMACIÓN DEL HERO
let dots = [];
let canvas, ctx;

function initHeroAnimation() {
    canvas = document.getElementById('hero-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    
    const parent = canvas.parentElement;
    canvas.width = parent.clientWidth;
    canvas.height = parent.clientHeight;
    
    dots = [];
    for (let i = 0; i < 70; i++) {
        dots.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4
        });
    }
}

function animateHero() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(201, 167, 81, 0.6)"; 
    ctx.strokeStyle = "rgba(201, 167, 81, 0.15)";

    dots.forEach((p, i) => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < dots.length; j++) {
            let p2 = dots[j];
            let dist = Math.hypot(p.x - p2.x, p.y - p2.y);
            if (dist < 120) {
                ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
            }
        }
    });
    requestAnimationFrame(animateHero);
}

// 4. LÓGICA DE TABS
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

// 5. DATOS MOCK Y GRÁFICO LME
function loadDocuments() {
    const container = document.getElementById('docs-container');
    if (!container) return;
    const mockData = [
        { titulo: "Reglamento General de Minería 2026", url: "#", tipo: "PDF", fecha: "10/03/2026" },
        { titulo: "Manual de Exportación de Concentrados", url: "#", tipo: "Documento", fecha: "05/03/2026" },
        { titulo: "Ley de Fomento Metalúrgico", url: "#", tipo: "Ley", fecha: "20/02/2026" }
    ];
    container.innerHTML = mockData.map(doc => `
        <div class="doc-item">
            <span class="tag">${doc.tipo}</span>
            <h4 style="margin:10px 0">${doc.titulo}</h4>
            <p style="font-size:0.8rem; color:gray">Publicado: ${doc.fecha}</p>
            <a href="${doc.url}" style="color:var(--oro); text-decoration:none; font-weight:600">⬇ Descargar</a>
        </div>
    `).join('');
}

function loadSocialFeeds() {
    const yt = document.getElementById('yt-content');
    const fb = document.getElementById('fb-content');
    if(yt) yt.innerHTML = `<div style="background:#000; height:150px; border-radius:8px; display:flex; align-items:center; justify-content:center; color:white">Video Institucional</div>`;
    if(fb) fb.innerHTML = `<p style="font-size:0.9rem"><strong>@MineriaBolivia:</strong> Actualización de normativas mineras en curso...</p>`;
}

// NUEVO: Función para el gráfico de la Bolsa de Londres
function initMarketChart() {
    const ctxChart = document.getElementById('lme-chart');
    if (!ctxChart) return; // Solo se ejecuta si encuentra el canvas del gráfico
    
    new Chart(ctxChart, {
        type: 'line',
        data: {
            labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie'],
            datasets: [
                {
                    label: 'Oro ($)',
                    data: [2140, 2145, 2138, 2150, 2155],
                    borderColor: '#C9A751', // Oro
                    backgroundColor: 'rgba(201, 167, 81, 0.2)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Zinc ($)',
                    data: [2510, 2525, 2540, 2530, 2540],
                    borderColor: '#15592F', // Verde
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: document.documentElement.getAttribute('data-theme') === 'dark' ? '#fff' : '#242732' } }
            },
            scales: {
                y: { ticks: { color: document.documentElement.getAttribute('data-theme') === 'dark' ? '#fff' : '#363534' } },
                x: { ticks: { color: document.documentElement.getAttribute('data-theme') === 'dark' ? '#fff' : '#363534' } }
            }
        }
    });
}

// 6. INICIALIZACIÓN
document.addEventListener('DOMContentLoaded', () => {
    loadSharedComponents(); // 1. Inyectar HTML
    
    // 2. Dar tiempo a que el HTML se inyecte antes de asignar eventos
    setTimeout(() => {
        loadPriceTicker();
        initHeroAnimation();
        if(canvas) animateHero();
        initTabs();
        loadDocuments();
        loadSocialFeeds();
        initMarketChart(); // Inicializar el gráfico si estamos en mercados.html

        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.onclick = () => {
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                const newTheme = isDark ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                themeToggle.innerText = isDark ? '🌙' : '☀️';
                localStorage.setItem('theme', newTheme);
                
                // Recargar para que el gráfico actualice sus colores al cambiar de tema
                if(document.getElementById('lme-chart')) {
                    location.reload(); 
                }
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
            if (index >= slides.length) currentSlide = 0;
            else if (index < 0) currentSlide = slides.length - 1;
            else currentSlide = index;
            slides[currentSlide].classList.add('active');
        }
        const nextBtn = document.getElementById('nextSlide');
        const prevBtn = document.getElementById('prevSlide');
        if (nextBtn) nextBtn.onclick = () => showSlide(++currentSlide);
        if (prevBtn) prevBtn.onclick = () => showSlide(--currentSlide);
        if (slides.length > 0) setInterval(() => showSlide(++currentSlide), 5000);
    }, 50); 
});

window.onresize = initHeroAnimation;
