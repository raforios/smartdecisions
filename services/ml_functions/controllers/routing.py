'''
    Routing controller
'''
from services.logger_config import custom_logger as logger
from services.routing import ClusterSpec, cluster_points, order_points
from services.utils import handle_operation
from schemas.routing import ClustersRequest, ClustersResponse, OrderRequest, OrderResponse


@handle_operation(exc_type = (ValueError, TypeError))
async def clustering_points(request_body: ClustersRequest) -> ClustersResponse:
    '''
    Controller splitting the points in compact groups of even size.
    '''
    labels = cluster_points(request_body.points, ClusterSpec(
        clusters = request_body.clusters, seed = request_body.seed,
        iterations = request_body.iterations))
    message = f'{len(labels)} point(s) grouped in {request_body.clusters} cluster(s).'
    logger.info(message)
    return ClustersResponse(labels = labels)


@handle_operation(exc_type = (ValueError, TypeError))
async def ordering_points(request_body: OrderRequest) -> OrderResponse:
    '''
    Controller putting the stops in visit order.
    '''
    order = order_points(request_body.points, request_body.passes)
    message = f'{len(order)} stop(s) put in visit order.'
    logger.info(message)
    return OrderResponse(order = order)
