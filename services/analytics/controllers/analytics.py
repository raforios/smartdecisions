'''
    Analytics controllers.
'''
import os
from typing import Any, Dict, List
from boto3.resources.base import ServiceResource
from dotenv import dotenv_values
from fastapi import Request

from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    AnalyticsRunResponse,
    AnalyticsSummary,
    CommercialSummaryResponse,
    ForecastResponse,
    Opportunity,
    SegmentationResponse
)
from services.affinity_engine import compute_opportunities
from services.analytics_runs import get_latest_run_for_dataset, persist_run
from services.commercial_summary import build_commercial_summary
from services.dataset_loader import get_dataset_metadata, load_dataframe_from_s3
from services.forecast_engine import build_forecast
from services.segmentation_engine import build_segmentation
from services.utils import handle_service_errors


_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

# Caps on opportunities kept in the run (DynamoDB item limit + usable table).
_MAX_PER_PRODUCT = 60      # top stores kept per recommended product
_MAX_OPPORTUNITIES = 800   # overall safety cap


def _top_opportunities_per_product(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''
        Keeps the top-scoring stores for each recommended product, so the
        product summary lists every recommendation instead of only the single
        highest-scoring product. Bounded by _MAX_PER_PRODUCT and _MAX_OPPORTUNITIES.
    '''
    from collections import defaultdict # pylint: disable=import-outside-toplevel
    ranked = sorted(opportunities, key = lambda opp: opp.get('opportunity_score', 0), reverse = True)
    per_product: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    kept: List[Dict[str, Any]] = []
    for opp in ranked:
        product = opp.get('recommended_product_id') or opp.get('recommended_product_name')
        if len(per_product[product]) < _MAX_PER_PRODUCT:
            per_product[product].append(opp)
            kept.append(opp)
        if len(kept) >= _MAX_OPPORTUNITIES:
            break
    return kept


def _read_int_setting(name: str, default: int) -> int:
    '''
        Reads an integer config knob from env / .env, with a fallback.
    '''
    raw = os.environ.get(name) or _LOCAL_ENV_PARAMS.get(name)
    try:
        return int(raw) if raw is not None and str(raw).strip() != '' else default
    except (TypeError, ValueError):
        return default


def _read_float_setting(name: str, default: float) -> float:
    '''
        Reads a float config knob from env / .env, with a fallback.
    '''
    raw = os.environ.get(name) or _LOCAL_ENV_PARAMS.get(name)
    try:
        return float(raw) if raw is not None and str(raw).strip() != '' else default
    except (TypeError, ValueError):
        return default


def _engine_parameters() -> Dict[str, Any]:
    '''
        Reads the affinity-engine tuning parameters from the environment.

        item_level defaults to 'categoria': at SKU level real mass-consumption
        baskets are too sparse to yield rules, while category-level affinity is
        dense and interpretable. Override with AFFINITY_ITEM_LEVEL=producto.
    '''
    return {
        'min_support': _read_float_setting('AFFINITY_MIN_SUPPORT', 0.01),
        'min_lift': _read_float_setting('AFFINITY_MIN_LIFT', 1.0),
        'top_n_per_pdv': _read_int_setting('AFFINITY_TOP_N_PER_PDV', 10),
        'item_level': (os.getenv('AFFINITY_ITEM_LEVEL') or 'categoria').strip().lower()
    }


def _opportunities_to_schema(items: List[Dict[str, Any]]) -> List[Opportunity]:
    '''
        Maps raw dicts into Pydantic Opportunity instances.
    '''
    return [Opportunity(**item) for item in items]


def _summary_to_schema(summary: Dict[str, Any]) -> AnalyticsSummary:
    '''
        Maps the engine summary dict into the Pydantic schema.
    '''
    return AnalyticsSummary(**summary)


@handle_service_errors('ANALYTICS')
async def commercial_summary_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> CommercialSummaryResponse:
    '''
        Loads the normalized dataset and builds the general commercial summary
        (KPIs, best/worst client, top/bottom products, distributions and the
        monthly trend). Read-only: it derives everything from the dataset on the
        fly, so it is not persisted as a run.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])
    summary = build_commercial_summary(dataframe)
    return CommercialSummaryResponse(dataset_id = dataset_id, **summary)


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
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])
    result = build_forecast(
        dataframe = dataframe,
        months_ahead = params.get('months_ahead', 3),
        method = params.get('method', 'linear'),
        group_by = params.get('group_by')
    )
    return ForecastResponse(dataset_id = dataset_id, **result)


@handle_service_errors('ANALYTICS')
async def segmentation_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SegmentationResponse:
    '''
        Loads the normalized dataset and builds the customer value segmentation
        (Alto/Medio/Bajo). Read-only.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])
    result = build_segmentation(dataframe)
    return SegmentationResponse(dataset_id = dataset_id, **result)


@handle_service_errors('ANALYTICS')
async def run_analytics_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
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
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])

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
            'summary': summary,
            'opportunities': top_opportunities,
            'parameters': parameters
        }
    )
    return AnalyticsRunResponse(
        dataset_id = persisted['dataset_id'],
        run_id = persisted['run_id'],
        status = persisted['status'],
        summary = _summary_to_schema(persisted['summary']),
        opportunities = _opportunities_to_schema(persisted['opportunities']),
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
        summary = _summary_to_schema(run['summary']),
        opportunities = _opportunities_to_schema(run['opportunities']),
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
        opportunities = _opportunities_to_schema(pdv_opportunities)
    )
