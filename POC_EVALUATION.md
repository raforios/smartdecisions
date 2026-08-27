# POC_EVALUATION.md — Cómo evaluar SmartDecisions

> Guía para reproducir el producto end-to-end y juzgar si está listo para
> ponerlo delante de un comprador. **Tiempo estimado: 15 minutos.**
>
> **Última revisión: 2026-08-27.** Reescrito tras el giro a MVP vendible: los
> tres servicios ya están desplegados, el dataset de prueba cambió y el módulo
> Playground se está retirando.
>
> Documentos hermanos: `SMARTDECISIONS.md` (visión), `POC_PROGRESS.md`
> (bitácora), `CLAUDE.md` (estándares).

---

## 1. ¿Qué se está evaluando?

Una **plataforma SaaS de inteligencia comercial**: toma un archivo de ventas y
devuelve un dashboard de gerencia, recomendaciones de venta cruzada valorizadas
en Bs, un pronóstico, una segmentación de clientes, el margen real por categoría
y la lista de clientes que estás por perder.

La prueba de fuego no es que cada módulo funcione por separado. Es que **un solo
archivo alimente todos los módulos**. Si tienes que cargar datos aparte para ver
las rutas, el producto todavía no está.

---

## 2. Arquitectura en 30 segundos

```
                  ┌────────────────────────────────────────┐
                  │  Navegador — S3 + CloudFront           │
                  │  app/portal/demo/* — Vanilla JS        │
                  └───────────────┬────────────────────────┘
                                  │ HTTPS + JWT (30 min)
                                  ▼
      ┌──────────────────────────────────────────────────────────┐
      │      API Gateway → Lambdas (FastAPI + Mangum)            │
      ├──────────────────────────────────────────────────────────┤
      │  BASE          AUTH · EVENTS · FILES                     │
      │  SMARTDECISIONS  INGEST · ANALYTICS · OPTIMIZATION       │
      │                  ML_FUNCTIONS · MINING_ANALYSIS          │
      └───────┬──────────────────────┬──────────────┬────────────┘
              ▼                      ▼              ▼
        ┌───────────┐          ┌───────────┐  ┌───────────┐
        │ DynamoDB  │          │    S3     │  │   MySQL   │
        └───────────┘          └───────────┘  └───────────┘

  Archivos grandes: navegador ──URL pre-firmada──▶ S3  (sin pasar por API GW)
```

---

## 3. Camino rápido: evaluar contra producción (5 min)

Todo está desplegado. No hace falta levantar nada.

1. Abre el demo y entra con tus credenciales de AUTH.
2. **Módulo Excel → Descargar plantilla.** Verifica que trae las 14 columnas,
   incluida `Costo Unitario`, y la hoja "Instrucciones".
3. Sube `tools/samples/ventas_demo.xlsx`.
4. Recorre las tarjetas de análisis.

**Qué medir en el archivo de demo (23.250 filas, 24 meses, 204 clientes):**

| Módulo | Qué debe salir |
|---|---|
| Carga | 23.250 / 23.250 filas válidas, 0 rechazadas |
| Resumen | Bs 1.145.657 de venta, 9.050 ventas, 24 meses en la tendencia |
| Margen | Margen bruto 22,2%; CAFES primero por margen |
| Oportunidades | ~600 acciones en ~192 puntos de venta, ~Bs 39.400 de venta potencial |
| Pronóstico | 24 puntos históricos + el horizonte elegido |
| Segmentación | Alto = 41 clientes concentrando ~61% de la venta |
| Cartera | 56 clientes en riesgo |

Si algún número se aleja mucho, el dataset o el motor cambiaron: revisa antes de
salir a mostrar.

---

## 4. Camino completo: levantar en local

### 4.1 Entorno

```bash
python -m venv .venv && source .venv/bin/activate
docker run -d --name dynamodb-local-container -p 3100:8000 amazon/dynamodb-local
for svc in ingest optimization analytics; do
    (cd services/$svc && ./dynamodb.sh && pip install -r requirements.txt)
done
```

Los `.env` de cada servicio ya apuntan a las URLs productivas de AUTH/EVENTS/FILES
y a DynamoDB local en `http://localhost:3100`. Si nadie los tocó, no hay nada que
configurar.

### 4.2 Generar los archivos de muestra

```bash
# Fixture rápido: ~2.000 filas, 3 meses
python tools/build_sample_dataset.py --rows 2000 --months 3 \
    --output tools/samples/ventas_muestra_2k.xlsx

# Archivo de demo: ~23.000 filas, 24 meses
python tools/build_sample_dataset.py --rows 24000 --months 24 \
    --output tools/samples/ventas_demo.xlsx
```

Requiere `data/DetalleVentas.csv` (el export real del distribuidor).

> **Importante:** el muestreo es **por cliente**, nunca por fila. Un muestreo
> aleatorio de filas parte las facturas y la afinidad deja de encontrar reglas.

### 4.3 Arrancar los servicios y el demo

```bash
cd services/ingest        && python main.py   # :3110
cd services/optimization  && python main.py   # :3120
cd services/analytics     && python main.py   # :3130
cd portal && python -m http.server 8000       # http://localhost:8000/demo/
```

Cada servicio expone Swagger en `http://localhost:31X0/docs`.

---

## 5. Batería de verificación técnica

### 5.1 Tests y calidad

```bash
(cd services/ingest    && pytest tests/ -q && pylint services/ controllers/ routes/ schemas/ tests/)
(cd services/analytics && pytest tests/ -q && pylint services/ controllers/ routes/ schemas/ tests/)
```

**Umbral:** todos los tests en verde y Pylint 10.00/10. Al 2026-08-27:
ingest 14/14, analytics 48/48, ambos 10.00.

### 5.2 Equivalencia XLSX / CSV

El mismo contenido debe ingresar idéntico en los dos formatos. Lo cubre
`services/ingest/tests/test_excel_parser.py::test_xlsx_and_csv_yield_the_same_rows`.

Regresión que cubre ese test: con fechas ISO, el parseo day-first hacía que
pandas dedujera `%Y-%d-%m` y **perdiera el 61% de las filas** en CSV mientras el
XLSX cargaba entero.

### 5.3 Degradación sin columnas opcionales

Sube un archivo sin `Costo Unitario`. **El bloque de margen debe desaparecer**,
no mostrar ceros. Igual sin `Latitud`/`Longitud`: el módulo de rutas se
deshabilita en vez de dibujar un mapa vacío.

### 5.4 Ventana de fechas

Todos los endpoints de análisis aceptan `date_from` y `date_to` (`YYYY-MM-DD`):

```bash
curl -H "Authorization: Bearer <token>" \
  "$ANALYTICS_URL/v1/analytics/summary/<dataset_id>?date_from=2023-06-01&date_to=2023-12-31"
```

La respuesta trae un bloque `periodo` que declara el rango disponible y el
aplicado. Un rango sin ventas devuelve un error explícito, **no un informe en
cero** (un informe en cero se lee como "no vendiste nada", que es otra cosa).

### 5.5 Trazabilidad

Cada acción emite dos eventos a EVENTS: uno de auditoría y uno de usage_log.

```bash
curl -H "Authorization: Bearer <token>" \
     "$EVENTS_URL/v1/events/audit?microservice=INGEST"
```

---

## 6. KPIs de aceptación

| Categoría | Métrica | Umbral |
|---|---|---|
| Validación | Filas válidas en el archivo de demo | 100% |
| Validación | Paridad XLSX vs CSV | Idéntica |
| Negocio | Oportunidades detectadas | ≥ 100 |
| Negocio | Venta potencial identificada | > Bs 10.000 |
| Negocio | Margen bruto reportado | Coherente con el costo cargado |
| Estadístico | Meses de histórico para el pronóstico | ≥ 12 |
| Performance | Ingesta de 23k filas | < 3 s |
| Performance | Resumen completo (5 motores) | < 1 s |
| Performance | Afinidad | < 5 s |
| Operación | 5xx en el camino feliz | 0 |
| Trazabilidad | Audit en EVENTS por cada CREATE | 100% |
| UX | Idioma | Español neutro, sin voseo |

> El umbral de performance de la afinidad es el que más ha dolido: con el archivo
> real de 121k filas tardaba ~28 s contra un timeout de API Gateway de 29 s, y
> devolvía 503. Con el archivo de demo baja a 0,3 s.

---

## 7. Limitaciones conocidas (al 2026-08-27)

| # | Limitación | Estado / mitigación |
|---|---|---|
| 1 | **Módulo Rutas incoherente**: pide `route_id` y `day` como enteros y lee de una tabla DynamoDB propia, sin relación con el archivo de ventas | En reforma: pasa a derivar día y ruta por proximidad geográfica sobre el dataset cargado |
| 2 | **Orden de visita con cruces**: el algoritmo es vecino más cercano voraz | Se reemplaza por 2-opt |
| 3 | **OSRM público**: una llamada por tramo contra un servidor con límite de tasa | Pasa a una sola llamada `/table`; servidor propio si hay uso real |
| 4 | **Playground ML sigue en el menú** | Se retira; se reemplaza por "Predicciones" |
| 5 | **Bloques nuevos del Resumen sin UI**: crecimiento, concentración, eficiencia, margen y cartera existen en la API pero el frontend aún no los dibuja | Siguiente tarea |
| 6 | **Costo unitario del demo es simulado** | Declarado en la hoja "Origen de los datos" del archivo |
| 7 | **Dato base pobre**: 4 meses reales, 1 ciudad, 1 canal, 1 región | El archivo de demo extiende el historial; conseguir un export más rico sigue siendo deseable |
| 8 | Sin multi-tenancy (un bucket S3 compartido) | Cuando haya tracción |
| 9 | Sin exportación a Excel de los resultados | Pendiente; una gerencia siempre lo pide |
| 10 | Token de 30 min; análisis largos pueden expirar la sesión | Mitigado con caché de resultados en `sessionStorage` |

---

## 8. Próximos pasos

1. Cablear al frontend los bloques nuevos (margen, crecimiento, concentración,
   eficiencia, cartera) y la barra de período.
2. Reformar el módulo de Rutas sobre el dataset de ventas.
3. Reemplazar Playground por "Predicciones".
4. Exportador a `.xlsx` de los resultados.
5. Incorporar Cotizaciones (`mining_analysis`) como módulo del segundo vertical.

---

## 9. Soporte

- **Bitácora:** `POC_PROGRESS.md` · **Visión:** `SMARTDECISIONS.md`
- **Estándares:** `CLAUDE.md`, `boilerplate.md`
- **Guion comercial:** `docs/DEMO_SCRIPT.md`
- **Contacto:** raforios@gmail.com
