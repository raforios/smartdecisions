'''
    Pydantic schemas for the valued warehouse reports.

    These mirror the printed layouts of the legacy system (NSIAF-MMM):
        - Inventario General de Almacenes Físico Valorado.
        - Inventario de Almacenes con Stock Existente.
        - Entradas y Salidas Valorado por Cuenta Contable.
        - Kardex Físico y Valorado.
        - Estadísticas de Salida de Artículos.
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# 1. Inventario General Físico Valorado                                       #
# --------------------------------------------------------------------------- #
class PhysicalValuedItemSchema(_Base):
    '''
        One item row. `agregado = inicio + ingreso`, `final = agregado - egreso`
        on both the physical (quantity) and valued (money) sides.
    '''
    item_code: str
    item_name: str
    unit: str
    fisico_inicio: Decimal
    fisico_ingreso: Decimal
    fisico_agregado: Decimal
    fisico_egreso: Decimal
    fisico_final: Decimal
    valorado_inicio: Decimal
    valorado_ingreso: Decimal
    valorado_agregado: Decimal
    valorado_egreso: Decimal
    valorado_final: Decimal
    precio_unitario: Decimal


class PhysicalValuedGroupSchema(_Base):
    '''
        Accounting group block with its item rows and closing valuation.
    '''
    group_code: str
    group_name: str
    items: List[PhysicalValuedItemSchema]
    fisico_final: Decimal
    valorado_final: Decimal


class PhysicalValuedSummaryRowSchema(_Base):
    '''
        One line of the by-group summary (captura 5 / resumen).
    '''
    group_code: str
    group_name: str
    fisico_final: Decimal
    valorado_final: Decimal


class PhysicalValuedReportSchema(_Base):
    '''
        Full Inventario General Físico Valorado report.
    '''
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    groups: List[PhysicalValuedGroupSchema]
    summary: List[PhysicalValuedSummaryRowSchema]
    grand_total_valorado: Decimal


# --------------------------------------------------------------------------- #
# 2. Inventario con Stock Existente                                           #
# --------------------------------------------------------------------------- #
class StockOnHandItemSchema(_Base):
    '''
        Item with remaining stock, valued from its live PEPS/FIFO layers.
    '''
    item_code: str
    item_name: str
    unit: str
    saldo_existente: Decimal
    precio_unitario: Decimal
    total_valorado: Decimal


class StockOnHandGroupSchema(_Base):
    '''
        Accounting group block for the stock-on-hand report.
    '''
    group_code: str
    group_name: str
    items: List[StockOnHandItemSchema]
    total_valorado: Decimal


class StockOnHandSummaryRowSchema(_Base):
    '''
        By-group summary line (captura 7 / resumen).
    '''
    group_code: str
    group_name: str
    saldo_existente: Decimal
    total_valorado: Decimal


class StockOnHandReportSchema(_Base):
    '''
        Full Inventario con Stock Existente report (snapshot as of generated_at).
    '''
    generated_at: datetime
    groups: List[StockOnHandGroupSchema]
    summary: List[StockOnHandSummaryRowSchema]
    grand_total_valorado: Decimal


# --------------------------------------------------------------------------- #
# 3. Entradas y Salidas Valorado por Cuenta Contable                          #
# --------------------------------------------------------------------------- #
class InOutByGroupRowSchema(_Base):
    '''
        Valued ins/outs for a single accounting group over the range.
    '''
    group_code: str
    group_name: str
    ingresos: Decimal
    salidas: Decimal
    saldo: Decimal


class InOutByGroupReportSchema(_Base):
    '''
        Full Entradas y Salidas Valorado por Cuenta Contable report.
    '''
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    rows: List[InOutByGroupRowSchema]
    total_ingresos: Decimal
    total_salidas: Decimal
    total_saldo: Decimal


# --------------------------------------------------------------------------- #
# 4. Kardex Físico y Valorado                                                 #
# --------------------------------------------------------------------------- #
class KardexValuedLineSchema(_Base):
    '''
        A single valued kardex line with running physical and money balances.
    '''
    created_at: datetime
    detail: str
    source_entry_id: Optional[int]
    entrada_qty: Decimal
    salida_qty: Decimal
    saldo_qty: Decimal
    unit_cost: Optional[Decimal]
    entrada_val: Decimal
    salida_val: Decimal
    saldo_val: Decimal


class KardexValuedItemSchema(_Base):
    '''
        Kardex of a single item with opening/closing balances.
    '''
    item_code: str
    item_name: str
    unit: str
    group_name: str
    saldo_inicial_qty: Decimal
    saldo_inicial_val: Decimal
    lines: List[KardexValuedLineSchema]
    saldo_final_qty: Decimal
    saldo_final_val: Decimal


class KardexValuedReportSchema(_Base):
    '''
        Full Kardex Físico y Valorado report (one or many items).
    '''
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    items: List[KardexValuedItemSchema]


# --------------------------------------------------------------------------- #
# 5. Estadísticas de Salida de Artículos                                      #
# --------------------------------------------------------------------------- #
class OutflowLineSchema(_Base):
    '''
        A single delivery line: who received how much and when.
    '''
    created_at: datetime
    recipient: str
    request_code: Optional[str]
    quantity: Decimal


class OutflowItemSchema(_Base):
    '''
        Aggregated outflow of a single item over the range.
    '''
    item_code: str
    item_name: str
    unit: str
    total_salida: Decimal
    lines: List[OutflowLineSchema]


class OutflowReportSchema(_Base):
    '''
        Full Estadísticas de Salida de Artículos report.
    '''
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    items: List[OutflowItemSchema]
    grand_total_salida: Decimal
