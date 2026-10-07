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
`factores/`, `playground/`) sólo se sirven en su propia ruta, y usan rutas
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
- Los tokens de color viven en `styles/demo.css` y son los mismos que los de
  `bearsoft.com.bo`. Azules fríos, verde-azulado de acento, sin dorados.

## Tablas

Tamaño fijo con paginación, no una tabla que crece con los datos. Con relleno
invisible en la última página para que la tarjeta no salte de altura.

## Capa de IA

`js/ai.js` expone `SD_AI.registerView(id, () => payload)`. Se registra **la
respuesta del backend tal cual**, sin transformar. El botón sólo aparece si
`SD_CONFIG.AI_URL` está definida.
