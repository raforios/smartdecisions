'''
    Reporte de visitas de los sitios de BearSoft, leído de los logs de CloudFront.

    Por qué desde los logs y no desde un contador en la página: el contador solo
    ve a quien ejecuta JavaScript, no sobrevive a un bloqueador y depende de un
    tercero que puede cerrar o empezar a cobrar. Los logs los escribe la misma
    CDN que sirve el sitio: cuentan cada petición, no piden nada al visitante y
    no dependen de nadie más.

    Qué cuenta y qué no. Una **visita** aquí es una dirección IP distinta en el
    día; una **página vista** es una petición a un `.html` o a la raíz. Los
    recursos —CSS, imágenes, JavaScript— se descartan, porque una sola página
    genera veinte peticiones y contarlas infla el número diez veces. No es
    analítica de sesiones: es tráfico real, sin adivinanzas.

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
}

# Extensiones que no son una página. Una sola visita pide el HTML y luego veinte
# recursos; contarlos todos multiplicaría el tráfico por diez.
ASSET_SUFFIXES = (
    '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2',
    '.map', '.json', '.webp', '.gif'
)

# Peticiones que no vienen de una persona mirando el sitio.
BOT_MARKERS = ('bot', 'crawl', 'spider', 'slurp', 'curl', 'wget', 'headless',
               'monitor', 'preview', 'scan')


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


def _collect(rows: Iterator[Dict[str, str]], since: date) -> Dict[str, Any]:
    '''
        Reduces the log lines to the figures the report prints.

        Args:
            rows (Iterator[Dict[str, str]]): Parsed log lines.
            since (date): Earliest day to count.

        Returns:
            Dict[str, Any]: Counters by day, page, country and referrer.
    '''
    by_day: Dict[str, Set[str]] = defaultdict(set)
    views_by_day: Counter = Counter()
    pages: Counter = Counter()
    countries: Counter = Counter()
    referrers: Counter = Counter()
    visitors: Set[str] = set()

    for row in rows:
        day = row.get('date', '')
        if not day or date.fromisoformat(day) < since:
            continue
        if not _is_person(row.get('cs(User-Agent)', '')):
            continue
        if not _is_page(row.get('cs-uri-stem', '')):
            continue

        ip = row.get('c-ip', '')
        by_day[day].add(ip)
        visitors.add(ip)
        views_by_day[day] += 1
        pages[row.get('cs-uri-stem', '/')] += 1
        countries[row.get('c-country', '??')] += 1

        referrer = row.get('cs(Referer)', '-')
        if referrer and referrer != '-' and 'bearsoft.com.bo' not in referrer:
            referrers[referrer.split('/')[2] if '//' in referrer else referrer] += 1

    return {
        'days': {day: len(ips) for day, ips in sorted(by_day.items())},
        'views': views_by_day,
        'pages': pages,
        'countries': countries,
        'referrers': referrers,
        'visitors': len(visitors),
        'total_views': sum(views_by_day.values()),
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

    print('\n  Países')
    for country, count in data['countries'].most_common(8):
        print(f'    {count:>5}  {country}')

    if data['referrers']:
        print('\n  De dónde llegaron')
        for source, count in data['referrers'].most_common(6):
            print(f'    {count:>5}  {source}')


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
