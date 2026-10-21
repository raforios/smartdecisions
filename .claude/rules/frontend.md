---
paths:
  - "portal/**/*.js"
  - "portal/**/*.css"
  - "portal/**/*.html"
---

# Frontend — portal demo y página pública

Vanilla JS sin build, servido desde S3 + CloudFront.

## Rutas: absolutas en el login, relativas en los módulos

La distribución mapea **404 → `/index.html` dejando la URL intacta**, así que la
página de login (`portal/demo/index.html`) puede ejecutarse bajo cualquier
subruta. Por eso **sus** rutas son absolutas (`/styles/demo.css`): con rutas
relativas sus scripts se resolvían contra esa subruta, devolvían HTML y el
navegador lanzaba `Unexpected token '<'`, con un bucle de recarga que impedía
cerrar la pestaña.

Las páginas de módulo (`home.html`, `excel/`, `routes/`, `minerales/`,
`factores/`) sólo se sirven en su propia ruta, y usan rutas
relativas (`../js/config.js`, `minerales.js`). Así funcionan hoy.

## Los códigos se traducen aquí

El backend devuelve `INSUFFICIENT`, `DAMPED_TREND`, `SOURCE_UNREADABLE`. Cada
módulo tiene su catálogo de etiquetas y su `errorText(error, fallback)`. Nunca
se muestra un código crudo al usuario.

## Antes de desplegar

- Comprueba que **cada `id` que busca el JS existe en el HTML**. Un
  `VIEW_TO_KIND is not defined` costó una demo entera.
- Comprueba que cada `src`/`href` local resuelve a un archivo que existe.
- `node --check` sobre cada `.js` tocado.

## Estilos

- Una sola definición por componente. Una copia en el CSS de un módulo pisa la
  compartida —carga después— y el mismo elemento se ve distinto en cada pantalla.
- **Cuidado con la especificidad.** `.card p` (0,1,1) le gana a `.ai-text`
  (0,1,0), y sólo dentro de tarjetas: eso hizo que un panel se viera bien en un
  módulo y mal en otro.
- **Tres tamaños de letra** para todo lo que no es título ni cifra
  (Rafael, 14-oct): `--fs-text` (texto y controles), `--fs-table` (celdas) y
  `--fs-label` (rótulos chicos), en `styles/demo.css`. Lo que importa va en
  negrita, nunca más grande. Ningún `font-size` suelto en rem para texto.
- **La tabla (`.table-wrapper`, `.data-table`) se define en
  `styles/demo.css`.** `routes.css` la redefinía y sus tablas salían más
  grandes que las demás; ya no. `minerales.css` conserva su variante de
  Minerales y Factores, pero con los mismos tamaños (`--fs-table`).
- **Una sola separación entre bloques** (tarjetas, paneles, gráficos, mapas),
  en horizontal y en vertical: `--gap-block` en `styles/demo.css` (Rafael,
  14-oct). Ninguna grilla de tarjetas con su propio `gap` en rem.
- **Los controles respiran:** botones, cajas y tablas nunca pegados
  (`.form-actions`, `.field`, `.field-row`); una caja de texto suelta toma el
  estilo común por `:where(main)`.
- **Controles universales** (Rafael, 21-oct): iguales en toda la aplicación y
  para todos los roles. Botones por función con su ícono antes del texto
  (`data-btn-icon`, lo dibuja `SD_UI.decorateButtons`): verde guarda
  (`.btn-save`), naranja cancela (`.btn-cancel`), rojo borra (`.btn-delete`),
  azul empieza algo nuevo (`.btn-primary`). Las acciones de una fila de
  tabla son íconos con tooltip (`.btn-icon` + `data-tip` + `aria-label`).
  Toda contraseña lleva el ojo (`SD_UI.revealToggle`). `data-icon` es de
  `shell.js`, que reemplaza el contenido entero: no se usa en botones.
- Los tokens de color viven en `styles/demo.css` y son los mismos que los de
  `bearsoft.com.bo`. Azules fríos, verde-azulado de acento, sin dorados.

## Tablas

Diez filas por página en **toda** tabla (Rafael, 21-oct). El paginador es uno
solo, automático, en `js/ui.js` (`SD_UI.paginate`): el módulo dibuja todas
las filas y el paginador oculta las que no están en la página, con la altura
de la primera para que la tarjeta no salte. Ningún módulo escribe su propio
paginador ni filas de relleno. Una fila `.detail-row` viaja con la de arriba.
Quedan fuera los estados financieros (`.statement-table`), las tablas dentro
de otra tabla y las que lleven `data-no-pager`.

## Capa de IA

`js/ai.js` expone `SD_AI.registerView(id, () => payload)`. Se registra **la
respuesta del backend tal cual**, sin transformar (en Análisis Financiero, el
período elegido tal como vino). El botón sólo aparece si `SD_CONFIG.API_URL`
está definida. Las pantallas de un producto nuevo no se agregan en AI: basta
con que su vista tenga un texto activo en `ai_prompts` (AI es base desde el
19-oct-2026).
