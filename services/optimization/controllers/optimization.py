'''
    Optimization controllers.

    Orchestration adapted from the legacy monolith
    (`api/controllers/optimization.py`). The math is unchanged; the only
    structural change is the data source: the monolith ran a raw SQL query
    against Postgres (`SELECT * FROM routes WHERE route_id = X AND day = Y`),
    while this microservice reads the same shape from DynamoDB via
    `services.route_data.get_route_points`.
'''
from typing import List, Optional
import pandas as pd
import osmnx as ox
import networkx as nx
from boto3.resources.base import ServiceResource

from schemas.optimization import DataMapResponse, OptimizationResponse, RouteResponse
from services.events_emitter import audit_event
from services.ml_optimization import (
    GeoAnalyzer,
    distance_between_points,
    fiter_order_df,
    optimal_route
)
from services.route_data import get_route_points


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
    day: int
) -> pd.DataFrame:
    '''
        Reads the route points from DynamoDB and returns them as the dataframe
        the optimization algorithm consumes. Replaces the monolith's
        `database_to_df` (SQL).
    '''
    items = get_route_points(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day
    )
    return _route_points_to_df(items)


# ---------------------------------------------------------------------------
# Algorithm helpers (verbatim from monolith)
# ---------------------------------------------------------------------------
def _draw_map(dtf: pd.DataFrame) -> pd.DataFrame:
    '''
        Tags the first / last / middle points with their map color.
    '''
    data = dtf.copy()
    size, _ = data.shape
    data_order = data.sort_values(by = 'client_id', ascending = True)
    data = data_order.reset_index(drop = True)
    data.loc[0, 'color'] = 'red'
    mask = (data.index >= 1) & (data.index < len(data) - 1)
    data.loc[mask, 'color'] = 'black'
    data.loc[size - 1, 'color'] = 'green'
    return data


def _distances(dtf: pd.DataFrame) -> pd.DataFrame:
    '''
        Creates the dataframe with linear distance calculations.
    '''
    dtf_distances = pd.DataFrame({
        'origin': dtf.at[0, 'client_id'],
        'target': dtf.at[0, 'client_id'],
        'x': dtf.at[0, 'x'],
        'y': dtf.at[0, 'y'],
        'distance': 0
    }, index = [0])
    for i in range(len(dtf)):
        for j in range(i + 1, len(dtf)):
            node_1 = (dtf.at[i, 'x'], dtf.at[i, 'y'])
            node_2 = (dtf.at[j, 'x'], dtf.at[j, 'y'])
            distance = distance_between_points(node_1, node_2)
            new_row = pd.DataFrame({
                'origin': dtf.at[i, 'client_id'],
                'target': dtf.at[j, 'client_id'],
                'x': dtf.at[j, 'x'],
                'y': dtf.at[j, 'y'],
                'distance': distance
            }, index = [i * j])
            dtf_distances = pd.concat([dtf_distances, new_row], ignore_index = True)
    return dtf_distances.reset_index(drop = True)


def _final_data(dtf: pd.DataFrame, dtf_distances: pd.DataFrame) -> pd.DataFrame:
    '''
        Creates the dataframe with the optimized and organized route.
    '''
    dtf_final = pd.DataFrame({
        'origin': dtf.at[0, 'target'],
        'target': dtf.at[1, 'target'],
        'distance': dtf.at[1, 'distance'],
        'x': dtf.at[0, 'x'],
        'y': dtf.at[0, 'y']
    }, index = [0])

    origin = dtf.at[0, 'target']
    target = dtf.at[1, 'target']
    dtf_final = optimal_route(len(dtf), origin, target, dtf_distances, dtf_final)

    dtf_final = pd.merge(
        dtf_final, dtf, left_on = 'origin', right_on = 'target', how = 'left'
    )
    dtf_final.drop(
        columns = ['x_x', 'y_x', 'origin_y', 'target_y', 'distance_y'],
        axis = 1, inplace = True
    )
    dtf_final = dtf_final.rename(columns = {
        'origin_x': 'origin', 'distance_x': 'distance',
        'y_y': 'y', 'x_y': 'x', 'target_x': 'target'
    })
    return dtf_final


def _final_route(dtf: pd.DataFrame, dist: int) -> pd.DataFrame:
    '''
        Projects the linear-distance route onto the OSM road network using
        osmnx and returns it with per-segment distances, times and nodes.
    '''
    start = dtf[dtf.index == 0][['y', 'x']].values[0]

    df_route = dtf.copy()
    df_route.index.name = 'visit_order'
    df_route.drop(columns = ['target'], axis = 1, inplace = True)

    df_route_segments = df_route.join(
        df_route.shift(-1),
        rsuffix = '_next'
    ).dropna()
    df_route_segments.drop(columns = ['distance_next'], axis = 1, inplace = True)
    df_route_segments = df_route_segments.rename(columns = {'origin_next': 'target'})

    df_route_segments['time_seg'] = df_route_segments.apply(
        lambda stop: distance_between_points(
            (stop.y, stop.x), (stop.y_next, stop.x_next)
        ),
        axis = 1
    )

    graph = ox.graph_from_point(start, dist = dist, network_type = 'drive')
    df_route_segments.loc[:, 'origin_node'] = df_route_segments[['y', 'x']].apply(
        lambda x: ox.distance.nearest_nodes(graph, x.iloc[1], x.iloc[0]), axis = 1
    )
    df_route_segments.loc[:, 'destination_node'] = df_route_segments[
        ['y_next', 'x_next']
    ].apply(
        lambda x: ox.distance.nearest_nodes(graph, x.iloc[1], x.iloc[0]), axis = 1
    )
    df_route_segments.loc[:, 'route'] = df_route_segments[
        ['origin_node', 'destination_node']
    ].apply(
        lambda x: nx.shortest_path(graph, x.iloc[0], x.iloc[1], weight = 'length'),
        axis = 1
    )
    return df_route_segments


def _df_to_pydantic(df: pd.DataFrame, model) -> list:
    '''
        Transforms a dataframe into a list of Pydantic instances.
    '''
    data = df.to_dict(orient = 'records')
    return [model(**item) for item in data]


# ---------------------------------------------------------------------------
# Public controllers (mirror monolith signatures)
# ---------------------------------------------------------------------------
async def preparing_data_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> Optional[List[DataMapResponse]]:
    '''
        Returns the base map data (geolocated client points tagged with color).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    data = _draw_map(dtf)
    return _df_to_pydantic(data, DataMapResponse)


async def data_ordered_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> Optional[List[OptimizationResponse]]:
    '''
        Returns the ordered linear-distance pairs (origin → target).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    dtf_distances = _distances(dtf)
    dtf_order = fiter_order_df(
        dtf_distances['origin'] == int(dtf_distances['origin'].iloc[0]),
        'distance',
        dtf_distances
    )
    dtf_final = _final_data(dtf_order, dtf_distances)
    return _df_to_pydantic(dtf_final, OptimizationResponse)


@audit_event('OPTIMIZATION', 'OptimalRoute', 'READ')
async def optimization_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    dist: int
) -> Optional[List[RouteResponse]]:
    '''
        Runs the full route-optimization pipeline (ordering + OSM projection).
    '''
    dtf_final_models = await data_ordered_controller(dynamodb_resource, route_id, day)
    dtf_final = pd.DataFrame([m.model_dump() for m in dtf_final_models])
    dtf_route = _final_route(dtf_final, dist)
    return _df_to_pydantic(dtf_route, RouteResponse)


async def simulation_algorithm_controller(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> dict:
    '''
        Returns the geodesic distance matrix between all client points
        (output of GeoAnalyzer.get_distance_matrix as a dict).
    '''
    dtf = _load_dataframe(dynamodb_resource, route_id, day)
    data = _draw_map(dtf)

    distance_matrix = data[data['day'] == day][['client_id', 'y', 'x']].reset_index(
        drop = True
    )
    distance_matrix = distance_matrix.rename(columns = {'y': 'latitude', 'x': 'longitude'})
    distance_matrix = distance_matrix.set_index('client_id')

    geo_analyzer = GeoAnalyzer()
    geo_analyzer.add_locations(distance_matrix)

    df_distances = geo_analyzer.get_distance_matrix()
    return df_distances.to_dict()
