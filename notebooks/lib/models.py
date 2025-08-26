'''
    Frontend models
'''

import os
from dataclasses import dataclass
import numpy as np

@dataclass
class OptimizationParams:
    '''
        Class to define Optimization Params
    '''
    route_id: int
    day: int
    primary: int
    dist: int = 1500

@dataclass
class UploadFileParams:
    '''
        Class to define Upload file params
    '''
    full_local_file_path: str
    bucket: str
    file_path: str
    validation: bool = True

    @property
    def local_path(self):
        '''
            Local Path property
        '''
        return os.path.dirname(self.full_local_file_path)

    @property
    def file_name(self):
        '''
            File Name property
        '''
        return os.path.basename(self.full_local_file_path)

@dataclass
class DeleteFileParams:
    '''
        Class to define Delete file params
    '''
    bucket_name: str
    file_name: str
    file_path: str

@dataclass
class LogisticCostParams:
    '''
        Class to define parameters for logistic cost calculation.
    '''
    x_matrix: np.ndarray
    y: np.ndarray
    w: np.ndarray
    b: float

@dataclass
class GradientDescentParams:
    '''
        Class to define parameters for logistic regression gradient descent.
    '''
    x_matrix: np.ndarray
    y: np.ndarray
    w_in: np.ndarray
    b_in: float
    alpha: float
    num_iters: int

@dataclass
class NormalizeFeaturesParams:
    '''
        Class to define feature normalization parameters.
    '''
    x_matrix: np.ndarray

@dataclass
class PredictLogisticParams:
    '''
        Class to define parameters for logistic regression prediction.
    '''
    x_matrix: np.ndarray
    w: np.ndarray
    b: float

@dataclass
class LinearGradientDescentParams:
    '''
        Class to define parameters for linear regression gradient descent.
    '''
    x: np.ndarray
    y: np.ndarray
    w_in: np.ndarray
    b_in: float
    alpha: float
    num_iters: int

@dataclass
class PredictLinearParams:
    '''
        Class to define parameters for linear regression prediction.
    '''
    x_test: np.ndarray
    w: np.ndarray
    b: float

@dataclass
class LinearGradientSingleDescentParams:
    '''
        Class to define parameters for linear regression (single-feature) gradient descent.
    '''
    x: np.ndarray
    y: np.ndarray
    w_in: float
    b_in: float
    alpha: float
    num_iters: int
