'''
    Commercial summary engine — the general sales dashboard.

    Turns a normalized sales DataFrame (from ingest) into a clear, business-
    readable snapshot: headline KPIs, best/worst performers, top/bottom products,
    breakdowns by category/channel/region/seller and the monthly trend. Every
    piece is pre-labeled in Spanish and pre-aggregated so the frontend only has
    to render tables and charts — the meaning is decided here.

    Columns used (all produced by ingest normalization; each is optional and
    simply skipped when absent):
        monto_total, cantidad, id_pedido, id_punto_venta, nombre_pdv,
        id_producto, nombre_producto, categoria, canal, region, ciudad,
        vendedor, fecha
'''
from typing import Any, Dict, List, Optional

import pandas as pd

from services.logger_config import custom_logger as logger

_MONTO = 'monto_total'
_CANTIDAD = 'cantidad'
_PEDIDO = 'id_pedido'
_CLIENTE_ID = 'id_punto_venta'
_CLIENTE_NOMBRE = 'nombre_pdv'
_PRODUCTO_ID = 'id_producto'
_PRODUCTO_NOMBRE = 'nombre_producto'


def _money(value: float) -> float:
    '''Rounds a monetary amount to 2 decimals, guarding against NaN.'''
    return round(float(value), 2) if pd.notna(value) else 0.0


def _label_series(dataframe: pd.DataFrame, id_col: str, name_col: str) -> pd.Series:
    '''
        Returns a readable label per row: the human name when available, else the
        id. Lets rankings show "Tienda Doña Rosa" instead of "PDV-007".
    '''
    if name_col in dataframe.columns:
        names = dataframe[name_col].fillna('').astype(str).str.strip()
        ids = dataframe[id_col].astype(str) if id_col in dataframe.columns else ''
        return names.where(names != '', ids)
    return dataframe[id_col].astype(str)


def _kpis(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Builds the headline KPI cards. Each is a {label, value, format, hint}
        dict so the UI renders it without knowing the business meaning.
    '''
    venta_total = _money(dataframe[_MONTO].sum()) if _MONTO in dataframe else 0.0
    num_ventas = int(dataframe[_PEDIDO].nunique()) if _PEDIDO in dataframe else len(dataframe)
    unidades = _money(dataframe[_CANTIDAD].sum()) if _CANTIDAD in dataframe else 0.0
    ticket = _money(venta_total / num_ventas) if num_ventas else 0.0
    num_clientes = int(dataframe[_CLIENTE_ID].nunique()) if _CLIENTE_ID in dataframe else 0
    num_productos = int(dataframe[_PRODUCTO_ID].nunique()) if _PRODUCTO_ID in dataframe else 0

    return [
        {'label': 'Venta total', 'value': venta_total, 'format': 'money',
         'hint': 'Suma de todas las ventas del periodo'},
        {'label': 'Número de ventas', 'value': num_ventas, 'format': 'int',
         'hint': 'Cantidad de pedidos/transacciones'},
        {'label': 'Ticket promedio', 'value': ticket, 'format': 'money',
         'hint': 'Venta total ÷ número de ventas'},
        {'label': 'Unidades vendidas', 'value': unidades, 'format': 'int',
         'hint': 'Suma de las cantidades vendidas'},
        {'label': 'Clientes', 'value': num_clientes, 'format': 'int',
         'hint': 'Puntos de venta distintos con compras'},
        {'label': 'Productos', 'value': num_productos, 'format': 'int',
         'hint': 'SKUs distintos vendidos'},
    ]


def _ranking(dataframe: pd.DataFrame, label_series: pd.Series, top: int, ascending: bool
             ) -> List[Dict[str, Any]]:
    '''
        Aggregates monto_total by a label and returns the top (or bottom) N as
        {label, monto} rows. Shared by best/worst client and top/bottom products.

        Rows with zero sales are excluded: a "least sold" list is only useful
        among items that actually sold — listing products with 0 adds no value.
    '''
    if _MONTO not in dataframe.columns:
        return []
    grouped = dataframe.assign(_label = label_series.values).groupby('_label')[_MONTO].sum()
    grouped = grouped[grouped > 0].sort_values(ascending = ascending).head(top)
    rows = [{'label': str(idx), 'monto': _money(val)} for idx, val in grouped.items()]
    # Bottom rankings read better ascending → smallest first; keep that order.
    return rows


def _distribution(dataframe: pd.DataFrame, dimension: str) -> List[Dict[str, Any]]:
    '''
        Sales share by a categorical dimension (categoria/canal/region/...),
        returned as {label, monto, porcentaje} sorted by amount desc. Empty when
        the column is absent so the UI can hide that chart.
    '''
    if dimension not in dataframe.columns or _MONTO not in dataframe.columns:
        return []
    grouped = (
        dataframe.assign(_dim = dataframe[dimension].fillna('Sin especificar').astype(str))
        .groupby('_dim')[_MONTO].sum().sort_values(ascending = False)
    )
    total = grouped.sum()
    if total <= 0:
        return []
    return [
        {'label': str(idx), 'monto': _money(val),
         'porcentaje': round(float(val) / float(total) * 100, 1)}
        for idx, val in grouped.items()
    ]


def _monthly_trend(dataframe: pd.DataFrame) -> List[Dict[str, Any]]:
    '''
        Monthly sales series as {mes: 'YYYY-MM', monto}. Empty when there is no
        parseable date column.
    '''
    if 'fecha' not in dataframe.columns or _MONTO not in dataframe.columns:
        return []
    fechas = pd.to_datetime(dataframe['fecha'], errors = 'coerce')
    valid = fechas.notna()
    if not valid.any():
        return []
    monthly = (
        dataframe.loc[valid].assign(_mes = fechas[valid].dt.strftime('%Y-%m'))
        .groupby('_mes')[_MONTO].sum().sort_index()
    )
    return [{'mes': str(idx), 'monto': _money(val)} for idx, val in monthly.items()]


def build_commercial_summary(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the full commercial summary from a normalized sales DataFrame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows (one product line
                per row) as produced by the ingest service.

        Returns:
            Dict[str, Any]: KPIs, best/worst client, top/bottom products, the
                distributions by dimension and the monthly trend — all labeled
                and aggregated, ready for tables and charts.
    '''
    message = f'Building commercial summary over {len(dataframe)} rows.'
    logger.info(message)

    client_labels = _label_series(dataframe, _CLIENTE_ID, _CLIENTE_NOMBRE)
    product_labels = _label_series(dataframe, _PRODUCTO_ID, _PRODUCTO_NOMBRE)

    return {
        'kpis': _kpis(dataframe),
        'mejor_cliente': _ranking(dataframe, client_labels, top = 10, ascending = False),
        'peor_cliente': _ranking(dataframe, client_labels, top = 10, ascending = True),
        'top_productos': _ranking(dataframe, product_labels, top = 10, ascending = False),
        'bottom_productos': _ranking(dataframe, product_labels, top = 10, ascending = True),
        'por_categoria': _distribution(dataframe, 'categoria'),
        'por_canal': _distribution(dataframe, 'canal'),
        'por_region': _distribution(dataframe, 'region'),
        'por_vendedor': _distribution(dataframe, 'vendedor'),
        'tendencia_mensual': _monthly_trend(dataframe),
    }
