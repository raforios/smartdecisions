'''
    Companies: routes handler (ADMIN only).

    Under /v1/auth, which the gateway already sends to AUTH.
'''
from fastapi import APIRouter, Depends, status
from controllers.companies import add_company, change_company, read_companies, remove_company
from controllers.users import get_current_admin_user
from schemas.companies import CompanyRequest, CompanyResponse, CompanyUpdateRequest
from services.logger_config import custom_logger as logger

router = APIRouter(prefix = '/v1/auth/companies', tags = ['Companies'],
                   dependencies = [Depends(get_current_admin_user)])


@router.get('', response_model = list[CompanyResponse], status_code = status.HTTP_200_OK,
            summary = 'Every company, with how many users it has')
async def list_companies_endpoint() -> list[CompanyResponse]:
    '''
        Endpoint listing the companies.
    '''
    logger.info('Listing the companies.')
    return await read_companies()


@router.post('', response_model = CompanyResponse, status_code = status.HTTP_201_CREATED,
             summary = 'Add a company')
async def create_company_endpoint(company: CompanyRequest) -> CompanyResponse:
    '''
        Endpoint adding a company.
    '''
    message = f'Adding company {company.name}.'
    logger.info(message)
    return await add_company(company)


@router.patch('/{name}', response_model = CompanyResponse, status_code = status.HTTP_200_OK,
              summary = 'Change a company\'s NIT or whether it is active')
async def update_company_endpoint(
    name: str,
    update: CompanyUpdateRequest
) -> CompanyResponse:
    '''
        Endpoint changing a company.
    '''
    message = f'Updating company {name}.'
    logger.info(message)
    return await change_company(name, update)


@router.delete('/{name}', response_model = CompanyResponse, status_code = status.HTTP_200_OK,
               summary = 'Remove a company without users')
async def delete_company_endpoint(name: str) -> CompanyResponse:
    '''
        Endpoint removing a company.
    '''
    message = f'Removing company {name}.'
    logger.info(message)
    return await remove_company(name)
