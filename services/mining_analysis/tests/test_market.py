'''
    Tests for the market side of the quotations: the public sources, the daily
    sync into DynamoDB (moto), the Art. 227 scales and the anticipated official
    quotation they produce. The official series is patched, not read.
'''
from datetime import date, datetime, timezone
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from models.market_prices import MarketPriceItem, RoyaltyRuleItem
from schemas.market import (
    EstimateConfidence,
    MarketError,
    MarketSource,
    MarketSyncResult,
    RateBasis,
    RoyaltyRuleSchema
)
from services import market_sources, official_estimate, prices_dyb, royalty_rules, utils
from services.exceptions import InvalidInputError, RegisterNotFoundError, ServiceUnavailableError
from services.prices_store import MineralRecord

CATALOGUE = [
    MineralRecord('1', 'Estaño'), MineralRecord('4', 'Cobre'), MineralRecord('5', 'Antimonio'),
    MineralRecord('8', 'Oro'), MineralRecord('9', 'Plata')
]
WESTMETALL_HTML = '''
<table>
<tr><th>Date</th><th>LME Copper Cash-Settlement</th><th>3-month</th><th>stock</th></tr>
<tr><td>15. September 2026</td><td>14,045.00</td><td>14,077.00</td><td>255,100</td></tr>
<tr><td>14. September 2026</td><td>14,044.00</td><td>14,065.50</td><td>255,900</td></tr>
<tr><td>13. September 2026</td><td></td><td></td><td></td></tr>
</table>
'''


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''
        Both market tables, mocked. The resource is handed to every call the
        way a route hands it over, so the test exercises the real contract.
    '''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        for name in (prices_dyb.MARKET_TABLE, prices_dyb.RULES_TABLE):
            schema = [{'AttributeName': 'mineral_id', 'KeyType': 'HASH'}]
            definitions = [{'AttributeName': 'mineral_id', 'AttributeType': 'S'}]
            if name == prices_dyb.MARKET_TABLE:
                schema.append({'AttributeName': 'date', 'KeyType': 'RANGE'})
                definitions.append({'AttributeName': 'date', 'AttributeType': 'S'})
            resource.create_table(TableName = name, KeySchema = schema,
                                  AttributeDefinitions = definitions,
                                  BillingMode = 'PAY_PER_REQUEST')
        yield resource


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def test_parse_westmetall_table_reads_dates_and_settlement():
    '''Rows with a settlement become dated USD/t values; empty days are skipped.'''
    series = market_sources.parse_westmetall_table(WESTMETALL_HTML)
    assert series == {date(2026, 9, 15): 14045.0, date(2026, 9, 14): 14044.0}
    with pytest.raises(ServiceUnavailableError) as failure:
        market_sources.parse_westmetall_table(
            '<html><table><tr><td>nothing</td></tr></table></html>'
        )
    assert failure.value.detail == MarketError.SOURCE_UNREADABLE.value


def test_fetch_westmetall_converts_tonnes_to_fine_pounds():
    '''
        14,045 USD/t settlement is 6.3707 USD/lb; the Ministry printed 6.3703
        that day from the cash buyer (14,044): the gap the module documents.
    '''
    with patch.object(market_sources, '_get', lambda url: WESTMETALL_HTML):
        series = market_sources.fetch_westmetall('Cu')
    assert series[date(2026, 9, 15)] == 6.3707


def test_fetch_lbma_reads_the_usd_value_and_refuses_bad_answers():
    '''The first value of each row is the USD fix; a non-JSON body is unreadable.'''
    class _Response:
        '''A stand-in for requests.Response with a fixed JSON body.'''
        def __init__(
            self,
            payload: object
        ) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            '''Never fails: the transport is not what these tests exercise.'''

        def json(self) -> object:
            '''The body, or the ValueError a non-JSON body raises.'''
            if self._payload is None:
                raise ValueError('not json')
            return self._payload
    rows = [{'d': '2026-09-01', 'v': [4367.25, 3223.9, 3765.88]},
            {'d': '2026-09-02', 'v': [0, 0, 0]}]
    with patch.object(market_sources.requests, 'get', lambda *a, **k: _Response(rows)):
        assert market_sources.fetch_lbma('gold_am') == {date(2026, 9, 1): 4367.25}
    with patch.object(market_sources.requests, 'get', lambda *a, **k: _Response(None)):
        with pytest.raises(ServiceUnavailableError) as failure:
            market_sources.fetch_lbma('gold_am')
    assert failure.value.detail == MarketError.SOURCE_UNREADABLE.value


def test_source_for_follows_the_published_catalogue():
    '''Gold -> LBMA AM, silver -> LBMA silver, LME metals -> Westmetall, Asian Metal -> none.'''
    assert market_sources.source_for('Oro')[0] is MarketSource.LBMA_GOLD_AM
    assert market_sources.source_for('Plata')[0] is MarketSource.LBMA_SILVER
    assert market_sources.source_for('Cobre')[0] is MarketSource.LME_CASH_WESTMETALL
    assert market_sources.source_for('estano')[0] is MarketSource.LME_CASH_WESTMETALL
    assert market_sources.source_for('Antimonio') is None
    assert market_sources.source_for('Kriptonita') is None


def test_sync_market_prices_stores_missing_days_once(dynamodb):
    '''First run stores what the sources have; second run finds it present.'''
    today = date(2026, 9, 15)
    series = {'Au': {date(2026, 9, 14): 4286.65, date(2026, 9, 15): 4265.5},
              'Ag': {date(2026, 9, 15): 63.17},
              'Cu': {date(2026, 9, 14): 6.3698, date(2026, 9, 15): 6.3703}}

    def fake_source(name):
        symbol = {'Oro': 'Au', 'Plata': 'Ag', 'Cobre': 'Cu', 'Estaño': 'Sn'}.get(name)
        if symbol == 'Sn':
            def failing():
                raise ServiceUnavailableError(detail = MarketError.SOURCE_UNAVAILABLE.value)
            return MarketSource.LME_CASH_WESTMETALL, failing, 'Sn', 'LF'
        if symbol is None:
            return None
        source = {'Au': MarketSource.LBMA_GOLD_AM, 'Ag': MarketSource.LBMA_SILVER,
                  'Cu': MarketSource.LME_CASH_WESTMETALL}[symbol]
        return source, lambda: series[symbol], symbol, 'OT'

    now = datetime(2026, 9, 15, 12, 0, tzinfo = timezone.utc)
    with patch.object(market_sources, 'list_minerals', lambda resource: CATALOGUE), \
         patch.object(market_sources, 'source_for', fake_source), \
         patch.object(market_sources, 'get_current_time_gmt', lambda: now):
        first = market_sources.sync_market_prices(dynamodb, 3)
        second = market_sources.sync_market_prices(dynamodb, 3)

    assert (first.stored, first.already_present) == (5, 0)
    assert first.failed_sources == [MarketSource.LME_CASH_WESTMETALL]
    assert first.without_publication == 4          # 3-day window x 3 minerals = 9 slots, 5 filled
    assert (second.stored, second.already_present) == (0, 5)
    stored = prices_dyb.query_market_prices(dynamodb, '4', {'from': date(2026, 9, 13), 'to': today})
    assert [(item.date, item.price, item.source) for item in stored] == [
        (date(2026, 9, 14), 6.3698, 'LME_CASH_WESTMETALL'),
        (date(2026, 9, 15), 6.3703, 'LME_CASH_WESTMETALL')
    ]


# ---------------------------------------------------------------------------
# Art. 227
# ---------------------------------------------------------------------------
def test_apply_rule_walks_floor_formula_and_cap():
    '''Copper at 6.52 caps at 5 %; gold at 550 sits on the formula; zinc at 0.40 floors at 1 %.'''
    rules = {rule.mineral_id: rule for rule in royalty_rules.default_rules()}
    assert royalty_rules.apply_rule(rules['4'], 6.52) == (5.0, 3.0, RateBasis.CAP)
    assert royalty_rules.apply_rule(rules['8'], 550.0) == (5.5, 3.3, RateBasis.FORMULA)
    assert royalty_rules.apply_rule(rules['3'], 0.40) == (1.0, 0.6, RateBasis.FLOOR)
    fixed = RoyaltyRuleItem(mineral_id = 'x', slope = 0, intercept = 0, min_rate = 3.5,
                            max_rate = 3.5, internal_factor = 0.6, legal_basis = 'Ley 535')
    assert royalty_rules.apply_rule(fixed, 999.0) == (3.5, 2.1, RateBasis.FIXED)


def test_default_rules_reproduce_the_ministry_report():
    '''The September report: every mineral capped, gold 7 %, silver 6 %, the rest 5 %.'''
    rules = {rule.mineral_id: rule for rule in royalty_rules.default_rules()}
    officials = {'1': 24.52, '2': 0.84, '3': 1.84, '4': 6.52, '5': 18575.0,
                 '6': 61028.20, '7': 13.30, '8': 4368.79, '9': 64.93}
    expected = {'8': 7.0, '9': 6.0}
    for mineral_id, quotation in officials.items():
        export, internal, basis = royalty_rules.apply_rule(rules[mineral_id], quotation)
        assert export == expected.get(mineral_id, 5.0)
        assert internal == round(export * 0.6, 3)
        assert basis is RateBasis.CAP


def test_ensure_rules_seeds_once_and_keeps_edits(dynamodb):
    '''An empty table gets the seed; an edited rule survives later reads.'''
    seeded = royalty_rules.ensure_rules(dynamodb)
    assert len(seeded) == 9
    royalty_rules.save_rule(dynamodb, RoyaltyRuleSchema(
        mineral_id = '4', slope = 3.0, intercept = -1.0, min_rate = 1.0, max_rate = 5.0,
        internal_factor = 0.6, legal_basis = 'prueba'
    ))
    again = royalty_rules.rules_by_mineral(dynamodb)
    assert len(again) == 9 and again['4'].slope == 3.0 and again['4'].legal_basis == 'prueba'
    with pytest.raises(RegisterNotFoundError):
        royalty_rules.rule_for(dynamodb, '99')


# ---------------------------------------------------------------------------
# Estimate
# ---------------------------------------------------------------------------
def _seed_market(
    dynamodb_resource,
    prices
):
    '''
        Stores (mineral_id, date, price, source) rows.
    '''
    prices_dyb.put_market_prices(dynamodb_resource, [
        MarketPriceItem(mineral_id = mineral, date = day, price = price, source = source)
        for mineral, day, price, source in prices
    ])


def test_estimate_row_averages_the_fortnight_and_applies_the_scale(dynamodb):
    '''
        Gold quoted 4 days at 4300 against 4368.79 in force: -1.57 %, 7 % cap,
        MEDIUM confidence; antimony has no source; a mineral with no days is NONE.
    '''
    _seed_market(dynamodb, [('8', date(2026, 9, 16 + offset), 4300.0, 'LBMA_GOLD_AM')
                            for offset in range(4)])
    officials = {'8': (4368.79, 10), '5': (18575.0, 4), '4': (6.52, 11)}
    with patch.object(official_estimate, 'average_low',
                      lambda resource, mineral_id, window: officials.get(mineral_id)):
        gold = official_estimate.estimate_row(dynamodb, '8', 'Oro', date(2026, 9, 21))
        antimony = official_estimate.estimate_row(dynamodb, '5', 'Antimonio', date(2026, 9, 21))
        copper = official_estimate.estimate_row(dynamodb, '4', 'Cobre', date(2026, 9, 21))

    assert gold.source is MarketSource.LBMA_GOLD_AM
    assert (gold.days_quoted, gold.calendar_days_elapsed) == (4, 6)
    assert gold.running_average == 4300.0 and gold.previous_official == 4368.79
    assert gold.change_percent == -1.57
    assert (gold.export_rate, gold.internal_rate, gold.rate_basis) == (7.0, 4.2, RateBasis.CAP)
    assert gold.confidence is EstimateConfidence.MEDIUM
    assert antimony.source is None and antimony.confidence is EstimateConfidence.NONE
    assert antimony.previous_official == 18575.0
    assert copper.days_quoted == 0 and copper.confidence is EstimateConfidence.NONE


def test_estimate_all_names_the_periods(dynamodb):
    '''On 21-sep the fortnight in progress is 16-30 Sep and it will rule 1-15 Oct.'''
    with patch.object(official_estimate, 'list_minerals', lambda resource: CATALOGUE), \
         patch.object(official_estimate, 'average_low', lambda *args: None):
        result = official_estimate.estimate_all(dynamodb, date(2026, 9, 21))
    assert (result.period_year, result.period_month, result.period_half) == (2026, 9, 2)
    assert (result.period_start, result.period_end) == (date(2026, 9, 16), date(2026, 9, 30))
    assert (result.valid_from, result.valid_to) == (date(2026, 10, 1), date(2026, 10, 15))
    assert [row.mineral_id for row in result.rows] == ['1', '4', '5', '8', '9']


def test_market_series_answers_codes_for_bad_requests(dynamodb):
    '''Unknown mineral, Asian Metal mineral and an inverted range each have a code.'''
    _seed_market(dynamodb, [('4', date(2026, 9, 15), 6.3703, 'LME_CASH_WESTMETALL')])
    with patch.object(official_estimate, 'list_minerals', lambda resource: CATALOGUE):
        series = official_estimate.market_series(dynamodb, '4', None, None)
        assert series.name == 'Cobre' and series.unit == 'LF'
        assert [(row.date, row.price) for row in series.items] == [(date(2026, 9, 15), 6.3703)]
        with pytest.raises(RegisterNotFoundError) as missing:
            official_estimate.market_series(dynamodb, '99', None, None)
        with pytest.raises(InvalidInputError) as paid:
            official_estimate.market_series(dynamodb, '5', None, None)
        with pytest.raises(InvalidInputError) as inverted:
            official_estimate.market_series(dynamodb, '4', date(2026, 9, 20), date(2026, 9, 1))
    assert missing.value.detail == MarketError.UNKNOWN_MINERAL.value
    assert paid.value.detail == MarketError.MINERAL_NOT_MARKET_QUOTED.value
    assert inverted.value.detail == MarketError.INVALID_DATE_RANGE.value


def test_audit_resolver_survives_a_result_without_id():
    '''
        A summary result must not blow up the audit decorator.

        `MarketSyncResult` names no row, and `_resolve_audit_data` used to read
        `.id` on any Pydantic model: the sync ran, wrote its days and then
        answered 500 from the decorator. The endpoint was unusable while the
        scheduled run — which never crosses the controller — worked fine.
    '''
    summary = MarketSyncResult(
        requested_days = 10, date_from = date(2026, 9, 13), date_to = date(2026, 9, 22),
        stored = 42, already_present = 0, without_publication = 18
    )

    entity_id, new_values = utils._resolve_audit_data(summary, None) # pylint: disable=protected-access

    assert entity_id is None
    assert new_values['stored'] == 42


def test_audit_resolver_prefers_the_identifier_when_there_is_one():
    '''A result that does name a row still audits against that row.'''
    rule = RoyaltyRuleSchema(
        mineral_id = '4', slope = 3.0769, intercept = -1.1538, min_rate = 1.0,
        max_rate = 5.0, internal_factor = 0.6, legal_basis = 'Ley 535 Art. 227'
    )

    entity_id, _ = utils._resolve_audit_data({'id': rule.mineral_id}, None) # pylint: disable=protected-access

    assert entity_id == '4'
