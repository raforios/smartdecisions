''' Cotizaciones Tab '''
import calendar
import os
from datetime import date
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.api_client import (
    upload_mining_prices,
    fetch_mineral_prices,
)
# IMPORTANTE: Importamos generate_ordered_pdf en lugar del legacy convert_df_to_pdf
from utils.exports import convert_df_to_excel, generate_ordered_pdf
from utils.mineral_reports import (
    render_daily_report_png,
    render_biweekly_report_png,
    png_to_pdf,
    thumbnail_png,
)

DAILY_TEMPLATE_PATH = os.path.join('img', 'Minerales_01.png')
BIWEEKLY_TEMPLATE_PATH = os.path.join('img', 'Minerales_02.png')
MONTH_NAMES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre',
    11: 'Noviembre', 12: 'Diciembre',
}

# Canonical order mirroring the printed template — guarantees row alignment
# regardless of what the catalog returns.
OFFICIAL_MINERAL_ORDER = (
    'Estaño', 'Plomo', 'Zinc', 'Cobre',
    'Antimonio', 'Wolfram', 'Bismuto', 'Oro', 'Plata',
)


def _build_daily_rows(prices_df: pd.DataFrame, ref_date: date) -> list:
    '''
    Computes the latest cotización per official mineral up to ref_date.
    Falls back to the most recent prior row when ref_date itself has no data.
    '''
    rows = []
    df = prices_df[prices_df['Fecha'] <= ref_date].copy()
    for mineral in OFFICIAL_MINERAL_ORDER:
        m_df = df[df['Mineral'].str.lower() == mineral.lower()]
        if m_df.empty:
            rows.append({
                'mineral': mineral, 'price_low': 0.0, 'price_high': 0.0,
                'price_date': ref_date, 'is_fallback': True,
            })
            continue
        last = m_df.sort_values('Fecha').iloc[-1]
        rows.append({
            'mineral': mineral,
            'price_low': float(last['Baja']),
            'price_high': float(last['Alta']),
            'price_date': last['Fecha'],
            'is_fallback': last['Fecha'] != ref_date,
        })
    return rows


def _build_biweekly_rows(prices_df: pd.DataFrame, year: int, month: int, half: int) -> list:
    '''
    Computes the simple mean of price_low (Baja) per mineral within the
    requested half of the month. Falls back to the most recent prior biweekly
    period that has data when the current period is empty.
    '''
    def bounds(y, m, h):
        if h == 1:
            return date(y, m, 1), date(y, m, 15)
        return date(y, m, 16), date(y, m, calendar.monthrange(y, m)[1])

    def prev_period(y, m, h):
        if h == 2: return y, m, 1
        if m == 1: return y - 1, 12, 2
        return y, m - 1, 2

    rows = []
    for mineral in OFFICIAL_MINERAL_ORDER:
        m_df = prices_df[prices_df['Mineral'].str.lower() == mineral.lower()]
        cur_y, cur_m, cur_h = year, month, half
        period_start, period_end = bounds(cur_y, cur_m, cur_h)
        is_fallback = False
        avg_low, sample = 0.0, 0
        if not m_df.empty:
            mask = (m_df['Fecha'] >= period_start) & (m_df['Fecha'] <= period_end)
            window = m_df[mask]
            if not window.empty:
                avg_low = float(window['Baja'].mean())
                sample = int(window['Fecha'].nunique())
            else:
                is_fallback = True
                for _ in range(24):
                    cur_y, cur_m, cur_h = prev_period(cur_y, cur_m, cur_h)
                    fb_s, fb_e = bounds(cur_y, cur_m, cur_h)
                    mask = (m_df['Fecha'] >= fb_s) & (m_df['Fecha'] <= fb_e)
                    window = m_df[mask]
                    if not window.empty:
                        avg_low = float(window['Baja'].mean())
                        sample = int(window['Fecha'].nunique())
                        period_start, period_end = fb_s, fb_e
                        break
        else:
            is_fallback = True
        rows.append({
            'mineral': mineral, 'avg_price_low': avg_low, 'sample_size': sample,
            'period_start': period_start, 'period_end': period_end,
            'is_fallback': is_fallback,
        })
    return rows


def _render_official_reports_section(prices_df: pd.DataFrame):
    '''
    Renders both official mineral reports (Minerales_01 daily and Minerales_02
    biweekly) at the top of the Cotizaciones tab, with PNG/PDF downloads.

    Computes report data client-side from `prices_df` so the section works
    even if the new backend endpoints are not yet deployed.
    '''
    st.subheader('🪪 Cotización Oficial de Minerales')

    if prices_df.empty:
        st.info('No hay cotizaciones cargadas para generar los reportes.')
        st.divider()
        return

    default_ref = prices_df['Fecha'].max()
    rep_col_left, rep_col_right = st.columns(2)

    with rep_col_left:
        st.markdown('**📋 Diario interno — Minerales_01**')
        ref_date = st.date_input(
            'Fecha de referencia',
            value=default_ref,
            key='daily_ref_date',
        )
        daily_rows = _build_daily_rows(prices_df, ref_date)
        daily_subtitle = f'Diario al {ref_date.strftime("%d/%m/%Y")}'
        daily_png = render_daily_report_png(
            daily_rows, DAILY_TEMPLATE_PATH, subtitle=daily_subtitle,
        )
        st.image(thumbnail_png(daily_png), caption=daily_subtitle)
        dl_a, dl_b = st.columns(2)
        with dl_a:
            st.download_button(
                '📥 Descargar PNG',
                daily_png,
                file_name=f'cotizacion_diaria_{ref_date}.png',
                mime='image/png',
                key='dl_daily_png',
                width='stretch',
            )
        with dl_b:
            st.download_button(
                '📄 Descargar PDF',
                png_to_pdf(daily_png),
                file_name=f'cotizacion_diaria_{ref_date}.pdf',
                mime='application/pdf',
                key='dl_daily_pdf',
                width='stretch',
            )

    with rep_col_right:
        st.markdown('**🏛️ Oficial quincenal — Minerales_02**')
        col_y, col_m, col_h = st.columns(3)
        with col_y:
            bw_year = st.number_input(
                'Año', min_value=2012, max_value=2100,
                value=default_ref.year, step=1, key='bw_year',
            )
        with col_m:
            bw_month = st.selectbox(
                'Mes', list(range(1, 13)),
                format_func=lambda m: MONTH_NAMES_ES[m],
                index=default_ref.month - 1, key='bw_month',
            )
        with col_h:
            bw_half = st.selectbox(
                'Quincena', [1, 2],
                format_func=lambda h: '1-15' if h == 1 else '16-fin',
                key='bw_half',
            )
        biweekly_rows = _build_biweekly_rows(
            prices_df, int(bw_year), int(bw_month), int(bw_half),
        )
        period_label = (f'{MONTH_NAMES_ES[int(bw_month)]} {int(bw_year)} '
                        f'(Q{int(bw_half)})')
        biweekly_subtitle = f'Oficial quincenal — {period_label}'
        bw_png = render_biweekly_report_png(
            biweekly_rows, BIWEEKLY_TEMPLATE_PATH, subtitle=biweekly_subtitle,
        )
        st.image(thumbnail_png(bw_png), caption=biweekly_subtitle)
        dl_a, dl_b = st.columns(2)
        with dl_a:
            st.download_button(
                '📥 Descargar PNG',
                bw_png,
                file_name=f'cotizacion_quincenal_{bw_year}-{int(bw_month):02d}_Q{bw_half}.png',
                mime='image/png',
                key='dl_bw_png',
                width='stretch',
            )
        with dl_b:
            st.download_button(
                '📄 Descargar PDF',
                png_to_pdf(bw_png),
                file_name=f'cotizacion_quincenal_{bw_year}-{int(bw_month):02d}_Q{bw_half}.pdf',
                mime='application/pdf',
                key='dl_bw_pdf',
                width='stretch',
            )

    st.divider()


def render_cotizaciones_tab():
    # Reports section needs the raw price catalog; fetch once and share with KPIs below.
    raw_prices = fetch_mineral_prices()
    prices_df = pd.DataFrame()
    if raw_prices:
        prices_df = pd.DataFrame([{
            'Fecha': pd.to_datetime(item['date']).date(),
            'Mineral': item['mineral']['name'],
            'Símbolo': item['mineral'].get('chemical_symbol') or '-',
            'Mercado': item['mineral'].get('quoted_in') or '-',
            'Unidad': item['mineral']['unit'],
            'Baja': float(item['price_low']),
            'Alta': float(item['price_high']) if item['price_high'] is not None
                    else float(item['price_low']),
        } for item in raw_prices]).sort_values('Fecha')

    _render_official_reports_section(prices_df)

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

    if not prices_df.empty:
        df_cot = prices_df

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
                    unidad = m_data.iloc[-1]['Unidad']

                    kpi_cols[j].metric(
                        label=f'{m_name} ({simbolo}) · {unidad}',
                        value=f'${last_price:,.4f}',
                        delta=f'{diff:.2f}%',
                        help=f'Cotización por {unidad} — Mercado: {m_data.iloc[-1]["Mercado"]}',
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
