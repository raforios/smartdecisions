'''
    Dependencies shared by the ingest routers.
'''
from typing import Any

from fastapi import Depends

from schemas.clients import CallerClaims
from services.security import get_current_payload


async def get_caller(payload: dict[str, Any] = Depends(get_current_payload)) -> CallerClaims:
    '''
        FastAPI dependency: the token claims as a DTO instead of a loose dict.

        Named and shaped as in OPTIMIZATION on purpose: the same problem is
        solved the same way in every service.

        Args:
            payload (dict[str, Any]): Decoded token claims.

        Returns:
            CallerClaims: Email, role and client of the caller.
    '''
    return CallerClaims(**payload)
