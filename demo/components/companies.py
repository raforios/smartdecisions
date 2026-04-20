''' Companies Tab (Tab 4) '''
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.config import UI_COLORS
from utils.api_client import fetch_companies_transactions
from utils.exports import convert_df_to_excel, generate_ordered_pdf

TABLE_STYLES = [
    {'selector': 'th', 'props': [('background-color', UI_COLORS.get('navy', '#1A2A3A')), ('color', 'white'), ('text-align', 'center'), ('vertical-align', 'middle')]},
    {'selector': 'td', 'props': [('text-align', 'right')]},
    {'selector': 'td:first-child', 'props': [('text-align', 'left')]}
]

HTML_WRAPPER = '<div style="overflow-x: auto; width: 100%; font-size: 0.85em; margin-bottom: 1em;">{}</div>'

def render_companies_tab(sel_year):
    st.markdown('### 🏢 Empresas Mineras (Transacciones)')
    data = fetch_companies_transactions(sel_year)
    
    if not data:
        st.info(f'No se encontraron transacciones para {sel_year}.')
        return

    df = pd.DataFrame(data)
    if 'amount_paid_bob' not in df.columns or 'company_name' not in df.columns:
        st.error("Los datos de la API no tienen el formato esperado.")
        return

    summary_df = df.groupby(['company_name'])['amount_paid_bob'].sum().reset_index()
    summary_df = summary_df.sort_values(by='amount_paid_bob', ascending=False)
    
    total_recaudado = summary_df['amount_paid_bob'].sum()

    top_20 = summary_df.head(19).copy()
    resto_val = summary_df.iloc[19:]['amount_paid_bob'].sum() if len(summary_df) > 19 else 0
    if resto_val > 0:
        top_20.loc[len(top_20)] = ['Resto', resto_val]

    top_20['participacion'] = (top_20['amount_paid_bob'] / total_recaudado) * 100

    top_20.rename(columns={
        'company_name': 'EMPRESA',
        'amount_paid_bob': 'MONTO RECAUDADO (Bs.)',
        'participacion': '% PARTICIPACIÓN'
    }, inplace=True)
    top_20.insert(0, 'NRO.', range(1, len(top_20) + 1))

    corp_palette = [
        UI_COLORS.get('navy', '#1A2A3A'), UI_COLORS.get('gold', '#C9A751'),
        UI_COLORS.get('blue_light', '#4A6984'), UI_COLORS.get('gold_light', '#E3C77A'),
        UI_COLORS.get('green', '#2E4034'), UI_COLORS.get('red', '#8B0000'),
        UI_COLORS.get('dark', '#363534'), UI_COLORS.get('gray', '#E5E7E9')
    ]

    # --- HISTOGRAMA A PRUEBA DE CORTES ---
    st.markdown('#### RECAUDACIÓN TOP 20 EMPRESAS')
    
    # TRUCO: Calculamos el valor máximo y le sumamos 30% de espacio extra
    max_val = top_20['MONTO RECAUDADO (Bs.)'].max()
    rango_maximo = max_val * 1.30 

    fig_bar = px.bar(
        top_20.sort_values(by='MONTO RECAUDADO (Bs.)', ascending=True),
        x='MONTO RECAUDADO (Bs.)', y='EMPRESA', orientation='h',
        color_discrete_sequence=[UI_COLORS.get('navy', '#1A2A3A')]
    )
    fig_bar.update_traces(texttemplate='%{x:,.0f}', textposition='outside')
    fig_bar.update_layout(
        height=650, 
        margin=dict(l=350, r=20, t=20, b=20), # 350px de espacio INTOCABLE para los nombres
        xaxis=dict(title=None, range=[0, rango_maximo]), # Fuerzo a que la barra acabe antes para que entre el número
        yaxis=dict(title=None)
    )
    st.plotly_chart(fig_bar, width='content')
    
    st.divider()
        
    # --- TORTA ESPACIOSA ---
    st.markdown('#### PARTICIPACIÓN PORCENTUAL')
    fig_pie = px.pie(
        top_20, values='MONTO RECAUDADO (Bs.)', names='EMPRESA',
        color_discrete_sequence=corp_palette
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent')
    fig_pie.update_layout(
        height=750, 
        margin=dict(l=20, r=20, t=20, b=250), # 250px abajo para la leyenda
        showlegend=True, 
        legend=dict(
            orientation="h", 
            yanchor="top", 
            y=-0.1, 
            xanchor="center", 
            x=0.5, 
            font=dict(size=11)
        )
    )
    st.plotly_chart(fig_pie, width='content')

    st.divider()

    st.markdown('#### DETALLE DE RECAUDACIÓN')
    styled_table = (
        top_20.style.format({
            'MONTO RECAUDADO (Bs.)': '{:,.2f}',
            '% PARTICIPACIÓN': '{:,.2f}%'
        })
        .set_table_styles(TABLE_STYLES)
        .hide(axis='index')
        .to_html()
    )
    st.markdown(HTML_WRAPPER.format(styled_table), unsafe_allow_html=True)

    st.divider()
    st.markdown('### 📥 EXPORTACIÓN DE DATOS')

    report_elements = [
        {'type': 'title', 'content': f'RECAUDACIÓN TOP 20 EMPRESAS MINERAS'},
        {'type': 'chart', 'content': fig_bar},
        {'type': 'page_break'},
        {'type': 'title', 'content': f'PARTICIPACIÓN PORCENTUAL TOP 20'},
        {'type': 'chart', 'content': fig_pie},
        {'type': 'page_break'},
        {'type': 'title', 'content': 'DETALLE DE RECAUDACIÓN POR EMPRESA'},
        {'type': 'table', 'content': top_20}
    ]

    c_exp1, c_exp2, c_space = st.columns([1.2, 1.2, 2.6])
    
    with c_exp1:
        st.download_button(
            label='📊 Exportar Excel', 
            data=convert_df_to_excel(top_20, 'Empresas'), 
            file_name=f'Empresas_{sel_year}.xlsx', 
            width='content'
        )
    with c_exp2:
        pdf_bytes = generate_ordered_pdf(
            report_title='REPORTE DE RECAUDACIÓN POR EMPRESAS MINERAS',
            period_string=f'GESTIÓN {sel_year}',
            currency='BOB',
            elements=report_elements
        )
        st.download_button(
            label='📄 Reporte PDF', 
            data=pdf_bytes, 
            file_name=f'Empresas_{sel_year}.pdf', 
            width='content'
        )
