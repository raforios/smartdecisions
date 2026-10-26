'''
    Reads `docs/parametros.md`, the single definition of the business values.

    Pure and free of any service: the seed of each service's own
    `<service>_parameters` table and the tests of that service read the same
    rows from here, so there is no second list to drift.
'''
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

DOCUMENT = Path(__file__).resolve().parents[2] / 'docs' / 'parametros.md'

# «| finance | CODE | NUMBER | 3 | What it governs |»
_ROW = re.compile(
    r'^\|\s*([a-z_]+)\s*\|\s*([A-Z0-9_]+)\s*\|\s*(NUMBER|TEXT|LIST)\s*'
    r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$'
)


@dataclass(frozen = True)
class DocumentRow:
    '''
        One business value as the document defines it.
    '''
    scope: str
    code: str
    kind: str
    raw: str
    description: str

    @property
    def value(self) -> Decimal | str | list[str]:
        '''
            The value in its type: a NUMBER as Decimal (what DynamoDB
            stores), a LIST split on spaces, a TEXT as written.
        '''
        if self.kind == 'NUMBER':
            return Decimal(self.raw)
        if self.kind == 'LIST':
            return self.raw.split()
        return self.raw


def read_rows(
    scope: str | None = None,
    document: Path = DOCUMENT
) -> list[DocumentRow]:
    '''
        The rows of the document, of one scope or of all.

        Args:
            scope (str | None): `global`, a service name, or None for all.
            document (Path): The document to read.

        Returns:
            list[DocumentRow]: The rows, in the document's order.
    '''
    rows = [DocumentRow(*match.groups())
            for match in map(_ROW.match, document.read_text(encoding = 'utf-8').splitlines())
            if match]
    return [row for row in rows if scope is None or row.scope == scope]


def write_rows(
    table: Any,
    rows: list[DocumentRow]
) -> None:
    '''
        Writes the rows into a service's parameters table, one item per code.
        The seed and every service's tests write them the same way.

        Args:
            table (Any): The boto3 DynamoDB Table.
            rows (list[DocumentRow]): The rows to write.
    '''
    with table.batch_writer() as batch:
        for row in rows:
            batch.put_item(Item = {'code': row.code, 'value': row.value,
                                   'value_type': row.kind, 'description': row.description})


def create_and_seed(
    resource: Any,
    table_name: str,
    scope: str
) -> None:
    '''
        Creates a service's parameters table and writes its rows: what a
        service's tests do in moto before the modules read their values.

        Args:
            resource (Any): The boto3 DynamoDB resource.
            table_name (str): The service's parameters table.
            scope (str): The service, as the document names it.
    '''
    table = resource.create_table(
        TableName = table_name,
        KeySchema = [{'AttributeName': 'code', 'KeyType': 'HASH'}],
        AttributeDefinitions = [{'AttributeName': 'code', 'AttributeType': 'S'}],
        BillingMode = 'PAY_PER_REQUEST')
    write_rows(table, read_rows(scope))
