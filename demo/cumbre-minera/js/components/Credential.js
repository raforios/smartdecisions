/**
 * Credencial de participante (QR imprimible).
 *
 * Reutilizable desde Registro (al crear) y desde Participantes (reimpresión).
 * El QR codifica todos los datos del participante en JSON; el lector de
 * asistencia extrae el `ci` de ahí (ver asistencia.js#extractCi).
 */

/** Construye el contenido JSON del QR con los datos del participante. */
export function buildQrValue(participant) {
    return JSON.stringify({
        ci: participant.ci,
        nombre: `${participant.first_name || ''} ${participant.last_name || ''}`.trim(),
        institucion: participant.institution_name || participant.company || '',
        rol: participant.role || '',
        eje: participant.axis_label || participant.axis || '',
        aula: participant.mesa_code || ''
    });
}

/** Dibuja el QR del participante en el canvas dado (usa QRious global). */
export function renderQr(canvas, participant) {
    if (typeof QRious === 'undefined' || !canvas) return;
    // Nivel 'M' mantiene legible el (mayor) payload JSON a un tamaño razonable.
    // eslint-disable-next-line no-new
    new QRious({ element: canvas, value: buildQrValue(participant), size: 200, level: 'M' });
}

/**
 * Abre la ventana de impresión de la credencial (96mm x 150mm) para un
 * participante. Genera el QR en un canvas temporal, así funciona tanto al
 * registrar como al reimprimir desde el listado.
 */
export function printCredential(participant) {
    const canvas = document.createElement('canvas');
    renderQr(canvas, participant);
    const qrDataUrl = (typeof QRious !== 'undefined') ? canvas.toDataURL('image/png') : '';

    const seated = participant.mesa_code;
    const seat = seated
        ? `<div class="seat">
               <div class="eje">${escapeHtml(participant.axis_label || participant.axis || '')}</div>
               <div class="aula"><span>Aula</span> ${escapeHtml(participant.mesa_code)}</div>
           </div>`
        : '<p class="rotativa"><strong>Asistencia rotativa</strong> — sin mesa fija</p>';
    const institution = participant.institution_name || participant.company || '';

    const win = window.open('', '_blank', 'width=420,height=640');
    if (!win) return;
    win.document.write(`
        <html><head><title>Credencial ${escapeHtml(participant.ci)}</title>
        <style>
            @page { size: 96mm 150mm; margin: 0; }
            * { box-sizing: border-box; }
            html, body { margin:0; padding:0; }
            body { width:96mm; min-height:150mm; font-family: Arial, sans-serif;
                   text-align:center; padding:8mm 6mm; color:#242732; }
            h1 { font-size:13px; margin:0 0 8px; color:#8B6914; }
            .name { font-size:18px; font-weight:bold; margin:4px 0 2px; }
            p { margin:2px 0; font-size:12px; }
            .inst { font-size:12px; font-weight:bold; }
            .seat { margin:8px auto; padding:6px 8px; border:1px solid #C9A751;
                    border-radius:8px; background:rgba(201,167,81,0.12); }
            .seat .eje { font-size:13px; font-weight:bold; line-height:1.25; }
            .seat .aula { margin-top:4px; font-size:13px; font-weight:bold; color:#8B6914; }
            .seat .aula span { display:block; font-size:8px; letter-spacing:1px;
                    text-transform:uppercase; font-weight:500; }
            .rotativa { color:#666; font-style:italic; }
            img.qr { margin-top:8px; width:30mm; height:30mm; }
            .cap { font-size:10px; color:#666; margin-top:3px; }
        </style></head><body onload="window.print()">
            <h1>Cumbre Minera 2026</h1>
            <div class="name">${escapeHtml(participant.first_name)} ${escapeHtml(participant.last_name)}</div>
            <p><strong>CI:</strong> ${escapeHtml(participant.ci)}</p>
            ${institution ? `<p class="inst">${escapeHtml(institution)}</p>` : ''}
            ${participant.role ? `<p><strong>Rol:</strong> ${escapeHtml(participant.role)}</p>` : ''}
            ${seat}
            <img class="qr" src="${qrDataUrl}" alt="QR">
            <div class="cap">Escanea para registrar asistencia</div>
        </body></html>
    `);
    win.document.close();
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
