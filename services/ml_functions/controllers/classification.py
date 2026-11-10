'''
    Classification controller
'''
from core.logger_config import custom_logger as logger
from core.utils import handle_operation
from services import training
from services.classification import association_rules, rank_tiers
from schemas.classification import (
    AssociationRule,
    AssociationRulesRequest,
    AssociationRulesResponse,
    ComputeCostLogisticRequest,
    ComputeGradientLogisticRequest,
    ComputeGradientLogisticResponse,
    GradientDescentLogisticRequest,
    GradientDescentLogisticResponse,
    PredictLogisticRequest,
    PredictLogisticResponse,
    SigmoidBatchRequest,
    TiersRequest,
    TiersResponse
)


@handle_operation(exc_type = (ValueError, TypeError))
async def calculating_sigmoid(request_body: SigmoidBatchRequest) -> list[float]:
    '''
        The sigmoid of each value.
    '''
    return training.sigmoid_batch(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def calculating_cost_logistic(request_body: ComputeCostLogisticRequest) -> float:
    '''
        The log loss of a logistic model.
    '''
    return training.logistic_cost(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def calculating_gradient_logistic(
    request_body: ComputeGradientLogisticRequest
) -> ComputeGradientLogisticResponse:
    '''
        The gradient of the log loss of a logistic model.
    '''
    return training.logistic_gradient(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def performing_gradient_descent_logistic(
    request_body: GradientDescentLogisticRequest
) -> GradientDescentLogisticResponse:
    '''
        Fits a logistic model by gradient descent.
    '''
    return training.train_logistic(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def predicting_logistic_classification(
    request_body: PredictLogisticRequest
) -> PredictLogisticResponse:
    '''
        The class of each example under a trained logistic model.
    '''
    return training.predict_classes(request_body)


@handle_operation(exc_type = (ValueError, TypeError))
async def ranking_tiers(request_body: TiersRequest) -> TiersResponse:
    '''
    Controller splitting the values in tiers by their place in the ranking.
    '''
    tiers = rank_tiers(request_body.values, request_body.cuts)
    message = f'{len(tiers)} value(s) split in {len(request_body.cuts) + 1} tiers.'
    logger.info(message)
    return TiersResponse(tiers = tiers)


@handle_operation(exc_type = (ValueError, TypeError))
async def mining_association_rules(
    request_body: AssociationRulesRequest
) -> AssociationRulesResponse:
    '''
    Controller mining the association rules of the transactions (Apriori).
    '''
    rules = association_rules(request_body.transactions, request_body.min_support,
                              request_body.min_lift)
    message = (f'{len(rules)} association rule(s) from '
               f'{len(request_body.transactions)} transaction(s).')
    logger.info(message)
    return AssociationRulesResponse(
        rules = [AssociationRule(antecedents = list(rule.antecedents),
                                 consequents = list(rule.consequents),
                                 support = rule.support, confidence = rule.confidence,
                                 lift = rule.lift) for rule in rules],
        transactions = len(request_body.transactions)
    )
