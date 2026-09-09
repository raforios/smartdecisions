import os
import sys
from markitdown import MarkItDown

# 1. Validar que el usuario pase el archivo por la terminal
if len(sys.argv) < 2:
    print('Error: Debes proporcionar el nombre o la ruta de un archivo PDF.')
    print('Uso: python pdf_to_markdown.py archivo.pdf')
    sys.exit(1)

# 2. Capturar la ruta del PDF ingresada por el usuario
ruta_pdf = sys.argv[1]

# 3. Validar que el archivo realmente exista en la computadora
if not os.path.exists(ruta_pdf):
    print(f'Error: El archivo "{ruta_pdf}" no existe.')
    sys.exit(1)

# 4. Crear la ruta del archivo Markdown en el mismo lugar
# os.path.splitext separa el nombre de la extensión (ej: 'doc.pdf' -> ('doc', '.pdf'))
ruta_base, _ = os.path.splitext(ruta_pdf)
ruta_markdown = ruta_base + '.md'

# 5. Convertir el archivo con MarkItDown
print(f'Convertiendo "{ruta_pdf}" a Markdown...')
try:
    md = MarkItDown()
    resultado = md.convert(ruta_pdf)

    # 6. Guardar el resultado en el archivo .md creado
    with open(ruta_markdown, 'w', encoding = 'utf-8') as archivo:
        archivo.write(resultado.text_content)

    print(f'¡Éxito! Archivo guardado en: {ruta_markdown}')

except Exception as e:
    print(f'Ocurrió un error durante la conversión: {e}')
