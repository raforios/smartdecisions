'''
    Shared helpers for the analytics engines.

    Every engine consumes the same normalized sales frame produced by the ingest
    service, so the canonical column names and the primitives to read money,
    build readable labels and derive the month live here instead of being
    re-implemented (and drifting) in each engine.
'''
from typing import Optional

import pandas as pd

# Canonical column names written by ingest normalization. Each one is optional:
# engines must degrade gracefully when a client's file lacks it.
MONTO = 'monto_total'
CANTIDAD = 'cantidad'
PEDIDO = 'id_pedido'
CLIENTE_ID = 'id_punto_venta'
CLIENTE_NOMBRE = 'nombre_pdv'
PRODUCTO_ID = 'id_producto'
PRODUCTO_NOMBRE = 'nombre_producto'
PRECIO = 'precio_unitario'
CATEGORIA = 'categoria'
VENDEDOR = 'vendedor'
FECHA = 'fecha'


def money(value: float) -> float:
    '''
        Rounds a monetary amount to 2 decimals, guarding against NaN.

        Args:
            value (float): Raw amount, possibly NaN coming from pandas.

        Returns:
            float: The amount rounded to 2 decimals, or 0.0 when not a number.
    '''
    return round(float(value), 2) if pd.notna(value) else 0.0


def ratio(numerator: float, denominator: float) -> float:
    '''
        Safe division used across the engines for shares and averages.

        Args:
            numerator (float): Dividend.
            denominator (float): Divisor; a zero or NaN yields 0.0.

        Returns:
            float: The quotient, or 0.0 when the divisor is unusable.
    '''
    if not denominator or pd.isna(denominator):
        return 0.0
    return float(numerator) / float(denominator)


def percent_change(current: float, previous: Optional[float]) -> Optional[float]:
    '''
        Percentage variation between two periods.

        Args:
            current (float): Value of the latest period.
            previous (float | None): Value of the reference period; None or zero
                means there is no base to compare against.

        Returns:
            float | None: The change in percent rounded to 1 decimal, or None
                when there is no comparable base (a growth from zero is
                undefined, not "infinite").
    '''
    if not previous or pd.isna(previous):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 1)


def label_series(dataframe: pd.DataFrame, id_col: str, name_col: str) -> Optional[pd.Series]:
    '''
        Returns a readable label per row: the human name when available, else
        the id. Lets rankings show 'Tienda Doña Rosa' instead of 'PDV-007'.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            id_col (str): Column holding the entity id.
            name_col (str): Column holding the human-readable name.

        Returns:
            pd.Series | None: The label per row, or None when neither column
                exists so the caller can skip that section entirely.
    '''
    if name_col in dataframe.columns:
        names = dataframe[name_col].fillna('').astype(str).str.strip()
        ids = dataframe[id_col].astype(str) if id_col in dataframe.columns else ''
        return names.where(names != '', ids)
    if id_col in dataframe.columns:
        return dataframe[id_col].astype(str)
    return None


def dates(dataframe: pd.DataFrame) -> Optional[pd.Series]:
    '''
        Parses the 'fecha' column into datetimes.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series | None: Coerced datetimes (NaT where unparseable), or None
                when the column is absent or holds no usable date at all.
    '''
    if FECHA not in dataframe.columns:
        return None
    parsed = pd.to_datetime(dataframe[FECHA], errors = 'coerce')
    return parsed if parsed.notna().any() else None


def order_count(dataframe: pd.DataFrame) -> int:
    '''
        Number of distinct orders, falling back to the row count when the file
        has no order id (each line is then its own transaction).

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            int: Distinct orders in the frame.
    '''
    if PEDIDO in dataframe.columns:
        return int(dataframe[PEDIDO].nunique())
    return int(len(dataframe))
