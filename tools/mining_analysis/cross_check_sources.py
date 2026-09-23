'''
    Cross-check of the official daily quotations against public sources.

    The Ministry's biweekly report averages the previous fortnight's daily
    quotes from the London markets. This tool takes every daily official value
    stored in `mining_prices` (loaded from the Ministry's own spreadsheets) and
    compares it with what the public sources publish for the same day:

      - LBMA JSON (prices.lbma.org.uk): gold AM, gold PM, silver.
      - Westmetall (LME cash settlement): copper, tin, lead, zinc, USD/t.

    It answers the question the daily-source design depends on: which series,
    exactly, reproduces the official figure — and how far the free proxy sits
    from it when it is not the very same number.

    Usage:
        python tools/mining_analysis/cross_check_sources.py [--profile deploy_ml]
'''
import argparse
import json
import re
import sys
import urllib.request
from collections import defaultdict
from statistics import mean, median
from typing import Dict, List, Tuple

import boto3
from boto3.dynamodb.conditions import Key

LBMA_URL = 'https://prices.lbma.org.uk/json/{series}.json'
WESTMETALL_URL = 'https://www.westmetall.com/en/markdaten.php?action=table&field=LME_{symbol}_cash'
POUNDS_PER_TONNE = 2204.62262
USER_AGENT = 'Mozilla/5.0 (SmartDecisions cross-check)'
MONTHS = {name: index for index, name in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
     'September', 'October', 'November', 'December'], start = 1)}

# Official catalogue id -> how the public source names it. Ids 5-7 (antimony,
# tungsten, bismuth) come from Asian Metal, a paid source, and are not checked.
LBMA_MINERALS = {'8': 'gold', '9': 'silver'}
LME_MINERALS = {'1': 'Sn', '2': 'Pb', '3': 'Zn', '4': 'Cu'}


def fetch(url: str) -> str:
    '''
        Downloads a URL as text with a browser-like agent.

        Args:
            url (str): Address to read.

        Returns:
            str: Body decoded as UTF-8.
    '''
    request = urllib.request.Request(url, headers = {'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout = 60) as response:
        return response.read().decode('utf-8', errors = 'ignore')


def lbma_series(series: str) -> Dict[str, float]:
    '''
        LBMA daily USD fixes keyed by ISO date.

        Args:
            series (str): 'gold_am', 'gold_pm' or 'silver'.

        Returns:
            Dict[str, float]: {date: usd}.
    '''
    rows = json.loads(fetch(LBMA_URL.format(series = series)))
    return {row['d']: row['v'][0] for row in rows if row.get('v') and row['v'][0]}


def westmetall_series(symbol: str) -> Dict[str, float]:
    '''
        LME cash settlement (USD/t) for the current year, keyed by ISO date.

        Args:
            symbol (str): 'Cu', 'Sn', 'Pb' or 'Zn'.

        Returns:
            Dict[str, float]: {date: usd_per_tonne}.
    '''
    html = fetch(WESTMETALL_URL.format(symbol = symbol))
    series: Dict[str, float] = {}
    for row in re.findall(r'<tr>(.*?)</tr>', html, re.S):
        cells = [re.sub(r'<[^>]+>', '', cell).strip()
                 for cell in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]
        match = re.match(r'(\d{2})\. (\w+) (\d{4})', cells[0]) if cells else None
        if not match or len(cells) < 2 or not cells[1]:
            continue
        day, month, year = match.groups()
        iso = f'{year}-{MONTHS[month]:02d}-{day}'
        series[iso] = float(cells[1].replace(',', ''))
    return series


def official_prices(
    profile: str,
    mineral_id: str
) -> Dict[str, float]:
    '''
        Official daily quotations of one mineral as stored in DynamoDB.

        Args:
            profile (str): AWS profile with read access.
            mineral_id (str): Catalogue id.

        Returns:
            Dict[str, float]: {date: price_low}.
    '''
    table = boto3.Session(profile_name = profile, region_name = 'us-east-1') \
        .resource('dynamodb').Table('mining_prices')
    items = table.query(KeyConditionExpression = Key('mineral_id').eq(mineral_id))['Items']
    return {item['date']: float(item['price_low']) for item in items if item.get('price_low')}


def compare(
    official: Dict[str, float],
    source: Dict[str, float],
    scale: float = 1.0
) -> Tuple[int, int, List[float]]:
    '''
        Matches official days with the source and measures the gap.

        Args:
            official (Dict[str, float]): Official values by date.
            source (Dict[str, float]): Source values by date (same unit after `scale`).
            scale (float): Multiplier taking the source into the official unit.

        Returns:
            Tuple[int, int, List[float]]: days compared, exact matches (to the
            official's own rounding), relative gaps in percent.
    '''
    compared, exact, gaps = 0, 0, []
    for day, value in official.items():
        if day not in source:
            continue
        candidate = source[day] * scale
        compared += 1
        # "Exact" = the same figure to the precision the Ministry publishes:
        # anything under 0.01 % is rounding, not a different quotation.
        if abs(candidate - value) / abs(value) < 1e-4:
            exact += 1
        gaps.append(100.0 * (candidate - value) / value)
    return compared, exact, gaps


def report(
    label: str,
    result: Tuple[int, int, List[float]]
) -> None:
    '''
        Prints one comparison line.
    '''
    compared, exact, gaps = result
    if not compared:
        print(f'  {label:26s} sin días comparables')
        return
    share = 100 * exact / compared
    print(f'  {label:26s} {compared:3d} días · exactos {exact:3d} ({share:5.1f} %) · '
          f'desvío mediano {median(gaps):+.3f} % · medio {mean(gaps):+.3f} % · '
          f'máx {max(abs(g) for g in gaps):.3f} %')


def main() -> int:
    '''
        Runs the cross-check and prints the verdict per mineral.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--profile', default = 'deploy_ml')
    args = parser.parse_args()

    print('LBMA (fix oficial):')
    lbma = {name: lbma_series(name) for name in ('gold_am', 'gold_pm', 'silver')}
    gold = official_prices(args.profile, '8')
    silver = official_prices(args.profile, '9')
    report('oro vs AM', compare(gold, lbma['gold_am']))
    report('oro vs PM', compare(gold, lbma['gold_pm']))
    lower = {day: min(lbma['gold_am'].get(day, 1e9), lbma['gold_pm'].get(day, 1e9))
             for day in gold if day in lbma['gold_am'] or day in lbma['gold_pm']}
    report('oro vs menor(AM, PM)', compare(gold, lower))
    report('plata vs fix', compare(silver, lbma['silver']))

    print('Westmetall (LME cash settlement, USD/t -> USD/lb):')
    names = {'1': 'estaño', '2': 'plomo', '3': 'zinc', '4': 'cobre'}
    missing: Dict[str, List[str]] = defaultdict(list)
    for mineral_id, symbol in LME_MINERALS.items():
        source = westmetall_series(symbol)
        official = official_prices(args.profile, mineral_id)
        report(f'{names[mineral_id]} vs settlement',
               compare(official, source, 1 / POUNDS_PER_TONNE))
        missing[symbol] = sorted(day for day in official if day not in source)
    for symbol, days in missing.items():
        if days:
            print(f'  {symbol}: {len(days)} día(s) oficiales sin dato en Westmetall, '
                  f'p. ej. {days[:3]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
