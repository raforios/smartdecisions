# SMARTDECISIONS

> **Documento único del producto:** qué es, cómo está construido, qué está
> **terminado y aprobado**, cuál es el **estado actual** y qué queda
> **pendiente**. Nada más. Se lee primero al abrir una sesión.
>
> Lo que no vive aquí: las reglas técnicas están en `CLAUDE.md` y
> `.claude/rules/`; los procedimientos en `.claude/skills/`; el guion comercial
> en `GUION_DEMO.md`; el contrato de columnas en el código que lo valida.
>
> **Última actualización: 2026-09-22**

---

## Regla de oro

`CLAUDE.md` manda sobre cualquier patrón que se encuentre en el código. **Si el
código existente la contradice, se avisa — no se propaga.** Todo el código de
AI, ANALYTICS, INGEST, MINING_ANALYSIS, OPTIMIZATION y QUOTES lo escribió
Claude: no hay "código heredado" que sirva de excusa.

---

## 1. El producto

**En una frase:** plataforma SaaS que convierte **un archivo de ventas** en
decisiones comerciales accionables —qué ofrecer a cada cliente, cuánto se va a
vender, a quién estás por perder, cuánto ganas de verdad y en qué orden recorrer
la ruta— **sin ERP, sin instalación y sin proyecto de integración**.

**Concepto diferenciador:** `Afinidad × Drop Size = Oportunidad Comercial Real`

**Tesis de coherencia:** una sola carga alimenta todos los módulos. *Si un
módulo necesita que el usuario cargue datos aparte, está mal diseñado.*

**Mercado:** gerencias comerciales de distribuidoras y consumo masivo en
Bolivia. Segundo vertical: mineras y comercializadoras (cotizaciones).

**Marca:** empresa **BearSoft**, producto **SmartDecisions**.

**Idioma:** todo lo que ve el usuario en castellano (UI, reportes, plantilla);
todo el código en inglés, incluidos los campos del contrato JSON.

### Módulos — cada uno es una pregunta de negocio

| Módulo | Pregunta que responde |
|---|---|
| Resumen Comercial | ¿Cómo vamos? ¿Crece? ¿De quién dependemos? ¿Cuánto ganamos? |
| Fuente de volumen | ¿De qué productos y clientes sale la venta? |
| Oportunidades | ¿Qué le ofrezco a cada cliente y cuánto vale? |
| Pronóstico | ¿Cuánto voy a vender los próximos meses? |
| Segmentación | ¿Quiénes son mis clientes valiosos? |
| Salud de Cartera | ¿A quién estoy por perder? |
| Cuentas por cobrar | ¿Cuánto me deben, qué tan vencido, cuánto recupero? |
| Stock del día | ¿Cuántos días me dura, qué está por quebrar, cuánto capital quieto? |
| Rutas | ¿En qué orden visito, dónde está cada vendedor y qué vendió? |
| Cotizaciones | ¿A qué precio se liquida el mineral y el dólar, y hacia dónde va? |
| Interpretación (IA) | ¿Qué significa esto? — sobre cualquiera de las anteriores |

---

## 2. Descripción técnica

Microservicios Python (FastAPI + Mangum sobre Lambda), cinco capas, DynamoDB.
Todos validan `Authorization` contra AUTH. Frontend Vanilla JS sin build en
`portal/demo/`, sobre S3 + CloudFront.

**Base**, compartidos por todos los productos de BearSoft: **AUTH** (JWT,
usuarios, roles, token de 30 min), **EVENTS** (auditoría y logs de uso),
**FILES** (S3).

| Servicio | Función | Infra |
|---|---|---|
| 📥 INGEST | Plantilla, parseo y validación de ventas, cobros, stock y visitas | 1024 MB / 30 s |
| 📊 ANALYTICS | Los nueve análisis comerciales | 2048 MB / 120 s |
| 🗺️ OPTIMIZATION | Planificación de rutas, seguimiento de vendedores, stock del día | 256 MB / 30 s |
| ⛏️ MINING_ANALYSIS | Cotización oficial de minerales, mercado diario, regalías, boletín | 1024 MB · Dynamo + MySQL local |
| 💵 QUOTES | Tipo de cambio del BCB, proyección y escenario de venta | 256 MB |
| 🧠 AI | Convierte la respuesta de cualquier servicio en una explicación | 512 MB · Bedrock |

**ML_FUNCTIONS** sigue desplegado pero ningún servicio lo consume.

**Qué entra en una revisión general:** los diez servicios de arriba (los seis
más AUTH, EVENTS, FILES y ML_FUNCTIONS). **FORMS, LOCALIZATION, TRADE,
EVENTS_MYSQL, PLANNING, CMS y MINING_SUMMIT no se tocan** sin pedido explícito:
son de clientes. **SUPPLIES es nuestro** y pasa a ser la base del facturador
para farmacias.

**Límites de infraestructura que condicionan el diseño:** Lambda 250 MB sin
comprimir (por eso no hay scikit-learn, osmnx, Prophet ni mlxtend); API Gateway
29 s y 10 MB (los archivos suben directo a S3 con URL pre-firmada); DynamoDB
400 KB por ítem (un run de analytics recorta a los mejores por producto); OSRM
público con límite de tasa (una sola llamada por día).

**Contrato de datos:** la fuente de verdad es el código, no este documento —
`SALES_COLUMNS`, `COLLECTION_COLUMNS`, `STOCK_COLUMNS` y `VISIT_COLUMNS` en
`services/ingest/schemas/ingest.py`, de donde se derivan el mapeador de
encabezados, el esquema del DataFrame y la plantilla publicada. Una fila = una
línea de venta; `Nro Factura` agrupa la canasta (sin eso no hay afinidad);
`Latitud`/`Longitud` habilitan Rutas y `Costo Unitario` habilita margen; cobros,
stock y visitas son hojas opcionales del mismo libro, cargables después.

**Cómo probarlo:** `/verificar-servicio <nombre>` corre la batería completa
(pytest, Pylint 10.00, firmas, type hints, hardcode, tamaño).
`python tools/build_sample_dataset.py --rows 24000 --months 24` regenera
`ventas_demo.xlsx` (22.008 filas, 24 meses, 266 clientes), cuyas cifras
esperadas están en `GUION_DEMO.md`.

---

## 3. Finalizado y aprobado

Desplegado, probado con datos reales y validado por Rafael.

| Pieza | Cuándo |
|---|---|
| AUTH, INGEST, ANALYTICS, QUOTES, AI, OPTIMIZATION en producción | 21-sep |
| Los nueve análisis comerciales, con Cartera y Cuentas por cobrar | 17-sep |
| **RUTAS backend** — plan → ruta → visita → venta → sobreventa → cierre, con geocercas y descuento transaccional de stock (85 tests) | 21-sep |
| **RUTAS frontend gerencia** — Planificar, Planes, Stock del día, En vivo, Comparación | 21-sep |
| **Pantalla del vendedor** — `routes/vendedor.html`, probada desde celular con `vendedor.demo@bearsoft.com.bo` (SELLER) | 22-sep |
| **Usuarios por cliente y roles** — `client` en el JWT, `MANAGER` y `SELLER`, `require_roles` en las seis APIs | 21-sep |
| Portal demo y `bearsoft.com.bo` publicados, con logs de CloudFront | 17-sep |
| Corrección del contrato de error (el `detail` viaja limpio, sin `"409: CODE"`) en los seis servicios, con test de regresión | 20-sep |
| Estandarización de firmas y type hints en los diez servicios, con verificación mecánica | 17-sep |

---

## 4. Estado actual

**MINING_ANALYSIS desplegado y probado en producción el 22-sep.** Falta que
Rafael lo dé por bueno y el frontend de la pantalla. Lo que se verificó contra
AWS: la regla `mining-analysis-daily-market-sync` ENABLED a `cron(0 23 * * ? *)`
apuntando al Lambda con `{"task":"sync_market"}`; el sync guardó 42 días (6
minerales × 7 hábiles de la ventana de 10) y al repetirlo saltó los 42 sin
reescribir; las 9 escalas del Art. 227 sembradas en `mining_royalty_rules`; y
`/market/estimate` devolviendo la quincena en curso (16→30 sep, que regirá del
1 al 15 de octubre) con Oro −0,74 %, Cobre +1,23 %, Estaño −1,43 % y los tres de
Asian Metal en `NONE` por no tener fuente libre. Sin errores en CloudWatch;
arranque en frío 7 s, sync en 2,3 s, 305 MB de 1024 MB.

Los dos trabajos que entraron en ese despliegue:

1. **Cotización anticipada de minerales.** El cruce de 115 días oficiales
   (`tools/mining_analysis/cross_check_sources.py`) fijó las fuentes: oro =
   **LBMA fix AM** (111/115 exactos), plata = LBMA fix (114/115), Cu/Sn/Pb/Zn =
   LME cash *buyer* vía Westmetall (su settlement va +0,01–0,1 %); Sb/W/Bi son
   de Asian Metal, de pago, y siguen viniendo del informe quincenal. Módulos
   `market_sources.py`, `royalty_rules.py` (escalas del Art. 227 como
   parámetros en Dynamo) y `official_estimate.py`. Endpoints `/market/sync`
   (ADMIN/MANAGER), `/market/estimate`, `/market/prices/{id}` y
   `/royalty-rules` (GET/PUT), más el handler programado `task=sync_market`.
   Tablas ya creadas: `mining_market_prices`, `mining_royalty_rules`.
2. **Alineación al boilerplate.** `db_connection.py` y `crud.py` son ahora los
   estándar de DynamoDB, idénticos a los de los otros cinco servicios, y el
   recurso se inyecta desde la ruta. Lo relacional, que se queda porque el
   Ministerio y la carga quincenal lo necesitan, vive en `db_connection_sql.py`
   y `crud_sql.py` con `GET_SQL_DB_DEPENDENCY`; sólo `/etl/upload`,
   `/royalties/*` lo usan. `crud_dyb.py` y `market_store.py` se eliminaron; el
   acceso de dominio es `prices_dyb.py`. **104 tests en verde y
   `/verificar-servicio` en ALL PASS** (Pylint 10.00, firmas, type hints).

**Pendiente de un redespliegue de MINING_ANALYSIS.** Al probar el botón
"Actualizar del mercado" desde el portal, el endpoint devolvió 500: el
decorador de auditoría leía `.id` sobre cualquier modelo Pydantic y
`MarketSyncResult` es un resumen, no una fila. Corregido en
`services/utils.py` —que en este servicio sigue siendo la variante MySQL, no
la estándar— con dos tests de regresión. La corrida programada nunca pasó por
ahí, por eso el sync nocturno funcionaba y el botón no.

**Frontend de minerales terminado y publicado (22-sep).** Panel "Cotización
anticipada" en `portal/demo/minerales/`: promedio corriente contra la oficial
vigente, alícuotas del Art. 227 con la parte de la escala que las decidió
(techo/piso/fórmula), días cotizados y confianza; al desplegar un mineral, los
días que construyeron el promedio y la fórmula legal que produjo la alícuota.
Selector "Al día" para verificar el corte de quincena sin esperar al
calendario, y botón de sync para ADMIN/MANAGER. Los formatos y el catálogo de
códigos se extrajeron a `minerales_shared.js`, compartido con el panel viejo.

**Flujo de Solicitudes eliminado de SUPPLIES (23-sep).** Como pediste: no lo
usa el producto de farmacias y no tenía sentido cargarlo. Se fueron
`routes/request.py`, `controllers/request.py`, `schemas/request.py` y
`tests/test_reservations.py` (1.116 líneas), más la máquina de estados y las
reservas de stock de `supplies_logic.py`, el campo `reserved_stock`, el rol
REQUESTER y el origen REQUEST del kardex. **Consecuencia a decidir:** el
dashboard del almacén perdió tres de sus KPI y el feed de solicitudes —eran
suyos—, y el reporte de salidas ya no nombra un destinatario, sólo quién
registró el movimiento.

**Reunión comercial del jueves.** Lo que se demuestra —módulo comercial y
RUTAS— ya está desplegado y probado; el minerales queda como avance.

---

## 5. Pendiente

En orden.

1. **Facturador para farmacias (SUPPLIES) — backend terminado, falta
   desplegar y la pantalla.** Módulo paralelo dentro de SUPPLIES sobre
   DynamoDB, con el mismo patrón que RUTAS dentro de OPTIMIZATION: archivos
   `*/pharmacy*.py` nuevos, `db_connection.py` y `crud.py` estándar de Dynamo,
   y lo relacional del almacén movido a `*_sql.py`. Cinco tablas ya creadas en
   AWS. 22 tests propios y `/verificar-servicio` en ALL PASS.

   Reglas acordadas que ya están implementadas: multicliente desde el inicio
   (el dueño es la farmacia y es parte de cada clave); **costo y precio de
   venta por lote**, porque los fija el laboratorio en cada compra; **PEPS con
   el reloj (FEFO)** — sale primero lo que vence antes, y una línea que abarca
   dos lotes se cobra al precio de cada uno; comprador con nombre y NIT/CI;
   descuentos por línea sólo si la farmacia los habilita; forma de pago
   (efectivo/QR/tarjeta); numeración propia por farmacia, atómica; anular una
   nota devuelve las unidades a los lotes exactos de los que salieron.

   Falta: despliegue de Rafael, y el frontend (mostrador, catálogo, recepción,
   e impresión térmica de 58 y 80 mm desde el navegador, como en
   MINING_SUMMIT) con el estilo visual de SmartDecisions. Fase siguiente:
   factura electrónica según la RND 11 (SIAT, SOAP/XML).

2. **Sección "Usuarios"** para que un MANAGER cree y administre a su gente.
3. **Alinear `mining_analysis/services/utils.py` al boilerplate estándar** — es
   la variante MySQL (828 líneas contra 408 del estándar); de ahí salió el 500
   del sync. Las 420 líneas extra son la carga masiva que `/etl/upload` y
   `/royalties/upload` todavía usan, así que no es un reemplazo directo.

**Lo que falta para vender, no para demostrar:** control de suscripción,
retención de datos y persistencia de lo que produce la capa de IA.

---

## 6. Decisiones vigentes

Las que siguen condicionando el código. Las revertidas no están.

### Negocio

- **La cotización oficial de una quincena es el promedio de la anterior.** La
  media del 1 al 15 rige del 16 al 30; **no** es la última cotización del día.
  El promedio va sobre los días que ese mineral tenga: Estaño puede tener 10 y
  Wólfram 2 en la misma quincena.
- **El BCB publica el viernes de noche una cotización que rige sábado, domingo
  y lunes.** La ventana del sync llega al final del bloque, no a "hoy".
- **El 27 de junio de 2026 el tipo de cambio dejó de estar fijo.** Toda serie
  proyectada arranca ahí; los años de 6,86 son otro régimen.
- **El Ministerio de Minería recibe el boletín en PDF y PNG** a cambio de los
  datos de cotizaciones. Ese intercambio no se toca.
- **SmartDecisions no reserva ni aparta stock del ERP del cliente:** reporta
  `disponible = existencia − comprometido`. Ser dueño de esa verdad sería ser
  dueño de la concurrencia y de la culpa. Lo que sí aporta es cobertura en días,
  fecha estimada de quiebre, capital inmovilizado y clase ABC.
- **Degradación elegante, no ceros.** Sin la columna opcional, la sección se
  declara no disponible y la UI la oculta. Mostrar 0 % de margen sin costos es
  mentir.
- **Aceptación parcial:** las filas inválidas se apartan con su motivo y el
  resto se carga. Coordenada 0 = sin dato.

### Técnicas

- **El backend devuelve datos y códigos, nunca texto de cara al usuario.** La
  interpretación es del frontend o de la capa de IA; no hay catálogos de textos
  en el repositorio.
- **Nada configurable vive en el código.** Las variables son requeridas: un
  `ENV_VARS['X'] or 30` sigue siendo un número elegido por el código. Si falta
  configuración, el servicio no arranca.
- **El dueño es parte de la consulta, no un filtro posterior.** Hoy el dueño es
  el `client` del token, o el email cuando no lo tiene. En OPTIMIZATION además
  es parte de la clave de partición, porque la carga borra la partición antes de
  escribir.
- **Un archivo se identifica por su contenido.** Misma huella y mismo dueño = el
  mismo dataset.
- **La cuenta por cobrar vive al nivel de factura**, sumando `total_amount` por
  `order_id`. Factura sin cobros es saldo abierto; cobro sin venta es
  incidencia con código, nunca descarte en silencio.
- **El modelo predictivo es suavizado exponencial con tendencia amortiguada**,
  ajustado por backtest, y cada proyección publica su error y el del modelo
  ingenuo.
- **La capa de IA recibe la respuesta del backend tal cual**; `view` sólo elige
  el rol. Los roles viven versionados en DynamoDB y la versión participa de la
  clave de caché.
- **El entorno local corre las mismas versiones que el Lambda.** Sin versiones
  fijadas en `requirements.txt`. El Lambda no tiene pyarrow: en pandas 3 una
  columna de miembros de un `str, Enum` se compara por `.value`.
- **Un libro se abre una sola vez por subida**; tres aperturas de openpyxl
  agotaban los 30 s del Lambda.
- **Los timestamps que llegan de un dispositivo se normalizan a
  `TARGET_TIMEZONE`** antes de decidir a qué día pertenecen. Un equipo en UTC
  ponía la ruta en el día siguiente.
- **No se crean carpetas nuevas dentro de un microservicio.** `scripts/` existe
  sólo en MINING_ANALYSIS, por la carga quincenal manual.
- **Los tests de los servicios base no importan módulos que validen entorno.**
  GitHub Actions corre sin `.env` y la colección falla antes de empezar.

### Infraestructura

- **Sin RDS por presupuesto.** Todo servicio nuevo va a DynamoDB + Lambda + S3.
- **Las tablas se crean con `create_dynamodb_tables.sh`**: `build_and_deploy.sh`
  no crea claves compuestas ni admite dos tablas por servicio. El acceso lo
  cubre `AmazonDynamoDBFullAccess` en el rol.
- **El `.env` completo viaja a las variables del Lambda: ningún valor lleva
  coma ni llave.** La coma separa variables y la llave abre una estructura
  anidada en `--environment Variables={...}`; una plantilla de URL va con `%s`.
  Un `LME_{symbol}_cash` abortó un despliegue **después** de subir el código.
- **Bedrock exige perfiles de inferencia** (`us.` delante) y un formulario de
  caso de uso por cuenta.
- **Los deploys de backend los hace Rafael**; los de frontend, el asistente.
- **Gotchas comprobados:** con red lenta `aws s3 cp` puede devolver 0 sin subir
  y el Lambda recarga el ZIP viejo (comprobar fecha en S3 y `CodeSize`); el
  CORS de un API ya creado no se actualiza desde el script (se agregó `PATCH` a
  OPTIMIZATION y AUTH con `update-api`).
