'''
    Export utilities for Excel and PDF generation.
'''
import io
import os
import tempfile
import pandas as pd
from fpdf import FPDF


class MiningReportPDF(FPDF):
    ''' Custom PDF class with official headers and footers. '''
    def header(self) -> None:
        try:
            self.image('./img/cropped-escudo.png', 10, 8, 20)
        except Exception:
            pass
        self.set_font('Arial', 'B', 11)
        self.set_text_color(44, 62, 80)
        self.cell(0, 5, 'ESTADO PLURINACIONAL DE BOLIVIA', ln=True, align='C')
        self.set_font('Arial', 'B', 9)
        self.cell(0, 5, 'MINISTERIO DE MINERIA Y METALURGIA', ln=True, align='C')
        self.set_font('Arial', '', 8)
        self.cell(0, 5, 'VICEMINISTERIO DE POLITICA MINERA, REGULACION Y FISCALIZACION', ln=True, align='C')
        self.ln(10)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'PAGINA {self.page_no()}', 0, 0, 'C')


def convert_df_to_excel(df: pd.DataFrame, sheet_name: str = 'Reporte') -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def convert_df_to_pdf(df: pd.DataFrame, title: str, currency: str) -> bytes:
    ''' Legacy method for single-table PDF export. '''
    if df.empty: return b""
    pdf = MiningReportPDF(orientation='P')
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f'REPORTE: {title.upper()} ({currency})', ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='ignore')


def _flatten_multiindex(columns) -> list:
    ''' Flattens Pandas MultiIndex columns into readable uppercase string headers. '''
    if isinstance(columns, pd.MultiIndex):
        return [' '.join([str(c).upper() for c in col if str(c).strip()]) for col in columns]
    return [str(c).upper() for c in columns]


def _draw_advanced_table(pdf, df, usable_width, start_y=None):
    ''' Helper function to draw tables with text wrapping and row highlighting '''
    flat_cols = _flatten_multiindex(df.columns)
    clean_cols = [c.replace('Ó', 'O').replace('Á', 'A').replace('Í', 'I').replace('É', 'E').replace('Ú', 'U') for c in flat_cols]

    col_widths = []
    for i, col in enumerate(df.columns):
        data_max = df[col].astype(str).map(len).max() if not df.empty else 5
        col_max = len(clean_cols[i])
        w = max(data_max * 1.5, col_max * 0.8) 
        w = max(w, 10)
        col_widths.append(w)

    total_width = sum(col_widths)
    if total_width > usable_width:
        factor = usable_width / total_width
        col_widths = [w * factor for w in col_widths]

    if start_y: pdf.set_y(start_y)
    header_height = 8
    x = pdf.get_x()
    y = pdf.get_y()
    
    pdf.set_fill_color(26, 43, 76)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 5)

    for i, col in enumerate(clean_cols):
        pdf.set_xy(x, y)
        pdf.rect(x, y, col_widths[i], header_height, 'DF')
        pdf.multi_cell(col_widths[i], 3.5, col, border=0, align='C')
        x += col_widths[i]
    pdf.set_y(y + header_height)

    pdf.set_text_color(0, 0, 0)
    for _, row in df.iterrows():
        if pdf.get_y() > 270:
            pdf.add_page()
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.set_fill_color(26, 43, 76)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font('Arial', 'B', 5)
            for i, col in enumerate(clean_cols):
                pdf.set_xy(x, y)
                pdf.rect(x, y, col_widths[i], header_height, 'DF')
                pdf.multi_cell(col_widths[i], 3.5, col, border=0, align='C')
                x += col_widths[i]
            pdf.set_y(y + header_height)
            pdf.set_text_color(0, 0, 0)

        val0 = str(row.iloc[0]).upper()
        if 'SUBTOTAL' in val0 or 'TOTAL' in val0:
            pdf.set_fill_color(210, 225, 240)
            pdf.set_font('Arial', 'B', 5)
            fill = True
        elif 'GAD' in val0:
            pdf.set_fill_color(255, 240, 200)
            pdf.set_font('Arial', 'B', 5)
            fill = True
        else:
            pdf.set_font('Arial', '', 5)
            fill = False

        x = pdf.get_x()
        y = pdf.get_y()
        row_h = 5
        
        for i, item in enumerate(row):
            pdf.set_xy(x, y)
            val = f"{item:,.2f}" if isinstance(item, (int, float)) else str(item).encode('latin-1', 'replace').decode('latin-1')
            val = val.upper()
            max_chars = max(int(col_widths[i] / 1.0), 2)

            if fill:
                pdf.rect(x, y, col_widths[i], row_h, 'DF')
            else:
                pdf.rect(x, y, col_widths[i], row_h, 'D')

            align = 'R' if isinstance(item, (int, float)) else 'L'
            pdf.cell(col_widths[i], row_h, str(val)[:max_chars], border=0, align=align)
            x += col_widths[i]
        
        pdf.set_y(y + row_h)
    pdf.ln(4)


def generate_ordered_pdf(report_title: str, period_string: str, currency: str, elements: list) -> bytes:
    ''' Generates a Portrait PDF respecting the exact sequence of elements and page breaks. '''
    pdf = MiningReportPDF(orientation='P')
    pdf.add_page()
    usable_width = 190 
    
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, 'BOLETIN INFORMATIVO', ln=True, align='C')
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 6, report_title.upper(), ln=True, align='C')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, period_string.upper(), ln=True, align='C')
    pdf.set_font('Arial', 'I', 9)
    pdf.cell(0, 6, f'(EXPRESADO EN {currency})', ln=True, align='C')
    pdf.ln(6)

    for el in elements:
        etype = el.get('type')
        content = el.get('content')

        if etype == 'page_break':
            pdf.add_page()
            
        elif etype == 'title':
            if pdf.get_y() > 240: pdf.add_page()
            pdf.ln(3)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_fill_color(230, 230, 230)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, f'  {str(content).upper()}', border=1, ln=True, fill=True)
            pdf.ln(3)

        elif etype == 'metrics':
            if not content: continue
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(0, 0, 0)
            w = usable_width / len(content)
            for metric in content:
                pdf.cell(w, 7, str(metric).upper(), border=1, align='C')
            pdf.ln(10)

        elif etype == 'table':
            if content is None or content.empty: continue
            _draw_advanced_table(pdf, content, usable_width)

        elif etype == 'chart':
            if content is None: continue
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    temp_path = tmp_file.name
                # Lienzo más ancho para acomodar la leyenda lateral en la torta
                content.write_image(temp_path, format='png', engine='kaleido', width=1100, height=600, scale=2)
                if pdf.get_y() > 160: pdf.add_page()
                pdf.image(temp_path, x=10, w=190)
                pdf.ln(115) 
                os.remove(temp_path)
            except Exception:
                pass

        elif etype == 'chart_row':
            figs = [f for f in content if f is not None]
            if not figs: continue
            if pdf.get_y() > 190: pdf.add_page()
            
            img_w = usable_width / len(figs)
            start_y = pdf.get_y()
            for i, fig in enumerate(figs):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                        temp_path = tmp_file.name
                        fig.write_image(temp_path, format='png', engine='kaleido', width=700, height=550, scale=2)
                    pdf.image(temp_path, x=10 + (i * img_w), y=start_y, w=img_w - 2)
                    os.remove(temp_path)
                except Exception:
                    pass
            pdf.set_y(start_y + (img_w * 0.8) + 5)

        elif etype == 'table_chart_row':
            table_df = content.get('table')
            chart_fig = content.get('chart')

            if table_df is None or table_df.empty or chart_fig is None:
                continue

            if pdf.get_y() > 180: 
                pdf.add_page()
            
            start_y = pdf.get_y()
            half_width = usable_width / 2.0

            _draw_advanced_table(pdf, table_df, half_width - 2, start_y)
            end_y_table = pdf.get_y()

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                    temp_path = tmp_file.name
                chart_fig.write_image(temp_path, format='png', engine='kaleido', width=600, height=550, scale=2)
                pdf.image(temp_path, x=12 + half_width, y=start_y, w=half_width - 2)
                os.remove(temp_path)
            except Exception:
                pass

            pdf.set_y(max(end_y_table, start_y + half_width * 1.0) + 5)

    return pdf.output(dest='S').encode('latin-1', errors='ignore')
