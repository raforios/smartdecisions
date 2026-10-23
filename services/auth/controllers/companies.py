'''
    Companies controller: the customers of the platform (ADMIN only).
'''
from schemas.companies import CompanyRequest, CompanyResponse, CompanyUpdateRequest
from services.companies import (
    create_company,
    delete_company,
    list_companies,
    update_company
)


async def read_companies() -> list[CompanyResponse]:
    '''
        Every company with its users.
    '''
    return list_companies()


async def add_company(company: CompanyRequest) -> CompanyResponse:
    '''
        Adds a company.
    '''
    return create_company(company)


async def change_company(
    name: str,
    update: CompanyUpdateRequest
) -> CompanyResponse:
    '''
        Changes a company's NIT or whether it is active.
    '''
    return update_company(name, update)


async def remove_company(name: str) -> CompanyResponse:
    '''
        Removes a company without users.
    '''
    return delete_company(name)
