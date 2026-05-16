'''
    Official Bulletin Component - Merged with Advanced Analytics
'''
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils.config import UI_COLORS, PALETTE_DEPT, MONTHS_SPANISH
from utils.api_client import upload_royalties_file, fetch_royalties_summary
from utils.exports import convert_df_to_excel, generate_ordered_pdf

def _safe_get(df: pd.DataFrame, new_col: str, possible_keys: list) -> None:
    for key in possible_keys:
        if key in df.columns:
            df[new_col] = pd.to_numeric(df[key], errors='coerce').fillna(0)
            return
    df[new_col] = 0.0

def _highlight_rows(row: pd.Series) -> list:
    val = str(row.iloc[0]).upper()
    if any(keyword in val for keyword in ['TOTAL', 'SUBTOTAL']):
        return [f'background-color: {UI_COLORS["subtotal_bg"]}; font-weight: bold; color: black;'] * len(row)
    if 'GAD' in val:
        return ['background-color: #FFF3CD; font-weight: bold; color: black;'] * len(row)
    return [''] * len(row)

TABLE_STYLES = [
    {'selector': 'th', 'props': [('background-color', UI_COLORS['navy']), ('color', 'white'), ('text-align', 'center'), ('vertical-align', 'middle')]},
    {'selector': 'td', 'props': [('text-align', 'right')]},
    {'selector': 'td:first-child', 'props': [('text-align', 'left')]}
]

HTML_WRAPPER = '<div style="overflow-x: auto; width: 100%; font-size: 0.85em; margin-bottom: 1em;">{}</div>'

def render_boletin_tab(sel_year: int, sel_currency: str, ex_rate: float) -> None:
    
    with st.expander('📥 CARGAR FUENTE DE DATOS CRUDA (XLS / XLSX)', expanded=False):
        file_raw = st.file_uploader('Subir archivo fuente del SIN', type=['xls', 'xlsx'], key='up_raw_bol')
        if file_raw and st.button('🚀 Procesar Transacciones'):
            with st.spinner('Ejecutando ETL Transaccional...'):
                res = upload_royalties_file(file_raw.name, file_raw.getvalue())
                if res and res.status_code == 201:
                    data = res.json()
                    st.success('Datos transaccionales procesados con éxito.')
                    rejected = data.get('rejected_records', [])
                    if rejected:
                        st.warning(f'⚠️ Atención: Se ignoraron {len(rejected)} registros que no coinciden con el padrón oficial.')
                        df_rejected = pd.DataFrame(rejected)
                        csv_data = df_rejected.to_csv(index=False).encode('utf-8')
                        st.download_button(label='⬇️ Descargar Reporte de Errores (CSV)', data=csv_data, file_name=f'errores_municipios_{sel_year}.csv', mime='text/csv', type='primary')
                else:
                    st.error(f'Error ETL: {res.text if res else "Error de conexión."}')

    raw_data = fetch_royalties_summary(sel_year)
    if not raw_data:
        st.info(f'No hay datos transaccionales registrados para la gestión {sel_year}.')
        return

    main_df = pd.DataFrame(raw_data)
    _safe_get(main_df, 'total_bruto_api', ['total_collected_bob', 'total_recaudado_bob'])
    _safe_get(main_df, 'total_neto_api', ['subtotal_bob', 'subtotal'])
    _safe_get(main_df, 'muni_neto_api', ['gov_muni_bob', 'distribucion_muni_bob'])
    _safe_get(main_df, 'dept_neto_api', ['gov_dept_bob', 'distribucion_dept_bob'])
    _safe_get(main_df, 'comision_api', ['commission_bob', 'comision_bob'])

    # NUEVA EXTRACCIÓN SEGURA: Garantizamos que el código oficial siempre sea numérico
    _safe_get(main_df, 'official_code_num', ['official_code', 'codigo_oficial', 'codigo_municipio'])

    # Cuadro 5 debe expresar RECAUDACIÓN BRUTA (`total_collected_bob`) y no
    # la suma distribuida (`subtotal_bob`). Mantenemos el desglose GAD vs
    # Municipio escalando cada parte por el ratio bruto/neto por fila, así
    # GAD + Munis dentro de un departamento totaliza el `total_collected_bob`
    # de ese departamento.
    _ratio = np.where(
        main_df['total_neto_api'] > 0,
        main_df['total_bruto_api'] / main_df['total_neto_api'],
        1.0,
    )
    main_df['muni_bruto_api'] = main_df['muni_neto_api'] * _ratio
    main_df['dept_bruto_api'] = main_df['dept_neto_api'] * _ratio

    factor = 1.0 if sel_currency == 'BOB' else ex_rate
    symbol = 'Bs.' if sel_currency == 'BOB' else '$'

    # LA MATEMÁTICA QUEDA INTACTA. NO SE ALTERA LA BASE DE DATOS CRUDA.
    for col in ['total_bruto', 'total_neto', 'muni_neto', 'dept_neto',
                'comision', 'muni_bruto', 'dept_bruto']:
        main_df[col] = main_df[f'{col}_api'] / factor

    st.divider()
    st.markdown('### 📅 FILTRO DE PERIODO DE ANÁLISIS')
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        start_month = st.selectbox('Mes Inicial', list(MONTHS_SPANISH.keys()), index=0, format_func=lambda x: MONTHS_SPANISH[x].upper())
    with c_m2:
        end_month = st.selectbox('Mes Final', list(MONTHS_SPANISH.keys()), index=11, format_func=lambda x: MONTHS_SPANISH[x].upper())
        
    if start_month > end_month:
        st.warning('El mes inicial no puede ser mayor al final. Ajustando al periodo seleccionado.')
        start_month, end_month = end_month, start_month

    period_str = f'{MONTHS_SPANISH[start_month].upper()} - {MONTHS_SPANISH[end_month].upper()}'
    current_df = main_df[(main_df['year'] == sel_year) & (main_df['month'] >= start_month) & (main_df['month'] <= end_month)].copy()
    previous_df = main_df[(main_df['year'] == (sel_year - 1)) & (main_df['month'] >= start_month) & (main_df['month'] <= end_month)].copy()

    if current_df.empty:
        st.warning(f'No hay registros en la base de datos para el periodo {period_str} de la gestión {sel_year}.')
        return

    st.divider()
    with st.expander('📊 RESUMEN ESTRATÉGICO (KPIs)', expanded=True):
        total_current = current_df['total_bruto'].sum()
        total_previous = previous_df['total_bruto'].sum()
        yoy_growth = ((total_current - total_previous) / total_previous) * 100 if total_previous > 0 else 0.0
        
        mom_df = current_df.groupby('month')['total_bruto'].sum().reset_index().sort_values('month')
        mom_growth = 0.0
        if len(mom_df) >= 2:
            last_m = mom_df.iloc[-1]['total_bruto']
            prev_m = mom_df.iloc[-2]['total_bruto']
            mom_growth = ((last_m - prev_m) / prev_m) * 100 if prev_m > 0 else 0.0

        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
        c_kpi1.metric(f'RECAUDACIÓN TOTAL ({sel_currency})', f'{symbol} {total_current:,.0f}')
        c_kpi2.metric('CRECIMIENTO YOY', f'{yoy_growth:.2f}%', delta=f'{yoy_growth:.1f}%')
        c_kpi3.metric('VARIACIÓN MOM', f'{mom_growth:.2f}%', delta=f'{mom_growth:.1f}%')
        
        st.markdown('<br>', unsafe_allow_html=True)
        c_kpi4, c_kpi5 = st.columns(2)
        c_kpi4.metric('RECAUDACIÓN DISTRIBUIDA (GOBERNACIONES)', f'{symbol} {current_df["dept_neto"].sum():,.0f}')
        c_kpi5.metric('RECAUDACIÓN DISTRIBUIDA (MUNICIPIOS)', f'{symbol} {current_df["muni_neto"].sum():,.0f}')

    st.divider()
    st.markdown(f'## 📑 REPORTE OFICIAL ({sel_currency})')
    
    with st.expander(f'1. RECAUDACIÓN TOTAL DE REGALÍAS MINERAS Y VARIACIONES. {period_str} {sel_year-1} - {sel_year}', expanded=True):
        df_m_act = current_df.groupby('month')[['total_bruto', 'total_neto']].sum().reset_index()
        df_m_pas = previous_df.groupby('month')[['total_bruto', 'total_neto']].sum().reset_index()
        
        df_m_comp = pd.merge(pd.DataFrame({'month': range(start_month, end_month + 1)}), df_m_pas, on='month', how='left').fillna(0)
        df_m_comp = pd.merge(df_m_comp, df_m_act, on='month', how='left', suffixes=('_pas', '_act')).fillna(0)

        df_m_comp['var_bruto'] = df_m_comp['total_bruto_act'] - df_m_comp['total_bruto_pas']
        df_m_comp['var_neto_abs'] = df_m_comp['total_neto_act'] - df_m_comp['total_neto_pas']
        df_m_comp['var_neto_rel'] = np.where(df_m_comp['total_neto_pas'] > 0, (df_m_comp['var_neto_abs'] / df_m_comp['total_neto_pas']) * 100, 0.0)
        df_m_comp['var_neto_mom'] = df_m_comp['total_neto_act'].pct_change().fillna(0) * 100
        df_m_comp['MES'] = df_m_comp['month'].map(MONTHS_SPANISH).str.upper()

        cols_1 = pd.MultiIndex.from_tuples([
            ('', 'MES'),
            ('RECAUDACIÓN TOTAL', f'{sel_year-1}'), ('RECAUDACIÓN TOTAL', f'{sel_year}'), ('RECAUDACIÓN TOTAL', 'VARIACIÓN'),
            ('RECAUDACIÓN DISTRIBUIDA', f'{sel_year-1}'), ('RECAUDACIÓN DISTRIBUIDA', f'{sel_year}'),
            ('VARIACIÓN DISTRIBUIDA', 'ABSOLUTA'), ('VARIACIÓN DISTRIBUIDA', 'RELATIVA'), ('VARIACIÓN DISTRIBUIDA', 'MES ANTERIOR')
        ])

        df_c1 = df_m_comp[['MES', 'total_bruto_pas', 'total_bruto_act', 'var_bruto', 'total_neto_pas', 'total_neto_act', 'var_neto_abs', 'var_neto_rel', 'var_neto_mom']].copy()
        df_c1.columns = cols_1
        
        total_row_c1 = {
            cols_1[0]: 'TOTAL GENERAL',
            cols_1[1]: df_m_comp['total_bruto_pas'].sum(),
            cols_1[2]: df_m_comp['total_bruto_act'].sum(),
            cols_1[3]: df_m_comp['var_bruto'].sum(),
            cols_1[4]: df_m_comp['total_neto_pas'].sum(),
            cols_1[5]: df_m_comp['total_neto_act'].sum(),
            cols_1[6]: df_m_comp['var_neto_abs'].sum(),
            cols_1[7]: ((df_m_comp['var_neto_abs'].sum() / df_m_comp['total_neto_pas'].sum()) * 100) if df_m_comp['total_neto_pas'].sum() > 0 else 0.0,
            cols_1[8]: np.nan
        }
        df_c1.loc[len(df_c1)] = total_row_c1

        format_dict_1 = {col: '{:,.0f}' for col in cols_1[1:7]}
        format_dict_1[cols_1[7]] = '{:,.2f}%'
        format_dict_1[cols_1[8]] = '{:,.2f}%'
        
        html_table_1 = (
            df_c1.style.format(format_dict_1, na_rep='-')
            .set_table_styles(TABLE_STYLES).apply(_highlight_rows, axis=1).hide(axis='index').to_html()
        )
        st.markdown(HTML_WRAPPER.format(html_table_1), unsafe_allow_html=True)

    with st.expander(f'2. REGALÍAS MINERAS DISTRIBUIDAS POR DEPARTAMENTOS EN {sel_currency}', expanded=True):
        df_dept_act = current_df.groupby('department')['total_bruto'].sum().reset_index()
        c_g1, c_g2 = st.columns([2.5, 1])
        with c_g1:
            fig_bar_act = px.bar(df_dept_act.sort_values('total_bruto', ascending=False), x='department', y='total_bruto', color_discrete_sequence=[UI_COLORS['navy']])
            fig_bar_act.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
            fig_bar_act.update_layout(height=450, margin=dict(l=20, r=20, t=20, b=100), xaxis=dict(title=None, tickangle=-45, automargin=True), yaxis_title=f'Monto Bruto ({sel_currency})')
            st.plotly_chart(fig_bar_act, width='content')
        with c_g2:
            fig_pie_act = px.pie(df_dept_act[df_dept_act['total_bruto'] > 0], values='total_bruto', names='department', color_discrete_sequence=PALETTE_DEPT)
            
            fig_pie_act.update_traces(textposition='inside', textinfo='percent')
            fig_pie_act.update_layout(
                height=450, 
                margin=dict(l=10, r=10, t=10, b=100),
                showlegend=True,
                legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_pie_act, width='content')

    with st.expander(f'3. RECAUDACIÓN DE REGALÍAS POR DEPARTAMENTO. {period_str} {sel_year-1} - {sel_year}', expanded=True):
        df_d_act = current_df.groupby('department')[['total_bruto', 'total_neto']].sum().reset_index()
        df_d_pas = previous_df.groupby('department')[['total_bruto', 'total_neto']].sum().reset_index()
        df_d_comp = pd.merge(df_d_pas, df_d_act, on='department', how='outer', suffixes=('_pas', '_act')).fillna(0).sort_values(by='total_bruto_act', ascending=False)
        df_d_comp['var_bruto'] = df_d_comp['total_bruto_act'] - df_d_comp['total_bruto_pas']
        df_d_comp['var_neto_abs'] = df_d_comp['total_neto_act'] - df_d_comp['total_neto_pas']
        df_d_comp['var_neto_rel'] = np.where(df_d_comp['total_neto_pas'] > 0, (df_d_comp['var_neto_abs'] / df_d_comp['total_neto_pas']) * 100, 0.0)

        col_dept = pd.MultiIndex.from_tuples([('', 'DEPARTAMENTO'), ('RECAUDACIÓN TOTAL', f'{sel_year-1}'), ('RECAUDACIÓN TOTAL', f'{sel_year}'), ('', 'VARIACIÓN ABSOLUTA'), ('RECAUDACIÓN DISTRIBUIDA', f'{sel_year-1}'), ('RECAUDACIÓN DISTRIBUIDA', f'{sel_year}'), ('VARIACIÓN', 'ABSOLUTA'), ('VARIACIÓN', 'RELATIVA')])
        
        df_c3 = df_d_comp[['department', 'total_bruto_pas', 'total_bruto_act', 'var_bruto', 'total_neto_pas', 'total_neto_act', 'var_neto_abs', 'var_neto_rel']].copy()
        df_c3.columns = col_dept
        
        total_row_c3 = {
            col_dept[0]: 'TOTAL GENERAL',
            col_dept[1]: df_d_comp['total_bruto_pas'].sum(),
            col_dept[2]: df_d_comp['total_bruto_act'].sum(),
            col_dept[3]: df_d_comp['var_bruto'].sum(),
            col_dept[4]: df_d_comp['total_neto_pas'].sum(),
            col_dept[5]: df_d_comp['total_neto_act'].sum(),
            col_dept[6]: df_d_comp['var_neto_abs'].sum(),
            col_dept[7]: ((df_d_comp['var_neto_abs'].sum() / df_d_comp['total_neto_pas'].sum()) * 100) if df_d_comp['total_neto_pas'].sum() > 0 else 0.0
        }
        df_c3.loc[len(df_c3)] = total_row_c3

        format_dict_3 = {col: '{:,.0f}' for col in col_dept[1:7]}
        format_dict_3[col_dept[7]] = '{:,.2f}%'

        html_table_3 = (
            df_c3.style.format(format_dict_3)
            .set_table_styles(TABLE_STYLES).apply(_highlight_rows, axis=1).hide(axis='index').to_html()
        )
        st.markdown(HTML_WRAPPER.format(html_table_3), unsafe_allow_html=True)

    with st.expander(f'4. MUNICIPIOS CON MAYOR RECAUDACIÓN (TOP 20). {period_str} {sel_year}', expanded=True):
        df_muni_top = current_df.groupby('municipality')['muni_neto'].sum().reset_index().sort_values('muni_neto', ascending=False)
        top_19 = df_muni_top.head(19).copy()
        resto_val = df_muni_top.iloc[19:]['muni_neto'].sum() if len(df_muni_top) > 19 else 0
        if resto_val > 0: top_19.loc[len(top_19)] = ['Resto', resto_val]
        top_19.insert(0, 'Nro.', range(1, len(top_19) + 1))
        top_19.rename(columns={'municipality': 'MUNICIPIO', 'muni_neto': 'MONTO RECAUDADO'}, inplace=True)

        c_t4, c_g4 = st.columns([1, 1.5])
        with c_t4:
            html_table_4 = (
                top_19.style.format({'MONTO RECAUDADO': '{:,.0f}'})
                .set_table_styles(TABLE_STYLES).apply(_highlight_rows, axis=1).hide(axis='index').to_html()
            )
            st.markdown(HTML_WRAPPER.format(html_table_4), unsafe_allow_html=True)
        with c_g4:
            df_chart_muni = top_19.copy()
            df_chart_muni['MONTO_MILLONES'] = df_chart_muni['MONTO RECAUDADO'] / 1_000_000
            
            fig_hist = px.bar(df_chart_muni.sort_values('MONTO_MILLONES', ascending=True), x='MONTO_MILLONES', y='MUNICIPIO', orientation='h', color_discrete_sequence=[UI_COLORS['blue_light']])
            
            fig_hist.update_traces(texttemplate='%{x:,.1f} M', textposition='outside', cliponaxis=False)
            fig_hist.update_layout(
                height=500, 
                margin=dict(l=150, r=100, t=10, b=50), 
                yaxis=dict(title=None, tickmode='linear', dtick=1, automargin=True), 
                xaxis=dict(title=f'Monto (Millones de {sel_currency})')
            )
            st.plotly_chart(fig_hist, width='content')

    with st.expander(f'5. RECAUDACIÓN POR DEPARTAMENTOS Y MUNICIPIOS. {period_str} {sel_year} (TRIMESTRE MÓVIL)', expanded=True):
        search_c5 = st.text_input('🔍 Buscar Municipio o Departamento:', placeholder='Ej. Huanuni', key='search_c5')

        min_month = current_df['month'].min()
        max_month = current_df['month'].max()
        min_q = (min_month - 1) // 3 + 1
        max_q = (max_month - 1) // 3 + 1
        
        col_order = ['DEPTOS/MUNICIPIOS']
        for q in range(min_q, max_q): col_order.append(f'TRIMESTRE {q}')
        
        months_in_max_q = [m for m in range((max_q-1)*3 + 1, max_q*3 + 1) if m <= max_month and m >= start_month]
        for m in months_in_max_q: col_order.append(MONTHS_SPANISH[m].upper())
        
        col_order.append(f'TOTAL TRIMESTRE {max_q}')
        col_order.append(f'TOTAL {period_str}')
        
        final_rows = []
        
        DEPT_ORDER = {
            'CHUQUISACA': 1, 'LA PAZ': 2, 'COCHABAMBA': 3, 
            'ORURO': 4, 'POTOSI': 5, 'POTOSÍ': 5, 'TARIJA': 6, 
            'SANTA CRUZ': 7, 'BENI': 8, 'PANDO': 9
        }
        sorted_depts = sorted(current_df['department'].unique(), key=lambda x: DEPT_ORDER.get(str(x).upper().strip(), 99))
        
        for dept in sorted_depts:
            dept_df = current_df[current_df['department'] == dept]
            dept_rows = []
            
            gad_row = {'DEPTOS/MUNICIPIOS': f'GAD {dept}'}
            total_gad = 0
            for q in range(min_q, max_q):
                val = dept_df[dept_df['month'].apply(lambda x: (x-1)//3+1) == q]['dept_bruto'].sum()
                gad_row[f'TRIMESTRE {q}'] = val; total_gad += val

            q_max_total = 0
            for m in months_in_max_q:
                val = dept_df[dept_df['month'] == m]['dept_bruto'].sum()
                gad_row[MONTHS_SPANISH[m].upper()] = val; q_max_total += val; total_gad += val
            
            gad_row[f'TOTAL TRIMESTRE {max_q}'] = q_max_total
            gad_row[f'TOTAL {period_str}'] = total_gad
            dept_rows.append(gad_row)
            
            # --- CORRECCIÓN DEFINITIVA DE ORDENAMIENTO POR OFFICIAL CODE ---
            muni_sort_df = dept_df[['municipality', 'official_code_num']].drop_duplicates(subset=['municipality']).copy()
            # Si un municipio no tiene código o es 0, lo enviamos al final asignándole un código alto
            muni_sort_df['official_code_num'] = muni_sort_df['official_code_num'].replace(0.0, 999999)
            # Ordenamos ascendentemente de forma estricta basada en el valor numérico
            sorted_munis = muni_sort_df.sort_values('official_code_num')['municipality'].tolist()

            for muni in sorted_munis:
                muni_df = dept_df[dept_df['municipality'] == muni]
                muni_row = {'DEPTOS/MUNICIPIOS': muni}
                total_muni = 0
                for q in range(min_q, max_q):
                    val = muni_df[muni_df['month'].apply(lambda x: (x-1)//3+1) == q]['muni_bruto'].sum()
                    muni_row[f'TRIMESTRE {q}'] = val; total_muni += val

                q_max_total = 0
                for m in months_in_max_q:
                    val = muni_df[muni_df['month'] == m]['muni_bruto'].sum()
                    muni_row[MONTHS_SPANISH[m].upper()] = val; q_max_total += val; total_muni += val
                    
                muni_row[f'TOTAL TRIMESTRE {max_q}'] = q_max_total
                muni_row[f'TOTAL {period_str}'] = total_muni
                dept_rows.append(muni_row)
                
            sub_row = {'DEPTOS/MUNICIPIOS': f'SUBTOTAL {dept}'}
            for col in col_order[1:]:
                sub_row[col] = sum(r[col] for r in dept_rows)
            dept_rows.append(sub_row)
            final_rows.extend(dept_rows)
            
        df_c5 = pd.DataFrame(final_rows)
        
        if search_c5:
            mask = df_c5['DEPTOS/MUNICIPIOS'].str.contains(search_c5, case=False) | df_c5['DEPTOS/MUNICIPIOS'].str.contains('GAD|SUBTOTAL|TOTAL')
            df_c5 = df_c5[mask]

        total_general = {'DEPTOS/MUNICIPIOS': 'TOTAL GENERAL'}
        for col in col_order[1:]:
            total_general[col] = df_c5[df_c5['DEPTOS/MUNICIPIOS'].str.contains('SUBTOTAL')][col].sum()
        df_c5.loc[len(df_c5)] = total_general

        html_table_5 = (
            df_c5.style.format({col: '{:,.0f}' for col in col_order[1:]})
            .set_table_styles(TABLE_STYLES).apply(_highlight_rows, axis=1).hide(axis='index').to_html()
        )
        st.markdown(HTML_WRAPPER.format(html_table_5), unsafe_allow_html=True)

    with st.expander(f'📈 PROYECCIÓN HISTÓRICA ({period_str})', expanded=True):
        raw_hist = fetch_royalties_summary(None)
        if raw_hist:
            df_hist = pd.DataFrame(raw_hist)
            _safe_get(df_hist, 'total_bruto_hist', ['total_collected_bob', 'total_recaudado_bob'])
            
            df_h = df_hist[(df_hist['year'] >= 2013) & (df_hist['month'] >= start_month) & (df_hist['month'] <= end_month)].copy()
            df_h['valor_calc'] = df_h['total_bruto_hist'] / factor
            df_h_global = df_h.groupby('year')['valor_calc'].sum().reset_index()
            
            if len(df_h_global) > 0:
                max_year = df_h_global['year'].max()
                
                if len(df_h_global) >= 2:
                    next_year = int(max_year) + 1
                    z = np.polyfit(df_h_global['year'], df_h_global['valor_calc'], 1)
                    p = np.poly1d(z)
                    predicted_val = p(next_year)
                    
                    df_pred = pd.DataFrame({'year': [next_year], 'valor_calc': [predicted_val], 'Tipo': ['Proyectado']})
                    df_h_global['Tipo'] = 'Histórico Real'
                    df_combined = pd.concat([df_h_global, df_pred], ignore_index=True)
                else:
                    df_h_global['Tipo'] = 'Histórico Real'
                    df_combined = df_h_global

                df_combined['valor_millones'] = df_combined['valor_calc'] / 1_000_000

                h1, h2 = st.columns([2, 1])
                with h1:
                    fig_pred = px.bar(
                        df_combined, x='year', y='valor_millones', color='Tipo',
                        color_discrete_map={'Histórico Real': UI_COLORS['navy'], 'Proyectado': UI_COLORS['gold']}
                    )
                    
                    fig_pred.update_traces(texttemplate='%{y:,.0f} M', textposition='outside', cliponaxis=False)
                    fig_pred.update_layout(
                        xaxis_type='category', 
                        height=350, 
                        yaxis_title=f'Millones de {sel_currency}', 
                        xaxis_title=None, 
                        margin=dict(t=50) 
                    )
                    st.plotly_chart(fig_pred, width='content')
                
                with h2:
                    if len(df_h_global) >= 2:
                        st.info('**MODELO PREDICTIVO:** Regresión Lineal (Mínimos Cuadrados) con Estacionalidad.')
                        st.write(f'Basado en la tendencia histórica específica del periodo **{period_str}**, el algoritmo proyecta una recaudación de **{symbol} {predicted_val:,.0f}** para esos mismos meses durante la gestión **{next_year}**.')
                    else:
                        st.warning('Datos históricos insuficientes (se requieren al menos 2 años) para generar la proyección matemática al próximo periodo.')
        else:
            st.info('No hay datos históricos cargados para visualizar esta sección.')

    st.divider()
    st.markdown('### 📥 EXPORTACIÓN DE DATOS')
    
    # Secuencia ordenada con saltos de página definidos
    report_elements = [
        {'type': 'title', 'content': 'RESUMEN ESTRATÉGICO (KPIs)'},
        {'type': 'metrics', 'content': [
            f'RECAUDACIÓN TOTAL: {symbol} {total_current:,.0f}',
            f'GOBERNACIONES: {symbol} {current_df["dept_neto"].sum():,.0f}',
            f'MUNICIPIOS: {symbol} {current_df["muni_neto"].sum():,.0f}'
        ]},
        {'type': 'title', 'content': f'1. RECAUDACIÓN TOTAL Y VARIACIONES. {period_str}'},
        {'type': 'table', 'content': df_c1 if 'df_c1' in locals() else None},
        
        {'type': 'page_break'},
        
        {'type': 'title', 'content': '2. REGALÍAS DISTRIBUIDAS POR DEPARTAMENTOS'},
        {'type': 'chart_row', 'content': [
            fig_bar_act if 'fig_bar_act' in locals() else None,
            fig_pie_act if 'fig_pie_act' in locals() else None
        ]},
        {'type': 'title', 'content': f'3. RECAUDACIÓN POR DEPARTAMENTO. {period_str}'},
        {'type': 'table', 'content': df_c3 if 'df_c3' in locals() else None},
        
        {'type': 'page_break'},
        
        {'type': 'title', 'content': '4. MUNICIPIOS CON MAYOR RECAUDACIÓN (TOP 20)'},
        {'type': 'table_chart_row', 'content': {
            'table': top_19 if 'top_19' in locals() else None, 
            'chart': fig_hist if 'fig_hist' in locals() else None
        }},
        
        {'type': 'page_break'},
        
        {'type': 'title', 'content': f'5. RECAUDACIÓN POR DEPTOS. Y MUNICIPIOS (TRIM. MÓVIL)'},
        {'type': 'table', 'content': df_c5 if 'df_c5' in locals() else None},
        {'type': 'title', 'content': 'PROYECCIÓN HISTÓRICA'},
        {'type': 'chart', 'content': fig_pred if 'fig_pred' in locals() else None}
    ]

    export_df = df_c5 if not current_df.empty else pd.DataFrame()
    
    # Nuevo layout de columnas para mantener armonía visual
    c_exp1, c_exp2, c_space = st.columns([1.2, 1.2, 2.6])
    
    with c_exp1:
        st.download_button(
            label='📊 Exportar Excel', 
            data=convert_df_to_excel(export_df, 'Boletin_Minero'), 
            file_name=f'Boletin_{sel_year}.xlsx', 
            width='content'
        )
    with c_exp2:
        pdf_bytes = generate_ordered_pdf(
            report_title='REGALÍAS MINERAS RECAUDADAS POR DEPARTAMENTOS Y MUNICIPIOS',
            period_string=f'{period_str} DE {sel_year}',
            currency=sel_currency,
            elements=report_elements
        )
        st.download_button(
            label='📄 Reporte PDF', 
            data=pdf_bytes, 
            file_name=f'Boletin_{sel_year}.pdf', 
            width='content'
        )
