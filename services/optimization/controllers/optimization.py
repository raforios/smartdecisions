'''
    Optimization controllers.

    Orchestration adapted from the legacy monolith
    (`api/controllers/optimization.py`). The math is unchanged; the only
    structural change is the data source: the monolith ran a raw SQL query
    against Postgres (`SELECT * FROM routes WHERE route_id = X AND day = Y`),
    while this microservice reads the same shape from DynamoDB via
    `services.optimization_utils.get_route_points`.
'''
from typing import List, Optional
import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.optimization import (
    BulkUploadResponse,
    RoutePlanResponse,
    DataMapResponse,
    OptimizationResponse,
    RouteResponse
)
from services.route_algorithm import GeoAnalyzer, filter_order_df
from services.optimization import (
    assign_days,
    available_sellers,
    build_client_points,
    build_day,
    build_distance_matrix,
    order_route,
    parse_route_csv,
    resolve_road_route,
    scope_to_period,
    tag_map_colors
)
from services.optimization_utils import (
    bulk_upload_points,
    get_dataset_metadata,
    get_route_points,
    load_dataframe_from_s3
)
from services.utils import audit_event, handle_service_errors


# ---------------------------------------------------------------------------
# Data-source adapter
# ---------------------------------------------------------------------------
def _route_points_to_df(items: List[dict]) -> pd.DataFrame:
    '''
        Converts the Dynamo response (RoutePoint items) into the DataFrame
        shape the algorithm expects: columns day, client_id, y (lat), x (lon).
    '''
    df = pd.DataFrame(items)
    df = df[['day', 'client_id', 'latitude', 'longitude']].reset_index(drop = True)
    df = df.rename(columns = {'latitude': 'y', 'longitude': 'x'})
    # Dynamo returns numeric values as Decimal — cast to native types so the
    # algorithm doesn't propagate Decimal-vs-float comparisons.
    df['day'] = df['day'].astype(int)
    df['client_id'] = df['client_id'].astype(int)
    df['y'] = df['y'].astype(float)
    df['x'] = df['x'].astype(float)
    return df


def _load_dataframe(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    owner_email: str
) -> pd.DataFrame:
    '''
        Reads the route points from DynamoDB and returns them as the dataframe
        the optimization algorithm consumes. Replaces the monolith's
        `database_to_df` (SQL).
    '''
    items = get_route_points(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day,
        owner_email = owner_email
    )
    return _route_points_to_df(items)


def _df_to_pydantic(df: pd.DataFrame, model) -> list:
    '''
        Transforms a dataframe into a list of Pydantic instances.
    '''
    data = df.to_dict(orient = 'records')
    return [model(**item) for item in data]


# ---------------------------------------------------------------------------
# Public controllers (mirror monolith signatures)
# ---------------------------------------------------------------------------
def _ordered_route_models(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    owner_email: str
) -> List[OptimizationResponse]:
    '''
        Computes the ordered linear-distance route and returns it as the
        OptimizationResponse list. Shared by `data_ordered_controller` and
        `optimization_algorithm_controller` so the latter does not have to
        call a decorated controller.
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day, owner_email)
    dtf_distances = build_distance_matrix(dtf)
    dtf_order = filter_order_df(
        dtf_distances['origin'] == int(dtf_distances['origin'].iloc[0]),
        'distance',
        dtf_distances
    )
    dtf_final = order_route(dtf_order, dtf_distances)
    return _df_to_pydantic(dtf_final, OptimizationResponse)


@handle_service_errors('OPTIMIZATION')
async def preparing_data_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> Optional[List[DataMapResponse]]:
    '''
        Returns the base map data (geolocated client points tagged with color).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day, current_user)
    data = tag_map_colors(dtf)
    return _df_to_pydantic(data, DataMapResponse)


@handle_service_errors('OPTIMIZATION')
async def data_ordered_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> Optional[List[OptimizationResponse]]:
    '''
        Returns the ordered linear-distance pairs (origin → target).
    '''
    return _ordered_route_models(dynamodb_resource, route_id, day, current_user)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'OptimalRoute', 'READ')
async def optimization_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> Optional[List[RouteResponse]]:
    '''
        Runs the full route-optimization pipeline (ordering + OSRM projection).

        The legacy OSM-graph radius (`dist`) is still accepted at the route
        layer for backward compatibility but no longer affects routing: OSRM
        resolves the full street geometry for every segment regardless.
    '''
    dtf_final_models = _ordered_route_models(dynamodb_resource, route_id, day, current_user)
    dtf_final = pd.DataFrame([m.model_dump() for m in dtf_final_models])
    dtf_route = resolve_road_route(dtf_final)
    return _df_to_pydantic(dtf_route, RouteResponse)


@handle_service_errors('OPTIMIZATION')
async def simulation_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> dict:
    '''
        Returns the geodesic distance matrix between all client points
        (output of GeoAnalyzer.get_distance_matrix as a dict).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day, current_user)
    data = tag_map_colors(dtf)

    distance_matrix = data[data['day'] == day][['client_id', 'y', 'x']].reset_index(
        drop = True
    )
    distance_matrix = distance_matrix.rename(columns = {'y': 'latitude', 'x': 'longitude'})
    distance_matrix = distance_matrix.set_index('client_id')

    geo_analyzer = GeoAnalyzer()
    geo_analyzer.add_locations(distance_matrix)

    df_distances = geo_analyzer.get_distance_matrix()
    return df_distances.to_dict()


# ---------------------------------------------------------------------------
# Bulk upload — CSV → DynamoDB
# ---------------------------------------------------------------------------
@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'RoutePoints', 'BULK_CREATE')
async def bulk_upload_routes_controller(
    dynamodb_resource: ServiceResource,
    csv_text: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> BulkUploadResponse:
    '''
        Parses a CSV body and persists every point into DynamoDB under the
        (route_id, day) partition. Re-uploading the same (route_id, day)
        replaces the previous content.

        The caller's email is part of the partition key, so a re-upload only
        replaces that client's own points: two clients planning "route 1, day 1"
        no longer erase each other. `request` is consumed by
        @handle_service_errors for the usage log.
    '''
    rows, headers, route_id, day = parse_route_csv(csv_text)
    written = bulk_upload_points(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day,
        points = rows,
        owner_email = current_user
    )
    return BulkUploadResponse(
        route_id = route_id,
        day = day,
        points_written = written,
        columns_detected = headers
    )


@handle_service_errors('OPTIMIZATION')
async def route_plan_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: dict,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> RoutePlanResponse:
    '''
        Builds a visit plan straight from an ingested sales dataset.

        The clients are the ones who actually bought in the period, the visit
        days come from clustering those clients geographically, and the order
        within each day is the 2-opt tour projected onto real streets. Nothing
        here is read from the legacy route table.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    dataframe = load_dataframe_from_s3(metadata['file_s3_key'])
    dataframe = scope_to_period(dataframe, params)

    sellers = available_sellers(dataframe)
    clients = build_client_points(dataframe, seller = params.get('seller'))
    clients = assign_days(clients, int(params.get('days') or 5))

    days = [
        build_day(clients, day)
        for day in sorted(clients['day'].unique())
    ]
    return RoutePlanResponse(
        dataset_id = dataset_id,
        sellers = sellers,
        seller = params.get('seller'),
        total_clients = int(len(clients)),
        days = [day for day in days if day.stops]
    )
