'''
    Analytics controllers.
'''
from typing import Any, Dict, List, Optional, Tuple
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    RunListResponse,
    RunSummary,
    AnalyticsRunResponse,
    AnalyticsSummary,
    CommercialSummaryResponse,
    ForecastResponse,
    Opportunity,
    PortfolioResponse,
    SegmentationResponse
)
from schemas.receivables import (
    CreditPolicyRequest,
    CreditPolicyResponse,
    ReceivablesResponse
)
from schemas.stock import StockResponse
from services.receivables import build_receivables, resolve_policy
from services.stock import build_stock
from services.affinity import compute_opportunities
from services.analytics import build_commercial_summary
from services.concentration import build_concentration
from services.efficiency import build_efficiency
from services.forecast import build_forecast
from services.growth import build_growth
from services.margin import build_margin
from services.portfolio import build_portfolio
from services.segmentation import build_segmentation
from services.volume import build_volume_source
from services.analytics_utils import (
    apply_date_range,
    get_credit_policy,
    get_dataset_metadata,
    get_latest_run_for_dataset,
    HISTORY_DEFAULT_LIMIT,
    list_runs_for_owner,
    load_dataframe_from_s3,
    persist_run,
    save_credit_policy
)
from services.environment import load_and_validate_env_vars
from services.utils import handle_service_errors


# Caps on opportunities kept in the run (DynamoDB item limit + usable table)
# and the affinity-engine tuning knobs. Configurable per deployment.
_SETTINGS = load_and_validate_env_vars({
    'ANALYTICS_MAX_PER_PRODUCT': int,
    'ANALYTICS_MAX_OPPORTUNITIES': int,
    'AFFINITY_MIN_SUPPORT': float,
    'AFFINITY_MIN_LIFT': float,
    'AFFINITY_TOP_N_PER_PDV': int,
    'AFFINITY_ITEM_LEVEL': str,
})
_MAX_PER_PRODUCT = _SETTINGS['ANALYTICS_MAX_PER_PRODUCT']
_MAX_OPPORTUNITIES = _SETTINGS['ANALYTICS_MAX_OPPORTUNITIES']


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
        'min_support': _SETTINGS['AFFINITY_MIN_SUPPORT'],
        'min_lift': _SETTINGS['AFFINITY_MIN_LIFT'],
        'top_n_per_pdv': _SETTINGS['AFFINITY_TOP_N_PER_PDV'],
        'item_level': _SETTINGS['AFFINITY_ITEM_LEVEL'].strip().lower()
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
        the sales picture plus growth, volume source, concentration, efficiency
        and gross margin. Read-only: everything is derived on the fly from the
        dataset, so nothing is persisted as a run.
    '''
    dataframe, period = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    summary = build_commercial_summary(dataframe)
    return CommercialSummaryResponse(
        dataset_id = dataset_id,
        period = period,
        growth = build_growth(dataframe),
        volume_source = build_volume_source(dataframe),
        concentration = build_concentration(dataframe),
        efficiency = build_efficiency(dataframe),
        margin = build_margin(dataframe),
        **summary.model_dump()
    )


@handle_service_errors('ANALYTICS')
async def receivables_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ReceivablesResponse:
    '''
        Loads the dataset with its payments and builds the receivables view:
        position, aging, recoverability, who owes, who collects, what falls due
        and what the credit is worth once financed and provisioned.

        The payments are read from the collections file INGEST attached to the
        dataset. Their absence is not an error: it means every credit invoice is
        still open, which is what a client who has not loaded payments yet
        should see.

        Read-only: everything is derived on the fly, so nothing is persisted as
        a run.
    '''
    dataframe, period = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    collections_key = metadata.get('collections_s3_key')

    block = build_receivables(
        sales = dataframe,
        collections = load_dataframe_from_s3(collections_key) if collections_key else None,
        stored_policy = get_credit_policy(
            dynamodb_resource = dynamodb_resource,
            owner_email = current_user
        )
    )
    return ReceivablesResponse(
        dataset_id = dataset_id,
        period = period,
        **block.model_dump()
    )


@handle_service_errors('ANALYTICS')
async def stock_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: Dict[str, Any],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        Loads the latest stock snapshot of the dataset and reports what it
        implies: coverage in days at the demand observed, which products are
        about to run out and when, and how much capital is immobilized.

        The snapshot comes from the stock file INGEST attached to the dataset.
        Its absence is answered with a code, not with an empty warehouse.

        Read-only, and deliberately so: `available` reflects what the client's
        ERP already committed. Nothing here reserves or promises stock.
    '''
    dataframe, period = _scoped_dataframe(dynamodb_resource, dataset_id, params)
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    stock_key = metadata.get('stock_s3_key')

    block = build_stock(
        sales = dataframe,
        stock = load_dataframe_from_s3(stock_key) if stock_key else None
    )
    return StockResponse(
        dataset_id = dataset_id,
        period = period,
        **block.model_dump()
    )


@handle_service_errors('ANALYTICS')
async def get_credit_policy_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CreditPolicyResponse:
    '''
        Returns the credit policy that will be applied to the caller's book:
        their own where they set it, the service default everywhere else.
    '''
    resolved = resolve_policy(get_credit_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user
    ))
    return CreditPolicyResponse(
        owner_email = current_user,
        **resolved.as_dto().model_dump()
    )


@handle_service_errors('ANALYTICS')
async def save_credit_policy_controller(
    dynamodb_resource: ServiceResource,
    policy: CreditPolicyRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CreditPolicyResponse:
    '''
        Stores the caller's credit policy and answers with how it resolves.

        Answering with the resolved policy and not with what was sent is
        deliberate: the caller has to be able to see which defaults filled the
        gaps before a provision is computed with them.
    '''
    save_credit_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        policy = policy.model_dump(exclude_none = True)
    )
    return await get_credit_policy_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user
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
async def list_runs_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    limit: int = HISTORY_DEFAULT_LIMIT
) -> RunListResponse:
    '''
        Returns the caller's own analyses, most recent first.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            request (Request): Incoming request, used by the audit decorator.
            current_user (str): Authenticated caller and owner of the rows.
            limit (int): Most rows to return.

        Returns:
            RunListResponse: The caller's analyses.
    '''
    items = list_runs_for_owner(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        limit = limit
    )
    return RunListResponse(
        owner_email = current_user,
        count = len(items),
        runs = [
            RunSummary(
                run_id = item['run_id'],
                dataset_id = item['dataset_id'],
                status = item['status'],
                total_opportunities = int(item.get('summary', {}).get(
                    'total_opportunities', 0)),
                total_pos_with_opportunities = int(item.get('summary', {}).get(
                    'total_pos_with_opportunities', 0)),
                total_expected_value = _optional_float(
                    item.get('summary', {}).get('total_expected_value')
                ),
                created_at = str(item['created_at'])
            )
            for item in items
        ]
    )


def _optional_float(value: Any) -> Optional[float]:
    '''
        Renders a DynamoDB number as a float, tolerating its absence.

        Args:
            value (Any): Raw stored value, possibly None or Decimal.

        Returns:
            float | None: The number, or None when there is none.
    '''
    return None if value is None else float(value)


@handle_service_errors('ANALYTICS')
async def get_results_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> AnalyticsResultsResponse:
    '''
        Returns the most recent persisted run for the dataset.
    '''
    run = get_latest_run_for_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
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
    current_user: str
) -> AnalyticsPdvResponse:
    '''
        Returns the opportunities for a single PdV from the latest run.
    '''
    run = get_latest_run_for_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
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
