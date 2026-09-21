'''
    Dependencies shared by the planning and the tracking routers.
'''
from typing import Any, Dict

from fastapi import Depends, File, UploadFile

from schemas.localization import CallerClaims
from services.common import decode_csv_upload
from services.security import get_current_payload


async def csv_upload_text(file: UploadFile = File(...)) -> str:
    '''
        FastAPI dependency: the uploaded CSV as text, or the shared upload
        error codes. Every bulk-upload endpoint declares it instead of
        repeating the read-and-decode dance.

        Args:
            file (UploadFile): The multipart file.

        Returns:
            str: Decoded CSV text.
    '''
    return decode_csv_upload(file.filename or '', await file.read())


async def get_caller(payload: Dict[str, Any] = Depends(get_current_payload)) -> CallerClaims:
    '''
        FastAPI dependency: the token claims as a DTO instead of a loose dict.

        Args:
            payload (Dict[str, Any]): Decoded token claims.

        Returns:
            CallerClaims: Email, role and client of the caller.
    '''
    return CallerClaims(**payload)
