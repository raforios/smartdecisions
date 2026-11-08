'''
    A movement of the shelf, told to SmartDecisions (Rafael, 8-nov-2026).

    Every sale, cancellation, return and purchase moves the shelf and the
    money of its month: the financial analysis gets the month again and the
    commercial one gets today's shelf, both only when the shop wants it.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from services.billing_bridge import share_stock
from services.billing_finance import share_month


def share_movement(
    dynamodb_resource: ServiceResource,
    owner: str,
    day: str,
    request: Request | None
) -> None:
    '''
        Sends what a movement changed: its month to FINANCE and today's shelf
        to COMMERCIAL.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            day (str): When the movement's money counts, ISO date or timestamp.
            request (Request | None): The incoming request, for the token.
    '''
    share_month(dynamodb_resource, owner, day, request)
    share_stock(dynamodb_resource, owner, request)
