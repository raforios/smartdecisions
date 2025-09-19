'''
    Base schemas for common validations.
'''
from pydantic import BaseModel, field_validator
import numpy as np

class NumPyValidatorBase(BaseModel):
    '''
    Base class with a common validator for NumPy-compatible data structures.
    '''
    @field_validator('x_matrix', 'x', 'x_test', mode = 'before')
    @classmethod
    def validate_numpy_array(cls, v, info):
        '''
        Validates that a list of lists can be safely converted to a NumPy array.
        '''
        field_name = info.field_name
        try:
            np_array = np.array(v, dtype=np.float64)
            if np_array.ndim not in [1, 2]:
                raise ValueError(f'{field_name} must be a 1D or 2D list of floats.')
            return v
        except Exception as e:
            raise ValueError(
                f'''Invalid input for {field_name}. Must be a list or list of lists of floats.
                Error: {e}'''
            ) from e
