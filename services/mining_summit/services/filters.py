'''
    Shared client-side filtering helpers for the Mining Summit service.
'''
from typing import Any, Dict, List, Optional


def filter_items_by_date_range(
    items: List[Dict[str, Any]],
    date_field: str,
    date_from: Optional[str],
    date_to: Optional[str]
) -> List[Dict[str, Any]]:
    '''
        Filters a list of items by an inclusive [date_from, date_to] range on
        the given field.

        Date bounds are applied client-side because the generic CRUD primitive
        only pushes equality filters down to DynamoDB.

        Args:
            items (List[Dict[str, Any]]): Already-paginated items to filter.
            date_field (str): Item attribute holding the comparable date string.
            date_from (Optional[str]): Inclusive lower bound (YYYY-MM-DD).
            date_to (Optional[str]): Inclusive upper bound (YYYY-MM-DD).

        Returns:
            List[Dict[str, Any]]: Items whose date falls within the range.
    '''
    if not date_from and not date_to:
        return items
    filtered: List[Dict[str, Any]] = []
    for item in items:
        value = item.get(date_field)
        if not value:
            continue
        if date_from and value < date_from:
            continue
        if date_to and value > date_to:
            continue
        filtered.append(item)
    return filtered
