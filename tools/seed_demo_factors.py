'''
    Loads the external factors of the two demo companies, with their history.

    The «Efecto del tipo de cambio» view discounts distribution from the margin
    with the fuel price and the fleet's yield of each day, and the module shows
    every active factor next to the sales of the same period. The companies are
    invented, so their factors are too: plausible figures, one reading a month
    from the start of the demo sales to today. It goes through QUOTES' own
    functions, so the definitions and readings pass the same rules as a load
    from the screen.

        python -m tools.seed_demo_factors                    # simulation
        python -m tools.seed_demo_factors --yes

    Re-running corrects instead of duplicating: a factor is redeclared and a
    reading is idempotent by day.
'''
import argparse
from collections.abc import Callable
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
QUOTES_PATH = ROOT / 'services' / 'quotes'
sys.path.insert(0, str(QUOTES_PATH))
# The service validates its environment on import, so it is loaded first.
load_dotenv(QUOTES_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.factors import (  # noqa: E402
    FactorDefinitionSchema,
    FactorValueSchema
)
from services.factors import (  # noqa: E402
    FUEL_EFFICIENCY_CODE,
    FUEL_PRICE_CODE,
    declare_factor,
    load_values
)

PROFILE = 'deploy_ml'
REGION = 'us-east-1'
OWNERS = ('Distribuidora Andina S.R.L.', 'Comercial Illimani S.R.L.')
# The demo sales start in October 2024; the factors start with them.
HISTORY_START = date(2024, 10, 1)
# The real pump prices: frozen at 3,72 since 2005; 9,80 from 17/12/2025, a
# partial cut of the subsidy; 17,95 from 19/09/2026 (DS 5716), with the
# subsidy gone and the price tied to the international one.
SUBSIDY_CUT = date(2025, 12, 17)
SUBSIDY_END = date(2026, 9, 19)
SUBSIDISED_DIESEL = 3.72
PARTIAL_DIESEL = 9.80
FREE_DIESEL = 17.95
FLEET_YIELD = 5.0
TARIFF_BEFORE, TARIFF_AFTER, TARIFF_CHANGE = 10.0, 12.0, date(2026, 3, 1)
# Monthly inflation, %: quiet while the rate was fixed, higher after the
# subsidy cut, eased after the float. Invented, like the tariff.
INFLATION_FIXED, INFLATION_SUBSIDY, INFLATION_FLOAT = 0.6, 1.8, 1.2
FLOAT_START = date(2026, 6, 27)


@dataclass(frozen = True)
class DemoFactor:
    '''
        One factor and how its value moves with the month.
    '''
    definition: FactorDefinitionSchema
    value_on: Callable[[date], float]


def _inflation(day: date) -> float:
    '''
        The month's inflation, by regime.

        Args:
            day (date): First day of the month.

        Returns:
            float: Monthly inflation, percent.
    '''
    if day >= FLOAT_START:
        return INFLATION_FLOAT
    return INFLATION_SUBSIDY if day >= SUBSIDY_CUT else INFLATION_FIXED


def _diesel(day: date) -> float:
    '''
        The pump price of diesel on a day.

        Args:
            day (date): The day.

        Returns:
            float: Bolivianos per litre.
    '''
    if day >= SUBSIDY_END:
        return FREE_DIESEL
    return PARTIAL_DIESEL if day >= SUBSIDY_CUT else SUBSIDISED_DIESEL


FACTORS: tuple[DemoFactor, ...] = (
    DemoFactor(
        FactorDefinitionSchema(code = FUEL_PRICE_CODE, name = 'Diésel', unit = 'Bs/litro',
                               source = 'Precio en surtidor (demo)',
                               effective_from = HISTORY_START),
        _diesel
    ),
    DemoFactor(
        FactorDefinitionSchema(code = FUEL_EFFICIENCY_CODE,
                               name = 'Rendimiento de la flota (reparto urbano)',
                               unit = 'km/litro', source = 'Registro de flota (demo)',
                               effective_from = HISTORY_START),
        lambda day: FLEET_YIELD
    ),
    DemoFactor(
        FactorDefinitionSchema(code = 'ARANCEL', name = 'Arancel promedio de importación',
                               unit = '%', source = 'Aduana Nacional (demo)',
                               effective_from = HISTORY_START),
        lambda day: TARIFF_AFTER if day >= TARIFF_CHANGE else TARIFF_BEFORE
    ),
    DemoFactor(
        FactorDefinitionSchema(code = 'INFLACION', name = 'Inflación mensual',
                               unit = '%', source = 'INE (demo)',
                               effective_from = HISTORY_START),
        _inflation
    ),
)


def months(
    start: date,
    end: date
) -> list[date]:
    '''
        The first day of every month from `start` to `end`.

        Args:
            start (date): First month.
            end (date): Last day included.

        Returns:
            list[date]: One date per month.
    '''
    days, current = [], date(start.year, start.month, 1)
    while current <= end:
        days.append(current)
        current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
    return days


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(description = 'Carga los factores de demo.')
    parser.add_argument('--yes', action = 'store_true', help = 'Escribe en DynamoDB.')
    args = parser.parse_args()

    # A reading on the first of every month, plus one on each day a price
    # changed: a factor reads the latest value on or before a day, so a change
    # loaded only on the first of the next month would arrive weeks late.
    calendar = sorted(set(months(HISTORY_START, date.today()))
                      | {SUBSIDY_CUT, SUBSIDY_END, TARIFF_CHANGE, FLOAT_START})
    for factor in FACTORS:
        first, last = factor.value_on(calendar[0]), factor.value_on(calendar[-1])
        print(f'{factor.definition.code:12} {factor.definition.unit:10} '
              f'{len(calendar)} lecturas  {calendar[0]} {first} … {calendar[-1]} {last}')
    if not args.yes:
        print(f'Simulación para {", ".join(OWNERS)}: no se escribió nada. Repite con --yes.')
        return 0

    resource = boto3.Session(profile_name = PROFILE, region_name = REGION).resource('dynamodb')
    for owner in OWNERS:
        for factor in FACTORS:
            declare_factor(resource, owner, factor.definition)
            load_values(resource, owner, factor.definition.code,
                        [FactorValueSchema(factor_date = day, value = factor.value_on(day))
                         for day in calendar])
        print(f'{owner}: {len(FACTORS)} factores cargados.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
