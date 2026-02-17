'''
    Mining Analysis Controllers
'''
import json
import asyncio
import time
from typing import List
from fastapi import Request
from sqlalchemy.orm import Session
from services.utils import (
    UsageLogData,
    handle_service_errors,
    send_audit_event,
    send_usage_log
)
from services.logger_config import custom_logger as logger
from services.mining_analysis import (
    process_mining_etl_service,
    get_all_prices_service
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema
)

# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('MINING_ANALYSIS')
async def bulk_upload_mining_controller(
    db: Session,
    file_content: bytes,
    file_name: str,
    request: Request,
    current_user: str,
    delimiter: str = ','
) -> BulkUploadMiningResponseSchema:
    '''
        Controller to handle the bulk upload of mining prices via ETL.
        Orchestrates service logic, audit events, and usage logging.
    '''

    start_time = time.perf_counter()
    status_code = 201
    result = {}

    try:
        result = await process_mining_etl_service(
            db = db,
            file_content = file_content,
            delimiter = delimiter
        )

        audit_data = {
            'microservice': 'MINING_ANALYSIS',
            'entity_name': 'MiningPrice',
            'entity_id': 0,
            'action': 'BULK_UPLOAD',
            'user_id': 'usr_test',
            'old_values': None,
            'new_values': json.dumps(result)
        }

        asyncio.create_task(send_audit_event(audit_data))

    finally:
        end_time = time.perf_counter()
        log_data = UsageLogData(
            microservice = 'MINING_ANALYSIS',
            endpoint = request.url.path,
            method = request.method,
            status_code = status_code,
            ip_address = request.client.host,
            user_app = current_user,
            request_body = {'file_name': file_name},
            response_body = result,
            response_time_ms = int((end_time - start_time) * 1000)
        )

        asyncio.create_task(send_usage_log(log_data.model_dump()))

    return BulkUploadMiningResponseSchema(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_mineral_prices_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> List[MiningPriceResponseSchema]:
    ''' 
        Controller to fetch all processed prices.
    '''
    message = f'User {current_user} requested all mineral prices.'
    logger.info(message)
    prices = await get_all_prices_service(db=db)
    return [MiningPriceResponseSchema.model_validate(p) for p in prices]
