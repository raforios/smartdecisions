/**
 * Visor tipo libro (flipbook) del brochure de la Cumbre.
 *
 * Renderiza assets/BROCHURE.pdf con PDF.js (cada página a imagen) y lo muestra
 * con la librería page-flip (efecto de pasar hojas). Se abre al hacer clic en
 * la imagen del hero de la landing.
 */
(function () {
    const PDF_URL = 'assets/BROCHURE.pdf';
    const WORKER_SRC = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    const trigger = document.getElementById('brochure-trigger');
    const modal = document.getElementById('flipbook-modal');
    if (!trigger || !modal) return;

    const backdrop = document.getElementById('flipbook-backdrop');
    const closeBtn = document.getElementById('flipbook-close');
    const loading = document.getElementById('flipbook-loading');
    const viewport = document.getElementById('flipbook-viewport');
    const bookEl = document.getElementById('flipbook');
    const prevBtn = document.getElementById('flip-prev');
    const nextBtn = document.getElementById('flip-next');
    const indicator = document.getElementById('flip-page-indicator');

    let images = null;
    let pageFlip = null;

    async function renderPdf() {
        pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;
        const pdf = await pdfjsLib.getDocument(PDF_URL).promise;
        const out = [];
        for (let i = 1; i <= pdf.numPages; i += 1) {
            const page = await pdf.getPage(i);
            const vp = page.getViewport({ scale: 1.4 });
            const canvas = document.createElement('canvas');
            canvas.width = vp.width;
            canvas.height = vp.height;
            await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise;
            out.push(canvas.toDataURL('image/jpeg', 0.82));
        }
        return out;
    }

    function updateIndicator() {
        if (!pageFlip) return;
        const current = pageFlip.getCurrentPageIndex() + 1;
        indicator.textContent = `Página ${current} de ${pageFlip.getPageCount()}`;
    }

    function buildBook() {
        const PageFlip = (window.St && window.St.PageFlip) || window.PageFlip;
        if (!PageFlip) {
            loading.hidden = false;
            loading.textContent = 'El visor no está disponible.';
            return;
        }
        pageFlip = new PageFlip(bookEl, {
            width: 420,
            height: 543,
            size: 'stretch',
            minWidth: 300,
            maxWidth: 600,
            minHeight: 400,
            maxHeight: 780,
            maxShadowOpacity: 0.5,
            showCover: true,
            mobileScrollSupport: true
        });
        pageFlip.loadFromImages(images);
        pageFlip.on('flip', updateIndicator);
        updateIndicator();
    }

    async function open() {
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        if (images) return;
        loading.hidden = false;
        viewport.hidden = true;
        try {
            images = await renderPdf();
        } catch (error) {
            loading.textContent = 'No se pudo cargar el brochure.';
            return;
        }
        loading.hidden = true;
        viewport.hidden = false;
        buildBook();
    }

    function close() {
        modal.hidden = true;
        document.body.style.overflow = '';
    }

    trigger.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    prevBtn.addEventListener('click', () => { if (pageFlip) pageFlip.flipPrev(); });
    nextBtn.addEventListener('click', () => { if (pageFlip) pageFlip.flipNext(); });
    document.addEventListener('keydown', (event) => {
        if (modal.hidden) return;
        if (event.key === 'Escape') close();
        if (event.key === 'ArrowLeft' && pageFlip) pageFlip.flipPrev();
        if (event.key === 'ArrowRight' && pageFlip) pageFlip.flipNext();
    });
})();
