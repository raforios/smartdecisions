'''
    Commercial efficiency engine — the quality of each sale, not its size.

    In mass consumption the total is driven by three levers that a summary of
    revenue alone never exposes:

        * Drop size: how many units and how many distinct products travel in a
          single order. Growing it is cheaper than winning a new client.
        * Seller productivity: sales, clients served, average ticket and lines
          per order side by side, so the team is compared on the same yardstick.
        * Selling price drift: the average price actually charged per product
          against the previous period, which surfaces silent discounting.
'''
from typing import Any, Dict, List, Optional

import pandas as pd

from services.frame_utils import (
    CANTIDAD,
    CLIENTE_ID,
    MONTO,
    PRODUCTO_ID,
    PRODUCTO_NOMBRE,
    VENDEDOR,
    dates,
    label_series,
    money,
    order_count,
    percent_change,
    ratio
)
from services.logger_config import custom_logger as logger

_MAX_SELLERS = 50
_MAX_PRICE_ROWS = 100
# Price drift is only reported for products with enough movement in both halves
# of the period; a single invoice is an anecdote, not a trend.
_MIN_UNITS_FOR_PRICE = 5


def _drop_size_kpis(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Builds the drop-size cards: units per order, distinct lines per order
        and the average amount per order.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: KPI cards ready for the UI.
    '''
    orders = order_count(dataframe)
    units = float(dataframe[CANTIDAD].sum()) if CANTIDAD in dataframe.columns else 0.0
    amount = float(dataframe[MONTO].sum()) if MONTO in dataframe.columns else 0.0
    # Every row of the normalized frame is one product line of one order.
    lines_per_order = ratio(len(dataframe), orders)

    return [
        {'label': 'Unidades por pedido', 'value': round(ratio(units, orders), 2),
         'format': 'decimal', 'hint': 'Drop size: unidades que salen en cada pedido'},
        {'label': 'Productos por pedido', 'value': round(lines_per_order, 2),
         'format': 'decimal', 'hint': 'Líneas distintas por pedido — mide la venta cruzada'},
        {'label': 'Monto por pedido', 'value': money(ratio(amount, orders)),
         'format': 'money', 'hint': 'Ticket promedio del período'},
        {'label': 'Pedidos', 'value': float(orders), 'format': 'int',
         'hint': 'Transacciones distintas en el período'},
    ]


def _seller_productivity(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Compares sellers on sales, clients served, orders, average ticket and
        lines per order.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: One row per seller, best sales first. Empty
                when the file has no seller column.
    '''
    if VENDEDOR not in dataframe.columns or MONTO not in dataframe.columns:
        return []

    labelled = dataframe.assign(
        _vendedor = dataframe[VENDEDOR].fillna('Sin asignar').astype(str))
    rows: List[Dict[str, Any]] = []
    for seller, group in labelled.groupby('_vendedor'):
        orders = order_count(group)
        amount = float(group[MONTO].sum())
        clients = int(group[CLIENTE_ID].nunique()) if CLIENTE_ID in group.columns else 0
        rows.append({
            'vendedor': str(seller),
            'monto': money(amount),
            'pedidos': orders,
            'clientes': clients,
            'ticket_promedio': money(ratio(amount, orders)),
            'lineas_por_pedido': round(ratio(len(group), orders), 2),
            'monto_por_cliente': money(ratio(amount, clients)) if clients else 0.0
        })
    rows.sort(key = lambda row: row['monto'], reverse = True)
    return rows[:_MAX_SELLERS]


def _average_price(group: pd.DataFrame) -> Optional[float]:
    '''
        Average price actually charged: amount divided by units, which reflects
        discounts far better than the nominal unit price.

        Args:
            group (pd.DataFrame): Rows of a single product.

        Returns:
            float | None: The realized average price, or None when the group
                does not move enough units to be meaningful.
    '''
    units = float(group[CANTIDAD].sum())
    if units < _MIN_UNITS_FOR_PRICE:
        return None
    return ratio(float(group[MONTO].sum()), units)


def _price_drift(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Realized average price per product in the second half of the period
        against the first half.

        Splitting by the median date (instead of by month) keeps the comparison
        available on short datasets, where a month-over-month cut would leave
        most products with no base period.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: Products whose price moved, largest drop
                first. Empty when quantities, amounts or dates are missing.
    '''
    parsed_dates = dates(dataframe)
    labels = label_series(dataframe, PRODUCTO_ID, PRODUCTO_NOMBRE)
    if parsed_dates is None or labels is None:
        return []
    if CANTIDAD not in dataframe.columns or MONTO not in dataframe.columns:
        return []

    valid = parsed_dates.notna()
    scoped = dataframe.loc[valid].assign(
        _label = labels[valid].values, _fecha = parsed_dates[valid].values)
    if scoped.empty:
        return []

    cut = scoped['_fecha'].median()
    recent = scoped.loc[scoped['_fecha'] >= cut]
    earlier = scoped.loc[scoped['_fecha'] < cut]
    if earlier.empty or recent.empty:
        return []

    recent_prices = {label: _average_price(group)
                     for label, group in recent.groupby('_label')}
    earlier_prices = {label: _average_price(group)
                      for label, group in earlier.groupby('_label')}

    rows: List[Dict[str, Any]] = []
    for label, current in recent_prices.items():
        previous = earlier_prices.get(label)
        if current is None or previous is None:
            continue
        variation = percent_change(current, previous)
        if variation is None or variation == 0:
            continue
        rows.append({
            'producto': str(label),
            'precio_actual': money(current),
            'precio_anterior': money(previous),
            'variacion': variation
        })
    rows.sort(key = lambda row: row['variacion'])
    return rows[:_MAX_PRICE_ROWS]


def build_efficiency(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the commercial efficiency block of the summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'kpis' (drop size), 'vendedores' (productivity
                table) and 'precios' (realized price drift). Sections the data
                cannot support come back empty rather than raising.
    '''
    message = f'Building efficiency block over {len(dataframe)} rows.'
    logger.info(message)
    return {
        'kpis': _drop_size_kpis(dataframe),
        'vendedores': _seller_productivity(dataframe),
        'precios': _price_drift(dataframe)
    }
