'''
    Mining Analysis BI Dashboard - Enterprise Professional Edition
'''
import streamlit as st
from datetime import datetime

# Importación de componentes refactorizados
from components.auth import require_auth
from components.cotizaciones import render_cotizaciones_tab
from components.boletin import render_boletin_tab
from components.companies import render_companies_tab

# --- CONFIGURACIÓN Y ESTILOS (Restaurando el CSS Original) ---
st.set_page_config(page_title='Mining BI', layout='wide', page_icon='⛏️')
st.markdown('''
    <style>
    .main { background-color: #f4f7f6; }
    .stMetric { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
    ''', unsafe_allow_html=True)

# Lógica de Login (Detiene la app si no se autentica)
require_auth()

# --- SIDEBAR (Restaurado) ---
try:
    # Use_container_width deprecado por Streamlit, usamos width parameter seguro o dejamos que la imagen auto-ajuste.
    st.sidebar.image('./img/cropped-escudo.png')
except:
    pass
st.sidebar.caption('Panel de Control BI')

if st.sidebar.button('Cerrar Sesión', use_container_width=True):
    st.session_state['auth_token'] = None
    st.rerun()

st.title('📊 BI Minera y Metalurgia')

# --- PARÁMETROS GLOBALES ---
col_y, col_c, col_r = st.columns([1, 1, 1])
with col_y:
    sel_year = st.selectbox('Gestión Fiscal', list(range(datetime.now().year, 2012, -1)))
with col_c:
    sel_currency = st.radio('Divisa', ['BOB', 'USD'], horizontal=True)
with col_r:
    ex_rate = st.number_input('Tipo de Cambio (Bs/USD)', value=6.96)

# --- TABS (Restaurado el esquema de 4 pestañas o 3 sin el Histórico) ---
tab_cot, tab_boletin, tab_companies = st.tabs([
    '📈 Cotizaciones Internacionales', 
    '📑 Boletín Oficial',
    '🏢 Empresas Mineras'
])

with tab_cot:
    render_cotizaciones_tab()
    
with tab_boletin:
    # Pasamos EXTRICAMENTE los 3 argumentos requeridos para arreglar el TypeError
    render_boletin_tab(sel_year, sel_currency, ex_rate)
    
with tab_companies:
    render_companies_tab(sel_year)
