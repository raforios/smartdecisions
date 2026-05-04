export class Footer {
    static render(data) {
        const socialHtml = data.redesSociales.map(r => {
            if (r.svg) return `<a href="${r.url}" target="_blank" title="${r.nombre}"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 16 16"><path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865l8.875 11.633Z"/></svg></a>`;
            return `<a href="${r.url}" target="_blank" title="${r.nombre}"><i class="${r.icono}"></i></a>`;
        }).join('');

        return `
            <section class="contacto-section container" style="margin-bottom: 2rem; margin-top: 4rem;">
                <div class="contacto-info">
                    <h2 class="section-title">Contacto Institucional</h2>
                    <div class="contact-item"><i class="fa-solid fa-building"></i><div><strong>Oficina Central - MMM</strong><br>${data.contacto.oficinaCentral}</div></div>
                    <div class="contact-item"><i class="fa-solid fa-building"></i><div><strong>Oficina Piso 2 - MMM</strong><br>${data.contacto.oficinaPiso2}</div></div>
                    <div class="contact-item"><i class="fa-solid fa-location-dot"></i><div><strong>Oficina Av. Arce - MMM</strong><br>${data.contacto.oficinaArce}</div></div>
                    <div class="contact-item"><i class="fa-solid fa-phone"></i><div><strong>Teléfono:</strong> ${data.contacto.telefono}</div></div>
                </div>
                <div class="contacto-mapa">
                    <iframe src="${data.contacto.mapaEmbed}" width="100%" height="300" style="border:0; border-radius: 8px;" loading="lazy"></iframe>
                    <a href="${data.contacto.mapaLink}" target="_blank" class="map-link">Ver en Google Maps <i class="fa-solid fa-arrow-right"></i></a>
                </div>
            </section>

            <div class="tricolor-line"></div>
            <footer class="footer">
                <div class="social-footer">
                    <span>Encuéntranos en nuestras redes:</span>
                    <div class="social-icons">${socialHtml}</div>
                </div>
                <p>© ${new Date().getFullYear()} ${data.institucion.nombreCorto} ${data.institucion.nombreLargo} | Estado Plurinacional de Bolivia</p>
            </footer>
        `;
    }
}
