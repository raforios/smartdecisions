'''
    The forecast endpoint answers its model, built, with the chosen model.

    The controller imports nothing that validates the environment, so the CI
    runs this with no .env.
'''
import asyncio

from controllers.classification import mining_association_rules, ranking_tiers
from controllers.prediction import forecast_series
from controllers.routing import clustering_points, ordering_points
from schemas.classification import (
    AssociationRulesRequest,
    AssociationRulesResponse,
    TiersRequest,
    TiersResponse
)
from schemas.routing import ClustersRequest, ClustersResponse, OrderRequest, OrderResponse
from schemas.prediction import ForecastModel, ForecastRequest, ForecastResponse
from tests.test_forecast import SEASONAL


def test_the_forecast_answers_its_model_with_the_chosen_projection():
    '''A monthly seasonal series comes back projected by the seasonal model.'''
    answer = asyncio.run(forecast_series(ForecastRequest(
        values = SEASONAL, horizon = 12, season_length = 12, backtest_points = 12)))
    assert isinstance(answer, ForecastResponse)
    assert answer.model is ForecastModel.HOLT_WINTERS
    assert len(answer.forecast) == 12 and answer.tested_points == 7


def test_the_tiers_answer_their_model():
    '''The tiers endpoint answers TiersResponse.'''
    answer = asyncio.run(ranking_tiers(TiersRequest(values = [3.0, 1.0, 2.0], cuts = [0.5])))
    assert isinstance(answer, TiersResponse) and answer.tiers == [0, 1, 0]


def test_the_association_rules_answer_their_model():
    '''The association-rules endpoint answers AssociationRulesResponse.'''
    answer = asyncio.run(mining_association_rules(AssociationRulesRequest(
        transactions = [['a', 'b'], ['a', 'b'], ['c']], min_support = 0.5, min_lift = 1.0)))
    assert isinstance(answer, AssociationRulesResponse)
    assert answer.transactions == 3 and len(answer.rules) == 2


def test_the_clusters_answer_their_model():
    '''The clusters endpoint answers ClustersResponse.'''
    answer = asyncio.run(clustering_points(ClustersRequest(
        points = [[0.0, 0.0], [0.0, 0.001], [1.0, 1.0], [1.0, 1.001]],
        clusters = 2, seed = 7, iterations = 60)))
    assert isinstance(answer, ClustersResponse) and len(answer.labels) == 4


def test_the_order_answers_its_model():
    '''The order endpoint answers OrderResponse.'''
    answer = asyncio.run(ordering_points(OrderRequest(
        points = [[0.0, 0.0], [0.0, 0.2], [0.0, 0.1]], passes = 8)))
    assert isinstance(answer, OrderResponse) and answer.order == [0, 2, 1]
