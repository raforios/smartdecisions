'''
    What a client loads — HTTP layer.

    The figures belong to the client of the token; every user of that client
    sees the same ones, and the user who made each change is recorded. Two
    channels with one validator: rows by API, or a file already uploaded
    through FILES.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Header, Query, Request, status

from controllers.entries import (
    delete_entry_controller,
    delete_period_controller,
    list_entries_controller,
    list_loads_controller,
    load_entries_controller,
    load_entries_file_controller,
    update_entry_controller
)
from schemas.entries import (
    EntryFileLoadSchema,
    EntryListResponseSchema,
    EntryLoadSchema,
    EntrySchema,
    EntryUpdateSchema,
    LoadListResponseSchema,
    LoadResultSchema,
    PeriodDeleteResultSchema,
    Periodicity
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user, require_roles

router = APIRouter(prefix = '/v1/finance', tags = ['Financial analysis — loads'])

# A FastAPI endpoint declares its dependencies as parameters —resource, caller,
# body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments

# The financial analysis is for the people who run the client's business
# (Rafael: «sólo la plana mayor»), not for the sellers on the street.
FINANCE_ROLES = ('MANAGER',)

_PERIODICITY = Query(..., description = 'DAILY, MONTHLY or ANNUAL.')
_DATE = Query(..., min_length = 4, max_length = 10, description = 'YYYY-MM-DD, YYYY-MM or YYYY.')
_ACCOUNT = Query(..., min_length = 1, max_length = 20)


@router.post(
    '/loads',
    response_model = LoadResultSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Load amounts by API',
    description = (
        'Rows with the API field names. A row that breaks a rule is set aside '
        'with its code and the rest goes in; the same account and period '
        'loaded again replaces the earlier amount and nothing else.'
    )
)
async def load_entries_endpoint(
    request: Request,
    load: EntryLoadSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> LoadResultSchema:
    '''
        Endpoint loading amounts by API.
    '''
    message = (f'User: {current_user} ({client}). '
               f'Loading {len(load.rows)} row(s), {load.flow.value}.')
    logger.info(message)
    return await load_entries_controller(
        dynamodb_resource = dynamodb_resource,
        load = load,
        client = client,
        current_user = current_user,
        request = request
    )


@router.post(
    '/loads/file',
    response_model = LoadResultSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Load amounts from the template',
    description = (
        'The file is uploaded first through FILES; this endpoint receives its '
        'key, reads it through FILES and removes it once its rows are in.'
    )
)
async def load_entries_file_endpoint(
    request: Request,
    load: EntryFileLoadSchema,
    authorization: str | None = Header(None),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> LoadResultSchema:
    '''
        Endpoint loading amounts from a file.
    '''
    message = f'User: {current_user} ({client}). Loading file {load.file_key}, {load.flow.value}.'
    logger.info(message)
    return await load_entries_file_controller(
        dynamodb_resource = dynamodb_resource,
        load = load,
        client = client,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.get(
    '/loads',
    response_model = LoadListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The loads of the client, newest first'
)
async def list_loads_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> LoadListResponseSchema:
    '''
        Endpoint listing the loads.
    '''
    message = f'User: {current_user} ({client}). Reading the loads.'
    logger.info(message)
    return await list_loads_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        current_user = current_user,
        request = request
    )


@router.get(
    '/entries',
    response_model = EntryListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The amounts of the client',
    description = 'All of them, or those of a periodicity and a date prefix (2026, 2026-03).'
)
async def list_entries_endpoint(
    request: Request,
    periodicity: Periodicity | None = Query(None),
    date: str | None = Query(None, min_length = 4, max_length = 10),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> EntryListResponseSchema:
    '''
        Endpoint listing the amounts.
    '''
    message = f'User: {current_user} ({client}). Reading amounts {periodicity} {date}.'
    logger.info(message)
    return await list_entries_controller(
        dynamodb_resource = dynamodb_resource,
        period = (periodicity, date),
        client = client,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/entries',
    response_model = EntrySchema,
    status_code = status.HTTP_200_OK,
    summary = 'Correct one amount',
    description = (
        'Its figure, its date, its note or its invoice flags. A new date '
        'passes the same rules as a load.'
    )
)
async def update_entry_endpoint(
    request: Request,
    update: EntryUpdateSchema,
    periodicity: Periodicity = _PERIODICITY,
    date: str = _DATE,
    account_code: str = _ACCOUNT,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> EntrySchema:
    '''
        Endpoint correcting an amount.
    '''
    message = (f'User: {current_user} ({client}). '
               f'Correcting {periodicity.value} {date} {account_code}.')
    logger.info(message)
    return await update_entry_controller(
        dynamodb_resource = dynamodb_resource,
        target = (periodicity, date, account_code),
        update = update,
        client = client,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/entries',
    response_model = EntrySchema,
    status_code = status.HTTP_200_OK,
    summary = 'Remove one amount'
)
async def delete_entry_endpoint(
    request: Request,
    periodicity: Periodicity = _PERIODICITY,
    date: str = _DATE,
    account_code: str = _ACCOUNT,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> EntrySchema:
    '''
        Endpoint removing an amount.
    '''
    message = (f'User: {current_user} ({client}). '
               f'Removing {periodicity.value} {date} {account_code}.')
    logger.info(message)
    return await delete_entry_controller(
        dynamodb_resource = dynamodb_resource,
        target = (periodicity, date, account_code),
        client = client,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/periods',
    response_model = PeriodDeleteResultSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Empty a period',
    description = (
        'Every amount of a periodicity whose date starts with the one given: '
        'DAILY 2026-03 removes every day of March, which is what has to happen '
        'before March is loaded as a month.'
    )
)
async def delete_period_endpoint(
    request: Request,
    periodicity: Periodicity = _PERIODICITY,
    date: str = _DATE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> PeriodDeleteResultSchema:
    '''
        Endpoint emptying a period.
    '''
    message = f'User: {current_user} ({client}). Emptying {periodicity.value} {date}.'
    logger.info(message)
    return await delete_period_controller(
        dynamodb_resource = dynamodb_resource,
        period = (periodicity, date),
        client = client,
        current_user = current_user,
        request = request
    )
