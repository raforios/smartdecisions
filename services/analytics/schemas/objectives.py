'''
    Pydantic V2 DTOs for objective attainment — what was decided against what
    happened.

    Every other block in ANALYTICS describes the past on its own terms. This
    one judges it, and judging needs a yardstick the company owns: the
    objective, the cut where a percentage stops being acceptable, and what a
    bolivian is worth in points. None of those are facts about the data, so
    none of them are decided here.

    One objective is measured TWICE, and that is the point of the block: a
    client can hit their number on paper and owe every bolivian of it.
    `invoiced` answers whether they bought; `collected` answers whether the
    company got paid. Reporting only the first is how a quarter looks healthy
    until the cash does not arrive.
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.analytics import PeriodInfo


class Semaphore(str, Enum):
    '''
        How a percentage reads at a glance.

        A code and never a colour name in the user's language: the wording —
        and the colour itself— belongs to whoever draws the screen.
    '''
    GREEN = 'GREEN'
    YELLOW = 'YELLOW'
    RED = 'RED'


class CommercialPolicySchema(BaseModel):
    """
        The yardstick one account is judged with.

        Stored per owner because it is not a fact about the data: two
        companies reading the same sales disagree on where yellow becomes
        green, and on what a bolivian is worth in points. What the client
        does not set falls back to the service default, field by field.
    """
    yellow_from: float | None = Field(
        None, ge = 0,
        description = 'Attainment where RED becomes YELLOW, as a fraction.'
    )
    green_from: float | None = Field(
        None, ge = 0,
        description = 'Attainment where YELLOW becomes GREEN, as a fraction.'
    )
    bs_per_point: float | None = Field(
        None, gt = 0,
        description = 'Currency per point for a cluster with no rate of its own.'
    )
    points_per_cluster: dict[str, float] | None = Field(
        None,
        description = 'Currency per point, by cluster. The cluster names are '
                      'the account\'s own: the product declares none.'
    )
    usd_cost_share: float | None = Field(
        None, ge = 0, le = 1,
        description = 'Share of the cost bought in dollars, for any category '
                      'without one of its own. 1.0 is a pure importer.'
    )
    usd_cost_share_by_category: dict[str, float] | None = Field(
        None,
        description = 'Share of the cost bought in dollars, by category.'
    )


class ClientScoreSchema(BaseModel):
    '''
        One client in one month, judged against their objective.
    '''
    pos_id: str
    pos_name: str | None = None
    period: str = Field(..., description = "The month, as 'YYYY-MM'.")
    cluster: str | None = None
    supervisor: str | None = None
    market: str | None = None
    channel: str | None = None
    seller: str | None = None
    target_amount: float = Field(..., ge = 0)
    invoiced_amount: float = Field(..., ge = 0)
    collected_amount: float = Field(..., ge = 0)
    debt_amount: float = Field(..., description = 'Invoiced minus collected.')
    invoiced_ratio: float = Field(..., ge = 0)
    collected_ratio: float = Field(..., ge = 0)
    invoiced_semaphore: Semaphore
    collected_semaphore: Semaphore
    points: float = Field(..., ge = 0)


class ClusterCellSchema(BaseModel):
    """
        One cell of the cluster-by-semaphore matrix.

        `weight_on_target` is the cell's share of the whole objective, and it
        is the figure that stops the matrix from misleading: twenty red
        clients worth two per cent of the objective are a very different
        morning from three red clients worth forty.
    """
    cluster: str
    semaphore: Semaphore
    clients_count: int = Field(..., ge = 0)
    target_amount: float = Field(..., ge = 0)
    invoiced_amount: float = Field(..., ge = 0)
    collected_amount: float = Field(..., ge = 0)
    debt_amount: float
    invoiced_ratio: float = Field(..., ge = 0)
    weight_on_target: float = Field(..., ge = 0)


class ObjectivesTotalsSchema(BaseModel):
    '''
        The header figures: the whole account in one line.
    '''
    clients_count: int = Field(..., ge = 0)
    periods: list[str] = Field(default_factory = list)
    target_amount: float = Field(..., ge = 0)
    invoiced_amount: float = Field(..., ge = 0)
    collected_amount: float = Field(..., ge = 0)
    debt_amount: float
    invoiced_ratio: float = Field(..., ge = 0)
    collected_ratio: float = Field(..., ge = 0)
    debt_ratio: float = Field(..., ge = 0, description = 'Debt over objective.')
    points: float = Field(..., ge = 0)


class ObjectivesBlockSchema(BaseModel):
    """
        Attainment, whole: the totals, the matrix and every client behind it.

        The three travel together because a manager who sees a red cell asks
        which clients are in it, and a second round trip to answer that is how
        a screen stops being used.
    """
    totals: ObjectivesTotalsSchema
    by_cluster: list[ClusterCellSchema] = Field(default_factory = list)
    clients: list[ClientScoreSchema] = Field(default_factory = list)
    policy: CommercialPolicySchema
    clients_without_objective: int = Field(
        0, ge = 0,
        description = 'Clients who invoiced in the window and were never given '
                      'an objective. Reported, never scored: a percentage '
                      'against a target nobody set would be an invention.'
    )


class ObjectivesResponse(ObjectivesBlockSchema):
    """
        Full attainment view for GET /v1/analytics/objectives/{dataset_id}.
    """
    dataset_id: str
    period: PeriodInfo = PeriodInfo()
    available_periods: list[str] = Field(
        default_factory = list,
        description = 'Every month the objectives file has; without a window '
                      'only the latest is judged.'
    )


class CommercialPolicyResponse(CommercialPolicySchema):
    """
        The yardstick as it will actually be applied, defaults filled in.

        It answers the question a caller cannot answer from what they sent:
        which cuts are really in force before a semaphore is drawn.
    """
    owner_email: str
