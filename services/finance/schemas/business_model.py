'''
    Pydantic V2 DTOs for the client's business model: what it sells, to whom,
    how it collects, what it spends on and what it expects this year.

    A guided form, not a document (Rafael, 19/20-oct-2026): each answer has its
    own field so the AI knows what it is comparing with the figures. No PDF or
    Word is uploaded.
'''
from pydantic import BaseModel, Field, model_validator

SHORT_TEXT = 500
LONG_TEXT = 2000


class BusinessModelSchema(BaseModel):
    '''
        The business model as the client's MANAGER describes it.
    '''
    sells: str = Field(..., min_length = 1, max_length = SHORT_TEXT,
                       description = 'What the business sells.')
    customers: str = Field(..., min_length = 1, max_length = SHORT_TEXT,
                           description = 'Who it sells to.')
    cash_sales_percent: float = Field(..., ge = 0, le = 100,
                                      description = 'Share of the sales collected on the spot.')
    credit_days: int = Field(..., ge = 0, le = 365,
                             description = 'Days the credit sales take to be collected.')
    main_costs: str = Field(..., min_length = 1, max_length = SHORT_TEXT,
                            description = 'What the business spends the most on.')
    sales_goal: float | None = Field(None, gt = 0,
                                     description = 'Net sales expected this year, in Bs.')
    margin_goal_percent: float | None = Field(None, gt = -100, lt = 100,
                                              description = 'Profit over net sales expected.')
    notes: str | None = Field(None, max_length = LONG_TEXT,
                              description = 'Anything else, in the owner\'s words.')

    @model_validator(mode = 'after')
    def expects_something(self) -> 'BusinessModelSchema':
        '''
            What the owner expects this year is sales, margin or both, never
            neither: it is what the AI compares the results with.

            Returns:
                BusinessModelSchema: The same model.

            Raises:
                ValueError: GOAL_MISSING.
        '''
        if self.sales_goal is None and self.margin_goal_percent is None:
            raise ValueError('GOAL_MISSING')
        return self


class BusinessModelResponseSchema(BaseModel):
    '''
        The business model the client stored, if any, and when it last changed.
    '''
    business_model: BusinessModelSchema | None
    updated_at: str | None = None
