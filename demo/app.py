'''
    Mining Analysis BI Dashboard - Enterprise Professional Edition
'''
import streamlit as st

# Importación de componentes refactorizados
from components.auth import require_auth
from components.cotizaciones import render_cotizaciones_tab

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

# Sólo las cotizaciones: el boletín de regalías y las empresas se retiraron
# (Rafael, 19-oct-2026); el tablero arma el reporte diario y el quincenal.
render_cotizaciones_tab()
