'''
    Pydantic V2 DTOs for the Analytics service.

    The public contract is the list of `Opportunity` items: each one represents
    a (point of sale, recommended product) pair, ranked by expected monetary
    impact (Afinidad × Drop Size, per SMARTDECISIONS.md §2). The pairing of
    affinity rules with drop-size weighting is the differentiator of the SaaS.
'''
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Opportunity(BaseModel):
    '''
        A single actionable recommendation for a point of sale.
    '''
    model_config = ConfigDict(json_schema_extra = {
        'example': {
            'pdv_id': 'PDV-007',
            'pdv_name': 'Tienda Doña Rosa',
            'recommended_product_id': 'SKU-B200',
            'recommended_product_name': 'Yogurt Natural 1L',
            'based_on_products': ['SKU-A100'],
            'support': 0.18,
            'confidence': 0.62,
            'lift': 2.4,
            'expected_drop_size_units': 6.0,
            'expected_drop_size_amount': 90.0,
            'opportunity_score': 133.92,
            'rationale': (
                'Quienes compran Galleta Integral 200g tienden a comprar Yogurt '
                'Natural 1L (lift 2.4). Drop size esperado: 6 unidades / $90.'
            )
        }
    })

    pdv_id: str
    pdv_name: Optional[str] = None
    recommended_product_id: str
    recommended_product_name: Optional[str] = None
    based_on_products: list[str] = Field(
        ..., description = 'Antecedent SKUs the PdV already purchases.'
    )
    support: float = Field(..., ge = 0, le = 1)
    confidence: float = Field(..., ge = 0, le = 1)
    lift: float = Field(..., ge = 0)
    expected_drop_size_units: float = Field(..., ge = 0)
    expected_drop_size_amount: Optional[float] = Field(
        default = None, ge = 0,
        description = 'Only present when precio_unitario is available in the source.'
    )
    opportunity_score: float = Field(
        ..., ge = 0,
        description = '''Ranking metric = lift * confidence * expected_drop_size_amount
        (or _units when amount missing).'''
    )
    rationale: str = Field(...,
        description = 'Human-readable Spanish explanation for the end user.')


class AnalyticsSummary(BaseModel):
    '''
        High-level numbers describing an analytics run.
    '''
    total_pdvs_with_opportunities: int = Field(..., ge = 0)
    total_opportunities: int = Field(..., ge = 0)
    total_expected_value: Optional[float] = Field(
        default = None,
        description = '''Sum of expected_drop_size_amount across all opportunities
        (when prices are available).'''
    )
    affinity_rules_evaluated: int = Field(..., ge = 0)
    parameters: dict


class AnalyticsRunResponse(BaseModel):
    '''
        Response payload for POST /v1/analytics/run/{dataset_id}.
    '''
    dataset_id: str
    run_id: str
    status: str = Field(..., description = "'completed' or 'failed'.")
    summary: AnalyticsSummary
    opportunities: list[Opportunity]
    created_at: datetime


class AnalyticsResultsResponse(BaseModel):
    '''
        Compact result for GET /v1/analytics/results/{dataset_id}.
    '''
    dataset_id: str
    run_id: str
    status: str
    summary: AnalyticsSummary
    opportunities: list[Opportunity]
    created_at: datetime


class AnalyticsPdvResponse(BaseModel):
    '''
        Top N opportunities for a single point of sale.
    '''
    dataset_id: str
    pdv_id: str
    opportunities: list[Opportunity]


# --- Commercial summary (general sales dashboard) ---

class KpiCard(BaseModel):
    '''
        A single headline KPI. `format` tells the UI how to render `value`
        ('money' -> Bs with 2 decimals, 'int' -> thousands-grouped integer).
    '''
    label: str
    value: float
    format: str
    hint: Optional[str] = None


class RankRow(BaseModel):
    '''One row of a best/worst ranking: a readable label and its amount (Bs).'''
    label: str
    monto: float


class DistRow(BaseModel):
    '''
        One slice of a categorical distribution: label, amount (Bs) and its
        share of the total.
    '''
    label: str
    monto: float
    porcentaje: float


class TrendPoint(BaseModel):
    '''One point of the monthly sales trend.'''
    mes: str
    monto: float


class CommercialSummaryResponse(BaseModel):
    '''
        Full commercial summary for GET /v1/analytics/summary/{dataset_id}.
        Every section is pre-labeled and pre-aggregated for tables + charts.
    '''
    dataset_id: str
    kpis: list[KpiCard]
    mejor_cliente: list[RankRow]
    peor_cliente: list[RankRow]
    top_productos: list[RankRow]
    bottom_productos: list[RankRow]
    por_categoria: list[DistRow]
    por_canal: list[DistRow]
    por_region: list[DistRow]
    por_vendedor: list[DistRow]
    tendencia_mensual: list[TrendPoint]


# --- Demand forecast ---

class ForecastPoint(BaseModel):
    '''One month of a forecast series (historical or projected).'''
    mes: str
    monto: float


class ForecastSeries(BaseModel):
    '''
        A named forecast series: its historical months and the projected ones,
        plus the projected total for the horizon.
    '''
    nombre: str
    historico: list[ForecastPoint]
    pronostico: list[ForecastPoint]
    total_pronosticado: float


class ForecastResponse(BaseModel):
    '''
        Demand forecast for GET /v1/analytics/forecast/{dataset_id}.
    '''
    dataset_id: str
    method: str
    method_label: str
    months_ahead: int
    series: list[ForecastSeries]


# --- Customer segmentation ---

class SegmentTier(BaseModel):
    '''A value tier (Alto/Medio/Bajo) with its client count and sales share.'''
    tier: str
    clientes: int
    monto: float
    porcentaje: float


class SegmentClient(BaseModel):
    '''One client row: label, tier, total amount and number of purchases.'''
    cliente: str
    tier: str
    monto: float
    compras: int


class SegmentationResponse(BaseModel):
    '''
        Customer value segmentation for GET /v1/analytics/segmentation/{dataset_id}.
    '''
    dataset_id: str
    total_clientes: int
    tiers: list[SegmentTier]
    clientes: list[SegmentClient]
