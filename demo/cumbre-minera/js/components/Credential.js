/**
 * Credencial de participante (sticker QR imprimible).
 *
 * Genera una IMAGEN PNG de 6 cm x 7 cm lista para la impresora de stickers
 * (INNOVATE DP30S). Muestra solo nombre, eje temático, rol y aula, con un QR
 * grande. El QR codifica UNICAMENTE el CI: menos módulos → módulos más grandes
 * y gruesos, que es lo que permite que la térmica los imprima legibles (el
 * lector de asistencia acepta tanto CI plano como el JSON antiguo, ver
 * asistencia.js#extractCi).
 */

// ~305 DPI (12 px/mm): resolución alta para que la térmica tenga módulos nítidos.
const PX_PER_MM = 12;
const STICKER_W_MM = 60;
const STICKER_H_MM = 70;

const GOLD = '#8B6914';
const INK = '#242732';

/** Milímetros → píxeles del lienzo. */
function mm(value) {
    return Math.round(value * PX_PER_MM);
}

/** Valor codificado en el QR: solo el CI (máxima legibilidad en térmica). */
export function buildQrValue(participant) {
    return String(participant.ci || '').trim();
}

/**
 * Dibuja el QR del participante en el canvas dado (usa QRious global).
 * Nivel 'H' (máxima corrección de error) para tolerar la impresión térmica.
 */
export function renderQr(canvas, participant, size = 220) {
    if (typeof QRious === 'undefined' || !canvas) return;
    // eslint-disable-next-line no-new
    new QRious({ element: canvas, value: buildQrValue(participant), size, level: 'H' });
}

/** Fija la fuente Arial del contexto en milímetros. */
function setFont(ctx, sizeMm, weight = '') {
    ctx.font = `${weight ? weight + ' ' : ''}${mm(sizeMm)}px Arial, sans-serif`;
}

/** Parte un texto en líneas que caben en maxWidth con la fuente actual. */
function wrapLines(ctx, text, maxWidth) {
    const words = String(text).split(/\s+/).filter(Boolean);
    const lines = [];
    let line = '';
    for (const word of words) {
        const candidate = line ? `${line} ${word}` : word;
        if (line && ctx.measureText(candidate).width > maxWidth) {
            lines.push(line);
            line = word;
        } else {
            line = candidate;
        }
    }
    if (line) lines.push(line);
    return lines.length ? lines : [''];
}

/** Dibuja líneas centradas y devuelve la Y siguiente. */
function drawLines(ctx, lines, centerX, top, lineHeightMm) {
    let cursor = top;
    for (const line of lines) {
        ctx.fillText(line, centerX, cursor);
        cursor += mm(lineHeightMm);
    }
    return cursor;
}

/**
 * Construye el lienzo del sticker (6x7 cm) con nombre, eje, rol, aula y el QR.
 */
export function buildCredentialCanvas(participant) {
    const canvas = document.createElement('canvas');
    canvas.width = mm(STICKER_W_MM);
    canvas.height = mm(STICKER_H_MM);
    const ctx = canvas.getContext('2d');

    // Fondo blanco (la térmica imprime negro sobre blanco).
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Borde tenue como guía de recorte.
    ctx.strokeStyle = GOLD;
    ctx.lineWidth = mm(0.4);
    ctx.strokeRect(mm(1), mm(1), canvas.width - mm(2), canvas.height - mm(2));

    const centerX = canvas.width / 2;
    const contentWidth = canvas.width - mm(4) * 2;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    let cursor = mm(4);

    // Nombre (hasta 2 líneas).
    const name = `${participant.first_name || ''} ${participant.last_name || ''}`
        .trim().toUpperCase();
    ctx.fillStyle = INK;
    setFont(ctx, 5, 'bold');
    cursor = drawLines(ctx, wrapLines(ctx, name, contentWidth).slice(0, 2), centerX, cursor, 6);
    cursor += mm(2);

    // Eje / Rol / Aula. El eje puede ocupar 2 líneas; aula resaltada en dorado.
    const eje = participant.axis_label || participant.axis || '—';
    const rol = participant.role || '—';
    const aula = participant.mesa_code || 'Sin aula';

    setFont(ctx, 3.4);
    ctx.fillStyle = INK;
    cursor = drawLines(ctx, wrapLines(ctx, `Eje: ${eje}`, contentWidth).slice(0, 2), centerX, cursor, 4.4);
    cursor = drawLines(ctx, [`Rol: ${rol}`], centerX, cursor, 4.4);

    setFont(ctx, 4, 'bold');
    ctx.fillStyle = GOLD;
    cursor = drawLines(ctx, [`Aula: ${aula}`], centerX, cursor, 5);
    cursor += mm(2);

    // QR (solo CI): ocupa todo el ancho/alto útil restante para ser bien legible.
    if (typeof QRious !== 'undefined') {
        const bottomPad = mm(4);
        const qrSize = Math.max(mm(20), Math.min(contentWidth, canvas.height - bottomPad - cursor));
        const qrCanvas = document.createElement('canvas');
        // eslint-disable-next-line no-new
        new QRious({ element: qrCanvas, value: buildQrValue(participant), size: qrSize, level: 'H' });
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(qrCanvas, centerX - qrSize / 2, cursor, qrSize, qrSize);
    }

    return canvas;
}

/** Detecta iOS/iPadOS (Safari ignora el atributo download de un enlace). */
function isIOS() {
    const ua = navigator.userAgent || '';
    return /iP(ad|hone|od)/.test(ua) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

/** Convierte un dataURL en Blob de forma síncrona (mantiene el gesto del usuario). */
function dataUrlToBlob(dataUrl) {
    const [head, body] = dataUrl.split(',');
    const mime = (head.match(/:(.*?);/) || [null, 'image/png'])[1];
    const binary = atob(body);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mime });
}

/** Abre la imagen en una pestaña para que en iOS se guarde con "mantener presionado". */
function openImageTab(dataUrl) {
    const win = window.open('', '_blank');
    if (!win) {
        window.location.href = dataUrl;
        return;
    }
    win.document.write(
        '<!doctype html><html><head><meta name="viewport" ' +
        'content="width=device-width,initial-scale=1"><title>Credencial</title></head>' +
        '<body style="margin:0;background:#111;color:#fff;font-family:Arial;text-align:center">' +
        '<p style="padding:12px;font-size:15px">Mantén presionada la imagen y elige ' +
        '<b>Guardar en Fotos</b>.</p>' +
        '<img src="' + dataUrl + '" style="max-width:100%;height:auto"></body></html>'
    );
    win.document.close();
}

/**
 * Genera la credencial como imagen PNG (6x7 cm) y la entrega según la plataforma:
 * Web Share (iOS/Android → Fotos/Archivos), o descarga directa (desktop/Android),
 * o apertura para guardar manualmente en iOS antiguos. Evita el bug de iOS donde
 * el atributo `download` no descarga la imagen.
 */
export function printCredential(participant) {
    const canvas = buildCredentialCanvas(participant);
    const dataUrl = canvas.toDataURL('image/png');
    const filename = `credencial_${String(participant.ci || 'sticker').trim()}.png`;
    const blob = dataUrlToBlob(dataUrl);

    // 1) Web Share con archivo: mejor experiencia en móvil (guarda en Fotos/Archivos).
    if (navigator.canShare) {
        try {
            const file = new File([blob], filename, { type: 'image/png' });
            if (navigator.canShare({ files: [file] })) {
                navigator.share({ files: [file], title: filename })
                    .catch(() => openImageTab(dataUrl));
                return;
            }
        } catch (_) { /* sin soporte de compartir archivos: seguir */ }
    }

    // 2) iOS sin Web Share: abrir la imagen para guardarla manualmente.
    if (isIOS()) {
        openImageTab(dataUrl);
        return;
    }

    // 3) Desktop / Android: descarga directa.
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 15000);
}
