''' Cotizaciones Tab '''
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api_client import upload_mining_prices, fetch_mineral_prices
from utils.exports import convert_df_to_excel, convert_df_to_pdf

def render_cotizaciones_tab():
    with st.expander('📥 Carga de Datos (CSV Cotizaciones)'):
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            file_cot = st.file_uploader('Subir archivo de cotización diario', type=['csv'], key='up_cot')
        with col_c2:
            delim = st.selectbox('Separador', [',', ';', '|'])
            
        if file_cot and st.button('🚀 Procesar Cotizaciones'):
            with st.spinner('Procesando cotizaciones en memoria...'):
                res_etl = upload_mining_prices(file_cot.name, file_cot.getvalue(), delim)
                if res_etl and res_etl.status_code == 201:
                    st.success('ETL Exitoso. Registros procesados.')
                else:
                    st.error('Error procesando archivo.')

    raw_prices = fetch_mineral_prices()
    if raw_prices:
        df_cot = pd.DataFrame([{
            'Fecha': item['date'], 'Mineral': item['mineral']['name'], 'Unidad': item['mineral']['unit'],
            'Baja': float(item['price_low']), 'Alta': float(item['price_high']) or float(item['price_low'])
        } for item in raw_prices])
        df_cot['Fecha'] = pd.to_datetime(df_cot['Fecha'])
        df_cot = df_cot.sort_values('Fecha')

        st.subheader('Resumen de Mercado (Variación 24h)')
        kpi_cols = st.columns(4)
        minerals_list = df_cot['Mineral'].unique()
        for i, m_name in enumerate(minerals_list[:4]):
            m_data = df_cot[df_cot['Mineral'] == m_name]
            last_price = m_data.iloc[-1]['Baja']
            prev_price = m_data.iloc[-2]['Baja'] if len(m_data) > 1 else last_price
            diff = ((last_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0
            kpi_cols[i].metric(label=f'{m_name}', value=f'${last_price:,.2f}', delta=f'{diff:.2f}%')

        st.divider()
        st.subheader('📈 Tendencias Globales y Volatilidad')
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            selected_minerals = st.multiselect('Comparativa', minerals_list, default=list(minerals_list)[:3])
            fig_comp = px.line(df_cot[df_cot['Mineral'].isin(selected_minerals)], x='Fecha', y='Baja', color='Mineral', template='plotly_white')
            st.plotly_chart(fig_comp, width='stretch') # SOLUCIÓN DEL WARNING DE ANCHURA
        with col_v2:
            target = st.selectbox('Análisis de Rango', minerals_list)
            t_df = df_cot[df_cot['Mineral'] == target]
            fig_detail = go.Figure()
            fig_detail.add_trace(go.Scatter(x=t_df['Fecha'], y=t_df['Baja'], name='Mínimo', line=dict(color='#007bff')))
            fig_detail.add_trace(go.Scatter(
                x=pd.concat([t_df['Fecha'], t_df['Fecha'][::-1]]), y=pd.concat([t_df['Alta'], t_df['Baja'][::-1]]),
                fill='toself', fillcolor='rgba(0,123,255,0.15)', line=dict(color='rgba(255,255,255,0)'), name='Volatilidad'
            ))
            fig_detail.update_layout(template='plotly_white')
            st.plotly_chart(fig_detail, width='stretch')

        st.divider()
        with st.spinner('Preparando exportaciones...'):
            xlsx_cot = convert_df_to_excel(df_cot, 'Cotizaciones')
            pdf_cot = convert_df_to_pdf(df_cot, 'Cotizaciones', 'USD')

        c_exp1, c_exp2, c_exp3 = st.columns([2, 1, 1])
        with c_exp1: st.subheader('📄 Exportación Consolidada')
        with c_exp2: st.download_button('📥 Excel', xlsx_cot, 'cotizaciones.xlsx', width='stretch')
        with c_exp3: st.download_button('📄 PDF Pro', pdf_cot, 'cotizaciones.pdf', width='stretch')
        
        with st.expander('🔍 Datos Crudos'):
            st.dataframe(df_cot.sort_values(by='Fecha', ascending=False), width='stretch')
