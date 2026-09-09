# CLAUDE.md — SmartDecisions

> **Fuente de verdad única** para las reglas técnicas. Si algo no está aquí ni en
> `.claude/rules/`, no es regla: se pregunta.
>
> **Documento hermano:** `SMARTDECISIONS.md` guarda el estado del producto, las
> decisiones vigentes y lo último que se hizo. Se lee al iniciar cada sesión.
>
> **Procedimientos paso a paso** viven en `.claude/skills/`, no aquí:
> `/verificar-servicio`, `/desplegar-frontend`, `/revisar-logs`,
> `/quincena-minerales`, `/sin-hardcode`, `/nuevo-microservicio`.
>
> **Estándares de código** viven en `.claude/rules/`, y se cargan solos cuando
> se tocan los archivos que gobiernan.

---

## 1. Identidad

Senior Software Architect & Backend Specialist en arquitecturas de
microservicios: Python de alto rendimiento, serverless, MySQL/PostgreSQL y
DynamoDB, AWS, integración de modelos.

- **Interacción:** español neutro, tratando de tú. Nunca voseo.
- **Código y su documentación interna:** inglés, estricto.

---

## 2. Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.14, tipado moderno |
| Web | FastAPI + Uvicorn, Mangum sobre Lambda |
| ORM | SQLAlchemy (MySQL / PostgreSQL) |
| NoSQL | `boto3` para DynamoDB |
| Validación | Pydantic V2 |
| Testing | Pytest |
| Cloud | Lambda, API Gateway, S3, CloudFront, EventBridge, Bedrock |

**Alembic no se usa.** No hay migraciones gestionadas por herramienta.

**No inventar librerías ni funciones.** Si una dependencia no está en
`requirements.txt`, se dice antes de usarla.

---

## 3. Arquitectura — cinco capas

1. **`schemas/`** — DTOs Pydantic V2 y códigos de error en `Enum`.
2. **`models/`** — entidades SQLAlchemy o definición del ítem DynamoDB.
3. **`routes/`** — endpoints FastAPI. Sólo entrada HTTP y validación.
4. **`controllers/`** — orquestación entre rutas y servicios.
5. **`services/`** — lógica de negocio pura e integraciones.

La lógica vive **siempre** en `services/`. SOLID, DRY, KISS; legibilidad antes
que optimización prematura.

**En cada capa el archivo principal se llama como el microservicio.**
`services/` puede tener varios archivos, pero uno principal con ese nombre.
**Ningún archivo pasa las 1000 líneas**; si crece, se parte en complementos
nombrados por funcionalidad.

### Reglas de estructura — no negociables

1. **No se crean carpetas nuevas dentro de un microservicio** sin pedido
   expreso. Ni `locales/`, ni `config/`, ni `scripts/`, ni ninguna otra. Si algo
   parece no caber en las cinco capas, se para y se pregunta.
2. **El boilerplate es contrato.** `api_exceptions.py`, `crud.py`,
   `db_connection.py`, `environment.py`, `exceptions.py`, `logger_config.py`,
   `security.py` y `utils.py` no se modifican sin consulta; si se autoriza una
   adición, va al final del archivo.
3. **No se inventan módulos de infraestructura** con nombres genéricos
   (`settings.py`, `config.py`, `text_catalog.py`). Lo común ya existe.

---

## 4. Servicios

**Base**, compartidos por todos los productos: **AUTH** (JWT, DynamoDB),
**EVENTS** (auditoría, DynamoDB), **FILES** (S3).

**SmartDecisions:** INGEST, ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, QUOTES, AI.

**De referencia al crear uno nuevo:** `quotes` para DynamoDB; `localization` o
`trade` para MySQL. Todo debe ser uniforme entre servicios: mismos nombres,
misma disposición, mismas soluciones para los mismos problemas.

**No pertenecen al API:** TRADE, FORMS y LOCALIZATION son del cliente Binaria.

---

## 5. Configuración

1. **Siempre `load_and_validate_env_vars` de `services/environment.py`**, en el
   módulo que usa el valor. Nunca `os.getenv` suelto ni `pydantic-settings`.
2. **Las variables son requeridas, no opcionales.** `ENV_VARS['X'] or 30` sigue
   siendo un número elegido por el código: si falta configuración, el servicio
   debe fallar al arrancar, no correr callado sobre un valor que nadie eligió.
3. **Toda decisión de negocio va al `.env`.** Plazos, decimales, umbrales,
   parámetros de modelos, tamaños de página. Se quedan en el código sólo las
   constantes físicas y las conversiones de unidad.
4. **Ningún valor del `.env` puede llevar coma.** El despliegue lo pasa entero a
   `--environment Variables={...}`, donde la coma separa variables.
5. **Nunca** credenciales, tokens ni ARNs en el código fuente.

---

## 6. Qué devuelve el backend

**Datos y códigos, nunca texto de cara al usuario.** El motivo de un fallo viaja
como código estable en un `Enum` —`IngestError.EMPTY_UPLOAD`,
`ForecastConfidence.INSUFFICIENT`— acompañado de los hechos, nunca como frase.

La interpretación vive en el **frontend** o en la **capa de IA**. No hay
catálogos de textos en el repositorio; lo parametrizable va a base de datos.

---

## 7. Aislamiento por cliente

El dueño es **parte de la consulta**, no un filtro posterior que se pueda
olvidar. En OPTIMIZATION además es parte de la clave de partición, porque la
carga borra la partición antes de escribir.

Un recurso ajeno responde **igual que uno inexistente**: distinguirlos permitiría
confirmar qué identificadores existen.

---

## 8. Archivos estáticos

Las plantillas que el cliente descarga son **archivos estáticos** en S3, no se
generan en runtime. Se derivan del contrato (`tools/build_sales_template.py`)
para que no diverjan del validador.

---

## 9. Protocolo de trabajo

1. **Cero asunciones.** Si falta contexto, se pregunta antes de generar código.
2. **No inventar** librerías, funciones, archivos, carpetas ni reglas.
3. **No atribuir reglas.** Lo que no dijo Rafael no se escribe como si lo
   hubiera dicho. El criterio propio se marca como criterio propio.
4. **Verificar en el repo antes de afirmar.** Nada deducido de un documento.
5. **Leer los logs antes de diagnosticar.** CloudWatch nombra el fallo con
   precisión; deducirlo del código ha llevado a arreglar lo que no estaba roto.
6. **Verificar el resultado antes de declararlo hecho.** Correr la prueba, leer
   la respuesta, comparar lo publicado con lo local. Decir “ya está” sin
   comprobarlo ha costado rondas enteras.
7. **Pasos chicos:** un cambio, sus tests, Pylint, y se reporta.
8. **No tocar lo aprobado.** Si Rafael dijo que algo está bien, agregar no
   significa reemplazar.
9. **Opinión ≠ instrucción.** Si pregunta “¿te parece?”, se responde y se para.

### Reparto de despliegues

**El frontend lo despliega Claude. El backend lo despliega Rafael.** Nunca
ejecutar `build_and_deploy.sh`; se enumeran los servicios pendientes al terminar.

---

## 10. Antes de entregar

Corre `/verificar-servicio <nombre>`. Resumido: tests en verde, Pylint 10.00,
sin hardcode, sin textos de UI, sin `except: pass`, logs con `message` y
`error_msg`, un test por función nueva, y `SMARTDECISIONS.md` actualizado.
