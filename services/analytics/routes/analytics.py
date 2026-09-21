'''
    Analytics: routes handler.
'''
from fastapi import APIRouter, Depends, Path, Query, Request, status
from boto3.resources.base import ServiceResource

from controllers.analytics import (
    get_credit_policy_controller,
    receivables_controller,
    save_credit_policy_controller,
    stock_controller,
    commercial_summary_controller,
    forecast_controller,
    get_pdv_opportunities_controller,
    get_results_controller,
    list_runs_controller,
    portfolio_controller,
    run_analytics_controller,
    segmentation_controller
)
from schemas.receivables import (
    CreditPolicyRequest,
    CreditPolicyResponse,
    ReceivablesResponse
)
from schemas.stock import StockResponse
from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    RunListResponse,
    AnalyticsRunResponse,
    CommercialSummaryResponse,
    ForecastResponse,
    PortfolioResponse,
    SegmentationResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.analytics_utils import (
    FORECAST_MONTHS_AHEAD,
    HISTORY_DEFAULT_LIMIT
)
from services.forecast import MAX_MONTHS_AHEAD
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/analytics', tags = ['Analytics'])

_ISO_DATE = '^\\d{4}-\\d{2}-\\d{2}$'


class DateWindow: # pylint: disable=too-few-public-methods
    '''
        Optional reporting window shared by every analysis endpoint.

        Grouped as a dependency rather than two loose query parameters because
        the window is one concept: it travels together, it is validated
        together, and declaring it once keeps the contract from drifting
        between endpoints.
    '''

    def __init__(
        self,
        date_from: str = Query(
            None, pattern = _ISO_DATE, description = 'Inclusive start, YYYY-MM-DD.'
        ),
        date_to: str = Query(
            None, pattern = _ISO_DATE, description = 'Inclusive end, YYYY-MM-DD.'
        )
    ):
        self.date_from = date_from
        self.date_to = date_to

    def as_params(self) -> dict:
        '''
            Returns the window as the params dict the controllers expect.

            Returns:
                dict: Keys 'date_from' and 'date_to'.
        '''
        return {'date_from': self.date_from, 'date_to': self.date_to}


class ForecastOptions: # pylint: disable=too-few-public-methods
    '''
        Forecast tuning on top of the shared window: method, horizon and
        whether to split the projection by category.

        The window is composed rather than inherited so its query parameters
        stay declared in exactly one place.
    '''

    def __init__(
        self,
        window: DateWindow = Depends(),
        method: str = Query('linear', pattern = '^(linear|moving_average)$'),
        months_ahead: int = Query(
            FORECAST_MONTHS_AHEAD, ge = 1, le = MAX_MONTHS_AHEAD
        ),
        group_by: str = Query(None, pattern = '^(category)$')
    ):
        self.window = window
        self.method = method
        self.months_ahead = months_ahead
        self.group_by = group_by

    def as_params(self) -> dict:
        '''
            Returns the forecast parameters merged with the window.

            Returns:
                dict: Method, horizon, grouping and the date window.
        '''
        params = self.window.as_params()
        params.update({
            'method': self.method,
            'months_ahead': self.months_ahead,
            'group_by': self.group_by
        })
        return params


@router.get(
    '/summary/{dataset_id}',
    response_model = CommercialSummaryResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Commercial summary (KPIs, rankings, distributions, trend)',
    description = (
        'Reads the normalized dataset and returns the general sales dashboard: '
        'headline KPIs, best/worst client, top/bottom products, breakdowns by '
        'category/channel/region/seller and the monthly trend. Read-only.'
    )
)
async def commercial_summary_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> CommercialSummaryResponse:
    '''
        Endpoint returning the commercial summary for a dataset_id.
    '''
    message = f'Commercial summary for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await commercial_summary_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )


@router.get(
    '/forecast/{dataset_id}',
    response_model = ForecastResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Demand forecast (linear trend / moving average, total or by category)',
    description = (
        'Projects future monthly sales from the normalized dataset. Choose the '
        'method (linear / moving_average), the horizon in months and whether to '
        'split by category. Read-only.'
    )
)
async def forecast_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    options: ForecastOptions = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ForecastResponse:
    '''
        Endpoint returning the demand forecast for a dataset_id.
    '''
    message = (
        f'Forecast for dataset {dataset_id} '
        f'({options.method}, {options.months_ahead}m) by {current_user}.'
    )
    logger.info(message)
    return await forecast_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = options.as_params(),
        current_user = current_user,
        request = request
    )


@router.get(
    '/segmentation/{dataset_id}',
    response_model = SegmentationResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Customer value segmentation (Alto / Medio / Bajo)',
    description = (
        'Reads the normalized dataset and classifies clients into value tiers '
        'by their total purchases, so the team can prioritize. Read-only.'
    )
)
async def segmentation_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> SegmentationResponse:
    '''
        Endpoint returning the customer segmentation for a dataset_id.
    '''
    message = f'Segmentation for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await segmentation_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )


@router.post(
    '/run/{dataset_id}',
    response_model = AnalyticsRunResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Run the affinity × drop size engine on a previously ingested dataset',
    description = (
        'Reads the dataset from the ingest service (S3 via FILES bucket), '
        'computes association rules with a lightweight Apriori, weights each '
        'rule by the expected drop size of the consequent product and '
        'returns the top N opportunities per point of sale, ranked by '
        'expected monetary impact.'
    )
)
async def run_analytics_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> AnalyticsRunResponse:
    '''
        Endpoint to run the analytics pipeline on a dataset_id.
    '''
    message = f'Running analytics for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await run_analytics_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )


@router.get(
    '/runs',
    response_model = RunListResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Your own analyses, most recent first',
    description = (
        'Lists the analytics runs of the authenticated caller. Only theirs: the '
        'owner is part of the query, not a filter applied afterwards.'
    )
)
async def list_runs_endpoint(
    request: Request,
    limit: int = Query(
        HISTORY_DEFAULT_LIMIT, ge = 1, le = 100,
        description = 'Most rows to return.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> RunListResponse:
    ''' Endpoint listing the caller\'s own analyses. '''
    message = f'User: {current_user}. Requested their analysis history.'
    logger.info(message)

    return await list_runs_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user,
        limit = limit
    )


@router.get(
    '/results/{dataset_id}',
    response_model = AnalyticsResultsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the latest analytics run for a dataset',
    description = 'Returns the most recent persisted run (summary + opportunities).'
)
async def get_results_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> RunListResponse:
    '''
        Endpoint to retrieve the latest analytics results for a dataset.
    '''
    message = f'User: {current_user}. Retrieving analytics results for dataset {dataset_id}.'
    logger.info(message)
    return await get_results_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        request = request,
        current_user = current_user
    )


@router.get(
    '/results/{dataset_id}/pdv/{pdv_id}',
    response_model = AnalyticsPdvResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the top opportunities for a single point of sale',
    description = 'Filters the latest run to the recommendations targeting one PdV.'
)
async def get_pdv_opportunities_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    pdv_id: str = Path(..., min_length = 1, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> AnalyticsPdvResponse:
    '''
        Endpoint to retrieve opportunities filtered by point of sale.
    '''
    message = f'User: {current_user}. Retrieving opportunities for dataset {dataset_id} / pdv {
            pdv_id}.'
    logger.info(message)
    return await get_pdv_opportunities_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        pdv_id = pdv_id,
        request = request,
        current_user = current_user
    )


@router.get(
    '/receivables/{dataset_id}',
    response_model = ReceivablesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Receivables (aging, recoverability, collection agenda)',
    description = (
        'Reads the dataset with the payments attached to it and reports the '
        'credit book: how much is out, how old it is, how much of it is '
        'expected back, who owes it, who is responsible for collecting it, '
        'what falls due when, and what the credit leaves once financed and '
        'provisioned. Ages are measured against the last day with activity in '
        'the file, not today. The parameters applied travel in `policy`: the '
        'caller\'s own where they set them, the service defaults elsewhere. '
        'Read-only.'
    )
)
async def receivables_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ReceivablesResponse:
    '''
        Endpoint returning the receivables view for a dataset_id.
    '''
    message = f'Receivables for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await receivables_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )


@router.get(
    '/stock/{dataset_id}',
    response_model = StockResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Stock of the day (coverage, stockout risk, immobilized capital)',
    description = (
        'Reads the latest stock snapshot attached to the dataset and reports '
        'what it implies: days of coverage at the demand observed in the sales '
        'history, which products are about to run out and on what date, which '
        'ones hold capital nobody is buying, and the ABC class of each. '
        '`available` is on hand minus what the ERP already committed: it is '
        'REPORTED, never decided here — this service holds no reservations. '
        'Read-only.'
    )
)
async def stock_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> StockResponse:
    '''
        Endpoint returning the stock view for a dataset_id.
    '''
    message = f'Stock for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await stock_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )


@router.get(
    '/credit-policy',
    response_model = CreditPolicyResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Credit policy applied to the caller\'s book',
    description = (
        'Returns the aging buckets, the expected loss per bucket, the daily '
        'financial rate, the delinquency threshold and the term assumed when a '
        'credit sale states none. `source_code` says whether they are the '
        'caller\'s own parameters or the service defaults.'
    )
)
async def get_credit_policy_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> CreditPolicyResponse:
    '''
        Endpoint returning the caller's credit policy.
    '''
    message = f'Credit policy requested by {current_user}.'
    logger.info(message)
    return await get_credit_policy_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user
    )


@router.put(
    '/credit-policy',
    response_model = CreditPolicyResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Set the credit policy of the caller\'s book',
    description = (
        'Stores the parameters this client wants its receivables read with. '
        'Every field is optional and what is left out falls back to the service '
        'default, field by field. The answer is the RESOLVED policy, so the '
        'caller can see which defaults filled the gaps before a provision is '
        'computed with them.'
    )
)
async def save_credit_policy_endpoint(
    request: Request,
    policy: CreditPolicyRequest,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> CreditPolicyResponse:
    '''
        Endpoint storing the caller's credit policy.
    '''
    message = f'Credit policy updated by {current_user}.'
    logger.info(message)
    return await save_credit_policy_controller(
        dynamodb_resource = dynamodb_resource,
        policy = policy,
        request = request,
        current_user = current_user
    )


@router.get(
    '/portfolio/{dataset_id}',
    response_model = PortfolioResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Portfolio health (coverage, churn, clients at risk)',
    description = (
        'Reads the normalized dataset and reports how the client base is '
        'moving: coverage, purchase frequency, churn, month-by-month movement '
        '(new / recovered / retained / lost) and the actionable list of '
        'clients whose purchases collapsed or who stopped buying. Recency is '
        'measured against the newest date in the file, not today. Read-only.'
    )
)
async def portfolio_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> PortfolioResponse:
    '''
        Endpoint returning the portfolio health for a dataset_id.
    '''
    message = f'Portfolio health for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await portfolio_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )
