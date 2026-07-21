/**
 * Visor tipo libro (flipbook) para los PDF de la Cumbre (brochure y programa).
 *
 * Renderiza un PDF con PDF.js (cada página a imagen) y lo muestra con la
 * librería page-flip (efecto de pasar hojas). Se abre al hacer clic en el
 * gadget correspondiente de la landing. La misma fábrica se instancia para
 * cada documento; los elementos del visor se resuelven dentro de cada modal.
 */
(function () {
    const WORKER_SRC = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    function initFlipbook(config) {
        const trigger = document.getElementById(config.triggerId);
        const modal = document.getElementById(config.modalId);
        if (!trigger || !modal) return;

        const backdrop = modal.querySelector('.flipbook-backdrop');
        const closeBtn = modal.querySelector('.flipbook-close');
        const loading = modal.querySelector('.flipbook-loading');
        const viewport = modal.querySelector('.flipbook-viewport');
        const bookEl = modal.querySelector('.flipbook-book');
        const prevBtn = modal.querySelector('.flip-prev');
        const nextBtn = modal.querySelector('.flip-next');
        const indicator = modal.querySelector('.flip-page-indicator');

        let images = null;
        let pageFlip = null;

        async function renderPdf() {
            pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_SRC;
            const pdf = await pdfjsLib.getDocument(config.pdfUrl).promise;
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
                loading.textContent = config.errorText;
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
    }

    initFlipbook({
        triggerId: 'brochure-trigger',
        modalId: 'flipbook-modal',
        pdfUrl: 'assets/BROCHURE.pdf',
        errorText: 'No se pudo cargar el brochure.'
    });
    initFlipbook({
        triggerId: 'programa-trigger',
        modalId: 'programa-modal',
        pdfUrl: 'assets/PROGRAMA.pdf',
        errorText: 'No se pudo cargar el programa.'
    });
})();
