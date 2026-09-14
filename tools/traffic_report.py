'''
    Reporte de visitas de los sitios de BearSoft, leído de los logs de CloudFront.

    Por qué desde los logs y no desde un contador en la página: el contador solo
    ve a quien ejecuta JavaScript, no sobrevive a un bloqueador y depende de un
    tercero que puede cerrar o empezar a cobrar. Los logs los escribe la misma
    CDN que sirve el sitio: cuentan cada petición, no piden nada al visitante y
    no dependen de nadie más.

    Qué cuenta y qué no. Una **página vista** es una petición a un `.html` o a
    la raíz **que el sitio efectivamente sirvió**. Los recursos —CSS, imágenes,
    JavaScript— se descartan, porque una sola página genera veinte peticiones.
    Y se descarta todo lo que terminó en 403 o 404: internet zumba con
    escáneres que piden `/wp-login.php` y `/xmlrpc.php` a cualquier dominio, y
    contarlos multiplicaba el tráfico de BearSoft por diez. Ese ruido no se
    esconde: se informa aparte, al final de cada sitio.

    Una **visita** es una dirección IP distinta en el día, leída de
    `x-forwarded-for` y no de `c-ip`. Los sitios van detrás de Cloudflare, así
    que `c-ip` es el nodo de Cloudflare que reenvió la petición —contarlo era
    contar puntos de presencia de la CDN, no personas.

    No hay países: `c-country` no existe en este formato de log. Lo más cercano
    es el PoP de CloudFront que atendió la petición, que se reporta como tal y
    no como si fuera la ubicación del visitante.

    Uso:
        python -m tools.traffic_report                  # últimos 7 días
        python -m tools.traffic_report --days 30
        python -m tools.traffic_report --site smartdecisions
'''
import argparse
import gzip
import io
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Dict, Iterator, List, Set

import boto3


LOG_BUCKET = 'bearsoft-cloudfront-logs'
PROFILE = 'deploy_ml'

# Cada sitio escribe bajo su propio prefijo, así el reporte puede separarlos.
SITES = {
    'bearsoft': 'bearsoft/',
    'smartdecisions': 'smartdecisions/',
    'raforios': 'raforios/',
}

# Extensiones que no son una página. Una sola visita pide el HTML y luego veinte
# recursos; contarlos todos multiplicaría el tráfico por diez.
ASSET_SUFFIXES = (
    '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2',
    '.map', '.json', '.webp', '.gif'
)

# Peticiones que no vienen de una persona mirando el sitio. Sirve para los bots
# que se identifican; los escáneres de vulnerabilidades se anuncian como un
# Chrome cualquiera y sólo los delata el código de respuesta.
BOT_MARKERS = ('bot', 'crawl', 'spider', 'slurp', 'curl', 'wget', 'headless',
               'monitor', 'preview', 'scan')

# Respuestas que significan "el sitio entregó la página". Todo lo demás es una
# petición a algo que no existe: no es una visita, es alguien probando suerte.
SERVED_STATUSES = ('200', '304', '206')


def _session():
    '''
        Returns the AWS session used to read the logs.

        Returns:
            boto3.Session: Session on the deploy profile.
    '''
    return boto3.Session(profile_name = PROFILE, region_name = 'us-east-1')


def _log_files(prefix: str, since: date) -> Iterator[str]:
    '''
        Lists the log files written on or after a date.

        CloudFront names each file with the date it covers, so the listing can
        be filtered without opening anything.

        Args:
            prefix (str): Site prefix inside the bucket.
            since (date): Earliest day to include.

        Yields:
            str: Object keys.
    '''
    client = _session().client('s3')
    paginator = client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket = LOG_BUCKET, Prefix = prefix):
        for obj in page.get('Contents', []):
            if obj['LastModified'].date() >= since - timedelta(days = 1):
                yield obj['Key']


def _rows(keys: List[str]) -> Iterator[Dict[str, str]]:
    '''
        Reads every log line as a dictionary.

        The files are gzipped TSV with two header lines; the second one names
        the fields, so the parser never hardcodes column positions — CloudFront
        has added fields over the years and a positional parser breaks silently.

        Args:
            keys (List[str]): Object keys to read.

        Yields:
            Dict[str, str]: One request per line.
    '''
    client = _session().client('s3')
    for key in keys:
        body = client.get_object(Bucket = LOG_BUCKET, Key = key)['Body'].read()
        with gzip.open(io.BytesIO(body), 'rt', encoding = 'utf-8') as handle:
            fields: List[str] = []
            for line in handle:
                if line.startswith('#Fields:'):
                    fields = line.split(':', 1)[1].split()
                    continue
                if line.startswith('#') or not fields:
                    continue
                values = line.rstrip('\n').split('\t')
                if len(values) == len(fields):
                    yield dict(zip(fields, values))


def _is_page(uri: str) -> bool:
    '''
        Whether a request is a page view rather than an asset.

        Args:
            uri (str): Requested path.

        Returns:
            bool: True for the root or an HTML document.
    '''
    return not uri.lower().endswith(ASSET_SUFFIXES)


def _is_person(agent: str) -> bool:
    '''
        Whether the user agent looks like a person and not a crawler.

        Crude on purpose: a perfect list is impossible and a wrong exclusion is
        worse than an extra visit.

        Args:
            agent (str): User agent as logged (URL-encoded).

        Returns:
            bool: True when nothing marks it as automated.
    '''
    lowered = agent.lower()
    return not any(marker in lowered for marker in BOT_MARKERS)


def _client(row: Dict[str, str]) -> str:
    '''
        Returns the address of whoever asked, not of whoever relayed it.

        The sites sit behind Cloudflare, so `c-ip` is a Cloudflare edge node and
        counting it counts the CDN's points of presence. The real address
        travels in `x-forwarded-for`; its first hop is the client, the rest are
        the proxies it crossed.

        Args:
            row (Dict[str, str]): One parsed log line.

        Returns:
            str: Client address.
    '''
    forwarded = row.get('x-forwarded-for', '-')
    if forwarded and forwarded != '-':
        return forwarded.split(',')[0].strip()
    return row.get('c-ip', '')


def _collect(rows: Iterator[Dict[str, str]], since: date) -> Dict[str, Any]:
    '''
        Reduces the log lines to the figures the report prints.

        Separates what the site served from what it refused. The status code is
        not enough on its own: SmartDecisions answers every miss with its own
        index.html and a 200, so a scanner asking for `/.git/config` looks like
        a reader. `x-edge-result-type` still says `Error`, and that is what
        settles it.

        Args:
            rows (Iterator[Dict[str, str]]): Parsed log lines.
            since (date): Earliest day to count.

        Returns:
            Dict[str, Any]: Counters by day, page, edge location and referrer.
    '''
    served: List[Dict[str, str]] = []
    probed: Counter = Counter()
    scanners: Set[str] = set()

    for row in rows:
        day = row.get('date', '')
        if not day or date.fromisoformat(day) < since:
            continue
        if not _is_person(row.get('cs(User-Agent)', '')):
            continue
        uri = row.get('cs-uri-stem', '') or '/'
        if not _is_page(uri):
            continue

        result = row.get('x-edge-result-type', '')
        # A redirect is the same visit on its way to the real page; counting it
        # would count that visit twice.
        if result == 'Redirect':
            continue

        if result == 'Error' or row.get('sc-status', '') not in SERVED_STATUSES:
            probed[uri] += 1
            scanners.add(_client(row))
            continue

        served.append({
            'day': day,
            'client': _client(row),
            'uri': uri,
            'edge': row.get('x-edge-location', '???')[:3],
            'referrer': row.get('cs(Referer)', '-'),
        })

    return _reduce(served, probed, scanners)


def _reduce(
    served: List[Dict[str, str]],
    probed: Counter,
    scanners: Set[str]
) -> Dict[str, Any]:
    '''
        Turns the served requests into the published figures.

        Whoever asked for `/wp-login.php` is dropped from the visit count even
        for the pages they did get: they also fetch the home page, and counting
        them there was what made a scan look like an audience.

        Args:
            served (List[Dict[str, str]]): Requests the site answered.
            probed (Counter): Refused paths and how often each was asked for.
            scanners (Set[str]): Addresses that asked for something absent.

        Returns:
            Dict[str, Any]: Counters ready to print.
    '''
    by_day: Dict[str, Set[str]] = defaultdict(set)
    counts: Dict[str, Counter] = {
        name: Counter() for name in ('views', 'pages', 'edges', 'referrers')
    }
    visitors: Set[str] = set()

    for entry in served:
        if entry['client'] in scanners:
            continue
        by_day[entry['day']].add(entry['client'])
        visitors.add(entry['client'])
        counts['views'][entry['day']] += 1
        counts['pages'][entry['uri']] += 1
        counts['edges'][entry['edge']] += 1

        referrer = entry['referrer']
        if referrer and referrer != '-' and 'bearsoft.com.bo' not in referrer:
            source = referrer.split('/')[2] if '//' in referrer else referrer
            counts['referrers'][source] += 1

    return {
        'days': {day: len(ips) for day, ips in sorted(by_day.items())},
        **counts,
        'probed': probed,
        'visitors': len(visitors),
        'rejected': sum(probed.values()),
        'scanners': len(scanners),
        'total_views': sum(counts['views'].values()),
    }


def _print(site: str, data: Dict[str, Any], days: int) -> None:
    '''
        Prints the report.

        Args:
            site (str): Site being reported.
            data (Dict[str, Any]): Collected figures.
            days (int): Window in days.
    '''
    print(f'\n{"=" * 62}')
    print(f'  {site.upper()} — últimos {days} día(s)')
    print(f'{"=" * 62}')

    if not data['total_views']:
        print('  Sin visitas registradas todavía.')
        print('  CloudFront entrega los logs con hasta una hora de retraso.')
        return

    print(f'  Visitantes distintos : {data["visitors"]:,}')
    print(f'  Páginas vistas       : {data["total_views"]:,}')

    print('\n  Por día')
    for day, count in data['days'].items():
        views = data['views'][day]
        chart = '█' * min(40, count)
        print(f'    {day}  {count:>4} visitante(s)  {views:>5} vista(s)  {chart}')

    print('\n  Páginas más vistas')
    for page, count in data['pages'].most_common(8):
        print(f'    {count:>5}  {page}')

    print('\n  Dónde se atendió (PoP de CloudFront, no el país del visitante)')
    for edge, count in data['edges'].most_common(8):
        print(f'    {count:>5}  {edge}')

    if data['referrers']:
        print('\n  De dónde llegaron')
        for source, count in data['referrers'].most_common(6):
            print(f'    {count:>5}  {source}')

    _print_noise(data)


def _print_noise(data: Dict[str, Any]) -> None:
    '''
        Prints the rejected traffic, so the scanning is visible instead of
        inflating the visit count.

        Args:
            data (Dict[str, Any]): Collected figures.
    '''
    if not data['rejected']:
        return

    total = data['rejected'] + data['total_views']
    share = data['rejected'] / total * 100
    print(f'\n  Ruido descartado: {data["rejected"]:,} petición(es) a rutas que '
          f'no existen ({share:.0f}% de todo lo pedido)')
    print(f'    Desde {data["scanners"]:,} dirección(es), que quedan fuera del '
          f'conteo de visitas. Más buscado:')
    for uri, count in data['probed'].most_common(6):
        print(f'      {count:>4}  {uri}')


def main() -> int:
    '''
        Entry point of the report.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(description = 'Visitas desde los logs de CloudFront.')
    parser.add_argument('--days', type = int, default = 7,
                        help = 'Ventana en días. Por defecto 7.')
    parser.add_argument('--site', choices = list(SITES) + ['all'], default = 'all',
                        help = 'Sitio a reportar.')
    args = parser.parse_args()

    since = date.today() - timedelta(days = args.days - 1)
    chosen = SITES if args.site == 'all' else {args.site: SITES[args.site]}

    for site, prefix in chosen.items():
        keys = list(_log_files(prefix, since))
        if not keys:
            print(f'\n  {site.upper()}: todavía no hay archivos de log.')
            print('  CloudFront empieza a entregarlos ~1 h después de activarlos.')
            continue
        _print(site, _collect(_rows(keys), since), args.days)

    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
