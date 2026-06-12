# POC_PROGRESS.md — SmartDecisions POC

> Bitácora de trabajo del POC de **SmartDecisions** (empresa: **BaarSoft**).
> Mantenido por Claude entre sesiones para no perder contexto.
> Fuentes asociadas: `SMARTDECISIONS.md` (visión), `CLAUDE.md` (estándares).

---

## Plan maestro — 5 pasos del POC

1. **Cerrar la marca** — find-and-replace SmartBear→SmartDecisions, BearSoft→BaarSoft; aclarar TRADE/FORMS = Binaria; decidir mascota.
2. **Contrato Excel + validador + fix `routes.ipynb`** — plantilla `template_ventas_v1.xlsx`, parser pandas + validación pydantic/pandera, reutiliza FILES (S3). Fix de `/app/notebooks/routes.ipynb` como pre-req del paso 4.
3. **Motor afinidad × drop size (v0)** — microservicio `Analytics-Service` en Lambda, `mlxtend` + ML_FUNCTIONS, output accionable en $, persistencia en DynamoDB.
4. **Frontend demo estático (Vanilla JS) en S3+CloudFront — 3 módulos**
   - (a) Excel → oportunidades (del paso 3)
   - (b) Playground ML portando `frontend.ipynb` (regresión, gradiente, Z-score) con Chart.js
   - (c) Optimización de rutas portando `routes.ipynb` con Leaflet+OSM
5. **Empaquetar pitch técnico** — datos sintéticos, guion de demo 5 min, README "cómo evaluar el POC".

**Dependencias:** 1 → 2 → 3 → 4 → 5. Pasos 1 y 2 paralelizables.

**Infra confirmada:** CloudFront + S3 (frontend), Lambda + API Gateway (backend), DynamoDB (datos, sin RDS por presupuesto $0).

---

## Paso 1 — Cerrar la marca

**Estado:** COSMÉTICO COMPLETO — pendientes 3 decisiones estructurales del usuario.

**Cambios aplicados (2026-06-11):**

| Archivo | Cambio |
|---|---|
| `app/CLAUDE.md` | Título `SmartBear API` → `SmartDecisions API` |
| `app/SMARTDECISIONS.md` | Nota de marca reescrita (BaarSoft empresa, SmartDecisions producto, aclaración explícita TRADE/FORMS = Binaria); contexto histórico ("el artifact original decía...") preservado intencionalmente |
| `app/services/{auth,events,events_mysql,files,forms,localization,mining_summit,ml_functions,planning,supplies,trade}/main.py` + `api/main.py` | Metadata `'Owner': f'BearSoft …'` → `'BaarSoft …'` (12 archivos) |
| `app/frontend/main.py` + `pages/{load_file,optimization,dashboard,content_generator}.py` + `services/{rest,load_data}.py` | Streamlit titles, `page_title`, docstrings y comentarios `SmartBear` → `SmartDecisions` |
| `app/notebooks/lib/{rest,frontend_functions}.py` | Docstrings `SmartBear API` → `SmartDecisions API` |
| `app/notebooks/routes.ipynb` | Markdown cell `## Login into SmartBear API` → `SmartDecisions API` |
| `app/services/ci/api/start.sh` | Comentario y echo descriptivos (rutas del filesystem preservadas) |
| `app/services/supplies/README.md` + `app/demo/supplies/README.md` + `app/services/mining_analysis/README.md` + `boilerplate.md` | Texto descriptivo "ecosistema/arquitectura/proyecto SmartBear (BearSoft)" → "SmartDecisions (BaarSoft)" |

**Referencias preservadas intencionalmente (no tocar):**
- ~37 refs en paths absolutos del filesystem (`/Users/rafael/Work/projects/back/SmartBear/...`) en CI scripts, READMEs de auth/files/ml_functions y Postman collections → son la ruta física del directorio.
- 15 refs en outputs de tracebacks dentro de celdas ejecutadas en `routes.ipynb`, `frontend.ipynb`, `rutas_optimizadas.ipynb` → se regeneran al re-ejecutar el notebook; no editar JSON manualmente.
- 5 refs en este `POC_PROGRESS.md` y 3 en `SMARTDECISIONS.md` → documentación histórica del cambio.

**Verificación segura:**
- `deploy.config` revisado: **no contiene "smartbear" / "bearsoft"** → no hay recursos AWS (Lambda/S3/DynamoDB) cuyo nombre romperíamos al renombrar; ningún redeploy obligado.

**Pendiente de decisión del usuario para cerrar el paso 1:**
1. **Renombrar el directorio raíz `/SmartBear/` → `/SmartDecisions/`?** Requiere `git mv` + actualizar todos los paths absolutos en CI scripts y READMEs (~37 ocurrencias). Riesgo: scripts de deploy locales rotos hasta que se corrijan.
2. **Mascota:** ¿nueva, ninguna, o mantener el oso reinterpretado?
3. **Portal HTML landing:** ¿existe ya en algún lado del repo (no encontré landing dark-theme; sólo `/frontend/index.html` que es test de geolocalización y `/app/demo/*.html` que son del CMS minería)? Si está en otro repo o solo en artifact de Claude.ai, hay que decidir dónde vivirá.

---

## Memoria persistente vinculada

- `project_naming.md` — empresa BaarSoft / producto SmartDecisions / TRADE-FORMS son Binaria
- `project_deployment_strategy.md` — sin RDS; default DynamoDB+Lambda+S3/CloudFront
- `reference_deployed_services.md` — AUTH/FILES/EVENTS en API Gateway/Lambda
- `project_notebooks_as_frontend_spec.md` — frontend.ipynb + routes.ipynb son spec del frontend, no scratch pads
- `project_demo_portal_roadmap.md` — portal demo, CMS público en Dynamo

---

## Bitácora de sesiones

### 2026-06-11 — Inicio del POC
- Definido el plan de 5 pasos (revisado con notebooks como spec del frontend).
- Confirmada nomenclatura: empresa **BaarSoft**, producto **SmartDecisions**.
- Confirmada infra: CloudFront + S3 (frontend), Lambda + API Gateway (servicios).
- Paso 1 ejecutado: ~30 ocurrencias cosméticas reemplazadas (SmartBear→SmartDecisions, BearSoft→BaarSoft) en docs, código Python de servicios y frontend, scripts CI y READMEs.
- `deploy.config` verificado sin referencias a la marca antigua → no hay recursos AWS por renombrar.
- 3 decisiones estructurales pendientes (ver sección Paso 1).
