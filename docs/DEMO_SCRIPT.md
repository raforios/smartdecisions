# 🎤 SmartDecisions — Guion de demo (5 minutos)

> **Objetivo:** mostrar a un prospecto cómo SmartDecisions convierte un
> Excel de ventas en **decisiones comerciales con valor monetario** en
> menos de un minuto, sin ERP, sin instalación.

---

## 0. Preparación (antes de la reunión)

| Cosa | Cómo |
|---|---|
| Dataset sintético listo | `python tools/synthesize_sales.py` → `tools/samples/ventas_demo.xlsx` |
| 5 servicios corriendo | AUTH/EVENTS/FILES/ML_FUNCTIONS productivos · ingest/optimization/analytics locales (ver `POC_EVALUATION.md`) |
| Frontend abierto | `http://localhost:<port>/portal/demo/` |
| Credenciales demo | Email + password listos para copy/paste |
| Backup del PDF | Slides simples por si el wifi muere |
| Browser limpio | Sesión nueva, no caches viejas, dev tools cerrados |

**Nota:** la demo entera depende de que `ingest`, `optimization` y `analytics`
estén levantados (no están deployados a Lambda aún). Si solo querés
mostrar lo deployado en AWS, usa el módulo **Playground ML** que sí
golpea producción.

---

## 1. Hook — el problema (45 s)

> "El 90% de las micro y pequeñas empresas de LATAM toman decisiones
> comerciales con la intuición del dueño y una libreta. No usan ERP
> porque cuesta caro, requiere instalación y necesita un consultor.
> Pero **sí tienen** un Excel de ventas. SmartDecisions transforma ese
> Excel en una lista priorizada de acciones comerciales con su impacto
> esperado en dólares — sin ERP, sin instalación, en menos de un minuto."

**Apoyo visual:** abrir la landing `app/portal/index.html` y mostrar el
diferenciador en pantalla:

```
Afinidad × Drop Size = Oportunidad Comercial Real
```

---

## 2. Login y home del demo (15 s)

Click **"Entrar al demo en vivo"** en la landing → `demo/index.html`.

- Loguearse con credenciales demo.
- Mostrar el home con los 3 módulos.

> "Tres módulos pensados para distintos niveles de adopción:
> — el módulo principal para el dueño de la tienda,
> — el playground para que el equipo técnico del cliente vea qué hay
>   bajo el capot,
> — y la optimización de rutas para distribuidoras con flota."

---

## 3. Módulo Excel → Oportunidades (3 min)

> "Este es **el** módulo del producto."

### a) Plantilla (10 s)
- Click **"Descargar plantilla"** → abre `template_ventas_v1.xlsx`.
- Mostrar las 5 columnas obligatorias + 5 opcionales en la hoja
  **Instrucciones**.

> "El usuario no necesita inventar el formato — le damos la plantilla
> y validamos contra ella."

### b) Subida (20 s)
- Drag-and-drop `ventas_demo.xlsx` en la zona de upload.
- Click **"Subir y validar"**.
- Mostrar el spinner; en segundos aparece la sección de validación.

### c) Validación (30 s)
- 5 metric cards en pantalla:
  `Filas válidas: 4478/4478` · `Errores: 0` · `PdVs: 5` · `Productos: 12` ·
  `Rango: 2026-04-01 → 2026-05-30`.

> "El motor de validación es estricto: ningún archivo basura entra al
> motor de análisis. Si hay un error, el reporte por fila y columna
> está en español y le dice al usuario qué arreglar."

**Bonus didáctico (si el prospecto es técnico):** subir aparte un Excel
roto a propósito y mostrar la tabla de errores con mensajes claros
(`row=3 col=cantidad → "El valor debe ser mayor que el mínimo permitido."`).

### d) Ejecutar el motor (15 s)
- Click **"Ejecutar análisis"**.
- Spinner. En 5-15 s aparecen las oportunidades.

### e) La tabla de oportunidades (90 s)
- Card del impacto total: **$2,525.48 esperados**, 16 oportunidades,
  5/5 PdVs con acciones, 342 reglas evaluadas.

> "Esto es lo que paga el producto."

- Apuntar la **fila 1**: `PDV-024 → Cerveza Negra 6-pack` con lift 9.92,
  confianza 83 %, $242.27 esperados.

> "Esto NO es un dashboard que te muestra lo obvio. Esto te dice:
> 'a Mini-market El Sol no le estás vendiendo cerveza negra y deberías,
> porque PdVs con su mismo patrón de compra la venden mucho. Si la
> introduces, esperamos $242 de venta adicional por orden'."

- Pasar el cursor sobre la fila → **tooltip** con el rationale en
  español listo para copiar a una llamada comercial:
  > "Quienes compran Galleta Integral 200g tienden a comprar
  > Yogurt Natural 1L (lift 9.92). Drop size esperado en
  > Mini-market El Sol: 14 unidades / $242.27."

- Demostrar **filtro por PdV**: escribir "PDV-007" → 3 oportunidades
  filtradas para esa tienda.
- Demostrar **ordenable por columna**: click en "lift" → ranking por
  fuerza estadística en lugar de impacto monetario.

> "El dueño de la pyme exporta este Excel y arranca a llamar a sus
> PdVs con un guion accionable. Sin estadística, sin consultoría."

---

## 4. Diferenciador técnico — Playground ML (45 s)

> "Para los más técnicos: este módulo expone los algoritmos crudos
> del motor."

- Abrir `playground/` → tab **Lineal**.
- Click **"Entrenar"** con los datos pre-cargados → chart de costo
  vs iteraciones se anima en pantalla.

> "Regresión lineal con gradiente descendente, los mismos algoritmos
> que enseñan en cualquier Master de Data Science, pero detrás de
> una API gateway productiva en AWS Lambda."

- Click en tab **Z-Score + Sigmoid** → ejecutar Normalización.
- Mostrar μ, σ y la matriz normalizada.

> "Cuando el cliente quiera traer sus propios datos o sus propios
> modelos, el motor está listo."

---

## 5. Módulo Rutas — bonus si hay tiempo (45 s)

> "Para distribuidoras con flota."

- Abrir `routes/` → click **"Cargar puntos"** con route_id=2, day=1.
- Mapa Leaflet con tema dark, 5 markers de PdV.
- Toggle **"Ruta original"** ON → polyline azul punteada.
- Click **"Optimizar"** → spinner mientras `osmnx` calcula contra OSM.
- Polyline teal aparece con el orden óptimo.
- Apuntar el summary: **distancia total** vs original.

> "El motor proyecta la ruta sobre la red vial real de OpenStreetMap.
> Antes de comprar combustible, sabés cuánto te ahorrás."

---

## 6. Cierre — los números del POC (30 s)

> "Todo lo que viste corre en AWS, hoy, sin un solo dólar de
> infraestructura productiva en este POC:
>
> — 8 microservicios Python/FastAPI sobre AWS Lambda y DynamoDB
> — un frontend Vanilla JS sin build, publicado en CloudFront + S3
> — modelo de datos abierto: un Excel
> — pricing futuro: por dataset o por suscripción mensual baja
>
> El siguiente paso es traer un Excel de tu negocio a una sesión de
> trabajo y ver tus propias oportunidades. ¿Cuándo te queda?"

---

## Apéndice — qué decir si algo falla

| Falla | Cómo recuperar |
|---|---|
| No carga la plantilla | "Aquí estoy hablando con un servicio en producción. Pruebo el flujo con el dataset que ya tengo listo." → seguir con el upload directo. |
| El upload falla | Tener el `analytics_results.json` precargado como respaldo y mostrarlo desde un visor JSON local. |
| No hay internet | El módulo Playground ML aún funciona si los servicios están deployados — al menos podés mostrar el chart de convergencia. |
| Cerveza Negra no aparece como top | Re-generar el dataset con `--seed 42` (deterministic). Si igual no aparece, mostrar el segundo de la lista — el guion sigue siendo válido para cualquier oportunidad de alto score. |
| Prospecto pregunta por privacy | Recordar: el Excel del prospecto se queda en su bucket S3 (gateway FILES), y los datos se borran cuando termina el POC. Sin terceros ni training cruzado. |

---

## Apéndice — métricas que conviene tener a mano

Generadas con `tools/synthesize_sales.py --seed 42`:

| Métrica | Valor esperado |
|---|---|
| Filas | 4,478 |
| Órdenes únicas | 1,200 |
| PdVs | 5 |
| Productos | 12 |
| Rango de fechas | 60 días |
| Monto total ingresado | ~$565,521 |
| Oportunidades detectadas | 16 |
| PdVs con oportunidades | 5/5 |
| Impacto monetario esperado | ~$2,525 |
| Reglas Apriori evaluadas | ~342 |
| Tiempo end-to-end | ~10-20 s |
