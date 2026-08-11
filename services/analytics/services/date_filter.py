'''
    Date-range filtering shared by every analytics report.

    A sales export usually spans many months, but a manager reviews one quarter,
    one month or "this year vs last". Filtering happens once, here, so every
    engine receives an already-scoped frame and none of them has to know about
    date parsing — and so the reported period is described identically
    everywhere in the UI.
'''
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from services.exceptions import InvalidInputError
from services.frame_utils import dates
from services.logger_config import custom_logger as logger


def _parse_boundary(raw: Optional[str], field: str) -> Optional[pd.Timestamp]:
    '''
        Parses an ISO date coming from the query string.

        Args:
            raw (str | None): Date as 'YYYY-MM-DD'; None means "open end".
            field (str): Field name, used only to build a clear error message.

        Returns:
            pd.Timestamp | None: The parsed boundary, or None when not provided.

        Raises:
            InvalidInputError: If the value is present but not a valid date.
    '''
    if raw is None or str(raw).strip() == '':
        return None
    parsed = pd.to_datetime(raw, errors = 'coerce')
    if pd.isna(parsed):
        error_msg = f'Invalid {field} value "{raw}"; expected format YYYY-MM-DD.'
        logger.warning(error_msg)
        raise InvalidInputError(
            detail = f'La fecha "{raw}" no es válida. Usa el formato AAAA-MM-DD.'
        )
    return parsed


def _describe(available: Tuple[Any, Any], applied: Tuple[Any, Any], rows: int) -> Dict[str, Any]:
    '''
        Builds the period descriptor returned alongside every report.

        Args:
            available (tuple): (min, max) dates present in the whole dataset.
            applied (tuple): (from, to) boundaries actually applied, may be None.
            rows (int): Row count after filtering.

        Returns:
            Dict[str, Any]: Period metadata ready for the UI date pickers.
    '''
    def _iso(value: Any) -> Optional[str]:
        return None if value is None or pd.isna(value) else pd.Timestamp(value).strftime('%Y-%m-%d')

    return {
        'disponible_desde': _iso(available[0]),
        'disponible_hasta': _iso(available[1]),
        'desde': _iso(applied[0]) or _iso(available[0]),
        'hasta': _iso(applied[1]) or _iso(available[1]),
        'filtrado': applied[0] is not None or applied[1] is not None,
        'filas': int(rows),
    }


def apply_date_range(
    dataframe: pd.DataFrame,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    '''
        Restricts a sales frame to a date window and describes the result.

        Rows whose date cannot be parsed are dropped only when a filter is
        actually requested: with no filter the caller keeps the full dataset,
        undated rows included, preserving today's behaviour.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            date_from (str | None): Inclusive lower bound, 'YYYY-MM-DD'.
            date_to (str | None): Inclusive upper bound, 'YYYY-MM-DD'.

        Returns:
            Tuple[pd.DataFrame, Dict[str, Any]]: The scoped frame and the period
                descriptor ('disponible_desde/hasta', 'desde', 'hasta',
                'filtrado', 'filas').

        Raises:
            InvalidInputError: If a boundary is not a valid date, or if the
                requested window leaves no data to analyze.
    '''
    parsed_dates = dates(dataframe)
    lower = _parse_boundary(date_from, 'date_from')
    upper = _parse_boundary(date_to, 'date_to')

    if parsed_dates is None:
        # No usable date column: a filter cannot be honoured, so say so instead
        # of silently returning numbers for the wrong period.
        if lower is not None or upper is not None:
            raise InvalidInputError(
                detail = 'El archivo no tiene una columna de fecha válida, '
                         'no se puede filtrar por período.'
            )
        return dataframe, _describe((None, None), (None, None), len(dataframe))

    available = (parsed_dates.min(), parsed_dates.max())
    if lower is None and upper is None:
        return dataframe, _describe(available, (None, None), len(dataframe))

    mask = parsed_dates.notna()
    if lower is not None:
        mask &= parsed_dates >= lower
    if upper is not None:
        # Inclusive upper bound: a plain date means "up to the end of that day".
        mask &= parsed_dates <= upper + pd.Timedelta(days = 1) - pd.Timedelta(seconds = 1)

    scoped = dataframe.loc[mask]
    if scoped.empty:
        error_msg = f'Date range {date_from} → {date_to} matched no rows.'
        logger.warning(error_msg)
        raise InvalidInputError(
            detail = 'No hay ventas en el período seleccionado. Elige otro rango.'
        )

    message = f'Date filter {date_from} → {date_to} kept {len(scoped)} of {len(dataframe)} rows.'
    logger.info(message)
    return scoped, _describe(available, (lower, upper), len(scoped))
