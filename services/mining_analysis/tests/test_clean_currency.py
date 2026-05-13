'''
    Unit tests for clean_currency_pro.

    Regression coverage for the anglo/european decimal-separator bug that
    corrupted values like Bismuto `17.54` into `1754` on ETL ingest.
'''
import math
import pytest
from services.mining_analysis import clean_currency_pro


@pytest.mark.parametrize('raw, expected', [
    # Anglo decimal (regression: was being stripped to 1754)
    ('17.54', 17.54),
    ('17.540', 17.54),
    ('1,234.56', 1234.56),
    # European decimal
    ('1.234,56', 1234.56),
    ('26.500,00', 26500.00),
    ('218,632', 218.632),
    # Thousands grouping only
    ('1.234.567', 1234567.0),
    ('1,234,567', 1234567.0),
    # Integers expressed as strings
    ('1754', 1754.0),
    # Empty / placeholder
    ('-', 0.0),
    ('', 0.0),
    ('   ', 0.0),
    ('abc', 0.0),
    # Already-numeric Excel cells (pass-through)
    (17.54, 17.54),
    (1754, 1754.0),
    (0, 0.0),
    # Negative values
    ('-17.54', -17.54),
    ('-1.234,56', -1234.56),
    # Cells with currency symbols / units
    ('$1,234.56', 1234.56),
    ('Bs. 26.500,00', 26500.00),
])
def test_clean_currency_pro_variants(raw, expected):
    '''
    Verifies decimal-format detection across anglo, european and noisy inputs.
    '''
    assert clean_currency_pro(raw) == pytest.approx(expected)


def test_clean_currency_pro_none():
    '''
    None must collapse to 0.0 (matches pd.isna behavior).
    '''
    assert clean_currency_pro(None) == 0.0


def test_clean_currency_pro_nan():
    '''
    NaN floats must collapse to 0.0 instead of raising.
    '''
    assert clean_currency_pro(float('nan')) == 0.0


def test_clean_currency_pro_bismuto_regression():
    '''
    Direct regression: Bismuto 17.54 must NOT be parsed as 1754.
    '''
    assert clean_currency_pro('17.54') == 17.54
    assert not math.isclose(clean_currency_pro('17.54'), 1754)
