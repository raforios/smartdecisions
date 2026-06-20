# POC_EVALUATION.md — Cómo evaluar SmartDecisions

> Guía corta para que cualquier persona (técnica o no técnica) reproduzca
> el POC end-to-end y juzgue si vale la pena llevarlo a la siguiente
> fase. **Tiempo estimado: 20 minutos** la primera vez, 2 minutos a
> partir de la segunda.

---

## 1. ¿Qué se está evaluando?

Una **plataforma SaaS de inteligencia comercial** para micro y pequeñas
empresas, construida como un conjunto de microservicios serverless sobre
AWS. El producto **toma un Excel de ventas y devuelve una lista priorizada
de acciones comerciales con su impacto monetario esperado**, sin
requerir ERP, instalación ni configuración previa.

El POC cubre 4 escenarios:

| Módulo | Servicio que prueba | Pregunta que responde |
|---|---|---|
| Excel → Oportunidades | `ingest` + `analytics` | ¿El motor afinidad × drop size produce recomendaciones accionables? |
| Playground ML | `ml_functions` | ¿Los algoritmos crudos (regresión, gradient descent, Z-score) están disponibles como API? |
| Rutas | `optimization` | ¿La heurística de orden óptimo + proyección a red vial funciona? |
| Auditoría | `events` | ¿Cada acción queda registrada para trazabilidad? |

---

## 2. Arquitectura en 30 segundos

```
                       ┌───────────────────────────────────┐
                       │   Browser (S3 + CloudFront)       │
                       │   app/portal/demo/* — Vanilla JS  │
                       └─────────────┬─────────────────────┘
                                     │  HTTPS + JWT
                                     ▼
        ┌──────────────────────────────────────────────────────┐
        │  AWS API Gateway → 8 Lambdas (FastAPI + Mangum)      │
        ├──────────────────────────────────────────────────────┤
        │  AUTH (JWT)        EVENTS (audit/log)                │
        │  FILES (S3)        ML_FUNCTIONS (regression)         │
        │  INGEST (Excel→S3) ANALYTICS (afinidad×drop size)    │
        │  OPTIMIZATION (routes)  LOCALIZATION (cliente only)  │
        └─────────────┬───────────────────────┬────────────────┘
                      │                       │
                      ▼                       ▼
              ┌──────────────┐         ┌──────────────┐
              │  DynamoDB    │         │   AWS S3     │
              │  (NoSQL)     │         │   bucket     │
              └──────────────┘         └──────────────┘
```

**$0 de infraestructura productiva** mientras el POC no se publica:
todo el plano de datos vive en free-tier o en cuenta personal.

---

## 3. Requisitos previos

| Cosa | Mínimo |
|---|---|
| Python | 3.14 |
| Docker | Cualquier versión reciente (solo para DynamoDB local) |
| Node.js | No requerido (Vanilla JS, sin build) |
| AWS CLI | Solo si querés deployar; para evaluar local NO hace falta |
| Cuenta AWS | NO requerida para la evaluación local |

---

## 4. Setup en local — paso a paso

### 4.1 Clonar y crear venv

```bash
git clone <repo>
cd app
python -m venv .venv
source .venv/bin/activate
```

### 4.2 Levantar DynamoDB local

```bash
docker run -d --name dynamodb-local-container -p 3100:8000 amazon/dynamodb-local
```

### 4.3 Crear las tablas (las 3 que el POC necesita)

```bash
cd services/ingest        && ./dynamodb.sh
cd ../optimization        && ./dynamodb.sh
cd ../analytics           && ./dynamodb.sh
```

Cada script verifica si la tabla ya existe; es idempotente.

### 4.4 Instalar dependencias por servicio

> **Atajo:** para evaluar end-to-end alcanza con instalar los 3 servicios
> nuevos. Los 4 servicios productivos (AUTH/EVENTS/FILES/ML_FUNCTIONS)
> ya están en AWS — no hace falta levantarlos en local.

```bash
for svc in ingest optimization analytics; do
    (cd services/$svc && pip install -r requirements.txt)
done
```

### 4.5 Configurar variables de entorno

Cada servicio ya trae un `.env` listo apuntando a las URLs productivas
de AUTH/EVENTS/FILES y a DynamoDB local en `http://localhost:3100`.
**Si nadie tocó el `.env`, no hay que hacer nada en este paso.**

### 4.6 Generar el dataset sintético

```bash
python tools/synthesize_sales.py --output tools/samples/ventas_demo.xlsx --seed 42
```

Output esperado:
```
  rows                    : 4478
  unique orders           : 1200
  unique PdVs             : 5
  unique products         : 12
  date range              : 2026-04-01 → 2026-05-30
  total monto             : 565,521.50
```

### 4.7 Sembrar datos de rutas en DynamoDB local

```bash
cd services/optimization
PYTHONPATH=. python scripts/seed_from_csv.py \
    --csv scripts/sample_routes.csv \
    --endpoint-url http://localhost:3100
```

### 4.8 Arrancar los 3 servicios

En 3 terminales distintas:

```bash
# Terminal 1 — ingest (port 3110)
cd services/ingest && python main.py

# Terminal 2 — optimization (port 3120)
cd services/optimization && python main.py

# Terminal 3 — analytics (port 3130)
cd services/analytics && python main.py
```

Cada uno expone Swagger UI en `http://localhost:31X0/docs`.

### 4.9 Servir el demo estático

```bash
cd portal && python -m http.server 8000
```

Abrir `http://localhost:8000/demo/` en el browser.

---

## 5. Recorrido recomendado (15 minutos)

### Paso 1: login

URL: `http://localhost:8000/demo/`

Loguearse con un usuario válido del servicio AUTH productivo. Si no
tenés credenciales, pedírmelas o crear uno con
`POST ${AUTH_URL}/v1/auth/users` (ver Swagger del AUTH).

**Qué evaluar:** UX limpia, dark theme, redirección al home.

### Paso 2: módulo Excel (5 min)

1. Click **Descargar plantilla**. → llega `template_ventas_v1.xlsx`.
2. Subir `tools/samples/ventas_demo.xlsx`.
3. Click **Subir y validar**.

   **Qué medir:**
   - `valid_rows / total_rows = 4478 / 4478` (sin errores).
   - 5 PdVs detectados, 12 productos.

4. Click **Ejecutar análisis**.

   **Qué medir:**
   - 16 oportunidades.
   - 5/5 PdVs con acciones.
   - **`Impacto esperado ≈ $2,525.48`** → este número es **EL KPI** del POC.
   - 342 reglas evaluadas.

5. Ordenar la tabla por **Score** descendente.

   **Qué medir:**
   - El top 3 deberían ser cervezas (`SKU-C300/SKU-C301`) con lift > 9.
   - El rationale en español por fila es legible para un dueño de PyME.

### Paso 3: módulo Playground (5 min)

1. Tab **Lineal** → click **Entrenar** con el ejemplo pre-cargado.

   **Qué medir:**
   - Chart de costo se anima.
   - `w_final ≈ 2.0`, `b_final ≈ 0`, `costo_final < 0.001`.

2. Click **Usar pesos entrenados** → click **Predecir**.

   **Qué medir:** predicciones cercanas a la recta `y = 2x` para los
   x_test ingresados.

3. Tab **Z-Score + Sigmoid** → click **Normalizar**.

   **Qué medir:** μ y σ se calculan; la matriz `x_norm` tiene media 0 y
   varianza unitaria por columna.

### Paso 4: módulo Rutas (3 min)

1. `route_id = 2`, `day = 1`, `dist = 1500` (valores por defecto).
2. Click **Cargar puntos**.

   **Qué medir:** mapa centrado en La Paz, 5 markers (rojo=inicio,
   verde=fin, amarillos=intermedios), polyline azul punteada con el
   orden client_id.

3. Click **Optimizar**.

   **Qué medir:** spinner ~5-15 s (`osmnx` golpea OSM); aparece
   polyline teal y card de resumen con `paradas`, `segmentos`,
   `distancia total`, `radio OSM`.

### Paso 5: trazabilidad (2 min)

Cada acción que disparaste debió enviar **dos eventos** al servicio
EVENTS productivo:
- Una entrada de audit (creación de dataset, run de analytics, etc.).
- Una entrada de usage_log (endpoint + IP + ms + status).

Si tenés credenciales del EVENTS productivo:

```bash
curl -H "Authorization: Bearer <token>" \
     https://uyrs6ucto3.execute-api.us-east-1.amazonaws.com/v1/events/audit?microservice=INGEST
```

**Qué medir:** aparece tu dataset_id, action=CREATE, entity=IngestDataset.

---

## 6. KPIs del POC (qué juzgar)

| Categoría | Métrica | Umbral mínimo aceptable |
|---|---|---|
| Validación | Filas válidas / total | 100 % en archivo sintético |
| Negocio | Oportunidades detectadas | ≥ 10 |
| Negocio | Impacto monetario esperado | > $1,000 en el dataset demo |
| Negocio | PdVs con al menos una acción | 5/5 |
| Estadístico | Lift máximo de la top-1 | > 5 |
| Performance | Validación (4500 filas) | < 5 s |
| Performance | Run analytics (4500 filas) | < 20 s |
| Performance | Optimal route (10 puntos) | < 30 s |
| Operación | Sin errores 5xx en flujo happy path | 0 |
| Trazabilidad | Audit en EVENTS por cada CREATE | 100 % |
| UX | Idioma del rationale | Español para usuario no técnico |
| UX | Errores de validación legibles | Sí, sin jerga técnica |

Si **todos** los umbrales se cumplen, el POC es promovible a una fase
siguiente (piloto con 1-2 clientes reales).

---

## 7. Limitaciones conocidas

| # | Limitación | Mitigación / próximo paso |
|---|---|---|
| 1 | INGEST/OPTIMIZATION/ANALYTICS no están deployados a AWS aún | Levantar local; deploy a Lambda es el paso siguiente al POC. |
| 2 | Optimization dibuja segmentos lineales, no polyline OSM road-aligned | Backend retorna node IDs; resolver lat/lng requiere extensión menor del servicio. |
| 3 | Demo solo en español | i18n queda para fase 2. |
| 4 | Sin filtrado colaborativo de PdV ni grafo de afinidad | Roadmap §9 — fase 2. |
| 5 | Forecast / Prophet aún no integrado | Roadmap §9 — capa predictiva, fase 2. |
| 6 | Sin multi-tenancy (un solo bucket S3 compartido) | Fase 3, cuando haya tracción. |
| 7 | LOCALIZATION no expuesto al producto SmartDecisions (solo a Binaria) | Decisión consciente; rutas usa OPTIMIZATION. |

---

## 8. Próximos pasos sugeridos (si el POC pasa)

1. **Deploy de los 3 servicios nuevos** (ingest/optimization/analytics)
   a AWS Lambda + API Gateway.
2. **Migrar config.js a las URLs reales** de los 3 nuevos.
3. **Piloto con 1 cliente** que tenga un Excel real de 6-12 meses.
4. **Multi-tenancy** (prefijos S3 por tenant + claim en JWT).
5. **Forecasting** con Prophet/statsmodels (paso natural sobre los
   mismos datasets).
6. **Filtrado colaborativo** PdV × producto (matriz coseno).
7. **Dashboards prediseñados** además de la tabla cruda actual.

---

## 9. Soporte

- **Bitácora de desarrollo del POC:** `POC_PROGRESS.md`
- **Documentación del producto:** `SMARTDECISIONS.md`
- **Estándares de código:** `CLAUDE.md`, `boilerplate.md`
- **Guion para reuniones comerciales:** `docs/DEMO_SCRIPT.md`
- **Contacto:** raforios@gmail.com
