'''
    Public daily sources of the quotations the Ministry averages.

    Cross-checked against 115 official daily values per mineral (April to
    September 2026, `tools/mining_analysis/cross_check_sources.py`):

      - Gold: the LBMA AM fix, exact on 111 of 115 days (the other four are
        typing errors in the official spreadsheet).
      - Silver: the LBMA fix, exact on 114 of 115 days.
      - Copper, tin, lead, zinc: the LME cash *buyer* price, which no free
        source publishes; the cash *settlement* Westmetall republishes sits
        0.01-0.1 % above it. Irrelevant for the rate, and stated as such.
      - Antimony, tungsten, bismuth: Asian Metal, a paid source. No feed.

    Prices are stored in the unit the Ministry publishes: USD per troy ounce
    for the fixes, USD per fine pound for the LME metals.
'''
import re
from datetime import date as date_type, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import requests
from boto3.resources.base import ServiceResource

from models.market_prices import MarketPriceItem
from schemas.market import MarketError, MarketSource, MarketSyncResult
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.prices_dyb import put_market_prices, query_market_prices
from services.mining_analysis import OFFICIAL_MINERALS, normalize_name
from services.prices_store import list_minerals
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'LBMA_PRICES_URL': str,
    'WESTMETALL_TABLE_URL': str,
    'MARKET_SOURCE_TIMEOUT_SECONDS': int,
    'MARKET_SYNC_DAYS': int,
    'PRICE_DECIMALS': int
})
LBMA_PRICES_URL = ENV_VARS['LBMA_PRICES_URL']
WESTMETALL_TABLE_URL = ENV_VARS['WESTMETALL_TABLE_URL']
SOURCE_TIMEOUT = ENV_VARS['MARKET_SOURCE_TIMEOUT_SECONDS']
MARKET_SYNC_DAYS = ENV_VARS['MARKET_SYNC_DAYS']
PRICE_DECIMALS = ENV_VARS['PRICE_DECIMALS']

# Unit conversion, not a business choice: one metric tonne in avoirdupois pounds.
POUNDS_PER_TONNE = 2204.62262
_USER_AGENT = 'SmartDecisions/1.0 (BearSoft; daily quotation sync)'
_MONTHS = {name: index for index, name in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
     'September', 'October', 'November', 'December'], start = 1)}

Series = Dict[date_type, float]


def _get(url: str) -> str:
    '''
        Reads a source, or SOURCE_UNAVAILABLE.
    '''
    try:
        response = requests.get(
            url, headers = {'User-Agent': _USER_AGENT}, timeout = SOURCE_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as error:
        error_msg = f'Market source unavailable: {url} ({error}).'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNAVAILABLE.value) from error
    return response.text


def fetch_lbma(series: str) -> Series:
    '''
        The LBMA's own JSON of a fix: USD value per date.

        Args:
            series (str): 'gold_am' or 'silver'.

        Returns:
            Series: {date: usd_per_troy_ounce}.
    '''
    try:
        rows = requests.get(f'{LBMA_PRICES_URL}/{series}.json',
                            headers = {'User-Agent': _USER_AGENT}, timeout = SOURCE_TIMEOUT)
        rows.raise_for_status()
        payload = rows.json()
    except requests.RequestException as error:
        error_msg = f'LBMA {series} unavailable: {error}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNAVAILABLE.value) from error
    except ValueError as error:
        error_msg = f'LBMA {series} answered something that is not JSON.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNREADABLE.value) from error
    result: Series = {}
    for row in payload:
        values = row.get('v') or []
        if values and values[0]:
            result[date_type.fromisoformat(row['d'])] = float(values[0])
    return result


def parse_westmetall_table(html: str) -> Series:
    '''
        Westmetall's yearly table of an LME metal: cash settlement in USD/t.

        Args:
            html (str): The page.

        Returns:
            Series: {date: usd_per_tonne}.
    '''
    result: Series = {}
    for row in re.findall(r'<tr>(.*?)</tr>', html, re.S):
        cells = [re.sub(r'<[^>]+>', '', cell).strip()
                 for cell in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]
        match = re.match(r'(\d{2})\. (\w+) (\d{4})', cells[0]) if cells else None
        if not match or len(cells) < 2 or not cells[1] or match.group(2) not in _MONTHS:
            continue
        day, month, year = match.groups()
        try:
            when = date_type(int(year), _MONTHS[month], int(day))
            result[when] = float(cells[1].replace(',', ''))
        except ValueError:
            continue
    if not result:
        error_msg = 'Westmetall table had no readable rows; the page layout may have changed.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNREADABLE.value)
    return result


def fetch_westmetall(symbol: str) -> Series:
    '''
        LME cash settlement of one metal as USD per fine pound.

        Args:
            symbol (str): 'Cu', 'Sn', 'Pb' or 'Zn'.

        Returns:
            Series: {date: usd_per_pound} rounded to PRICE_DECIMALS.
    '''
    # `%s`, not `{symbol}`: the deploy hands the whole .env to
    # `--environment Variables={...}`, whose parser treats a brace as the
    # start of a nested structure and rejects the value.
    per_tonne = parse_westmetall_table(_get(WESTMETALL_TABLE_URL % symbol))
    return {day: round(value / POUNDS_PER_TONNE, PRICE_DECIMALS)
            for day, value in per_tonne.items()}


# ---------------------------------------------------------------------------
# Which source quotes which mineral
# ---------------------------------------------------------------------------
Fetcher = Callable[[], Series]


def source_for(name: str) -> Optional[Tuple[MarketSource, Fetcher, str, str]]:
    '''
        The daily source of a catalogue mineral, by its published metadata.

        Args:
            name (str): Mineral name as stored.

        Returns:
            Optional tuple (source, fetcher, symbol, unit), None for the
            Asian Metal minerals that have no free feed.
    '''
    entry = next((item for item in OFFICIAL_MINERALS
                  if normalize_name(item['name']) == normalize_name(name)), None)
    if entry is None:
        return None
    symbol, unit, market = entry['chemical_symbol'], entry['unit'], entry['quoted_in']
    if market == 'LFIX' and symbol == 'Au':
        return MarketSource.LBMA_GOLD_AM, lambda: fetch_lbma('gold_am'), symbol, unit
    if market == 'LFIX' and symbol == 'Ag':
        return MarketSource.LBMA_SILVER, lambda: fetch_lbma('silver'), symbol, unit
    if market == 'LME':
        return MarketSource.LME_CASH_WESTMETALL, lambda: fetch_westmetall(symbol), symbol, unit
    return None


class _SourceReader:
    '''
        Reads each source series once per run and remembers which failed.
    '''

    def __init__(self) -> None:
        self.series: Dict[str, Series] = {}
        self.failed: List[MarketSource] = []

    def read(
        self,
        source: MarketSource,
        symbol: str,
        fetcher: Fetcher
    ) -> Series:
        '''
            The series of one source/symbol, fetched on first use; empty when
            the source could not be read.

            Args:
                source (MarketSource): Which source.
                symbol (str): Metal symbol (several metals share a source).
                fetcher (Fetcher): How to read it.

            Returns:
                Series: The daily values, or {} on failure.
        '''
        key = f'{source.value}:{symbol}'
        if key not in self.series:
            try:
                self.series[key] = fetcher()
            except ServiceUnavailableError:
                self.series[key] = {}
                if source not in self.failed:
                    self.failed.append(source)
        return self.series[key]

    def failures(self) -> List[MarketSource]:
        '''
            The sources that could not be read in this run, once each.

            Returns:
                List[MarketSource]: Failed sources in the order they failed.
        '''
        return list(self.failed)


def _missing_rows(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    source: MarketSource,
    series: Series,
    window: Tuple[date_type, date_type]
) -> Tuple[List[MarketPriceItem], int, int]:
    '''
        The window days the store lacks and the source has.

        Args:
            mineral_id (str): Catalogue id.
            source (MarketSource): Where the values come from.
            series (Series): The source values by date.
            window (Tuple[date, date]): First and last day, inclusive.

        Returns:
            Tuple[List[MarketPriceItem], int, int]: rows to write, days already
            present, days without publication.
    '''
    start, end = window
    stamp = get_current_time_gmt().isoformat(timespec = 'seconds')
    existing = {
        item.date
        for item in query_market_prices(dynamodb_resource, mineral_id, {'from': start, 'to': end})
    }
    rows: List[MarketPriceItem] = []
    present, missing = 0, 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days = offset)
        if day in existing:
            present += 1
        elif day in series:
            rows.append(MarketPriceItem(
                mineral_id = mineral_id, date = day, price = round(series[day], PRICE_DECIMALS),
                source = source.value, retrieved_at = stamp
            ))
        else:
            missing += 1
    return rows, present, missing


def sync_market_prices(
    dynamodb_resource: ServiceResource,
    days_back: int
) -> MarketSyncResult:
    '''
        Reads every source once and stores the days of the window that were
        missing. A source that fails is reported and skipped; the others land.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            days_back (int): Window length ending today, inclusive.

        Returns:
            MarketSyncResult: What happened.
    '''
    now = get_current_time_gmt()
    window = (now.date() - timedelta(days = days_back - 1), now.date())
    reader = _SourceReader()
    totals = {'stored': 0, 'present': 0, 'missing': 0}
    for mineral in list_minerals(dynamodb_resource):
        resolved = source_for(mineral.name)
        if resolved is None:
            continue
        series = reader.read(resolved[0], resolved[2], resolved[1])
        if not series:
            continue
        rows, present, missing = _missing_rows(
            dynamodb_resource, mineral.mineral_id, resolved[0], series, window
        )
        totals['stored'] += put_market_prices(dynamodb_resource, rows)
        totals['present'] += present
        totals['missing'] += missing
    message = (f'Market sync {window[0]}..{window[1]}: {totals["stored"]} stored, '
               f'{totals["present"]} present, {totals["missing"]} without publication, '
               f'failed sources {[s.value for s in reader.failures()]}.')
    logger.info(message)
    return MarketSyncResult(
        requested_days = days_back, date_from = window[0], date_to = window[1],
        stored = totals['stored'], already_present = totals['present'],
        without_publication = totals['missing'], failed_sources = reader.failures()
    )


def scheduled_sync(dynamodb_resource: ServiceResource) -> MarketSyncResult:
    '''
        The daily run: repairs MARKET_SYNC_DAYS days back.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            MarketSyncResult: What happened.
    '''
    return sync_market_prices(dynamodb_resource, MARKET_SYNC_DAYS)
