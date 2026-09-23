'''
    Art. 227 of Ley 535: the scale that turns an official quotation into a
    royalty rate. Each mineral has a linear formula between a floor and a cap;
    domestic sales pay a fraction of the export rate.

    The scales live in DynamoDB as parameters, seeded from the Ministry's own
    biweekly report (INF/MMM/VMPMRF/DGPMRF/UCF/N°0041/2026) so the numbers can
    be corrected without touching code when the law or its reading changes.
'''
from typing import Dict, List, Tuple

from boto3.resources.base import ServiceResource

from models.market_prices import RoyaltyRuleItem
from schemas.market import MarketError, RateBasis, RoyaltyRuleSchema
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.prices_dyb import get_royalty_rule, list_royalty_rules, put_royalty_rule
from services.utils import get_current_time_gmt

LEGAL_BASIS = 'Ley 535 Art. 227 — INF/MMM/VMPMRF/DGPMRF/UCF/N°0041/2026'
# Domestic sales pay 60 % of the export rate: 5 -> 3, 7 -> 4.2, 6 -> 3.6, as
# the official table prints them.
INTERNAL_FACTOR = 0.6

# slope, intercept, floor, cap. The floor and the cap are where the formula
# meets 1 % (4 % gold, 3 % silver) and 5 % (7 % gold, 6 % silver): e.g. copper
# 3.0769 * 0.70 - 1.1538 = 1.0 and 3.0769 * 2.00 - 1.1538 = 5.0.
DEFAULT_SCALES: Dict[str, Tuple[float, float, float, float]] = {
    '1': (1.6, -3.0, 1.0, 5.0),                # Estaño, USD/LF
    '2': (13.33333, -3.0, 1.0, 5.0),           # Plomo, USD/LF
    '3': (8.60215, -3.08602, 1.0, 5.0),        # Zinc, USD/LF
    '4': (3.0769, -1.1538, 1.0, 5.0),          # Cobre, USD/LF
    '5': (0.0017391, -1.60870, 1.0, 5.0),      # Antimonio, USD/TMF
    '6': (0.00025, -1.0, 1.0, 5.0),            # Wolfram, USD/TMF
    '7': (0.61538, -1.15385, 1.0, 5.0),        # Bismuto, USD/LF
    '8': (0.01, 0.0, 4.0, 7.0),                # Oro, USD/OT
    '9': (0.75, 0.0, 3.0, 6.0)                 # Plata, USD/OT
}


def default_rules() -> List[RoyaltyRuleItem]:
    '''
        The seed scales, one per mineral of the catalogue.

        Returns:
            List[RoyaltyRuleItem]: Rules as the report states them.
    '''
    stamp = get_current_time_gmt().isoformat(timespec = 'seconds')
    return [
        RoyaltyRuleItem(
            mineral_id = mineral_id, slope = slope, intercept = intercept,
            min_rate = floor, max_rate = cap, internal_factor = INTERNAL_FACTOR,
            legal_basis = LEGAL_BASIS, updated_at = stamp
        )
        for mineral_id, (slope, intercept, floor, cap) in DEFAULT_SCALES.items()
    ]


def ensure_rules(dynamodb_resource: ServiceResource) -> List[RoyaltyRuleItem]:
    '''
        Seeds the scales the first time the table is empty; otherwise returns
        what is stored, which may have been edited since.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            List[RoyaltyRuleItem]: The rules in force.
    '''
    stored = list_royalty_rules(dynamodb_resource)
    if stored:
        return stored
    seeded = default_rules()
    for rule in seeded:
        put_royalty_rule(dynamodb_resource, rule)
    message = f'Royalty rules seeded for {len(seeded)} mineral(s).'
    logger.info(message)
    return seeded


def rules_by_mineral(dynamodb_resource: ServiceResource) -> Dict[str, RoyaltyRuleItem]:
    '''
        The rules in force keyed by mineral id.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            Dict[str, RoyaltyRuleItem]: {mineral_id: rule}.
    '''
    return {rule.mineral_id: rule for rule in ensure_rules(dynamodb_resource)}


def save_rule(
    dynamodb_resource: ServiceResource,
    rule: RoyaltyRuleSchema
) -> RoyaltyRuleItem:
    '''
        Creates or replaces one scale from the API.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            rule (RoyaltyRuleSchema): The scale as edited.

        Returns:
            RoyaltyRuleItem: What was stored.
    '''
    item = RoyaltyRuleItem(
        mineral_id = rule.mineral_id, slope = rule.slope, intercept = rule.intercept,
        min_rate = rule.min_rate, max_rate = rule.max_rate,
        internal_factor = rule.internal_factor, legal_basis = rule.legal_basis,
        updated_at = get_current_time_gmt().isoformat(timespec = 'seconds')
    )
    put_royalty_rule(dynamodb_resource, item)
    return item


def rule_for(
    dynamodb_resource: ServiceResource,
    mineral_id: str
) -> RoyaltyRuleItem:
    '''
        The scale of one mineral, or RULE_NOT_FOUND.

        Args:
            mineral_id (str): Catalogue id.

        Returns:
            RoyaltyRuleItem: The rule.
    '''
    rule = get_royalty_rule(dynamodb_resource, mineral_id)
    if rule is None:
        raise RegisterNotFoundError(detail = MarketError.RULE_NOT_FOUND.value)
    return rule


def apply_rule(
    rule: RoyaltyRuleItem,
    quotation: float
) -> Tuple[float, float, RateBasis]:
    '''
        The export and domestic rates for a quotation, and which part of the
        scale decided them.

        Args:
            rule (RoyaltyRuleItem): The mineral's scale.
            quotation (float): Official quotation in the mineral's unit.

        Returns:
            Tuple[float, float, RateBasis]: export rate %, domestic rate %, basis.
    '''
    if rule.slope == 0 and rule.min_rate == rule.max_rate:
        rate, basis = rule.max_rate, RateBasis.FIXED
    else:
        raw = rule.slope * quotation + rule.intercept
        if raw >= rule.max_rate:
            rate, basis = rule.max_rate, RateBasis.CAP
        elif raw <= rule.min_rate:
            rate, basis = rule.min_rate, RateBasis.FLOOR
        else:
            rate, basis = raw, RateBasis.FORMULA
    return round(rate, 3), round(rate * rule.internal_factor, 3), basis


def to_rule_schema(rule: RoyaltyRuleItem) -> RoyaltyRuleSchema:
    '''
        Stored rule -> DTO.

        Args:
            rule (RoyaltyRuleItem): The stored scale.

        Returns:
            RoyaltyRuleSchema: The scale as the API returns it.
    '''
    return RoyaltyRuleSchema(
        mineral_id = rule.mineral_id, slope = rule.slope, intercept = rule.intercept,
        min_rate = rule.min_rate, max_rate = rule.max_rate,
        internal_factor = rule.internal_factor, legal_basis = rule.legal_basis,
        updated_at = rule.updated_at
    )
