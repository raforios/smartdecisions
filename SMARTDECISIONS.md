# SMARTDECISIONS.md — Plataforma de Inteligencia Comercial y Analítica (SaaS)

> Archivo de contexto del proyecto para **Claude CLI**. Define el estado real del
> sistema, los objetivos y la forma de trabajar. El foco actual es **técnico**.
>
> USO: en la terminal, indícale a Claude "lee SMARTDECISIONS.md" para cargar el contexto.
>
> ⚠️ NOMBRE: empresa **BaarSoft**; producto / API / SaaS **SmartDecisions**.
> SmartBear fue descartado y ya no es relevante.
> "TRADE" y "FORMS" NO son parte de SmartDecisions: son módulos exclusivos del
> cliente **Binaria** y viven en este monorepo solo por conveniencia.
> Nota: "Smart Decisions" es una combinación genérica de palabras en inglés, por lo
> que el dominio/marca exactos podrían no estar disponibles o ser difíciles de
> defender legalmente. Verificar disponibilidad antes de lanzamiento público.

---

## 1. Qué es (en una frase)

Plataforma SaaS de microservicios que convierte datos de ventas y distribución en
**decisiones accionables**: predicción, optimización de rutas, afinidad de
productos y recomendaciones de venta — accesible incluso para micro y pequeñas
empresas que solo cargan un Excel, sin necesidad de un ERP.

**Concepto diferenciador del motor comercial:**
```
Afinidad × Drop Size = Oportunidad Comercial Real
```

---

## 2. Restricciones REALES del proyecto (leer primero)

- **Presupuesto: USD 0.** No hay dinero, solo trabajo de personas que apoyan.
  Toda decisión técnica debe priorizar **free-tier / open source / costo cero**.
- **Equipo:** trabajo voluntario, medio tiempo. Mantener el alcance realista.
- **Despliegue:** debe poder publicarse en la web **sin incurrir en costos**
  (ver sección 7: opciones de hosting gratuito).
- **Mercado objetivo:** micro y pequeñas empresas. El producto y su precio (cuando
  llegue) deben ser accesibles. Evitar sobre-ingeniería y dependencias caras.

---

## 3. Objetivos funcionales de la plataforma

1. Ayuda a la **toma de decisiones**.
2. **Optimización de rutas** para la distribución.
3. **Predicción de ventas**.
4. **Proyecciones**.
5. **Afinidad de productos** (market-basket / reglas de asociación: soporte,
   confianza, lift — "quien compra A tiende a comprar B"). Lib: `mlxtend`.
6. **Filtrado colaborativo por PdV** (matriz PdV × producto, similitud coseno /
   item-item CF — "PdV parecidos al tuyo venden bien X").
7. **Grafo de afinidad** (opcional, avanzado): productos/PdV como nodos; detección
   de comunidades (espíritu de label propagation / COPRA). Lib: `networkx`.
   > Nota: "COPRA" en la literatura es detección de comunidades en grafos, NO un
   > método de afinidad de ventas. Usar solo como nombre interno, no como
   > afirmación técnica ante terceros.
8. **Ponderación por Drop Size**: recomendación × tamaño de pedido esperado →
   prioriza oportunidades de mayor valor monetario real. **Diferenciador clave.**
9. **Capa predictiva**: forecast de demanda por SKU/zona; detección de caídas de
   consumo para reactivación. Lib: `statsmodels` / `Prophet`.

---

## 4. Estado ACTUAL del sistema (microservicios ya funcionando)

Arquitectura de microservicios en Python (FastAPI, Clean Architecture, AWS).
Todos validan el header `Authorization` contra AUTH.

| Servicio | Nombre | Función | Datos / Notas |
|----------|--------|---------|---------------|
| 🔐 **AUTH** | Auth-Handler-Service | Genera JWT, gestiona usuarios y login | Todos los demás dependen de él |
| 🔔 **EVENTS** | Events-Service | Auditoría, logs de uso, trazabilidad | DynamoDB (alta concurrencia); recibe logs vía `utils.py` |
| 📁 **FILES** | File-Handler-Service | Interfaz con AWS S3 | Subida, lectura, borrado, URLs pre-firmadas |
| 🧠 **ML_FUNCTIONS** | ML-Functions-Service | Motor de cálculo matemático/estadístico | Regresión lineal/logística, gradiente descendente, normalización Z-score |
| 🗺️ **LOCALIZATION** | Localization-Service | Rutas (planificadas vs ejecutadas), asistencia (check-in/out) | Provee datos geográficos |

> Servicios mencionados en planes previos (FORMS, TRADE) pueden incorporarse;
> confirmar su estado real en el repo antes de asumirlos. (TRADE fue marcado como
> inestable anteriormente.)

### Notebooks de prueba
- `/app/notebooks/frontend.ipynb` — **funcional**: ejemplos para la mayoría de
  endpoints del módulo de Machine Learning.
- `/app/notebooks/routes.ipynb` — **incompleto**: optimización de rutas; necesita
  ajustes para funcionar correctamente con los endpoints del servicio. **Tarea pendiente.**

### Frontend actual
- `/app/frontend` — pruebas hechas con **Streamlit**.
- Decisión abierta: (a) mantener y mejorar Streamlit, o (b) reemplazar por
  **Vanilla JavaScript**. Criterio: lo que permita **publicar gratis** y sea
  mantenible por el equipo. (Streamlit puro es difícil de hostear gratis con
  backend; un front estático en Vanilla JS es trivial de publicar gratis — ver §7.)

---

## 5. Modo de uso para usuarios finales (micro/pequeña empresa y DEMO)

Objetivo: que cualquiera pruebe el valor **sin ERP y sin fricción**.

1. El usuario entra a la interfaz web (nada que instalar).
2. Descarga una **plantilla Excel** con el formato esperado.
3. Sube su archivo de ventas (`.xlsx` / `.csv`) — usa el servicio **FILES** (S3).
4. La plataforma procesa (ML_FUNCTIONS + motor de afinidad) y muestra análisis,
   predicciones y recomendaciones en pantalla, con opción de descargar.

**Contrato de datos mínimo del Excel** (una fila = una línea de venta):

| Columna | Tipo | Obligatorio | Notas |
|---------|------|-------------|-------|
| `id_pedido` | texto/int | Sí | Agrupa productos de una misma venta/visita |
| `fecha` | fecha | Sí | ISO o dd/mm/aaaa |
| `id_punto_venta` | texto/int | Sí | Identifica al cliente/tienda |
| `nombre_pdv` | texto | No | Para la UI |
| `zona` | texto | No | Análisis por zona / rutas |
| `id_producto` | texto/int | Sí | SKU |
| `nombre_producto` | texto | No | Para la UI |
| `cantidad` | número | Sí | Unidades |
| `precio_unitario` | número | No | Necesario para Drop Size en $ |
| `monto_total` | número | No | Si falta, se calcula cantidad × precio |

- Mínimo para el motor: `id_pedido`, `id_punto_venta`, `id_producto`, `cantidad`.
- Validar al subir y dar **mensajes de error claros** (el usuario no es técnico).
- Proveer la plantilla `.xlsx` descargable.

> Regla de diseño: **el motor de análisis es el mismo** en modo Excel y en modo
> integración (API/ERP). Solo cambia la capa de ingesta. Mantener el core
> desacoplado de la fuente de datos (Excel y ERP = adaptadores intercambiables).

---

## 6. Stack tecnológico

- **Lenguaje:** Python 3.12+ (alinear con el estándar del repo).
- **API:** FastAPI + Pydantic V2. Clean Architecture + SOLID.
- **ML / Datos:** pandas, scikit-learn, `mlxtend` (afinidad), `networkx` (grafo),
  `statsmodels` / `Prophet` (forecast). Reusar **ML_FUNCTIONS** donde aplique.
- **Optimización de rutas:** evaluar `OR-Tools` (Google, open source) o heurísticas
  propias; conectar con **LOCALIZATION**.
- **Ingesta Excel:** `pandas.read_excel` / `openpyxl`; validación con `pydantic`/`pandera`.
- **Almacenamiento:** S3 vía **FILES**; DynamoDB para EVENTS. Postgres si hace
  falta relacional (preferir free-tier).
- **Frontend:** decisión §4. Si Vanilla JS → estático, publicable gratis.
- **Infra:** Docker; AWS (free-tier estricto mientras presupuesto = 0).
- **Tests:** Pytest.

---

## 7. Despliegue SIN COSTO (requisito duro)

Opciones gratuitas a evaluar (confirmar límites vigentes al implementar):

- **Frontend estático (Vanilla JS / HTML):** GitHub Pages, Cloudflare Pages,
  Netlify o Vercel (tier gratuito). Trivial y gratis. ← recomendado para el portal/demo.
- **Backend (FastAPI):** opciones con free-tier como Render, Railway, Fly.io, o
  AWS Lambda + API Gateway (serverless, paga por uso, casi nulo a bajo volumen).
- **Notebooks/PoC:** Hugging Face Spaces o Streamlit Community Cloud (gratis) si
  se mantiene Streamlit para demos rápidas.
- **Regla:** ningún componente debe requerir pago para el MVP. Documentar el
  costo $0 en cada decisión de despliegue.

---

## 8. Portal web (artifact existente)

Existe un portal HTML (marca a actualizar a "SmartDecisions / BaarSoft"; el
artifact original decía "BearSoft / SmartBear"). Es una landing de una sola página, dark theme, con
secciones: hero, nosotros, servicios, producto, cómo funciona, contacto
(formulario→mailto). Stack: HTML+CSS+JS vanilla, sin dependencias → **ya es
publicable gratis** (§7). El artifact traía un oso 🐻 como mascota (de "Bear"); con
"SmartDecisions" ese oso pierde sentido — decidir si se mantiene una mascota y cuál.

Tareas sobre el portal:
- [ ] Renombrar marca SmartBear/BearSoft → SmartDecisions/BaarSoft (logo, textos, footer).
- [ ] Revisar la mascota: el oso ya no corresponde; decidir si hay mascota nueva o ninguna.
- [ ] Ajustar el mensaje al nuevo enfoque (Excel self-service para micro/pequeña empresa).
- [ ] Conectar el botón "demo" al flujo real de carga de Excel cuando exista.
- [ ] Mantener el formulario de contacto vía `mailto` (cero costo de backend).

---

## 9. Roadmap técnico (presupuesto $0, medio tiempo)

### Fase 0 — Consolidar lo que existe + demo de valor (PRIORIDAD)
- [ ] Arreglar `/app/notebooks/routes.ipynb` (optimización de rutas con endpoints reales).
- [ ] Congelar el formato de plantilla Excel (§5) y construir parser + validador.
- [ ] Motor de afinidad v0 (market-basket + drop size) reutilizando ML_FUNCTIONS.
- [ ] Flujo demo end-to-end: subir Excel → análisis + recomendaciones → descargar.
- [ ] Decidir frontend (Streamlit vs Vanilla JS) según hosting gratis.

### Fase 1 — Publicar gratis y validar
- [ ] Desplegar el portal (GitHub/Cloudflare Pages).
- [ ] Desplegar backend en free-tier; demo accesible públicamente.
- [ ] Probar con datos reales y con Excel de ejemplo de una micro empresa.

### Fase 2 — Producto
- [ ] Filtrado colaborativo por PdV; grafo de afinidad (si aporta valor).
- [ ] Capa predictiva (forecast, detección de caídas).
- [ ] Multi-tenancy y planes solo cuando haya tracción.

---

## 10. Principios de trabajo para Claude CLI en este repo

- **Costo cero primero:** no proponer nada que requiera pago para el MVP. Si algo
  necesita pago, decirlo explícito y ofrecer alternativa gratis.
- **Partir de lo que existe:** reutilizar AUTH, EVENTS, FILES, ML_FUNCTIONS,
  LOCALIZATION. Confirmar en el repo antes de reescribir.
- **El motor es uno solo;** Excel/API/ERP son adaptadores de ingesta. No acoplar
  la lógica de análisis a la fuente.
- **Empezar simple:** afinidad + drop size end-to-end antes de grafo o predicción.
- **Llamar a las técnicas por su nombre real** en código y documentación.
- **Output accionable** (oportunidad en $), no solo métricas.
- **Validación robusta y mensajes claros:** el usuario final no es técnico.
- **Parquedad de dependencias:** justificar cada una; preferir open source maduro.
- Antes de tareas de archivos/datos, revisar el estado real en el repo y notebooks.
