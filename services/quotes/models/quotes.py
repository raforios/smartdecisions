'''
    DynamoDB item definitions for the exchange-rate history.

    The rate is published by the Banco Central de Bolivia, one figure per day.
    We keep our own copy because the BCB serves one date per request: building a
    series from it means one call per day, which is fine to backfill once and
    unacceptable to repeat on every screen refresh.

    Key design, driven by how the data is read:

      t_exchange_rates   PK: currency (S)   SK: date (S, ISO 'YYYY-MM-DD')

    Every read is "this currency, over this window" — the chart, the projection
    and the sale scenario all ask the same question. That is a Query on the
    partition with a range condition on the sort key. Currency is the partition
    because the BCB publishes some twenty of them and we will eventually want
    more than the dollar.
'''
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Dict, Optional


RATES_PARTITION_KEY = 'currency'
RATES_SORT_KEY = 'date'

# ISO 4217 code of the currency this module was built for. Kept as a constant
# rather than spelled inline so the day a second currency is stored, the
# distinction is explicit instead of a string repeated across the service.
USD = 'USD'


@dataclass(frozen = True)
class ExchangeRateItem:
    '''
        The official rate of one currency on one date.

        `official_rate` is the BCB's Tipo de Cambio Oficial in bolivianos per
        unit of foreign currency — the figure a sale is settled at.
    '''
    currency: str
    date: date_type
    official_rate: float
    source: Optional[str] = None
    retrieved_at: Optional[str] = None

    @classmethod
    def from_item(cls, item: Dict[str, Any]) -> 'ExchangeRateItem':
        '''
            Builds the record from a raw DynamoDB item.

            Args:
                item (Dict[str, Any]): Item as returned by boto3.

            Returns:
                ExchangeRateItem: The typed record, with the date parsed.
        '''
        return cls(
            currency = str(item[RATES_PARTITION_KEY]),
            date = date_type.fromisoformat(str(item[RATES_SORT_KEY])),
            official_rate = float(item['official_rate']),
            source = item.get('source'),
            retrieved_at = item.get('retrieved_at')
        )

    def to_item(self) -> Dict[str, Any]:
        '''
            Renders the record as the item DynamoDB stores.

            Returns:
                Dict[str, Any]: Item ready for put_item.
        '''
        return {
            RATES_PARTITION_KEY: self.currency,
            RATES_SORT_KEY: self.date.isoformat(),
            'official_rate': self.official_rate,
            'source': self.source,
            'retrieved_at': self.retrieved_at,
        }
