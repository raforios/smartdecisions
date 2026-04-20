import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# Configuración de la página (El toque profesional)
st.set_page_config(page_title="Minería Inteligente - MMM", page_icon="⛏️", layout="wide")

# --- GENERACIÓN DE DATOS (Simulando nuestro Pipeline ETL) ---
@st.cache_data
def load_mock_data():
    dates = pd.date_range(start="2025-01-01", end=datetime.now(), freq='D')
    minerals = ['Estaño', 'Zinc', 'Plata', 'Oro']
    departments = ['Potosí', 'Oruro', 'La Paz']
    
    data = []
    for date in dates:
        for min in minerals:
            price = np.random.uniform(15, 30) if min == 'Estaño' else np.random.uniform(1, 5)
            prod = np.random.uniform(100, 500)
            dept = np.random.choice(departments)
            data.append([date, min, price, prod, dept])
            
    df = pd.DataFrame(data, columns=['Fecha', 'Mineral', 'Precio_USD', 'Producción_TM', 'Departamento'])
    df['Regalias_Estimadas'] = df['Precio_USD'] * df['Producción_TM'] * 0.05 # 5% ficticio
    return df

df = load_mock_data()

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
st.sidebar.image("./img/cropped-escudo.png", width=250)
st.sidebar.title("Filtros Estratégicos")
selected_mineral = st.sidebar.multiselect("Seleccionar Mineral", options=df['Mineral'].unique(), default=['Estaño', 'Oro'])
date_range = st.sidebar.date_input("Rango de Fechas", [datetime(2025, 1, 1), datetime.now()])

# Filtrado dinámico
mask = (df['Mineral'].isin(selected_mineral)) & (df['Fecha'].dt.date >= date_range[0]) & (df['Fecha'].dt.date <= date_range[1])
df_filtered = df[mask]

# --- CUERPO PRINCIPAL ---
st.title("⛏️ Dashboard de Inteligencia Minera (PoC)")
st.markdown("### Ministerio de Minería y Metalurgia - Control de Gestión 2026")
st.divider()

# Indicadores Clave (KPIs) - EL EFECTO WOW INMEDIATO
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Producción (TM)", f"{df_filtered['Producción_TM'].sum():,.2f}")
with col2:
    avg_price = df_filtered['Precio_USD'].mean()
    st.metric("Precio Promedio Indice", f"US$ {avg_price:.2f}", delta=f"{np.random.uniform(-1,1):.2f}%")
with col3:
    st.metric("Regalías Proyectadas", f"US$ {df_filtered['Regalias_Estimadas'].sum():,.2f}")
with col4:
    st.metric("Centros Activos", "42", "3 nuevos")

st.divider()

# --- GRÁFICOS ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("Tendencia de Precios (Bolsa de Londres)")
    fig_line = px.line(df_filtered, x='Fecha', y='Precio_USD', color='Mineral', template="plotly_dark")
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.subheader("Producción por Departamento (TM)")
    fig_bar = px.bar(df_filtered, x='Departamento', y='Producción_TM', color='Mineral', barmode='group')
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# TABLA DE DATOS CRUDA (Para auditoría)
with st.expander("Ver Datos Consolidados (Auditoría Forense)"):
    st.dataframe(df_filtered, use_container_width=True)

st.info("Nota técnica: Este dashboard consume datos simulados mediante un pipeline de Python 3.12 y está listo para ser conectado a la base de datos MySQL de la Intranet vía SQLAlchemy.")
