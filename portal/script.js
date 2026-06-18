'use strict';

// Year in footer
document.getElementById('year').textContent = new Date().getFullYear();

// Contact form: client-side validation + mailto fallback (zero-backend POC)
const form = document.getElementById('contactForm');
const note = document.getElementById('formNote');
const CONTACT_EMAIL = 'raforios@gmail.com';

if (form) {
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        note.className = 'form-note';
        note.textContent = '';

        const data = new FormData(form);
        const name = (data.get('name') || '').toString().trim();
        const email = (data.get('email') || '').toString().trim();
        const message = (data.get('message') || '').toString().trim();

        if (!name || !email || !message) {
            note.classList.add('error');
            note.textContent = 'Completa los tres campos antes de enviar.';
            return;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            note.classList.add('error');
            note.textContent = 'El email no parece válido.';
            return;
        }

        const subject = encodeURIComponent(`SmartDecisions — contacto de ${name}`);
        const body = encodeURIComponent(`Nombre: ${name}\nEmail: ${email}\n\n${message}`);
        const mailto = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;

        note.classList.add('success');
        note.textContent = 'Abriendo tu cliente de correo…';
        window.location.href = mailto;
    });
}
