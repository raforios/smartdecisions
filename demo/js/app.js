import { ApiService } from './services/ApiService.js';
import { Header } from './components/Header.js';
import { Footer } from './components/Footer.js';

const api = new ApiService();

document.addEventListener('DOMContentLoaded', async () => {
    const siteData = await api.getConfig();
    if (!siteData) {
        console.error("No se pudo cargar la data del CMS.");
        return;
    }

    // 1. Inyectar Globales
    const navContainer = document.getElementById('navbar-container');
    const footerContainer = document.getElementById('footer-container');

    if (navContainer) {
        navContainer.innerHTML = Header.render(siteData);
        Header.initInteractions(); 
    }
    if (footerContainer) {
        footerContainer.innerHTML = Footer.render(siteData);
    }

    // 2. Inyectar Contenido Específico de Index
    renderHomeBlocks(siteData);

    // 3. Inicializar Lógicas (Tema, Canvas)
    initThemeToggle();
    initHeroAnimation();
    animateHero();
});

function renderHomeBlocks(data) {
    const contNoticias = document.getElementById('cms-noticias');
    if (contNoticias && data.noticias) {
        contNoticias.innerHTML = data.noticias.map(n => `
            <div class="prensa-item">
                <h3 style="color: var(--oro);"><i class="${n.icono}"></i> ${n.tipo}</h3>
                <p style="font-size: 0.9rem; margin-top: 10px;">${n.extracto}</p>
                <a href="#" style="font-size: 0.8rem; font-weight: bold; color: var(--negro);">${n.accion} ➔</a>
            </div>
        `).join('');
    }

    const contSlider = document.getElementById('cms-slider');
    if (contSlider && data.slider) {
        let slidesHtml = data.slider.map((s, index) => `
            <div class="slide ${index === 0 ? 'active' : ''}">
                <img src="${s.img}" alt="${s.title}" onerror="this.src='https://images.unsplash.com/photo-1590001158193-798d36136701?q=80&w=1200'">
                <div class="slide-caption"><strong>${s.title}:</strong> ${s.desc}</div>
            </div>
        `).join('');
        contSlider.innerHTML = slidesHtml + `<button id="prevSlide" class="slide-nav">❮</button><button id="nextSlide" class="slide-nav">❯</button>`;
        
        let currentSlide = 0;
        const slides = document.querySelectorAll('.slide');
        document.getElementById('nextSlide').onclick = () => showSlide(++currentSlide, slides);
        document.getElementById('prevSlide').onclick = () => showSlide(--currentSlide, slides);
        setInterval(() => showSlide(++currentSlide, slides), 5000);
    }

    const contDocs = document.getElementById('docs-container');
    if (contDocs && data.documentos) {
        contDocs.innerHTML = data.documentos.map(d => `
            <div class="doc-item">
                <span class="tag">${d.tipo}</span>
                <h4 style="margin:10px 0">${d.titulo}</h4>
                <p style="font-size:0.8rem; color:gray">Publicado: ${d.fecha}</p>
                <a href="#" style="color:var(--oro); text-decoration:none; font-weight:600">⬇ Descargar</a>
            </div>
        `).join('');
    }

    const contEntidades = document.getElementById('cms-entidades');
    if (contEntidades && data.entidades) {
        contEntidades.innerHTML = data.entidades.map(e => `
            <a href="${e.url}" target="_blank" class="entidad-card">${e.nombre} <i class="fa-solid fa-arrow-up-right-from-square"></i></a>
        `).join('');
    }
}

function showSlide(index, slides) {
    if (slides.length === 0) return;
    slides.forEach(s => s.classList.remove('active'));
    let currentSlide = index >= slides.length ? 0 : (index < 0 ? slides.length - 1 : index);
    slides[currentSlide].classList.add('active');
}

function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;
    themeToggle.onclick = () => {
        const newTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        themeToggle.innerText = newTheme === 'dark' ? '☀️' : '🌙';
        localStorage.setItem('theme', newTheme);
    };
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        themeToggle.innerText = savedTheme === 'dark' ? '☀️' : '🌙';
    }
}

// Lógica de Animación del Canvas
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
window.onresize = initHeroAnimation;
