''' Global configuration and constants for the Streamlit App. '''
import os

# API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:3020/v1/mining-analysis')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://jvxmqeg601.execute-api.us-east-1.amazonaws.com/minig_analysis/v1/mining-analysis')
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth')

UI_COLORS = {
    'navy': '#1A2A3A', 'gold': '#C9A751', 'red': '#8B0000',
    'dark': '#363534', 'blue_light': '#4A6984', 'gold_light': '#E3C77A',
    'green': '#2E4034', 'gray': '#E5E7E9', 'subtotal_bg': '#E5E7E9'
}

# ESTA ES LA VARIABLE QUE FALTA:
PALETTE_DEPT = [
    UI_COLORS['navy'], UI_COLORS['gold'], UI_COLORS['gray'],
    UI_COLORS['blue_light'], UI_COLORS['green'], UI_COLORS['red'],
    UI_COLORS['dark'], UI_COLORS['gold_light'], '#D9D9D9'
]

MONTHS_SPANISH = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}
