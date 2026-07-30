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
    Opportunity
)
from services.affinity_engine import compute_opportunities
from services.analytics_runs import get_latest_run_for_dataset, persist_run
from services.dataset_loader import get_dataset_metadata, load_dataframe_from_s3
from services.utils import handle_service_errors


_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}


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

    persisted = persist_run(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'dataset_id': dataset_id,
            'status': 'completed',
            'owner_email': current_user,
            'summary': summary,
            'opportunities': opportunities,
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
