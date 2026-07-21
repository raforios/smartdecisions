'use strict';

/**
 * BearSoft / SmartDecisions landing — data-driven render.
 * Content lives in ./js/content.json so copy can change without touching markup.
 */
document.addEventListener('DOMContentLoaded', function () {
    initHeaderParticles();

    // Footer copyright
    const copyrightElement = document.getElementById('copyright-year');
    if (copyrightElement) {
        const currentYear = new Date().getFullYear();
        copyrightElement.innerHTML = `&copy; ${currentYear} BearSoft. Todos los derechos reservados.`;
    }

    fetch('./js/content.json')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // ---- General ----
            const siteTitle = document.getElementById('site-title');
            if (siteTitle) siteTitle.textContent = data.general.siteTitle;

            const heroBrandName = document.getElementById('hero-brand-name');
            if (heroBrandName) heroBrandName.textContent = data.general.brandName;

            const cvButton = document.getElementById('cv-button');
            if (cvButton) cvButton.href = data.general.cvPath;

            const linkedinLink = document.getElementById('linkedin-link');
            if (linkedinLink) linkedinLink.href = `https://www.linkedin.com/in/${data.general.linkedinUser}`;

            const githubLink = document.getElementById('github-link');
            if (githubLink) githubLink.href = `https://github.com/${data.general.githubUser}`;

            const whatsappLink = document.getElementById('whatsapp-link');
            if (whatsappLink) whatsappLink.href = `https://wa.me/${data.general.whatsappNumber}`;

            // ---- Hero ----
            const heroTagline = document.getElementById('hero-tagline');
            if (heroTagline) heroTagline.textContent = data.hero.tagline;

            const heroSubtitle = document.getElementById('hero-subtitle');
            if (heroSubtitle) heroSubtitle.textContent = data.hero.subtitle;

            const heroCta = document.getElementById('hero-cta');
            if (heroCta) {
                heroCta.textContent = data.hero.ctaText;
                heroCta.href = data.hero.ctaLink;
            }

            // ---- About ----
            const aboutTitle = document.getElementById('about-title');
            if (aboutTitle) aboutTitle.textContent = data.about.title;

            const aboutIntro = document.getElementById('about-intro');
            if (aboutIntro) aboutIntro.textContent = data.about.intro;

            const aboutPoints = document.getElementById('about-points');
            if (aboutPoints) {
                aboutPoints.innerHTML = '';
                data.about.points.forEach(point => {
                    const li = document.createElement('li');
                    li.innerHTML = `<i class="${point.icon}"></i> <span>${point.text}</span>`;
                    aboutPoints.appendChild(li);
                });
            }
            const cvButtonText = document.getElementById('cv-button-text');
            if (cvButtonText) cvButtonText.textContent = data.about.cvButtonText;

            startCarousel('about-carousel-image', data.about.carouselImages);

            // ---- Expertise ----
            const expertiseTitle = document.getElementById('expertise-title');
            if (expertiseTitle) expertiseTitle.textContent = data.expertise.title;

            const expertiseGrid = document.getElementById('expertise-grid');
            if (expertiseGrid) {
                expertiseGrid.innerHTML = '';
                data.expertise.areas.forEach(area => {
                    const card = document.createElement('article');
                    card.classList.add('card');
                    card.innerHTML = `
                        <i class="${area.icon} card-icon"></i>
                        <h3>${area.name}</h3>
                        <p>${area.description}</p>
                        <p class="tech-list">${area.tech}</p>
                    `;
                    expertiseGrid.appendChild(card);
                });
            }

            // ---- SmartDecisions (producto) ----
            const mlAppTitle = document.getElementById('ml-app-title');
            if (mlAppTitle) mlAppTitle.textContent = data.mlApp.title;

            const mlAppIntro = document.getElementById('ml-app-intro');
            if (mlAppIntro) mlAppIntro.textContent = data.mlApp.intro;

            const mlAppFeatures = document.getElementById('ml-app-features');
            if (mlAppFeatures) {
                mlAppFeatures.innerHTML = '';
                data.mlApp.features.forEach(feature => {
                    const li = document.createElement('li');
                    li.innerHTML = `<i class="${feature.icon}"></i> <span>${feature.text}</span>`;
                    mlAppFeatures.appendChild(li);
                });
            }
            const mlAppCta = document.getElementById('ml-app-cta');
            if (mlAppCta) {
                mlAppCta.textContent = data.mlApp.ctaText;
                mlAppCta.href = data.mlApp.ctaLink;
            }

            startCarousel('ml-carousel-image', data.mlApp.carouselImages);

            // ---- SmartDecisions (producto completo: fórmula, beneficios, pasos, microservicios) ----
            if (data.smartDecisions) {
                const sd = data.smartDecisions;

                setText('smartdecisions-title', sd.title);
                setText('smartdecisions-intro', sd.intro);
                setText('smartdecisions-formula-note', sd.formulaNote);
                setText('smartdecisions-benefits-title', sd.benefitsTitle);
                setText('smartdecisions-steps-title', sd.stepsTitle);
                setText('smartdecisions-pillars-title', sd.pillarsTitle);

                const sdFormula = document.getElementById('smartdecisions-formula');
                if (sdFormula && sd.formula) {
                    sdFormula.innerHTML = `
                        <span>${sd.formula.left}</span>
                        <span class="formula-op">×</span>
                        <span>${sd.formula.middle}</span>
                        <span class="formula-op">=</span>
                        <span class="accent">${sd.formula.result}</span>
                    `;
                }

                renderCards('smartdecisions-benefits', sd.benefits);
                renderCards('smartdecisions-pillars', sd.pillars);

                const sdSteps = document.getElementById('smartdecisions-steps');
                if (sdSteps && Array.isArray(sd.steps)) {
                    sdSteps.innerHTML = '';
                    sd.steps.forEach(step => {
                        const li = document.createElement('li');
                        li.innerHTML = `
                            <div class="step-num">${step.num}</div>
                            <h3>${step.name}</h3>
                            <p>${step.description}</p>
                        `;
                        sdSteps.appendChild(li);
                    });
                }

                const sdCta = document.getElementById('smartdecisions-cta-btn');
                if (sdCta) {
                    sdCta.textContent = sd.ctaText;
                    sdCta.href = sd.ctaLink;
                }
            }

            // ---- Services ----
            const servicesTitle = document.getElementById('services-title');
            if (servicesTitle) servicesTitle.textContent = data.services.title;

            const servicesList = document.getElementById('services-list');
            if (servicesList) {
                servicesList.innerHTML = '';
                data.services.list.forEach(service => {
                    const li = document.createElement('li');
                    li.innerHTML = `<i class="${service.icon}"></i> <span>${service.text}</span>`;
                    servicesList.appendChild(li);
                });
            }

            // ---- Contact ----
            const contactMainTitle = document.getElementById('contact-main-title');
            if (contactMainTitle) contactMainTitle.textContent = data.contact.mainTitle;

            const contactIntro = document.getElementById('contact-intro');
            if (contactIntro) contactIntro.textContent = data.contact.intro;

            const formSubmitButton = document.getElementById('form-submit-button');
            if (formSubmitButton) formSubmitButton.textContent = data.contact.formSubmitText;
        })
        .catch(error => console.error('Error al cargar el contenido JSON:', error));
});

/**
 * Sets an element's text content when the element exists and a value is given.
 *
 * @param {string} elementId  Target element id.
 * @param {string} value      Text to set.
 */
function setText(elementId, value) {
    const element = document.getElementById(elementId);
    if (element && value != null) {
        element.textContent = value;
    }
}

/**
 * Renders a list of items as `.card` articles into the given grid container.
 * Each item may carry an optional `tag` (shown as a tech-list chip).
 *
 * @param {string} containerId  Target grid element id.
 * @param {Array<object>} items  Items with icon, name, description and optional tag.
 */
function renderCards(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container || !Array.isArray(items)) {
        return;
    }
    container.innerHTML = '';
    items.forEach(item => {
        const card = document.createElement('article');
        card.classList.add('card');
        const tag = item.tag ? `<p class="tech-list">${item.tag}</p>` : '';
        card.innerHTML = `
            <i class="${item.icon} card-icon"></i>
            <h3>${item.name}</h3>
            <p>${item.description}</p>
            ${tag}
        `;
        container.appendChild(card);
    });
}

/**
 * Header animation: particles.js tuned for the light hero background
 * (dark navy dots + subtle links instead of the original white-on-dark).
 */
function initHeaderParticles() {
    if (typeof particlesJS !== 'function' || !document.getElementById('particles-js')) {
        return;
    }
    particlesJS('particles-js', {
        particles: {
            number: { value: 70, density: { enable: true, value_area: 800 } },
            color: { value: '#0d1e4c' },
            shape: { type: 'circle' },
            opacity: { value: 0.35, random: false },
            size: { value: 3, random: true },
            line_linked: { enable: true, distance: 150, color: '#7a4a2a', opacity: 0.25, width: 1 },
            move: { enable: true, speed: 3, direction: 'none', out_mode: 'out' }
        },
        interactivity: {
            detect_on: 'canvas',
            events: {
                onhover: { enable: true, mode: 'grab' },
                onclick: { enable: true, mode: 'push' },
                resize: true
            },
            modes: {
                grab: { distance: 140, line_linked: { opacity: 0.5 } },
                push: { particles_nb: 4 }
            }
        },
        retina_detect: true
    });
}

/**
 * Cross-fades through a list of image URLs on the given <img> element.
 *
 * @param {string} elementId  Target <img> id.
 * @param {string[]} images   Ordered image URLs to cycle.
 */
function startCarousel(elementId, images) {
    const target = document.getElementById(elementId);
    if (!target || !Array.isArray(images) || images.length === 0) {
        return;
    }
    let currentIndex = 0;
    const transitionTime = 3000;

    target.src = images[currentIndex];
    target.style.transition = 'opacity 0.5s ease-in-out';

    if (images.length < 2) {
        return;
    }
    setInterval(() => {
        target.style.opacity = '0';
        setTimeout(() => {
            currentIndex = (currentIndex + 1) % images.length;
            target.src = images[currentIndex];
            target.style.opacity = '1';
        }, 500);
    }, transitionTime);
}
