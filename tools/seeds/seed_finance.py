'''
    Seeds the chart of accounts and the law parameters of FINANCE.

    Both come **from the approved contract** (`docs/cambios/smartdecisions/
    contrato.md`) and not from a list written here: the contract is the single
    definition Rafael reviews, and a copy in code would drift from it the day
    an account is added. A bold row of a catalog table is a group; the rest
    are its accounts. The type is the first digit of the code, an account
    named «(Menos) …» subtracts within its group, and the «Factura» column
    says whether a sale carries an invoice.

    It goes through FINANCE's own functions, so every account passes the same
    rules as one added by an ADMIN from the API: an existing group of its own
    type, a code never repeated.

        python -m tools.seeds.seed_finance            # simulation
        python -m tools.seeds.seed_finance --yes

    Re-running is safe: an account already in the catalog is left as it is,
    and a law value on the same date is corrected, not duplicated.
'''
import argparse
import re
import sys
from datetime import date
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
FINANCE_PATH = ROOT / 'services' / 'finance'
CONTRACT = ROOT / 'docs' / 'cambios' / 'smartdecisions' / 'contrato.md'
sys.path.insert(0, str(FINANCE_PATH))
# The service validates its environment on import, so it is loaded first.
load_dotenv(FINANCE_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.finance import AccountSchema, AccountType, LawParameterSchema  # noqa: E402
from services.exceptions import RegisterAlreadyExistsError  # noqa: E402
from services.finance import create_account, set_law_parameter  # noqa: E402
# pylint: enable=wrong-import-position

PROFILE = 'deploy_ml'
REGION = 'us-east-1'

# A catalog row of the contract: «| 6.1.07 | Name |», the code in bold for a
# group; the results table adds «| Sí |» or «| No |» for a sale with or
# without invoice.
_ACCOUNT_ROW = re.compile(
    r'^\|\s*(\*\*)?(\d+(?:\.\d+)+)(\*\*)?\s*\|\s*(.+?)\s*\|(?:\s*(Sí|No)?\s*\|)?\s*$'
)
_INVOICED = {'Sí': True, 'No': False}
# A law parameter row: «| IVA | Name | 13 | 1986-07-01 |».
_LAW_ROW = re.compile(
    r'^\|\s*([A-Z]{2,})\s*\|\s*(.+?)\s*\|\s*([\d.]+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*$'
)
_BOLD = re.compile(r'^\*\*(.+?)\*\*')
_SUBTRACTS_PREFIX = '(Menos)'


def read_accounts(text: str) -> list[AccountSchema]:
    '''
        The groups and accounts of the contract, groups before their accounts.

        Args:
            text (str): The contract.

        Returns:
            list[AccountSchema]: The catalog, in the order it is written.
    '''
    accounts: list[AccountSchema] = []
    group: str | None = None
    for line in text.splitlines():
        match = _ACCOUNT_ROW.match(line)
        if not match:
            continue
        is_group, code, name = bool(match.group(1)), match.group(2), match.group(4)
        # A group's name is its bold text; what follows explains it to the reader.
        bold = _BOLD.match(name)
        name = bold.group(1) if bold else name
        if is_group:
            group = code
        accounts.append(AccountSchema(
            account_code = code,
            name = name,
            account_type = AccountType(code[0]),
            group_code = None if is_group else group,
            subtracts = name.startswith(_SUBTRACTS_PREFIX),
            invoiced = _INVOICED.get(match.group(5))
        ))
    return accounts


def read_law_parameters(text: str) -> list[LawParameterSchema]:
    '''
        The law parameters of the contract with the day each one applies from.

        Args:
            text (str): The contract.

        Returns:
            list[LawParameterSchema]: The values.
    '''
    return [
        LawParameterSchema(parameter_code = match.group(1), name = match.group(2),
                           rate = float(match.group(3)),
                           valid_from = date.fromisoformat(match.group(4)))
        for match in map(_LAW_ROW.match, text.splitlines()) if match
    ]


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(description = 'Siembra el catálogo y las tasas de FINANCE.')
    parser.add_argument('--yes', action = 'store_true', help = 'Escribe en DynamoDB.')
    args = parser.parse_args()

    text = CONTRACT.read_text(encoding = 'utf-8')
    accounts = read_accounts(text)
    parameters = read_law_parameters(text)
    groups = sum(1 for account in accounts if account.group_code is None)
    subtracting = [account.account_code for account in accounts if account.subtracts]
    print(f'Catálogo: {groups} grupos y {len(accounts) - groups} cuentas; '
          f'restan: {", ".join(subtracting)}.')
    for parameter in parameters:
        print(f'Ley: {parameter.parameter_code} {parameter.rate} % desde {parameter.valid_from}')
    if not args.yes:
        print('Simulación: no se escribió nada. Repite con --yes.')
        return 0

    resource = boto3.Session(profile_name = PROFILE, region_name = REGION).resource('dynamodb')
    created = 0
    for account in accounts:
        try:
            create_account(resource, account)
            created += 1
        except RegisterAlreadyExistsError:
            continue
    for parameter in parameters:
        set_law_parameter(resource, parameter)
    print(f'{created} cuentas nuevas ({len(accounts) - created} ya estaban); '
          f'{len(parameters)} valores de ley.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
