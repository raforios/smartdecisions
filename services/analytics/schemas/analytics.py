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
        ('money' -> Bs with 2 decimals, 'int' -> thousands-grouped integer,
        'percent' -> share, 'decimal' -> plain number).

        `value` is optional because a percentage variation without a base
        period is undefined, not zero: growing from no sales at all has no
        percentage. The UI renders those as '—' instead of a misleading 0%.
    '''
    label: str
    value: Optional[float] = None
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


# --- Period scoping (shared by every analysis endpoint) ---

class PeriodInfo(BaseModel):
    '''
        Describes the window an analysis actually ran on, so the UI can state
        'Enero a Marzo de 2024' instead of leaving the user guessing whether a
        filter was applied.
    '''
    disponible_desde: Optional[str] = None
    disponible_hasta: Optional[str] = None
    desde: Optional[str] = None
    hasta: Optional[str] = None
    filtrado: bool = False
    filas: int = 0


# --- Growth (month-over-month, year-over-year, seasonality) ---

class MonthlyChange(BaseModel):
    '''One month of the sales series with its variation against the previous one.'''
    mes: str
    monto: float
    variacion: Optional[float] = None


class SeasonIndex(BaseModel):
    '''
        Seasonality index of one calendar month: 100 is an average month, 130
        means that month historically sells 30% above average.
    '''
    mes: str
    indice: float
    monto_promedio: float


class CategoryMix(BaseModel):
    '''
        How a category's share of total sales moved between the last month and
        the one before it. `cambio_participacion` is in percentage points.
    '''
    label: str
    monto_actual: float
    monto_anterior: float
    variacion: Optional[float] = None
    participacion_actual: float
    participacion_anterior: float
    cambio_participacion: float


class GrowthBlock(BaseModel):
    '''Growth section of the commercial summary.'''
    kpis: list[KpiCard] = []
    variacion_mensual: list[MonthlyChange] = []
    estacionalidad: list[SeasonIndex] = []
    mix_categoria: list[CategoryMix] = []


# --- Concentration (dependency risk) ---

class ClientConcentration(BaseModel):
    '''
        How dependent the business is on a few clients: what the top 10 weigh,
        how many clients make up 80% of sales (Pareto) and the HHI index with a
        plain-language reading of it.
    '''
    total_clientes: int = 0
    top10_monto: float = 0.0
    top10_porcentaje: float = 0.0
    pareto_clientes: int = 0
    pareto_porcentaje_clientes: float = 0.0
    hhi: float = 0.0
    hhi_lectura: Optional[str] = None
    top_clientes: list[RankRow] = []


class AbcClass(BaseModel):
    '''One ABC class with its product count, amount, share and what it means.'''
    clase: str
    productos: int
    monto: float
    porcentaje: float
    descripcion: str


class AbcProduct(BaseModel):
    '''One product's ABC classification and its cumulative share of sales.'''
    label: str
    monto: float
    clase: str
    acumulado: float


class AbcBlock(BaseModel):
    '''ABC classification of the product catalog.'''
    resumen: list[AbcClass] = []
    productos: list[AbcProduct] = []


class ConcentrationBlock(BaseModel):
    '''Concentration section of the commercial summary.'''
    clientes: ClientConcentration = ClientConcentration()
    abc: AbcBlock = AbcBlock()


# --- Efficiency (drop size, sales force, realized price) ---

class SellerProductivity(BaseModel):
    '''Productivity of one salesperson.'''
    vendedor: str
    monto: float
    pedidos: int
    clientes: int
    ticket_promedio: float
    lineas_por_pedido: float
    monto_por_cliente: float


class PriceDrift(BaseModel):
    '''
        Realized price of a product in the recent half of the period versus the
        earlier half. Catches discounting that never shows up in a price list.
    '''
    producto: str
    precio_actual: float
    precio_anterior: float
    variacion: Optional[float] = None


class EfficiencyBlock(BaseModel):
    '''Efficiency section of the commercial summary.'''
    kpis: list[KpiCard] = []
    vendedores: list[SellerProductivity] = []
    precios: list[PriceDrift] = []


# --- Gross margin (requires the optional unit-cost column) ---

class MarginRow(BaseModel):
    '''Revenue, cost and gross margin of one category / product / client / seller.'''
    label: str
    monto: float
    costo: float
    margen: float
    margen_porcentaje: float


class MarginAlert(BaseModel):
    '''A product sold below cost or at a negligible margin, with the reason.'''
    label: str
    monto: float
    margen: float
    margen_porcentaje: float
    motivo: str


class MarginBlock(BaseModel):
    '''
        Profitability section. `disponible` is False when the uploaded file had
        no 'Costo Unitario' column, in which case every list is empty and the UI
        hides the block instead of rendering zeros.
    '''
    disponible: bool = False
    kpis: list[KpiCard] = []
    por_categoria: list[MarginRow] = []
    por_producto: list[MarginRow] = []
    por_cliente: list[MarginRow] = []
    por_vendedor: list[MarginRow] = []
    alertas: list[MarginAlert] = []


# --- Portfolio health ---

class PortfolioMovement(BaseModel):
    '''Client movement in one month: new, recovered, retained and lost.'''
    mes: str
    activos: int
    nuevos: int
    recuperados: int
    retenidos: int
    perdidos: int
    churn: Optional[float] = None


class ClientAtRisk(BaseModel):
    '''
        A client whose purchases dropped sharply or who stopped buying.
        Recency is measured against the newest date in the dataset, not today,
        so an old file does not report the whole portfolio as lost.
    '''
    cliente: str
    monto_promedio_mes: float
    monto_ultimo_mes: float
    variacion: Optional[float] = None
    dias_sin_comprar: int
    ultima_compra: Optional[str] = None
    motivo: str


class PortfolioResponse(BaseModel):
    '''
        Portfolio health for GET /v1/analytics/portfolio/{dataset_id}.
    '''
    dataset_id: str
    periodo: PeriodInfo = PeriodInfo()
    kpis: list[KpiCard] = []
    movimiento: list[PortfolioMovement] = []
    en_riesgo: list[ClientAtRisk] = []
    total_en_riesgo: int = 0


# --- Commercial summary (assembled last: it embeds every block above) ---

class CommercialSummaryResponse(BaseModel):
    '''
        Full commercial summary for GET /v1/analytics/summary/{dataset_id}.

        The first block answers 'how much did we sell'; the four that follow
        answer the questions a manager asks next — is it growing, how exposed
        are we, how efficiently are we selling, and what does it actually earn.
        Every section is pre-labeled and pre-aggregated for tables + charts.
    '''
    dataset_id: str
    periodo: PeriodInfo = PeriodInfo()
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
    crecimiento: GrowthBlock = GrowthBlock()
    concentracion: ConcentrationBlock = ConcentrationBlock()
    eficiencia: EfficiencyBlock = EfficiencyBlock()
    margen: MarginBlock = MarginBlock()
