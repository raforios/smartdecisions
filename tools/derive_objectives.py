'''
    Derives monthly objectives from a client's own sales history.

    The demonstration has a gap that is not a defect: the company whose
    transactional file we have never sent us objectives, and the company whose
    objectives we have is a different one. Inventing a number per client would
    make every percentage in the report meaningless, so the objective is
    derived — and derived the way the prospect derives theirs, which is
    written down in their own `RESUMEN OBJ Q1 2020` sheet:

        forecast  ->  forecast x attainment rate  ->  objective

    Their sheet carries it as `FCST SO`, `FCST SO 70%` and `FCST FACT 70%`.
    The forecast here is the client's own average month over the history, so
    the objective is a demanding but reachable version of what they already
    do, which is exactly what a commercial objective is.

    This is OUR tool and it is run by us. It is not part of the product: a
    real account loads its objectives through the `objetivos` template or
    pushes them from its ERP, and nothing derives anything on their behalf.

    Usage:
        python -m tools.derive_objectives ventas.xlsx
        python -m tools.derive_objectives ventas.xlsx --rate 0.8 --out objetivos.xlsx
'''
import argparse
from pathlib import Path
from typing import Optional

import pandas as pd


# The share of the forecast that becomes the objective. It is the prospect's
# own figure — their columns are literally named "70%" — and it is exposed as
# a flag because it is the one number a commercial director argues about.
DEFAULT_ATTAINMENT_RATE = 0.70

# Template headers. Spanish, because this writes the file a client would
# have filled in themselves.
CLIENT_HEADER = 'Cliente'
PERIOD_HEADER = 'Periodo'
TARGET_HEADER = 'Objetivo'
DATE_HEADER = 'Fecha'
AMOUNT_HEADER = 'Monto Total'

# Objectives are round numbers. Nobody sets a client a target of 13.947,32 —
# the prospect's own file is full of figures like 13.940 and 82.620.
ROUNDING_STEP = 10


def derive(
    sales: pd.DataFrame,
    rate: float
) -> pd.DataFrame:
    '''
        Builds one objective per client and month from their history.

        Every month the client was active gets an objective, including the
        months they bought nothing after their first purchase: a client who
        went quiet in August still had a target in August, and that gap is
        the most useful thing the report will show.

        Args:
            sales (pd.DataFrame): Rows of the sales template.
            rate (float): Share of the forecast that becomes the objective.

        Returns:
            pd.DataFrame: Rows of the objectives template.

        Raises:
            ValueError: If the file carries neither the client nor the amount.
    '''
    missing = [header for header in (CLIENT_HEADER, DATE_HEADER, AMOUNT_HEADER)
               if header not in sales.columns]
    if missing:
        raise ValueError(f'The sales file has no {", ".join(missing)} column.')

    frame = sales.loc[:, [CLIENT_HEADER, DATE_HEADER, AMOUNT_HEADER]].copy()
    frame[PERIOD_HEADER] = pd.to_datetime(
        frame[DATE_HEADER], errors = 'coerce'
    ).dt.strftime('%Y-%m')
    frame = frame.dropna(subset = [PERIOD_HEADER])

    monthly = frame.groupby(
        [CLIENT_HEADER, PERIOD_HEADER], as_index = False
    )[AMOUNT_HEADER].sum()
    forecast = monthly.groupby(CLIENT_HEADER)[AMOUNT_HEADER].mean()

    # Every month in the window, for every client: the objective exists
    # whether or not they bought.
    periods = sorted(monthly[PERIOD_HEADER].unique())
    rows = [
        {
            CLIENT_HEADER: client,
            PERIOD_HEADER: period,
            TARGET_HEADER: _rounded(average * rate)
        }
        for client, average in forecast.items()
        for period in periods
    ]
    return pd.DataFrame(rows)


def _rounded(amount: float) -> float:
    '''
        An objective as somebody would actually write it.

        Args:
            amount (float): The derived figure.

        Returns:
            float: The figure, to the nearest step.
    '''
    return float(round(amount / ROUNDING_STEP) * ROUNDING_STEP)


def main(argument_list: Optional[list] = None) -> int:
    '''
        Entry point.

        Args:
            argument_list (list): Arguments, for tests. Defaults to argv.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('sales', help = 'A file with the sales template.')
    parser.add_argument('--rate', type = float, default = DEFAULT_ATTAINMENT_RATE,
                        help = 'Share of the forecast that becomes the objective.')
    parser.add_argument('--out', default = None,
                        help = 'Where to write. Defaults to plantilla_objetivos.xlsx '
                               'beside the sales file.')
    arguments = parser.parse_args(argument_list)

    source = Path(arguments.sales)
    destination = Path(arguments.out) if arguments.out else \
        source.with_name('objetivos.xlsx')

    objectives = derive(pd.read_excel(source), arguments.rate)
    objectives.to_excel(destination, index = False, sheet_name = 'Datos')

    print(f'{len(objectives)} objectives -> {destination}')
    print(f'  clients  {objectives[CLIENT_HEADER].nunique()}')
    print(f'  periods  {sorted(objectives[PERIOD_HEADER].unique())}')
    print(f'  total    {objectives[TARGET_HEADER].sum():,.2f}')
    print(f'  rate     {arguments.rate:.0%} of each client\'s average month')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
