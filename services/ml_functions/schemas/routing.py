'''
    Routing Schemas (Request/Response)
'''
from typing import Annotated

from pydantic import BaseModel, Field

# A (lat, lon) pair in degrees.
Point = Annotated[list[float], Field(min_length = 2, max_length = 2)]


class ClustersRequest(BaseModel):
    '''
        Points to split in compact groups of even size.
    '''
    points: list[Point] = Field(..., min_length = 1, max_length = 20000,
                                description = '(lat, lon) of each point.')
    clusters: int = Field(..., ge = 1, le = 366, description = 'How many groups.')
    seed: int = Field(..., ge = 0, description = 'Makes the same points group the same way.')
    iterations: int = Field(..., ge = 1, le = 1000, description = 'Most k-means iterations.')


class ClustersResponse(BaseModel):
    '''
        The group of each point (0-based), in the order they came.
    '''
    labels: list[int]


class OrderRequest(BaseModel):
    '''
        Stops to put in visit order.
    '''
    points: list[Point] = Field(..., min_length = 1, max_length = 2000,
                                description = '(lat, lon) of each stop; the path starts '
                                              'at the first one.')
    passes: int = Field(..., ge = 1, le = 100, description = 'Most 2-opt passes.')


class OrderResponse(BaseModel):
    '''
        Indices into the points, in visit order.
    '''
    order: list[int]
