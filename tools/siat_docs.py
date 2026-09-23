'''
    Baja la documentación técnica del SIAT a un solo archivo Markdown.

    El "Anexo Técnico" que la RND 11 menciona no es un PDF: es el sitio
    `siatinfo.impuestos.gob.bo`, repartido en decenas de páginas —los servicios
    SOAP, los XSD de cada tipo de factura, los algoritmos del código de control
    y los códigos de error—. Leerlo página por página cada vez cuesta tiempo y
    tokens; acá se consolida una vez y después se busca con `grep`.

    Sobre el certificado: la cadena TLS del SIAT está mal configurada y ningún
    cliente la valida. Esta herramienta lo salta a propósito y lo dice en el
    encabezado del archivo, porque lo que se baja así **es informativo**: antes
    de implementar contra él, confirmar el documento con el SIN.

    Uso:
        python tools/siat_docs.py                       # las páginas clave
        python tools/siat_docs.py --output docs/siat.md
        python tools/siat_docs.py --index               # lista lo que hay
'''
import argparse
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Tuple

BASE = 'https://siatinfo.impuestos.gob.bo'
INDEX_PATH = '/index.php/informacion/generalidades-sfvl'

# Lo que hace falta para facturar desde BILLING: cómo se autoriza el sistema,
# cómo se obtienen los códigos, cómo se manda la factura y cómo se lee un
# rechazo. El resto del sitio son sectores que no nos tocan.
PAGES: Tuple[Tuple[str, str], ...] = (
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
    # Los algoritmos son lo único del anexo que se implementa tal cual: el CUF
    # lo genera nuestro sistema, no el SIN, y un dígito mal calculado invalida
    # la factura entera.
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
        Un contexto TLS que no valida la cadena.

        Returns:
            ssl.SSLContext: Contexto sin verificación.
    '''
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def fetch(path: str) -> str:
    '''
        El HTML de una página del SIAT.

        Args:
            path (str): Ruta bajo el dominio.

        Returns:
            str: HTML, o cadena vacía si la página ya no existe.
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
        El contenido legible de una página, sin menús ni scripts.

        Args:
            html (str): HTML de la página.

        Returns:
            str: Texto plano con los saltos de párrafo conservados.
    '''
    body = re.sub(r'(?is)<(script|style|nav|header|footer|form).*?</\1>', ' ', html)
    body = re.sub(r'(?i)</(p|div|li|tr|h[1-6])>', '\n', body)
    body = re.sub(r'(?i)<li[^>]*>', '- ', body)
    body = re.sub(r'(?s)<[^>]+>', ' ', body)
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return '\n'.join(line.strip() for line in body.splitlines() if line.strip())


def downloads(html: str) -> List[str]:
    '''
        Los archivos descargables que la página enlaza.

        Args:
            html (str): HTML de la página.

        Returns:
            List[str]: URLs de PDF, XSD, WSDL o ZIP.
    '''
    found = re.findall(r'href="([^"]+\.(?:pdf|xsd|wsdl|zip|xml))"', html, re.I)
    return list(dict.fromkeys(found))


def build_index() -> str:
    '''
        Todo lo que la página de generalidades enlaza, para elegir qué agregar.

        Returns:
            str: Una línea por enlace.
    '''
    html = fetch(INDEX_PATH)
    links = re.findall(r'href="(/index\.php[^"]+)"[^>]*>\s*([^<]{4,90}?)\s*<', html)
    lines = []
    for href, label in dict.fromkeys(links):
        lines.append(f'{label.strip()}\n    {href}')
    return '\n'.join(lines)


def main() -> int:
    '''
        Punto de entrada.

        Returns:
            int: 0 siempre; las páginas caídas se avisan y se saltan.
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
