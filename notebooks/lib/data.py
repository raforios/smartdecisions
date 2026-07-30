'''
    File library with common functions to process external files
'''
import os
import random
from io import StringIO
import pandas as pd
import numpy as np
import sqlalchemy as sa
from dotenv import dotenv_values

BASEDIR = os.path.dirname(os.path.abspath(__file__))
PARAMETERS = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(BASEDIR)), 'notebooks', '.env'))

engine = sa.create_engine(PARAMETERS.get('DATABASE_URL'))

# ----------------------------------------------------------------
# Generating a list of hexadecimal colors
# ----------------------------------------------------------------
def hexa_color_generator_list(quantity) -> list:
    '''
        Generates a list of unique hexadecimal colors.    
    '''
    colors = set()
    while len(colors) < quantity :
        # Generate a random color
        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)
        hex_color = f'#{red:02x}{green:02x}{blue:02x}'
        colors.add(hex_color)

    return list(colors)

# ----------------------------------------------------------------
# Get data from a excel file
# ----------------------------------------------------------------
def get_excel_data(file_name: str) -> pd.DataFrame:
    ''' 
        Read data from excel file
    '''
    data_df = pd.read_excel(f'{PARAMETERS['DATA_FOLDER']}/{file_name}')
    return data_df

# ----------------------------------------------------------------
# Load data from excel file to database
# ----------------------------------------------------------------
def load_excel_data(model: dict, table: str, file_name: str) -> pd.DataFrame:
    '''
        Load data from excel file to database
    '''
    df_load = get_excel_data(file_name)

    df_load = df_load.reset_index(drop = True)

    df_load.index += 1

    df_load = df_load.reset_index().rename(columns = model)

    # Insertar los datos en la tabla
    df_load.to_sql(table, engine, if_exists = 'replace', index = False)

    print(f'total registers: {len(df_load)}')
    return df_load

# ----------------------------------------------------------------
# Load data from text file
# ----------------------------------------------------------------
def load_text_data(file_name: str, delimiter: str, until_col: int, skip_rows: int) -> tuple:
    '''
        Load data from text file
    '''
    data = np.loadtxt(file_name, delimiter = delimiter, skiprows = skip_rows)
    x_matrix = data[:,:until_col]
    y = data[:,until_col]
    return x_matrix, y


def parse_txt_data(file_content: str, delimiter: str,
    until_col: int, skip_rows: int) -> tuple:
    '''
    Parsea el contenido de un archivo TXT (con formato CSV)
    para extraer una matriz de características X y un array de etiquetas Y.

    Args:
        file_content (str): El contenido del archivo TXT como una cadena.

    Returns:
        tuple[np.ndarray, np.ndarray]: Una tupla que contiene la matriz X
                                       y el array Y.
    '''
    # Usar StringIO para que numpy.loadtxt pueda leer la cadena como un archivo
    data_io = StringIO(file_content)

    data = np.loadtxt(data_io, delimiter = delimiter, skiprows = skip_rows, dtype = np.float64)
    x_matrix = data[:,:until_col]
    y = data[:,until_col]
    return x_matrix, y
