'''
    Routing: routes handler
'''
from fastapi import APIRouter, Depends
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.routing import clustering_points, ordering_points
from schemas.routing import ClustersRequest, ClustersResponse, OrderRequest, OrderResponse

router = APIRouter(prefix = '/v1/routing', tags = ['ML Routing'])


@router.post(
    '/clusters',
    response_model = ClustersResponse,
    summary = 'Split points in compact groups of even size',
    description = '''k-means over (lat, lon), then evened out so no group passes
        an even share. The same points and seed always give the same groups.
        The visit days COMMERCIAL plans.'''
)
async def clusters_route(
    request: ClustersRequest,
    current_user: str = Depends(get_current_user)
) -> ClustersResponse:
    '''
        Splits the points in compact groups of even size.

        Args:
            request (ClustersRequest): The points, the groups, the seed and the iterations.
            current_user (str): The authenticated user's identifier (dependency-injected).

        Returns:
            ClustersResponse: The group of each point.
    '''
    message = (f'User: {current_user} asked {request.clusters} cluster(s) of '
               f'{len(request.points)} point(s).')
    logger.info(message)
    return await clustering_points(request)


@router.post(
    '/order',
    response_model = OrderResponse,
    summary = 'Put stops in visit order',
    description = '''Nearest neighbour, then 2-opt over the great-circle
        distances, for an open path that starts at the first stop. The order
        COMMERCIAL proposes for a route.'''
)
async def order_route(
    request: OrderRequest,
    current_user: str = Depends(get_current_user)
) -> OrderResponse:
    '''
        Puts the stops in visit order.

        Args:
            request (OrderRequest): The stops and the most 2-opt passes.
            current_user (str): The authenticated user's identifier (dependency-injected).

        Returns:
            OrderResponse: Indices into the stops, in visit order.
    '''
    message = f'User: {current_user} asked the order of {len(request.points)} stop(s).'
    logger.info(message)
    return await ordering_points(request)
