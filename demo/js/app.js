import { ApiService } from './services/ApiService.js';
import { MiningApiService } from './services/MiningApiService.js';
import { CmsApiService } from './services/CmsApiService.js';
import { Header } from './components/Header.js';
import { Footer } from './components/Footer.js';
import { Ticker } from './components/Ticker.js';

const api = new ApiService();

// Visible labels and icons attached to each news.type returned by the CMS.
// The CMS stores the raw type; the portal owns presentation, so the map
// lives here instead of leaking display strings into the API.
const NEWS_TYPE_LABELS = {
    press: 'Notas de Prensa',
    communique: 'Comunicados',
    photo: 'Fotografías',
    article: 'Artículos',
};
const NEWS_TYPE_ICONS = {
    press: 'fa-solid fa-newspaper',
    communique: 'fa-solid fa-bullhorn',
    photo: 'fa-solid fa-camera',
    article: 'fa-solid fa-file-lines',
};
const SLIDER_PLACEHOLDER = 'https://images.unsplash.com/photo-1590001158193-798d36136701?q=80&w=1200';

document.addEventListener('DOMContentLoaded', async () => {
    const siteData = await api.getConfig();
    if (!siteData) {
        console.error('No se pudo cargar la data del CMS.');
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

    // 2. Arrancar el ticker de cotizaciones (consume el endpoint público).
    const miningApi = new MiningApiService(siteData.api || {});
    const ticker = new Ticker(miningApi, {
        refreshMs: siteData.api?.tickerRefreshMs ?? 600_000,
        fallback: siteData.tickerPrecios || [],
    });
    ticker.start();

    // 3. Pedir contenido editorial al CMS en paralelo. Si el endpoint cae
    //    o devuelve vacío, caemos al bloque equivalente del config.json
    //    para que la página nunca aparezca en blanco.
    const cmsApi = new CmsApiService(siteData.api || {});
    // Home page: keep the listings short. Full catalogs live in their
    // own dedicated pages (institucional.html, documentacion.html, etc.)
    // that will be wired in Fase B.
    const [newsPayload, slidesPayload, docsPayload, entitiesPayload] =
        await Promise.all([
            cmsApi.getNews({ limit: 6 }),
            cmsApi.getSlides(),
            cmsApi.getDocuments({ limit: 6 }),
            cmsApi.getEntities(),
        ]);

    renderNews(pickItems(newsPayload, siteData.noticias, normalizeCmsNews,
        normalizeConfigNews));
    renderSlider(pickItems(slidesPayload, siteData.slider, normalizeCmsSlide,
        normalizeConfigSlide));
    renderDocuments(pickItems(docsPayload, siteData.documentos,
        normalizeCmsDocument, normalizeConfigDocument));
    renderEntities(pickItems(entitiesPayload, siteData.entidades,
        normalizeCmsEntity, normalizeConfigEntity));

    // 4. Inicializar Lógicas (Tema, Canvas)
    initThemeToggle();
    initHeroAnimation();
    animateHero();
});


// ---------- Source selection ----------

function pickItems(cmsPayload, fallbackList, mapCms, mapFallback) {
    const cmsItems = cmsPayload?.items;
    if (Array.isArray(cmsItems) && cmsItems.length) {
        return cmsItems.map(mapCms);
    }
    return Array.isArray(fallbackList) ? fallbackList.map(mapFallback) : [];
}


// ---------- News ----------

function normalizeCmsNews(item) {
    const summary = item.summary
        || (item.body ? truncate(item.body, 220) : '');
    return {
        tipo: NEWS_TYPE_LABELS[item.type] || item.type || 'Noticia',
        icono: NEWS_TYPE_ICONS[item.type] || 'fa-solid fa-newspaper',
        extracto: summary,
        accion: 'Ver más',
        href: `detail.html?type=news&id=${encodeURIComponent(item.id)}`,
        image: item.image_url || null,
    };
}

function normalizeConfigNews(item) {
    return {
        tipo: item.tipo,
        icono: item.icono,
        extracto: item.extracto,
        accion: item.accion || 'Ver más',
        href: item.href || '#',
        image: item.image || null,
    };
}

function renderNews(items) {
    const target = document.getElementById('cms-noticias');
    if (!target || !items.length) return;
    target.innerHTML = items.map(n => `
        <article class="prensa-item">
            <header class="prensa-item-head">
                <span class="prensa-tag"><i class="${n.icono}"></i> ${n.tipo}</span>
            </header>
            <p class="prensa-extracto">${n.extracto}</p>
            <a href="${n.href}" class="prensa-cta">${n.accion} <i class="fa-solid fa-arrow-right"></i></a>
        </article>
    `).join('');
}


// ---------- Slider ----------

function normalizeCmsSlide(item) {
    return {
        img: item.image_url || SLIDER_PLACEHOLDER,
        title: item.title,
        desc: item.description || '',
        link: item.link_url || null,
    };
}

function normalizeConfigSlide(item) {
    return {
        img: item.img,
        title: item.title,
        desc: item.desc,
        link: item.link || null,
    };
}

function renderSlider(items) {
    const target = document.getElementById('cms-slider');
    if (!target || !items.length) return;
    const slidesHtml = items.map((slide, index) => {
        const caption = `<div class="slide-caption"><strong>${slide.title}:</strong> ${slide.desc}</div>`;
        const figure = `<img src="${slide.img}" alt="${slide.title}" onerror="this.src='${SLIDER_PLACEHOLDER}'">`;
        const body = slide.link
            ? `<a href="${slide.link}" target="_blank" rel="noopener">${figure}${caption}</a>`
            : `${figure}${caption}`;
        return `<div class="slide ${index === 0 ? 'active' : ''}">${body}</div>`;
    }).join('');
    target.innerHTML = slidesHtml +
        '<button id="prevSlide" class="slide-nav">❮</button>' +
        '<button id="nextSlide" class="slide-nav">❯</button>';

    let currentSlide = 0;
    const slides = target.querySelectorAll('.slide');
    document.getElementById('nextSlide').onclick = () => showSlide(++currentSlide, slides);
    document.getElementById('prevSlide').onclick = () => showSlide(--currentSlide, slides);
    if (slides.length > 1) setInterval(() => showSlide(++currentSlide, slides), 5000);
}

function showSlide(index, slides) {
    if (slides.length === 0) return;
    slides.forEach(s => s.classList.remove('active'));
    const next = index >= slides.length ? 0 : (index < 0 ? slides.length - 1 : index);
    slides[next].classList.add('active');
}


// ---------- Documents ----------

function normalizeCmsDocument(item) {
    return {
        tipo: item.doc_type || 'DOC',
        titulo: item.title,
        fecha: formatDate(item.doc_date),
        href: `detail.html?type=document&id=${encodeURIComponent(item.id)}`,
    };
}

function normalizeConfigDocument(item) {
    return {
        tipo: item.tipo,
        titulo: item.titulo,
        fecha: item.fecha,
        href: item.href || '#',
    };
}

function renderDocuments(items) {
    const target = document.getElementById('docs-container');
    if (!target || !items.length) return;
    target.innerHTML = items.map(d => `
        <article class="doc-item">
            <span class="tag">${d.tipo}</span>
            <h4 class="doc-title">${d.titulo}</h4>
            <p class="doc-date">${d.fecha ? 'Publicado: ' + d.fecha : ''}</p>
            <a href="${d.href}" class="doc-cta">Ver detalle <i class="fa-solid fa-arrow-right"></i></a>
        </article>
    `).join('');
}


// ---------- Entities ----------

function normalizeCmsEntity(item) {
    return {
        nombre: item.name,
        href: `detail.html?type=entity&id=${encodeURIComponent(item.id)}`,
        logo: item.logo_url || null,
    };
}

function normalizeConfigEntity(item) {
    return {
        nombre: item.nombre,
        href: item.url || '#',
        logo: item.logo || null,
    };
}

function renderEntities(items) {
    const target = document.getElementById('cms-entidades');
    if (!target || !items.length) return;
    target.innerHTML = items.map(e => `
        <a href="${e.href}" class="entidad-card">
            <span class="entidad-name">${e.nombre}</span>
            <i class="fa-solid fa-arrow-right entidad-arrow"></i>
        </a>
    `).join('');
}


// ---------- Helpers ----------

function truncate(text, max) {
    if (!text) return '';
    return text.length > max ? text.slice(0, max).trimEnd() + '…' : text;
}

function formatDate(isoDate) {
    if (!isoDate) return '';
    const [year, month, day] = String(isoDate).split('-');
    if (!day || !month || !year) return isoDate;
    return `${day}/${month}/${year}`;
}


// ---------- Theme + Hero animation (unchanged from previous version) ----------

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
