'''
    Downloads the SIAT technical documentation into a single Markdown file.

    The "Anexo Técnico" that RND 11 mentions is not a PDF: it is the site
    `siatinfo.impuestos.gob.bo`, spread over dozens of pages —the SOAP
    services, the XSD of each invoice type, the control-code algorithms and
    the error codes. Reading it page by page every time costs time and tokens;
    here it is consolidated once and then searched with `grep`.

    About the certificate: the SIAT TLS chain is misconfigured and no client
    validates it. This tool skips it on purpose and says so in the header of
    the file, because what is downloaded this way **is informative**: confirm
    the document with the SIN before implementing against it.

    Usage:
        python tools/siat_docs.py                       # the key pages
        python tools/siat_docs.py --output docs/siat.md
        python tools/siat_docs.py --index               # lists what there is
'''
import argparse
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'https://siatinfo.impuestos.gob.bo'
INDEX_PATH = '/index.php/informacion/generalidades-sfvl'

# What invoicing from BILLING needs: how the system is authorised, how the
# codes are obtained, how an invoice is sent and how a rejection is read. The
# rest of the site covers sectors that are not ours.
PAGES: tuple[tuple[str, str], ...] = (
    ('Proceso de autorización del sistema',
     '/index.php/facturacion-en-linea/autorizacion-de-sistemas/proceso-de-autorizacion'),
    ('Fase I — pruebas',
     '/index.php/facturacion-en-linea/autorizacion-de-sistemas/'
     'pruebas-para-la-autorizacion-del-sistema-de-facturacion/fase-i-pruebas'),
    ('Fase II — inspección',
     '/index.php/facturacion-en-linea/autorizacion-de-sistemas/'
     'pruebas-para-la-autorizacion-del-sistema-de-facturacion/fase-ii-inspeccion'),
    ('Fase III — pruebas piloto',
     '/index.php/facturacion-en-linea/autorizacion-de-sistemas/'
     'pruebas-para-la-autorizacion-del-sistema-de-facturacion/fase-iii-pruebas-piloto'),
    ('Códigos de autorización (CUIS, CUFD, CUF)',
     '/index.php/informacion/codigos-de-autorizacion'),
    ('Servicio: solicitud de CUIS',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/codigos/solicitud-cuis'),
    ('Servicio: solicitud de CUFD',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/codigos/solicitud-cufd'),
    ('Servicio: verificación de NIT',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/codigos/verifica-nit'),
    ('Servicio: registro de punto de venta',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/'
     'operaciones/registro-punto-de-venta'),
    ('Servicio: registro de evento significativo',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/'
     'operaciones/registro-evento-significativo'),
    ('Servicio: recepción de factura computarizada',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/'
     'facturacion-computarizada/recepcion-factura-computarizada'),
    ('Servicio: recepción factura compra-venta',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/'
     'servicio-factura-compra-venta/recepcion-factura-compra-venta'),
    ('XSD: factura de compra y venta',
     '/index.php/facturacion-en-linea/archivos-xml-xsd-de-facturas-electronicas/'
     'factura-de-compra-y-venta'),
    ('Algoritmo del código de control',
     '/index.php/facturacion-manual/algoritmos/codigo-de-control'),
    ('Códigos de error del SIAT',
     '/index.php/facturacion-en-linea/implementacion-servicios-facturacion/codigos-error-siat'),
    # The algorithms are the only part of the annex implemented as they are:
    # our system generates the CUF, not the SIN, and one wrong digit voids the
    # whole invoice.
    ('Algoritmo: generación del CUF',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/generacion-cuf'),
    ('Algoritmo: módulo 11 (dígito autoverificador)',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/algoritmo-modulo-11'),
    ('Algoritmo: base 16',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/base-16'),
    ('Algoritmo: SHA-256, MD5 y CRC32',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/generacion-de-sha-256-md5-y-crc32'),
    ('Algoritmo: código QR',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/codigo-respuesta-rapida-qr'),
    ('Algoritmo: compresión GZIP',
     '/index.php/facturacion-en-linea/algoritmos-utilizados/comprimir-gzip'),
    ('Homologación de productos y servicios',
     '/index.php/facturacion-en-linea/requerimientos/homologacion-de-productos-servicios'),
    ('Sucursales y puntos de venta',
     '/index.php/facturacion-en-linea/requerimientos/sucursales-y-puntos-de-venta'),
)


def _context() -> ssl.SSLContext:
    '''
        A TLS context that does not validate the chain.

        Returns:
            ssl.SSLContext: Context without verification.
    '''
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def fetch(path: str) -> str:
    '''
        The HTML of one SIAT page.

        Args:
            path (str): Path under the domain.

        Returns:
            str: HTML, or an empty string when the page no longer exists.
    '''
    try:
        with urllib.request.urlopen(BASE + path, timeout = 30,
                                    context = _context()) as response:
            return response.read().decode('utf-8', 'replace')
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        print(f'  aviso: {path} → {error}', file = sys.stderr)
        return ''


def to_text(html: str) -> str:
    '''
        The readable content of a page, without menus or scripts.

        Args:
            html (str): The page's HTML.

        Returns:
            str: Plain text, paragraph breaks kept.
    '''
    body = re.sub(r'(?is)<(script|style|nav|header|footer|form).*?</\1>', ' ', html)
    body = re.sub(r'(?i)</(p|div|li|tr|h[1-6])>', '\n', body)
    body = re.sub(r'(?i)<li[^>]*>', '- ', body)
    body = re.sub(r'(?s)<[^>]+>', ' ', body)
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return '\n'.join(line.strip() for line in body.splitlines() if line.strip())


def downloads(html: str) -> list[str]:
    '''
        The downloadable files the page links to.

        Args:
            html (str): The page's HTML.

        Returns:
            list[str]: URLs of PDF, XSD, WSDL or ZIP files.
    '''
    found = re.findall(r'href="([^"]+\.(?:pdf|xsd|wsdl|zip|xml))"', html, re.I)
    return list(dict.fromkeys(found))


def build_index() -> str:
    '''
        Everything the overview page links to, to choose what to add.

        Returns:
            str: One line per link.
    '''
    html = fetch(INDEX_PATH)
    links = re.findall(r'href="(/index\.php[^"]+)"[^>]*>\s*([^<]{4,90}?)\s*<', html)
    lines = []
    for href, label in dict.fromkeys(links):
        lines.append(f'{label.strip()}\n    {href}')
    return '\n'.join(lines)


def main() -> int:
    '''
        Entry point.

        Returns:
            int: Always 0; pages that are down are reported and skipped.
    '''
    parser = argparse.ArgumentParser(
        description = 'Consolida la documentación técnica del SIAT en un Markdown.'
    )
    parser.add_argument('--output', type = Path, default = Path('SIAT.md'))
    parser.add_argument('--index', action = 'store_true',
                        help = 'Sólo lista los enlaces disponibles.')
    args = parser.parse_args()

    if args.index:
        print(build_index())
        return 0

    parts = [
        '# SIAT — documentación técnica\n',
        'Consolidado de `siatinfo.impuestos.gob.bo` con `tools/siat_docs.py`.\n',
        '> **La cadena TLS del sitio no valida y la descarga la omite.** Lo de acá\n'
        '> es informativo: antes de implementar, confirmar con el SIN.\n'
    ]
    for title, path in PAGES:
        print(f'  {title}')
        html = fetch(path)
        if not html:
            continue
        parts.append(f'\n---\n\n## {title}\n\n`{BASE}{path}`\n')
        parts.append(to_text(html))
        for url in downloads(html):
            parts.append(f'\n**Descarga:** {url}')

    body = '\n'.join(parts)
    args.output.write_text(body, encoding = 'utf-8')
    print(f'\n{args.output} · {len(body):,} caracteres')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
