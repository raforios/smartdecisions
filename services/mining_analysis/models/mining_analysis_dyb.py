'''
    DynamoDB item definitions for the quotations data (minerals and prices).

    The relational models in mining_analysis.py stay untouched and remain the
    default; these describe the same two entities when the service is configured
    to run on DynamoDB, so a deployment without a relational database can still
    serve quotations.

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
from typing import Any, Dict, Optional


MINERALS_TABLE_KEY = 'mineral_id'
PRICES_PARTITION_KEY = 'mineral_id'
PRICES_SORT_KEY = 'date'


@dataclass(frozen = True)
class MineralItem:
    '''
        One mineral of the catalogue as stored in DynamoDB.

        Mirrors the columns of the relational Mineral model so the service layer
        reads the same attribute names whichever backend is active.
    '''
    mineral_id: str
    name: str
    unit: str
    chemical_symbol: Optional[str] = None
    quoted_in: Optional[str] = None
    method: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'MineralItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

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
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    created_at: Optional[str] = None

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'MiningPriceItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

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

    def to_item(self) -> Dict[str, Any]:
        '''
            Renders the record as the item DynamoDB stores.

            Returns:
                Dict[str, Any]: Item ready for put_item.
        '''
        return {
            PRICES_PARTITION_KEY: self.mineral_id,
            PRICES_SORT_KEY: self.date.isoformat(),
            'price_low': self.price_low,
            'price_high': self.price_high,
            'created_at': self.created_at,
        }
