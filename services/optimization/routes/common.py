'''
    Dependencies shared by the planning and the tracking routers.
'''
from fastapi import File, UploadFile

from services.common import decode_csv_upload


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
