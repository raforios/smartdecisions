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
        description = 'Ranking metric = lift * confidence * expected_drop_size_amount (or _units when amount missing).'
    )
    rationale: str = Field(..., description = 'Human-readable Spanish explanation for the end user.')


class AnalyticsSummary(BaseModel):
    '''
        High-level numbers describing an analytics run.
    '''
    total_pdvs_with_opportunities: int = Field(..., ge = 0)
    total_opportunities: int = Field(..., ge = 0)
    total_expected_value: Optional[float] = Field(
        default = None,
        description = 'Sum of expected_drop_size_amount across all opportunities (when prices are available).'
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
