'''
    Seeds PARAMETERS with the business values of every service.

    They come **from `docs/parametros.md`** and not from a list written here:
    that table is the single definition Rafael reviews. After the seed, the
    ADMIN changes any value through the PARAMETERS API and no service has to
    be released again (CLAUDE.md §5.3).

    It goes through PARAMETERS' own functions, so every value passes the same
    type check as one set by an ADMIN.

        python -m tools.seeds.seed_parameters            # simulation
        python -m tools.seeds.seed_parameters --yes
        python -m tools.seeds.seed_parameters --yes --scope finance

    Re-running sets the values again; a value the ADMIN changed by API is
    overwritten, so run it only when the table in the document changes.
'''
import argparse
import re
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS_PATH = ROOT / 'services' / 'parameters'
DOCUMENT = ROOT / 'docs' / 'parametros.md'
sys.path.insert(0, str(PARAMETERS_PATH))
# The service validates its environment on import, so it is loaded first.
load_dotenv(PARAMETERS_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.parameters import ParameterSchema, ValueType  # noqa: E402
from services.parameters import set_parameter  # noqa: E402
# pylint: enable=wrong-import-position

PROFILE = 'deploy_ml'
REGION = 'us-east-1'

# «| finance | CODE | NUMBER | 3 | What it governs |»
_ROW = re.compile(
    r'^\|\s*([a-z_]+)\s*\|\s*([A-Z0-9_]+)\s*\|\s*(NUMBER|TEXT|LIST)\s*'
    r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$'
)


def read_parameters(text: str) -> list[tuple[tuple[str, str], ParameterSchema]]:
    '''
        The parameters of the document, typed.

        Args:
            text (str): The document.

        Returns:
            list[tuple[tuple[str, str], ParameterSchema]]: ((scope, code), parameter).
    '''
    parameters = []
    for match in map(_ROW.match, text.splitlines()):
        if not match:
            continue
        scope, code, kind, raw, description = match.groups()
        value_type = ValueType(kind)
        value: float | str | list[str] = raw
        if value_type is ValueType.NUMBER:
            value = float(raw)
        elif value_type is ValueType.LIST:
            value = raw.split()
        parameters.append(((scope, code), ParameterSchema(
            value_type = value_type, value = value, description = description)))
    return parameters


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(description = 'Siembra PARAMETERS desde docs/parametros.md.')
    parser.add_argument('--yes', action = 'store_true', help = 'Escribe en DynamoDB.')
    parser.add_argument('--scope', help = 'Sólo un alcance (global, finance, ...).')
    args = parser.parse_args()

    parameters = [(key, parameter)
                  for key, parameter in read_parameters(DOCUMENT.read_text(encoding = 'utf-8'))
                  if args.scope is None or key[0] == args.scope]
    for (scope, code), parameter in parameters:
        print(f'{scope:10} {code:28} {parameter.value_type.value:6} {parameter.value}')
    if not args.yes:
        print('Simulación: no se escribió nada. Repite con --yes.')
        return 0

    resource = boto3.Session(profile_name = PROFILE, region_name = REGION).resource('dynamodb')
    for key, parameter in parameters:
        set_parameter(resource, key, parameter)
    print(f'{len(parameters)} parámetro(s) escritos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
