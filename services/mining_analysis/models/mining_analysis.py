'''
    DynamoDB item definitions for the quotations data (minerals and prices).

    The service runs only on DynamoDB since 02-11-2026; the relational copy
    of the quotations lives in `tools/etl_minerals/`, which publishes here.

    Key design, driven by how the data is actually read:

      minerals        PK: mineral_id (S)
          A catalogue of a handful of rows. Lookups by name resolve against a
          scan, which is cheaper than maintaining an index for nine items.

      mining_prices   PK: mineral_id (S)   SK: date (S, ISO 'YYYY-MM-DD')
          Every read is "this mineral, over this window": the biweekly average,
          the latest quote before a date and the fallback search. That is a
          Query on the partition with a range condition on the sort key, which
          is the cheapest access pattern DynamoDB offers. Listing everything
          falls back to a scan, used only by the full export.
'''
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any


MINERALS_TABLE_KEY = 'mineral_id'
PRICES_PARTITION_KEY = 'mineral_id'
PRICES_SORT_KEY = 'date'


@dataclass(frozen = True)
class MineralItem:
    '''
        One mineral of the catalogue as stored in DynamoDB.

        Keeps the column names of the ETL's `t_minerals`, so a publish from
        `tools/etl_minerals/` lands with the same attribute names.
    '''
    mineral_id: str
    name: str
    unit: str
    chemical_symbol: str | None = None
    quoted_in: str | None = None
    method: str | None = None
    created_at: str | None = None

    @classmethod
    def from_item(
        cls,
        item: dict[str, Any]
    ) -> MineralItem:
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (dict[str, Any]): Item as returned by boto3.

            Returns:
                MineralItem: The typed record.
        '''
        return cls(
            mineral_id = str(item[MINERALS_TABLE_KEY]),
            name = str(item.get('name', '')),
            unit = str(item.get('unit', '')),
            chemical_symbol = item.get('chemical_symbol'),
            quoted_in = item.get('quoted_in'),
            method = item.get('method'),
            created_at = item.get('created_at')
        )


@dataclass(frozen = True)
class MiningPriceItem:
    '''
        One daily quotation as stored in DynamoDB.

        `date` is kept as an ISO string because that is what makes it usable as
        a sort key; the store layer converts it to a date for the callers.
    '''
    mineral_id: str
    date: date_type
    price_low: float | None = None
    price_high: float | None = None
    created_at: str | None = None

    @classmethod
    def from_item(
        cls,
        item: dict[str, Any]
    ) -> MiningPriceItem:
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (dict[str, Any]): Item as returned by boto3.

            Returns:
                MiningPriceItem: The typed record, with the date parsed.
        '''
        return cls(
            mineral_id = str(item[PRICES_PARTITION_KEY]),
            date = date_type.fromisoformat(str(item[PRICES_SORT_KEY])),
            price_low = None if item.get('price_low') is None else float(item['price_low']),
            price_high = None if item.get('price_high') is None else float(item['price_high']),
            created_at = item.get('created_at')
        )

    def to_item(self) -> dict[str, Any]:
        '''
            Renders the record as the item DynamoDB stores.

            Returns:
                dict[str, Any]: Item ready for put_item.
        '''
        return {
            PRICES_PARTITION_KEY: self.mineral_id,
            PRICES_SORT_KEY: self.date.isoformat(),
            'price_low': self.price_low,
            'price_high': self.price_high,
            'created_at': self.created_at,
        }
