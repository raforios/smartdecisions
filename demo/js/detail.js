/**
 * detail.js — single dynamic template behind every "Ver más" link.
 *
 * Reads `?type=<news|document|slide|entity>&id=<uuid>` from the URL,
 * fetches the matching CMS public endpoint by id, and renders the
 * item. Different entity types render slightly different shells:
 *   - news    → hero image + title + meta + body
 *   - document → title + tag + date + "Ver en portal Ministerio" button
 *   - slide   → image + title + description + link (rare)
 *   - entity  → logo + name + description + "Ir al sitio" button
 *
 * On 404 / network failure the page falls back to a friendly message
 * with a link back home. The header + footer are rendered the same way
 * as the rest of the portal (shared Header / Footer components).
 */
import { ApiService } from './services/ApiService.js';
import { CmsApiService } from './services/CmsApiService.js';
import { Header } from './components/Header.js';
import { Footer } from './components/Footer.js';

const api = new ApiService();

const MONTHS_ES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

const NEWS_TYPE_LABELS = {
    press: 'Nota de prensa',
    communique: 'Comunicado',
    photo: 'Galería',
    article: 'Artículo',
};

document.addEventListener('DOMContentLoaded', async () => {
    const siteData = await api.getConfig();
    if (!siteData) {
        _renderError('No se pudo cargar la configuración del sitio.');
        return;
    }
    _renderShell(siteData);

    const params = new URLSearchParams(window.location.search);
    const type = params.get('type');
    const id = params.get('id');
    if (!type || !id) {
        _renderError('Faltan parámetros (?type=&id=).');
        return;
    }

    const cms = new CmsApiService(siteData.api || {});
    let item = null;
    try {
        item = await _fetchByType(cms, type, id);
    } catch (err) {
        item = null;
    }

    if (!item) {
        _renderNotFound(type);
        return;
    }

    document.title = `${item.title || item.name || 'Detalle'} | Ministerio`;
    _render(type, item);
});

function _renderShell(siteData) {
    const navContainer = document.getElementById('navbar-container');
    const footerContainer = document.getElementById('footer-container');
    if (navContainer) {
        navContainer.innerHTML = Header.render(siteData);
        Header.initInteractions();
    }
    if (footerContainer) {
        footerContainer.innerHTML = Footer.render(siteData);
    }
}

async function _fetchByType(cms, type, id) {
    switch (type) {
        case 'news':     return cms.getNewsById(id);
        case 'document': return cms.getDocumentById(id);
        case 'slide':    return cms.getSlideById(id);
        case 'entity':   return cms.getEntityById(id);
        default:         return null;
    }
}

function _render(type, item) {
    switch (type) {
        case 'news':     return _renderNews(item);
        case 'document': return _renderDocument(item);
        case 'slide':    return _renderSlide(item);
        case 'entity':   return _renderEntity(item);
        default:         return _renderError('Tipo desconocido.');
    }
}

function _renderNews(item) {
    const host = document.getElementById('detail-host');
    const typeLabel = NEWS_TYPE_LABELS[item.type] || item.type || 'Noticia';
    const dateText = _formatDate(item.published_at);
    const hero = item.image_url
        ? `<img class="detail-hero" src="${_safe(item.image_url)}" alt="${_safe(item.title)}" onerror="this.style.display='none'">`
        : '';
    // Preserve paragraph breaks from the scraper output: lines separated
    // by two spaces or by typical sentence terminators stay together,
    // but explicit \n becomes a real <br>. Body comes plain-text from
    // the CMS, so we escape and inject <br> manually.
    const bodyHtml = _safe(item.body || item.summary || '')
        .replace(/\n+/g, '<br><br>');
    host.innerHTML = `
        ${hero}
        <span class="detail-tag">${_safe(typeLabel)}</span>
        <h1 class="detail-title">${_safe(item.title || '')}</h1>
        ${dateText ? `<p class="detail-meta"><i class="fa-regular fa-calendar"></i> ${dateText}</p>` : ''}
        <div class="detail-body">${bodyHtml || '<p>Sin contenido disponible.</p>'}</div>
    `;
}

function _renderDocument(item) {
    const host = document.getElementById('detail-host');
    const dateText = _formatDate(item.doc_date);
    const fileUrl = item.file_url;
    const isExternal = fileUrl && !fileUrl.includes('.s3.amazonaws.com');
    const buttonLabel = isExternal
        ? 'Ver en portal Ministerio'
        : 'Descargar archivo';
    const button = fileUrl
        ? `<a class="detail-cta" href="${_safe(fileUrl)}" target="_blank" rel="noopener">
              <i class="fa-solid fa-up-right-from-square"></i> ${buttonLabel}
           </a>`
        : '<p class="detail-meta">El archivo no está disponible en este momento.</p>';
    host.innerHTML = `
        <span class="detail-tag">${_safe(item.doc_type || 'DOC')}</span>
        <h1 class="detail-title">${_safe(item.title || '')}</h1>
        ${dateText ? `<p class="detail-meta"><i class="fa-regular fa-calendar"></i> ${dateText}</p>` : ''}
        <div class="detail-body">
            <p>Este es un documento institucional publicado por el Ministerio de Minería y Metalurgia.</p>
        </div>
        ${button}
    `;
}

function _renderSlide(item) {
    const host = document.getElementById('detail-host');
    const hero = item.image_url
        ? `<img class="detail-hero" src="${_safe(item.image_url)}" alt="${_safe(item.title)}">`
        : '';
    const link = item.link_url
        ? `<a class="detail-cta" href="${_safe(item.link_url)}" target="_blank" rel="noopener">
              <i class="fa-solid fa-arrow-right"></i> Más información
           </a>`
        : '';
    host.innerHTML = `
        ${hero}
        <h1 class="detail-title">${_safe(item.title || '')}</h1>
        <div class="detail-body">${_safe(item.description || '')}</div>
        ${link}
    `;
}

function _renderEntity(item) {
    const host = document.getElementById('detail-host');
    const logo = item.logo_url
        ? `<img class="detail-logo" src="${_safe(item.logo_url)}" alt="${_safe(item.name)}">`
        : '';
    host.innerHTML = `
        ${logo}
        <h1 class="detail-title">${_safe(item.name || '')}</h1>
        <div class="detail-body">${_safe(item.short_description || '')}</div>
        <a class="detail-cta" href="${_safe(item.url)}" target="_blank" rel="noopener">
            <i class="fa-solid fa-up-right-from-square"></i> Ir al sitio oficial
        </a>
    `;
}

function _renderNotFound(type) {
    const host = document.getElementById('detail-host');
    host.innerHTML = `
        <h1 class="detail-title">Contenido no disponible</h1>
        <p class="detail-meta">El elemento que buscas no existe o ya no está publicado.</p>
        <a class="detail-cta" href="index.html">
            <i class="fa-solid fa-arrow-left"></i> Volver al inicio
        </a>
    `;
}

function _renderError(message) {
    const host = document.getElementById('detail-host');
    host.innerHTML = `<p class="detail-meta">${_safe(message)}</p>`;
}

function _formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return `${date.getDate()} de ${MONTHS_ES[date.getMonth()]} de ${date.getFullYear()}`;
}

function _safe(text) {
    return String(text ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}
