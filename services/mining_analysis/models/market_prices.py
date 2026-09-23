'''
    DynamoDB item definitions for the market side of the quotations: the daily
    prices read from public sources before the Ministry publishes, and the
    royalty scales of Art. 227 that turn an average into a rate.

    Key design, driven by how the data is read:
      mining_market_prices  PK: mineral_id (S)   SK: date (S, ISO 'YYYY-MM-DD')
          Same shape as `mining_prices`: every read is "this mineral over this
          fortnight", a Query on the partition bounded by the sort key. Kept in
          its own table so the official history is never mixed with a proxy.
      mining_royalty_rules  PK: mineral_id (S)
          Nine rows, read whole on every estimate.
'''
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Dict, Optional

MARKET_PARTITION_KEY = 'mineral_id'
MARKET_SORT_KEY = 'date'
RULES_TABLE_KEY = 'mineral_id'


@dataclass(frozen = True)
class MarketPriceItem:
    '''
        One daily market quotation in the unit the Ministry publishes (USD per
        fine pound for LME metals, USD per troy ounce for the fixes).
    '''
    mineral_id: str
    date: date_type
    price: float
    source: str
    retrieved_at: Optional[str] = None

    @classmethod
    def from_item(
        cls,
        item: Dict[str, Any]
    ) -> 'MarketPriceItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

            Returns:
                MarketPriceItem: The typed record.
        '''
        return cls(
            mineral_id = str(item[MARKET_PARTITION_KEY]),
            date = date_type.fromisoformat(str(item[MARKET_SORT_KEY])),
            price = float(item['price']),
            source = str(item.get('source', '')),
            retrieved_at = item.get('retrieved_at')
        )

    def to_item(self) -> Dict[str, Any]:
        '''
            The record as a DynamoDB item (floats still native; the store
            converts them).

            Returns:
                Dict[str, Any]: Item ready to be written.
        '''
        return {
            MARKET_PARTITION_KEY: self.mineral_id,
            MARKET_SORT_KEY: self.date.isoformat(),
            'price': self.price,
            'source': self.source,
            'retrieved_at': self.retrieved_at
        }


@dataclass(frozen = True)
class RoyaltyRuleItem:
    '''
        The Art. 227 scale of one mineral: rate = clamp(slope * CO + intercept,
        min_rate, max_rate) for exports, times `internal_factor` for domestic
        sales. `slope = 0` with equal bounds is a fixed rate.
    '''
    mineral_id: str
    slope: float
    intercept: float
    min_rate: float
    max_rate: float
    internal_factor: float
    legal_basis: str
    updated_at: Optional[str] = None

    @classmethod
    def from_item(
        cls,
        item: Dict[str, Any]
    ) -> 'RoyaltyRuleItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

            Returns:
                RoyaltyRuleItem: The typed record.
        '''
        return cls(
            mineral_id = str(item[RULES_TABLE_KEY]),
            slope = float(item['slope']),
            intercept = float(item['intercept']),
            min_rate = float(item['min_rate']),
            max_rate = float(item['max_rate']),
            internal_factor = float(item['internal_factor']),
            legal_basis = str(item.get('legal_basis', '')),
            updated_at = item.get('updated_at')
        )

    def to_item(self) -> Dict[str, Any]:
        '''
            The record as a DynamoDB item.

            Returns:
                Dict[str, Any]: Item ready to be written.
        '''
        return {
            RULES_TABLE_KEY: self.mineral_id,
            'slope': self.slope,
            'intercept': self.intercept,
            'min_rate': self.min_rate,
            'max_rate': self.max_rate,
            'internal_factor': self.internal_factor,
            'legal_basis': self.legal_basis,
            'updated_at': self.updated_at
        }
