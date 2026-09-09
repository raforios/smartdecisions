# Guía de instalación y uso — Scraper de Notibol (Windows 10)

Esta guía es para instalar y usar el programa que descarga las noticias de
**Notibol** de una fecha y las guarda en un archivo **Excel**. Está pensada para
Windows 10 Pro (22H2) y **no requiere conocimientos técnicos**: seguí los pasos
en orden.

Al final vas a poder ejecutar un comando y obtener un Excel con las columnas:
**Fecha · Medio · Titular · Enlace**.

En el Excel: la columna **Medio** dice qué medio publicó la nota; el **Titular**
es clickeable y abre la noticia en la página de Notibol; el **Enlace** lleva a la
nota original en el medio que la publicó (por ejemplo El Deber, Los Tiempos, ANF).

---

## Qué vas a recibir

Una carpeta (por ejemplo `notibol`) con estos dos archivos:

- `notibol_scraper.py` — el programa.
- `requirements_notibol.txt` — la lista de componentes que necesita.

Guardá esa carpeta en un lugar fácil de encontrar, por ejemplo el **Escritorio**:
`C:\Users\TU_USUARIO\Desktop\notibol`

---

## Paso 1 — Instalar Python (una sola vez)

1. Entrá a **https://www.python.org/downloads/windows/**
2. Descargá el instalador **"Windows installer (64-bit)"** de la última versión
   estable (por ejemplo Python 3.12).
3. Ejecutá el instalador descargado.
4. **MUY IMPORTANTE:** en la primera pantalla marcá la casilla
   ✅ **"Add python.exe to PATH"** (abajo de todo), y recién ahí hacé clic en
   **"Install Now"**.
5. Esperá a que termine y hacé clic en **"Close"**.

> Si te salteás la casilla "Add python.exe to PATH", los comandos de más abajo no
> van a funcionar. En ese caso, desinstalá Python desde "Agregar o quitar
> programas" y volvé a instalarlo marcando la casilla.

---

## Paso 2 — Abrir la carpeta en la terminal (PowerShell)

1. Abrí el **Explorador de archivos** y entrá a la carpeta `notibol`
   (donde están los dos archivos).
2. Hacé clic en la **barra de dirección** (arriba, donde dice la ruta), escribí
   `powershell` y presioná **Enter**.
3. Se abre una ventana negra/azul (PowerShell) **ya ubicada en esa carpeta**.

> Alternativa: mantené presionada la tecla **Shift**, hacé clic derecho dentro
> de la carpeta y elegí **"Abrir la ventana de PowerShell aquí"**.

---

## Paso 3 — Instalar los componentes (una sola vez)

En la ventana de PowerShell, escribí este comando y presioná **Enter**:

```powershell
pip install -r requirements_notibol.txt
```

Vas a ver que descarga e instala tres componentes. Cuando termine y vuelva a
aparecer el cursor, ya está listo.

> Si aparece un error que dice que `pip` no se reconoce, cerrá PowerShell,
> reiniciá la computadora y volvé al Paso 2 (esto pasa cuando Windows todavía no
> "tomó" la instalación de Python).

---

## Paso 4 — Ejecutar el programa

Siempre desde la ventana de PowerShell abierta en la carpeta `notibol`.

**Descargar las noticias de una fecha** (reemplazá la fecha por la que quieras,
en formato **año-mes-día**):

```powershell
python notibol_scraper.py --fecha 2026-08-04
```

Vas a ver el avance página por página, luego un mensaje de que está resolviendo
los enlaces a la fuente original (esto tarda unos segundos) y, al final:

```
Listo: 72 noticia(s) -> notibol_economia_2026-08-04.xlsx
```

El archivo **`notibol_economia_2026-08-04.xlsx`** queda **en la misma carpeta**.
Abrilo con Excel: cada fila es una noticia; el titular y los enlaces son
clickeables.

---

## Otras formas de usarlo (opcional)

**Elegir el nombre o la ubicación del Excel:**

```powershell
python notibol_scraper.py --fecha 2026-08-04 --out C:\Users\TU_USUARIO\Desktop\noticias.xlsx
```

**Buscar en otra sección del portal** (por defecto es *Economía*):

```powershell
python notibol_scraper.py --fecha 2026-08-04 --base https://notibol.com/bolivia/politica
```

**Ver la ayuda:**

```powershell
python notibol_scraper.py --help
```

---

## Valores por defecto (qué pasa si no los indicás)

| Opción | ¿Obligatoria? | Si no la ponés |
|---|---|---|
| `--fecha` | **Sí** | El programa avisa que falta la fecha |
| `--base` | No | Usa la sección **Economía** (`https://notibol.com/bolivia/economia`) |
| `--out` | No | Guarda como `notibol_economia_<fecha>.xlsx` en la carpeta actual |

---

## Problemas frecuentes

- **"python no se reconoce como comando"** → Python no quedó en el PATH.
  Reinstalá Python (Paso 1) marcando ✅ *"Add python.exe to PATH"*.
- **"pip no se reconoce como comando"** → Reiniciá la computadora y reintentá el
  Paso 3.
- **La fecha da error** → Usá siempre el formato `año-mes-día` con guiones y
  cuatro dígitos de año, por ejemplo `2026-08-04`.
- **Dice "0 noticia(s)"** → Puede que no haya noticias para esa fecha, o que no
  haya conexión a internet. Probá abrir en el navegador
  `https://notibol.com/bolivia/economia/2026-08-04` para confirmar.
- **No abre el Excel** → Asegurate de tener instalado Microsoft Excel (o
  LibreOffice Calc, que también lo abre).

---

## Uso día a día (resumen)

Una vez instalado todo (Pasos 1 a 3, que se hacen una sola vez), el uso diario es
solo:

1. Abrir la carpeta `notibol` → escribir `powershell` en la barra de dirección → Enter.
2. Ejecutar: `python notibol_scraper.py --fecha AÑO-MES-DÍA`
3. Abrir el Excel que se generó en la carpeta.
