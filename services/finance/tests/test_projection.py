'''
    Tests for the projection, with figures worked out by hand.

    What they defend: the manager's percentages are kept within the ranges
    `finance_parameters` holds, the realistic series come from ML_FUNCTIONS, and the
    IUE of April is paid from the reserve first and from the cash only for
    what the reserve does not cover (Rafael, 17-oct). The model itself is
    tested in ML_FUNCTIONS, which owns it.
'''
from unittest.mock import Mock

import pytest

from schemas.projection import ProjectionError, ScenarioInputSchema, ScenarioName
from services import projection as P
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.report import Context, build_report
from tests.test_report import CATALOG, FINANCE_VALUES, RATES, SETTINGS, _month

PROJECTION_VALUES = {
    **FINANCE_VALUES, 'PROJECTION_HORIZON': 12.0, 'PROJECTION_MAX_HORIZON': 24.0,
    'WORST_SALES_CHANGE': -15.0, 'WORST_OUTFLOW_CHANGE': 5.0, 'BEST_SALES_CHANGE': 10.0,
    'BEST_OUTFLOW_CHANGE': -5.0, 'MAX_SCENARIO_CHANGE': 90.0,
    'BACKTEST_MONTHS': 12.0,
    'NON_CASH_ACCOUNTS': ['6.1.06', '6.2.04'], 'IUE_PAYMENT_MONTH': 4.0,
}
PSETTINGS = P.projection_settings_from(PROJECTION_VALUES)
# Thirteen months, September 2025 to September 2026, each the month worked by
# hand in test_report: profit 365, invoiced gross sales 1.000, cash 100.
MONTHS = [f'2025-{m:02d}' for m in range(9, 13)] + [f'2026-{m:02d}' for m in range(1, 10)]


def _projection(
    provision: float | None,
    asked: P.ProjectionRequest = P.ProjectionRequest()
):
    '''
        The default projection of the thirteen months.

        Returns:
            ProjectionSchema: The projection.
    '''
    entries = [entry for key in MONTHS for entry in _month(date = key)]
    report = build_report(entries, Context(CATALOG, RATES, provision, SETTINGS))
    _, invoiced = P.monthly_sums(entries, CATALOG, (PSETTINGS.non_cash_accounts, '4.1'))
    request = P.validated_request(asked, PSETTINGS)
    # What ML_FUNCTIONS answers for a flat history: the same month, again.
    flat = P.Forecasts(sales = [990.0] * request[0], outflow = [625.0] * request[0],
                       model = 'NAIVE', error_percent = 0.0, naive_error_percent = 0.0,
                       tested_points = 12)
    return P.build_projection(P.History(report.months, {}, invoiced), PSETTINGS,
                              P.Taxes(RATES, 'IUE', provision), request, flat)


def test_the_managers_values_are_kept_within_range():
    '''Empty keeps the default; out of range is refused with its code.'''
    horizon, worst, best = P.validated_request(P.ProjectionRequest(), PSETTINGS)
    assert (horizon, worst.sales_change, best.sales_change) == (12, -15, 10)
    custom = ScenarioInputSchema(sales_change = -20, outflow_change = 0)
    assert P.validated_request(P.ProjectionRequest(horizon = 6, worst = custom),
                               PSETTINGS)[:2] == (6, custom)
    for asked, code in ((P.ProjectionRequest(horizon = 25), ProjectionError.HORIZON_OUT_OF_RANGE),
                        (P.ProjectionRequest(horizon = 0), ProjectionError.HORIZON_OUT_OF_RANGE),
                        (P.ProjectionRequest(best = ScenarioInputSchema(
                            sales_change = 95, outflow_change = 0)),
                         ProjectionError.CHANGE_OUT_OF_RANGE)):
        with pytest.raises(InvalidInputError) as failure:
            P.validated_request(asked, PSETTINGS)
        assert failure.value.detail == code.value


def test_the_iue_is_paid_from_the_reserve_first():
    '''2% of 1.000 invoiced a month goes to the reserve: 12 x 20 = 240 for
    2026. In April 2027 the IUE of 2026 is 25% of 12 x 365 = 1.095: 240 come
    from the reserve and 855 from the cash.'''
    realistic = next(s for s in _projection(2.0).scenarios if s.name is ScenarioName.REALISTIC)
    march, april = realistic.months[5], realistic.months[6]
    assert (march.period, april.period) == ('2027-03', '2027-04')
    assert april.income_tax_paid == pytest.approx(1095)
    # April adds its profit less its own provision, gets the 240 back and pays 1.095.
    assert april.cash - march.cash == pytest.approx(365 - 20 + 240 - 1095)
    # What is left is 2027's own reserve: January to April, 4 x 20.
    assert april.reserve == pytest.approx(80)


def test_without_a_provision_the_whole_iue_comes_out_of_the_cash():
    '''No reserve: April pays the 1.095 from the cash, and the notice says why.'''
    projection = _projection(None)
    realistic = next(s for s in projection.scenarios if s.name is ScenarioName.REALISTIC)
    march, april = realistic.months[5], realistic.months[6]
    assert april.cash - march.cash == pytest.approx(365 - 1095)
    assert ProjectionError.IUE_PROVISION_NOT_SET in projection.notices


def test_the_worst_scenario_runs_out_first():
    '''A worst case the manager types —selling half— runs the cash out; the best never.'''
    asked = P.ProjectionRequest(worst = ScenarioInputSchema(sales_change = -50,
                                                            outflow_change = 5))
    scenarios = {s.name: s for s in _projection(None, asked).scenarios}
    worst, best = scenarios[ScenarioName.WORST], scenarios[ScenarioName.BEST]
    assert worst.months[-1].cash < scenarios[ScenarioName.REALISTIC].months[-1].cash
    assert best.months[-1].cash > scenarios[ScenarioName.REALISTIC].months[-1].cash
    assert worst.cash_runs_out is not None and best.cash_runs_out is None


def test_the_realistic_series_are_asked_to_ml_functions(monkeypatch):
    '''Both series go to the shared forecast as monthly series, without model
    parameters: ML_FUNCTIONS chooses and fits the model (19-oct-2026). If it
    cannot answer, the projection says so with a code.'''
    entries = [entry for key in MONTHS for entry in _month(date = key)]
    report = build_report(entries, Context(CATALOG, RATES, None, SETTINGS))
    history = P.History(report.months, {}, {})
    sent = []

    def answer(
        url,
        json,
        **_
    ):
        sent.append((url, json))
        return Mock(ok = True, json = lambda: {'forecast': [json['values'][-1]] * json['horizon'],
                                               'model': 'HOLT_WINTERS', 'tested_points': 7,
                                               'error_percent': 1.5, 'naive_error_percent': 2.0})
    monkeypatch.setattr(P.requests, 'post', answer)
    found = P.forecasts_for(history, 3, PSETTINGS, 'Bearer x')
    assert (found.sales, found.outflow) == ([990.0] * 3, [625.0] * 3)
    assert sent[0][0].endswith('/v1/prediction/forecast')
    assert sent[0][1] == {'values': sent[0][1]['values'], 'horizon': 3, 'season_length': 12,
                          'backtest_points': 12}
    assert (found.model, found.tested_points) == ('HOLT_WINTERS', 7)

    monkeypatch.setattr(P.requests, 'post', lambda *a, **k: Mock(ok = False, status_code = 503,
                                                                 text = 'down'))
    with pytest.raises(ServiceUnavailableError) as failure:
        P.forecasts_for(history, 3, PSETTINGS, 'Bearer x')
    assert failure.value.detail == ProjectionError.FORECAST_UNAVAILABLE.value
