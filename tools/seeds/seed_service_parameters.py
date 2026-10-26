'''
    Seeds a service's own `<service>_parameters` table from its rows in
    `docs/parametros.md`.

    Each microservice keeps its parameters in its own tables (Rafael,
    24-oct-2026): its business values live in `<service>_parameters`, one item
    per code, and the service reads them with its own role. This writes them.

        python -m tools.seeds.seed_service_parameters commercial          # simulation
        python -m tools.seeds.seed_service_parameters commercial --yes

    Re-running writes the document's values again, over any value changed in
    the table, so run it only when the document changes.
'''
import argparse
import sys

import boto3

from tools.seeds.parameters_document import read_rows, write_rows

PROFILE = 'deploy_ml'
REGION = 'us-east-1'


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success, 1 when the service has no rows.
    '''
    parser = argparse.ArgumentParser(
        description = 'Siembra la tabla <servicio>_parameters desde docs/parametros.md.')
    parser.add_argument('service', help = 'El servicio dueño de los valores (commercial, ...).')
    parser.add_argument('--yes', action = 'store_true', help = 'Escribe en DynamoDB.')
    args = parser.parse_args()

    rows = read_rows(args.service)
    if not rows:
        print(f'docs/parametros.md no tiene filas de {args.service}.')
        return 1
    table_name = f'{args.service}_parameters'
    for row in rows:
        print(f'{row.code:36} {row.kind:6} {row.raw}')
    if not args.yes:
        print(f'Simulación: {len(rows)} valor(es) para {table_name}. Repite con --yes.')
        return 0

    write_rows(boto3.Session(profile_name = PROFILE, region_name = REGION)
               .resource('dynamodb').Table(table_name), rows)
    print(f'{len(rows)} valor(es) escritos en {table_name}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
