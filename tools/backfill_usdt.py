'''
    Fills the USDT series backwards, from the day the official rate started to
    float (27/06/2026) to the first reading QUOTES took itself.

    Binance P2P only answers the price of now, so QUOTES' own series starts
    the day the daily reading went live (06/10/2026). A comparison against
    the official rate needs the whole floating period, and that history exists
    in a public repository that has read Binance P2P every fifteen minutes
    since August 2024: github.com/mauforonda/dolares, file `buy.csv`.

    Its `naive` column —the most frequent price in the best decile of offers—
    is the figure Binance's quote endpoint returns: on 06/10 both read 11,86.
    A day's value is the median of that day's readings.

    A day QUOTES already read is never overwritten: ours is the reference, the
    backfill only covers what came before it. Each backfilled day says where
    it came from in `source`.

        python -m tools.backfill_usdt                     # simulation
        python -m tools.backfill_usdt --yes
        python -m tools.backfill_usdt --start 2026-06-27 --yes
'''
import argparse
import csv
import io
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

import boto3
import requests
from boto3.dynamodb.conditions import Key
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
QUOTES_ENV = dotenv_values(ROOT / 'services' / 'quotes' / '.env')
TABLE = QUOTES_ENV['DYNAMODB_TABLE_NAME_EXCHANGE_RATES']
CURRENCY = QUOTES_ENV['PARALLEL_CURRENCY']
PROFILE = 'deploy_ml'
REGION = 'us-east-1'

SOURCE_URL = 'https://raw.githubusercontent.com/mauforonda/dolares/main/buy.csv'
SOURCE_NAME = 'BINANCE_P2P_MAUFORONDA'
FLOAT_START = date(2026, 6, 27)
TIMEOUT_SECONDS = 60
PRICE_COLUMN = 'naive'
DECIMALS = 2


def daily_rates(
    text: str,
    start: date
) -> Dict[date, float]:
    '''
        One price per day from the intraday readings.

        Args:
            text (str): The CSV, with `timestamp` and the price column.
            start (date): First day kept.

        Returns:
            Dict[date, float]: Median of each day's readings, from `start`.
    '''
    readings: Dict[date, List[float]] = defaultdict(list)
    for row in csv.DictReader(io.StringIO(text)):
        # The timestamp carries Bolivia's offset: its first ten characters
        # are already the local day.
        day = date.fromisoformat(row['timestamp'][:10])
        if day >= start and row[PRICE_COLUMN]:
            readings[day].append(float(row[PRICE_COLUMN]))
    return {day: round(statistics.median(values), DECIMALS)
            for day, values in sorted(readings.items())}


def stored_days(table) -> set:
    '''
        The days QUOTES already has a USDT reading for.

        Args:
            table: The exchange-rate table.

        Returns:
            set: ISO dates.
    '''
    days, kwargs = set(), {'KeyConditionExpression': Key('currency').eq(CURRENCY)}
    while True:
        page = table.query(**kwargs)
        days.update(item['date'] for item in page['Items'])
        if 'LastEvaluatedKey' not in page:
            return days
        kwargs['ExclusiveStartKey'] = page['LastEvaluatedKey']


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(description = 'Rellena la serie del USDT.')
    parser.add_argument('--start', type = date.fromisoformat, default = FLOAT_START)
    parser.add_argument('--yes', action = 'store_true', help = 'Escribe en DynamoDB.')
    args = parser.parse_args()

    response = requests.get(SOURCE_URL, timeout = TIMEOUT_SECONDS)
    response.raise_for_status()
    rates = daily_rates(response.text, args.start)

    table = boto3.Session(profile_name = PROFILE, region_name = REGION) \
        .resource('dynamodb').Table(TABLE)
    existing = stored_days(table)
    # Only before QUOTES' first reading: a later day it has not read yet is
    # one its daily job will read, and a backfilled value there would make
    # the job skip it.
    first_own = min(existing) if existing else date.today().isoformat()
    missing = {day: rate for day, rate in rates.items() if day.isoformat() < first_own}
    print(f'{len(rates)} día(s) en la fuente; {len(existing)} ya leídos por QUOTES; '
          f'{len(missing)} por rellenar.')
    if missing:
        first, last = min(missing), max(missing)
        print(f'  {first} {missing[first]} … {last} {missing[last]}')
    if not args.yes:
        print('Simulación: no se escribió nada. Repite con --yes.')
        return 0

    retrieved_at = datetime.now(timezone.utc).isoformat()
    with table.batch_writer() as batch:
        for day, rate in missing.items():
            batch.put_item(Item = {
                'currency': CURRENCY, 'date': day.isoformat(),
                'official_rate': Decimal(str(rate)), 'source': SOURCE_NAME,
                'retrieved_at': retrieved_at
            })
    print(f'{len(missing)} día(s) escritos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
