'''
    Gross-margin engine: turns a sales report into a profitability report.

    Everything here depends on the optional 'costo_unitario' column. Most ERP
    exports do not carry it, so every section degrades to empty rather than
    raising: a client without cost data still gets the full commercial summary,
    just without the margin blocks.

    The distinction this module exists to make is the one a commercial manager
    actually cares about: the biggest seller and the biggest earner are rarely
    the same product, the same client or the same salesperson.
'''
from typing import Any, Dict, List, Optional

import pandas as pd

from services.frame_utils import (
    CANTIDAD,
    CATEGORIA,
    CLIENTE_ID,
    CLIENTE_NOMBRE,
    COSTO,
    MONTO,
    PRODUCTO_ID,
    PRODUCTO_NOMBRE,
    VENDEDOR,
    label_series,
    money,
    order_count,
    ratio
)


# Rows kept in each breakdown, so the response stays renderable in a table.
_TOP_ROWS: int = 15
# A product is flagged when its realized margin falls below this share of
# revenue. Selling at 2% gross does not cover distribution and is worth seeing.
_THIN_MARGIN: float = 0.02


def has_cost_data(dataframe: pd.DataFrame) -> bool:
    '''
        Reports whether the frame can support any margin analysis at all.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            bool: True when unit cost, quantity and amount are all usable.
    '''
    required = {COSTO, CANTIDAD, MONTO}
    if not required.issubset(dataframe.columns):
        return False
    return bool(pd.to_numeric(dataframe[COSTO], errors = 'coerce').notna().any())


def _with_margin(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Adds the per-line cost and gross margin columns, keeping only the rows
        where both operands are usable.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame: Rows carrying 'costo_linea' and 'margen_linea'.
    '''
    frame = dataframe.copy()
    frame[COSTO] = pd.to_numeric(frame[COSTO], errors = 'coerce')
    frame[CANTIDAD] = pd.to_numeric(frame[CANTIDAD], errors = 'coerce')
    frame[MONTO] = pd.to_numeric(frame[MONTO], errors = 'coerce')

    frame = frame[frame[COSTO].notna() & frame[CANTIDAD].notna() & frame[MONTO].notna()]
    frame['costo_linea'] = frame[COSTO] * frame[CANTIDAD]
    frame['margen_linea'] = frame[MONTO] - frame['costo_linea']
    return frame


def _kpis(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Builds the headline profitability cards.

        Args:
            frame (pd.DataFrame): Rows already carrying the margin columns.

        Returns:
            List[Dict[str, Any]]: KPI cards ready for the dashboard.
    '''
    revenue = float(frame[MONTO].sum())
    cost = float(frame['costo_linea'].sum())
    margin = revenue - cost
    orders = order_count(frame)

    return [
        {
            'label': 'Margen bruto', 'value': money(margin), 'format': 'money',
            'hint': 'Venta menos costo de la mercadería vendida'
        },
        {
            'label': 'Margen bruto %', 'value': round(ratio(margin, revenue) * 100, 1),
            'format': 'percent', 'hint': 'Qué porcentaje de cada boliviano vendido queda'
        },
        {
            'label': 'Costo de la mercadería', 'value': money(cost), 'format': 'money',
            'hint': 'Lo que costó comprar lo que se vendió'
        },
        {
            'label': 'Margen por pedido', 'value': money(ratio(margin, orders)),
            'format': 'money', 'hint': 'Ganancia bruta promedio de cada pedido'
        },
    ]


def _breakdown(frame: pd.DataFrame, labels: Optional[pd.Series], top: int) -> List[Dict[str, Any]]:
    '''
        Aggregates revenue, cost and margin by an arbitrary label series.

        Args:
            frame (pd.DataFrame): Rows carrying the margin columns.
            labels (pd.Series | None): Grouping label per row; None skips the
                section entirely.
            top (int): Maximum rows returned, ordered by margin contribution.

        Returns:
            List[Dict[str, Any]]: One row per group, richest margin first.
    '''
    if labels is None or labels.empty:
        return []

    grouped = frame.groupby(labels.values, dropna = False).agg(
        monto = (MONTO, 'sum'),
        costo = ('costo_linea', 'sum'),
        margen = ('margen_linea', 'sum')
    ).sort_values('margen', ascending = False).head(top)

    return [
        {
            'label': str(label),
            'monto': money(row['monto']),
            'costo': money(row['costo']),
            'margen': money(row['margen']),
            'margen_porcentaje': round(ratio(row['margen'], row['monto']) * 100, 1)
        }
        for label, row in grouped.iterrows()
    ]


def _thin_margin_products(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Lists products whose realized margin is negative or negligible.

        This is the section a manager acts on first: it usually surfaces a
        mispriced item or a promotion that was never switched off.

        Args:
            frame (pd.DataFrame): Rows carrying the margin columns.

        Returns:
            List[Dict[str, Any]]: Loss-making or barely profitable products.
        '''
    labels = label_series(frame, PRODUCTO_ID, PRODUCTO_NOMBRE)
    if labels is None:
        return []

    grouped = frame.groupby(labels.values, dropna = False).agg(
        monto = (MONTO, 'sum'),
        margen = ('margen_linea', 'sum')
    )
    grouped = grouped[grouped['monto'] > 0]
    grouped['share'] = grouped['margen'] / grouped['monto']

    flagged = grouped[grouped['share'] < _THIN_MARGIN].sort_values('margen')
    return [
        {
            'label': str(label),
            'monto': money(row['monto']),
            'margen': money(row['margen']),
            'margen_porcentaje': round(row['share'] * 100, 1),
            'motivo': (
                'Se vende por debajo del costo' if row['margen'] < 0
                else 'Margen casi nulo'
            )
        }
        for label, row in flagged.head(_TOP_ROWS).iterrows()
    ]


def build_margin(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the whole profitability block from the normalized sales frame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'disponible' (whether the file carried cost data),
                'kpis', 'por_categoria', 'por_producto', 'por_cliente',
                'por_vendedor' and 'alertas'. When cost data is absent every
                section is empty and 'disponible' is False — never an error.
    '''
    if not has_cost_data(dataframe):
        return {
            'disponible': False, 'kpis': [], 'por_categoria': [],
            'por_producto': [], 'por_cliente': [], 'por_vendedor': [],
            'alertas': []
        }

    frame = _with_margin(dataframe)
    if frame.empty:
        return {
            'disponible': False, 'kpis': [], 'por_categoria': [],
            'por_producto': [], 'por_cliente': [], 'por_vendedor': [],
            'alertas': []
        }

    categories = frame[CATEGORIA] if CATEGORIA in frame.columns else None
    sellers = frame[VENDEDOR] if VENDEDOR in frame.columns else None

    return {
        'disponible': True,
        'kpis': _kpis(frame),
        'por_categoria': _breakdown(frame, categories, _TOP_ROWS),
        'por_producto': _breakdown(
            frame, label_series(frame, PRODUCTO_ID, PRODUCTO_NOMBRE), _TOP_ROWS
        ),
        'por_cliente': _breakdown(
            frame, label_series(frame, CLIENTE_ID, CLIENTE_NOMBRE), _TOP_ROWS
        ),
        'por_vendedor': _breakdown(frame, sellers, _TOP_ROWS),
        'alertas': _thin_margin_products(frame)
    }
