''' Cotizaciones Tab '''
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api_client import upload_mining_prices, fetch_mineral_prices
# IMPORTANTE: Importamos generate_ordered_pdf en lugar del legacy convert_df_to_pdf
from utils.exports import convert_df_to_excel, generate_ordered_pdf 

def render_cotizaciones_tab():
    with st.expander('📥 Carga de Datos (CSV Cotizaciones)'):
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            file_cot = st.file_uploader('Subir archivo de cotización diario', type=['csv', 'xlsx', 'xls'], key='up_cot')
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
            'Fecha': pd.to_datetime(item['date']).date(),
            'Mineral': item['mineral']['name'],
            'Símbolo': item['mineral'].get('chemical_symbol') or '-',
            'Mercado': item['mineral'].get('quoted_in') or '-',
            'Unidad': item['mineral']['unit'],
            'Baja': float(item['price_low']),
            'Alta': float(item['price_high']) if item['price_high'] is not None else float(item['price_low'])
        } for item in raw_prices])
        
        df_cot = df_cot.sort_values('Fecha')

        st.subheader('Resumen de Mercado (Variación Diario)')
        
        # 1. CARDS DISTRIBUIDOS EN 3 COLUMNAS (Patrón Armónico 3x3)
        minerals_list = df_cot['Mineral'].unique()
        
        for i in range(0, len(minerals_list), 3):
            kpi_cols = st.columns(3)
            for j in range(3):
                if i + j < len(minerals_list):
                    m_name = minerals_list[i + j]
                    m_data = df_cot[df_cot['Mineral'] == m_name]
                    
                    last_price = m_data.iloc[-1]['Baja']
                    prev_price = m_data.iloc[-2]['Baja'] if len(m_data) > 1 else last_price
                    diff = ((last_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0.0
                    
                    simbolo = m_data.iloc[-1]['Símbolo']
                    
                    kpi_cols[j].metric(
                        label=f'{m_name} ({simbolo})', 
                        value=f'${last_price:,.2f}', 
                        delta=f'{diff:.2f}%'
                    )

        st.divider()
        st.subheader('📈 Tendencias Globales y Volatilidad')
        
        selected_minerals = st.multiselect('Comparativa Global', minerals_list, default=list(minerals_list))
        if selected_minerals:
            fig_comp = px.line(
                df_cot[df_cot['Mineral'].isin(selected_minerals)], 
                x='Fecha', 
                y='Baja', 
                color='Mineral', 
                template='plotly_white'
            )
            fig_comp.update_xaxes(rangeslider_visible=True)
            st.plotly_chart(fig_comp, width='stretch')

        st.divider()
        st.subheader('📊 Análisis de Rango (Máximo y Mínimo)')
        
        df_volatil = df_cot[df_cot['Alta'] > df_cot['Baja']]
        minerales_volatiles = df_volatil['Mineral'].unique()
        
        if len(minerales_volatiles) > 0:
            target = st.selectbox('Seleccione un mineral', minerales_volatiles)
            t_df = df_cot[df_cot['Mineral'] == target]
            
            fig_detail = go.Figure()
            fig_detail.add_trace(go.Scatter(x=t_df['Fecha'], y=t_df['Baja'], name='Mínimo (Baja)', line=dict(color='#007bff')))
            fig_detail.add_trace(go.Scatter(x=t_df['Fecha'], y=t_df['Alta'], name='Máximo (Alta)', line=dict(color='#ffc107')))
            
            fig_detail.add_trace(go.Scatter(
                x=pd.concat([t_df['Fecha'], t_df['Fecha'][::-1]]), 
                y=pd.concat([t_df['Alta'], t_df['Baja'][::-1]]),
                fill='toself', fillcolor='rgba(0,123,255,0.15)', line=dict(color='rgba(255,255,255,0)'), name='Volatilidad'
            ))
            fig_detail.update_layout(template='plotly_white', hovermode='x unified')
            fig_detail.update_xaxes(rangeslider_visible=True)
            st.plotly_chart(fig_detail, width='stretch')
        else:
            st.info('No hay minerales con volatilidad registrada (diferencia entre alta y baja).')

        st.divider()
        with st.spinner('Preparando exportaciones...'):
            xlsx_cot = convert_df_to_excel(df_cot, 'Cotizaciones')
            
            # --- NUEVA LÓGICA DE EXPORTACIÓN A PDF AVANZADA ---
            pdf_elements = []
            
            # Gráfico Global Estático
            if selected_minerals and 'fig_comp' in locals():
                pdf_elements.append({'type': 'title', 'content': 'TENDENCIAS DE PRECIOS GLOBALES'})
                fig_comp_static = go.Figure(fig_comp)
                fig_comp_static.update_xaxes(rangeslider_visible=False) # Plotly en PDF no soporta el slider
                pdf_elements.append({'type': 'chart', 'content': fig_comp_static})
            
            # Gráfico de Volatilidad Estático
            if len(minerales_volatiles) > 0 and 'fig_detail' in locals():
                pdf_elements.append({'type': 'page_break', 'content': ''})
                pdf_elements.append({'type': 'title', 'content': f'ANALISIS DE VOLATILIDAD - {target.upper()}'})
                fig_detail_static = go.Figure(fig_detail)
                fig_detail_static.update_xaxes(rangeslider_visible=False)
                pdf_elements.append({'type': 'chart', 'content': fig_detail_static})
                
            # Tabla de Datos
            pdf_elements.append({'type': 'page_break', 'content': ''})
            pdf_elements.append({'type': 'title', 'content': 'REGISTRO HISTORICO DE PRECIOS'})
            
            df_export = df_cot.copy().sort_values(by='Fecha', ascending=False)
            df_export['Fecha'] = df_export['Fecha'].astype(str) # Forzar formato texto limpio
            pdf_elements.append({'type': 'table', 'content': df_export})
            
            period_str = f"Al {df_cot['Fecha'].max()}" if not df_cot.empty else ""
            pdf_cot = generate_ordered_pdf('COTIZACIONES DE MINERALES', period_str, 'USD', pdf_elements)

        c_exp1, c_exp2, c_exp3 = st.columns([2, 1, 1])
        with c_exp1: st.subheader('📄 Exportación Consolidada')
        with c_exp2: st.download_button('📥 Excel', xlsx_cot, 'cotizaciones.xlsx', width='stretch')
        with c_exp3: st.download_button('📄 PDF Pro', pdf_cot, 'cotizaciones.pdf', width='stretch')
        
        with st.expander('🔍 Datos Crudos', expanded=True):
            st.dataframe(df_cot.sort_values(by='Fecha', ascending=False), width='stretch')
