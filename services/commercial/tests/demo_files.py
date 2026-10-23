'''
    The demo sales and payments served in place of S3, for the tests of the
    views that read a whole dataset (dashboard, client card).
'''
from tests.test_controllers import _collections_frame, _sales_frame

METADATA = {'file_s3_key': 'sales.csv', 'collections_s3_key': 'payments.csv',
            'status': 'validated'}
FRAMES = {'sales.csv': _sales_frame, 'payments.csv': _collections_frame}


def serve_demo_files(
    monkeypatch,
    modules: tuple
) -> None:
    '''
        Makes every given controller module read the demo files.

        Args:
            monkeypatch: Pytest fixture.
            modules (tuple): The controller modules that load the dataset.
    '''
    for module in modules:
        monkeypatch.setattr(module, 'get_dataset_metadata', lambda **_: METADATA)
        if hasattr(module, 'load_dataframe'):
            monkeypatch.setattr(module, 'load_dataframe', lambda key, _token: FRAMES[key]())
