'''
    Analytics controllers.
'''
from typing import Any, Dict, List, Optional, Tuple
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    AnalyticsRunResponse,
    AnalyticsSummary,
    CommercialSummaryResponse,
    ForecastResponse,
    Opportunity,
    PortfolioResponse,
    SegmentationResponse
)
from services.analytics import (
    build_commercial_summary,
    build_concentration,
    build_efficiency,
    build_forecast,
    build_growth,
    build_margin,
    build_portfolio,
    build_segmentation,
    compute_opportunities
)
from services.analytics_utils import (
    apply_date_range,
    get_dataset_metadata,
    get_latest_run_for_dataset,
    load_dataframe_from_s3,
    persist_run,
    setting
)
from services.environment import load_and_validate_env_vars
from services.utils import handle_service_errors


# Caps on opportunities kept in the run (DynamoDB item limit + usable table)
# and the affinity-engine tuning knobs. Configurable per deployment.
_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'ANALYTICS_MAX_PER_PRODUCT': int,
    'ANALYTICS_MAX_OPPORTUNITIES': int,
    'AFFINITY_MIN_SUPPORT': float,
    'AFFINITY_MIN_LIFT': float,
    'AFFINITY_TOP_N_PER_PDV': int,
    'AFFINITY_ITEM_LEVEL': str,
})
_MAX_PER_PRODUCT = setting(_SETTINGS, 'ANALYTICS_MAX_PER_PRODUCT', 60)
_MAX_OPPORTUNITIES = setting(_SETTINGS, 'ANALYTICS_MAX_OPPORTUNITIES', 800)


def _top_opportunities_per_product(opportunities: List[Opportunity]) -> List[Opportunity]:
    '''
        Keeps the top-scoring stores for each recommended product, so the
        product summary lists every recommendation instead of only the single
        highest-scoring product. Bounded by _MAX_PER_PRODUCT and _MAX_OPPORTUNITIES.
    '''
    from collections import defaultdict # pylint: disable=import-outside-toplevel
    ranked = sorted(opportunities, key = lambda opp: opp.opportunity_score, reverse = True)
    per_product: Dict[Any, List[Opportunity]] = defaultdict(list)
    kept: List[Opportunity] = []
    for opp in ranked:
        product = opp.recommended_product_id or opp.recommended_product_name
        if len(per_product[product]) < _MAX_PER_PRODUCT:
            per_product[product].append(opp)
            kept.append(opp)
        if len(kept) >= _MAX_OPPORTUNITIES:
            break
    return kept


def _engine_parameters() -> Dict[str, Any]:
    '''
        Reads the affinity-engine tuning parameters from the environment.

        item_level defaults to 'category': at SKU level real mass-consumption
        baskets are too sparse to yield rules, while category-level affinity is
        dense and interpretable. Override with AFFINITY_ITEM_LEVEL=product.
    '''
    return {
        'min_support': setting(_SETTINGS, 'AFFINITY_MIN_SUPPORT', 0.01),
        'min_lift': setting(_SETTINGS, 'AFFINITY_MIN_LIFT', 1.0),
        'top_n_per_pdv': setting(_SETTINGS, 'AFFINITY_TOP_N_PER_PDV', 10),
        'item_level': setting(_SETTINGS, 'AFFINITY_ITEM_LEVEL', 'category').strip().lower()
    }


def _opportunities_from_item(items: List[Dict[str, Any]]) -> List[Opportunity]:
    '''
        Rebuilds the opportunity DTOs from a stored DynamoDB item.

        Args:
            items (List[Dict[str, Any]]): Opportunities as persisted.

        Returns:
            List[Opportunity]: Validated DTOs.
    '''
    return [Opportunity.model_validate(item) for item in items]


def _summary_from_item(summary: Dict[str, Any]) -> AnalyticsSummary:
    '''
        Rebuilds the run summary DTO from a stored DynamoDB item.

        Args:
            summary (Dict[str, Any]): Summary as persisted.

        Returns:
            AnalyticsSummary: Validated DTO.
    '''
    return AnalyticsSummary.model_validate(summary)


def _scoped_dataframe(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[Any, Dict[str, Any]]:
    '''
        Loads the normalized dataset from S3 and narrows it to the requested
        date window.

        Every analysis endpoint scopes its data the same way, so the window is
        resolved once here and reported back with the result: a manager reading
        a number needs to know which period produced it.

        Args:
            dynamodb_resource (ServiceResource): Injected DynamoDB resource.
            dataset_id (str): Dataset to load.
            params (dict | None): May carry 'date_from' and 'date_to'.

        Returns:
            Tuple[Any, Dict[str, Any]]: The scoped DataFrame and the period
                descriptor.

        Raises:
            InvalidInputError: If the requested window leaves no rows.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])
    options = params or {}
    return apply_date_range(
        dataframe = dataframe,
        date_from = options.get('date_from'),
        date_to = options.get('date_to')
    )


@handle_service_errors('ANALYTICS')
async def commercial_summary_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> CommercialSummaryResponse:
    '''
        Loads the normalized dataset and builds the full commercial summary:
        the sales picture plus growth, concentration, efficiency and gross
        margin. Read-only: everything is derived on the fly from the dataset,
        so nothing is persisted as a run.
    '''
    dataframe, period = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    summary = build_commercial_summary(dataframe)
    return CommercialSummaryResponse(
        dataset_id = dataset_id,
        period = period,
        growth = build_growth(dataframe),
        concentration = build_concentration(dataframe),
        efficiency = build_efficiency(dataframe),
        margin = build_margin(dataframe),
        **summary.model_dump()
    )


@handle_service_errors('ANALYTICS')
async def portfolio_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> PortfolioResponse:
    '''
        Loads the normalized dataset and builds the portfolio-health view:
        coverage, churn, month-by-month client movement and the actionable list
        of clients at risk of being lost. Read-only.
    '''
    dataframe, period = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    return PortfolioResponse(
        dataset_id = dataset_id,
        period = period,
        **build_portfolio(dataframe).model_dump()
    )


@handle_service_errors('ANALYTICS')
async def forecast_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ForecastResponse:
    '''
        Loads the normalized dataset and builds the demand forecast with the
        requested method / horizon / grouping. Read-only.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    result = build_forecast(
        dataframe = dataframe,
        months_ahead = params.get('months_ahead', 3),
        method = params.get('method', 'linear'),
        group_by = params.get('group_by')
    )
    return ForecastResponse(dataset_id = dataset_id, **result.model_dump())


@handle_service_errors('ANALYTICS')
async def segmentation_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SegmentationResponse:
    '''
        Loads the normalized dataset and builds the customer value segmentation
        (Alto/Medio/Bajo). Read-only.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    result = build_segmentation(dataframe)
    return SegmentationResponse(dataset_id = dataset_id, **result.model_dump())


@handle_service_errors('ANALYTICS')
async def run_analytics_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> AnalyticsRunResponse:
    '''
        Full pipeline:
          1. Validate the dataset exists in ingest and is 'validated'.
          2. Download the .xlsx/.csv from S3.
          3. Run affinity × drop size.
          4. Persist the run.
          5. Return the public response.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, params)

    parameters = _engine_parameters()
    opportunities, summary = compute_opportunities(
        dataframe = dataframe,
        min_support = parameters['min_support'],
        min_lift = parameters['min_lift'],
        top_n_per_pdv = parameters['top_n_per_pdv'],
        item_level = parameters['item_level']
    )

    # A large dataset yields tens of thousands of opportunities — too big for one
    # DynamoDB item (400 KB). Keep the top stores PER recommended product (not the
    # global top, which would all be the single dominant product), so the
    # product-level summary shows every recommendation. `summary` keeps the total.
    top_opportunities = _top_opportunities_per_product(opportunities)

    persisted = persist_run(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'dataset_id': dataset_id,
            'status': 'completed',
            'owner_email': current_user,
            'summary': summary.model_dump(),
            'opportunities': [opportunity.model_dump() for opportunity in top_opportunities],
            'parameters': parameters
        }
    )
    return AnalyticsRunResponse(
        dataset_id = persisted['dataset_id'],
        run_id = persisted['run_id'],
        status = persisted['status'],
        summary = _summary_from_item(persisted['summary']),
        opportunities = _opportunities_from_item(persisted['opportunities']),
        created_at = persisted['created_at']
    )


@handle_service_errors('ANALYTICS')
async def get_results_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> AnalyticsResultsResponse:
    '''
        Returns the most recent persisted run for the dataset.
    '''
    run = get_latest_run_for_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    return AnalyticsResultsResponse(
        dataset_id = run['dataset_id'],
        run_id = run['run_id'],
        status = run['status'],
        summary = _summary_from_item(run['summary']),
        opportunities = _opportunities_from_item(run['opportunities']),
        created_at = run['created_at']
    )


@handle_service_errors('ANALYTICS')
async def get_pdv_opportunities_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    pdv_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> AnalyticsPdvResponse:
    '''
        Returns the opportunities for a single PdV from the latest run.
    '''
    run = get_latest_run_for_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    pdv_opportunities = [
        opp for opp in run['opportunities']
        if str(opp.get('pdv_id')) == str(pdv_id)
    ]
    return AnalyticsPdvResponse(
        dataset_id = run['dataset_id'],
        pdv_id = pdv_id,
        opportunities = _opportunities_from_item(pdv_opportunities)
    )
