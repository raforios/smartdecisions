# Mining Summit Service

Microservicio backend de la **Cumbre Nacional Minera**. Gestiona el ciclo
completo de participación del evento: acreditación masiva de participantes por
institución, asignación de asientos por eje temático, control de asistencia
diaria y generación de reportes. Expone una API REST protegida por JWT que
consume el panel de operación (frontend Vanilla JS sobre S3 + CloudFront).

---

## 1. Arquitectura

Construido con **Clean Architecture**: cada capa tiene una única responsabilidad
y depende solo de la capa inferior.

| Capa | Carpeta | Responsabilidad |
|------|---------|-----------------|
| Rutas | `routes/` | Entrada HTTP, validación de esquemas y control de acceso por rol. |
| Controladores | `controllers/` | Orquestación entre rutas y lógica de negocio. |
| Servicios | `services/` | Lógica de negocio, reglas del evento e integraciones. |
| Esquemas | `schemas/` | DTOs Pydantic v2 (request / response / query) y enumeraciones. |
| Modelos | `models/` | Forma de los documentos DynamoDB (`TypedDict`). |

**Stack:** Python 3.14 · FastAPI · Uvicorn · AWS Lambda (handler `Mangum`) ·
AWS DynamoDB (`boto3`) · Pydantic v2. La autenticación se delega al servicio
**AUTH**: este servicio solo valida el *Bearer token* y su claim `role`.

```text
mining_summit/
├── controllers/     # Orquestación entre rutas y servicios
├── models/          # Documentos DynamoDB (TypedDict)
├── routes/          # Endpoints FastAPI + control de acceso
├── schemas/         # DTOs Pydantic v2 y enumeraciones
├── services/        # Lógica de negocio y reglas del evento
├── tests/           # Pruebas unitarias (pytest)
├── main.py          # Punto de entrada FastAPI
├── requirements.txt
├── Dockerfile       # Imagen de build para Lambda
└── deploy.config    # Parámetros de despliegue
```

---

## 2. Modelo de datos

Todo el estado persiste en **DynamoDB** (no se usa base relacional). Las fechas
se calculan en la zona horaria configurada (`America/La_Paz`).

| Tabla | Clave de partición | Clave de orden | Descripción |
|-------|--------------------|----------------|-------------|
| `mining_summit_participants` | `ci` | — | Participante acreditado. Incluye estado de ciclo de vida (`ACTIVE` / `REPLACED` / `CANCELLED`). |
| `mining_summit_attendances` | `ci` | `attendance_date` | Asistencia diaria. La clave compuesta garantiza **una asistencia por persona por día**. |
| `mining_summit_institutions` | `id` | — | Catálogo oficial de instituciones, con su cupo asignado. |
| `mining_summit_aulas` | `code` | — | Aulas del campus. Cada aula guarda su capacidad y, opcionalmente, el eje temático al que está asignada. Un aula **pivote** (sin eje) queda de disposición libre hasta asignarse. |
| `mining_summit_load_batches` | `batch_id` | — | Bitácora de cada archivo cargado por el ETL (responsable + resultado). |

Las cinco tablas se aprovisionan por infraestructura, fuera del ciclo de vida de
la aplicación (ver [§7 Despliegue](#7-despliegue)).

---

## 3. Seguridad y roles

Todas las operaciones requieren el encabezado `Authorization: Bearer <jwt>`. El
control de acceso se basa en el claim **`role`** del token emitido por AUTH.

### Roles de acceso

| Rol | Perfil | Alcance |
|-----|--------|---------|
| `ADMIN` | Administrador | Acceso total: configuración, ETL, bajas y reemplazos, reportes y descargas. |
| `REGISTRATION` | Personal de acreditación | Busca por CI/QR, marca asistencia y da de alta participantes cuando la institución tiene cupo libre. Sin acceso a configuración ni reportes. |
| `REPORTS` | Consulta | Solo lectura: consulta reportes y descarga los archivos Excel. No registra ni modifica datos. |

### Roles de participante

Independientes de los roles de acceso, describen la función del asistente y se
imprimen en su credencial: `PARTICIPANTE`, `MODERADOR`, `VEEDOR`, `INVITADO`,
`ORGANIZADOR`, `PRENSA`, `FACILITADOR`, `SISTEMATIZADOR`, `COMUNICACION`,
`SISTEMAS` y `SIN_ROL`.

El rol **pertenece a la persona**, no a la institución: se elige en el formulario
de registro o se carga **por fila** en la columna `Rol` del Excel del ETL (acepta
etiquetas en español o los códigos, sin distinguir mayúsculas/acentos). La
institución ya **no** deriva ni impone rol.

**`SIN_ROL`** es el rol de las filas sin `Rol` asignado: la persona se registra
como dato maestro pero **no toma aula** (aunque traiga eje) hasta que se le asigne
un rol real. Para esas filas el eje deja de ser obligatorio.

---

## 4. Reglas de negocio

1. **Asiento por eje.** El participante elige un eje temático (1–6) en el Excel.
   Ese eje siempre se respeta; dentro de él, el motor lo asienta en el aula menos
   ocupada, distribuyendo de forma equitativa.
2. **Capacidad por eje.** Es la suma de las capacidades de sus aulas. Cuando se
   alcanza, el eje deja de admitir registros.
3. **Cupo por institución.** El ETL acredita únicamente a los primeros
   participantes que caben en el cupo; el resto queda como *no acreditado*.
4. **Asistencia diaria única.** Un mismo CI solo puede marcar asistencia una vez
   al día (un segundo intento responde `409 Conflict`). Solo se admite la
   asistencia de participantes `ACTIVE`.
5. **Baja y reemplazo.** La baja es lógica: se conserva el registro pero se
   excluye de los reportes y libera el asiento. Un reemplazo hereda el asiento
   del participante saliente, que queda marcado como `REPLACED`.

---

## 5. API

Prefijo común: `/v1/mining-summit`. La columna **Roles** indica quién puede
invocar cada endpoint (además de `ADMIN`, que siempre tiene acceso).

### Participantes

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `POST` | `/participants` | REGISTRATION | Alta on-the-fly; marca la primera asistencia y exige cupo libre si trae institución. Acepta `axis` para el asiento. |
| `GET` | `/participants` | REGISTRATION, REPORTS | Listado paginado. Por defecto solo `ACTIVE`; filtros por institución, eje, departamento, estado y rango de fechas. |
| `GET` | `/participants/{ci}` | REGISTRATION, REPORTS | Detalle por CI. |
| `PATCH` | `/participants/{ci}/deactivate` | — | Baja lógica: marca `CANCELLED` y libera el asiento. |
| `POST` | `/participants/{ci}/replace` | — | Reemplazo: el sustituto hereda el asiento; el saliente queda `REPLACED`. |

### Asistencias

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `POST` | `/attendances` | REGISTRATION | Marca asistencia diaria (solo participantes `ACTIVE`, una vez por día). |
| `GET` | `/attendances` | REGISTRATION, REPORTS | Listado filtrable por CI y rango de fechas. |

### Aulas y ejes

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `GET` | `/mesas` | autenticado | Aulas con su capacidad y eje, filtrable por eje. |
| `POST` | `/mesas` | — | Registra un aula nueva (código, bloque, ubicación, capacidad y **eje opcional**). Sin eje se crea como pivote (disposición libre). |
| `PATCH` | `/mesas/{code}` | — | Ajusta bloque, ubicación, capacidad y/o el eje de un aula (asignar una pivote a un eje). El código es fijo. |
| `DELETE` | `/mesas/{code}` | — | Elimina un aula de la asignación. |
| `GET` | `/axes` | autenticado | Ejes con su número de aulas y capacidad agregada. |

### Instituciones

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `GET` | `/institutions` | autenticado | Catálogo (orden alfabético) con rol y tipo de asiento derivados. |
| `POST` | `/institutions` | — | Crea una institución (id derivado del nombre si no se envía). |
| `GET` | `/institutions/{id}` | autenticado | Detalle, con **cupo usado y disponible** (`accredited_count`, `available_cupos`). |
| `PATCH` | `/institutions/{id}` | — | Edita nombre, sigla, categoría y/o cupo. |
| `PATCH` | `/institutions/{id}/cupos` | — | Atajo para ajustar solo el cupo. |
| `DELETE` | `/institutions/{id}` | — | Elimina una institución del catálogo. |

### ETL

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `POST` | `/etl/participants` | — | Carga un Excel de institución (`multipart/form-data`). Ver [§8](#8-operación). |

### Reportes

| Método | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| `GET` | `/reports/stats?group_by=department\|company` | REPORTS | Conteos y porcentajes por dimensión. |
| `GET` | `/reports/not-accredited` | REPORTS | Constancia de participantes no acreditados de todos los lotes. |
| `GET` | `/reports/participants.xlsx` | REPORTS | Descarga el reporte de participantes en Excel. |
| `GET` | `/reports/attendances.xlsx` | REPORTS | Descarga el reporte de asistencias en Excel. |

> Los endpoints marcados con **—** en la columna Roles son exclusivos de `ADMIN`.
> La especificación interactiva (Swagger) está disponible en `/docs`.

---

## 6. Configuración

Variables de entorno del servicio. Los secretos y credenciales nunca se
versionan; se inyectan por el entorno de ejecución.

**Requeridas**

| Variable | Descripción |
|----------|-------------|
| `SECRET_KEY`, `ALGORITHM` | Verificación de la firma del JWT emitido por AUTH. |
| `TARGET_TIMEZONE` | Zona horaria del evento (`America/La_Paz`). |
| `DYNAMODB_TABLE_NAME_PARTICIPANTS` | Tabla de participantes. |
| `DYNAMODB_TABLE_NAME_ATTENDANCES` | Tabla de asistencias. |
| `DYNAMODB_TABLE_NAME_INSTITUTIONS` | Tabla de instituciones. |
| `DYNAMODB_TABLE_NAME_AULAS` | Tabla de aulas. |
| `DYNAMODB_TABLE_NAME_LOAD_BATCHES` | Tabla de lotes del ETL. |
| `HOST`, `PORT` | Interfaz y puerto del servidor ASGI. |

**Opcionales**

| Variable | Descripción |
|----------|-------------|
| `APP_ENV` | Entorno lógico (`development` / `staging` / `production`). |
| `ROOT_PATH` | Prefijo de ruta cuando corre detrás de API Gateway. |
| `CORS_ALLOWED_ORIGINS` | Orígenes exactos adicionales (lista separada por comas). |
| `CORS_ALLOWED_ORIGIN_REGEX` | Patrón de orígenes permitidos. Por defecto cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo`. |
| `DYNAMODB_ENDPOINT_URL` | Endpoint alternativo de DynamoDB. Solo se usa para apuntar a una instancia distinta a la de AWS (p. ej. pruebas); en producción se omite. |

> La **región** de AWS la provee el propio entorno de ejecución (`AWS_REGION`),
> no una variable específica del servicio.

---

## 7. Despliegue

El servicio se empaqueta y despliega como **función AWS Lambda** (handler
`Mangum`) detrás de **API Gateway**, con **DynamoDB** como almacenamiento. Las
tablas se crean por infraestructura (CLI/IaC), de forma independiente al ciclo
de vida de la aplicación. Los parámetros de despliegue viven en `deploy.config`.

---

## 8. Operación

### 8.1 Sembrado de catálogos

Antes de la primera carga (o tras reiniciar las tablas) hay que poblar los
catálogos de instituciones y aulas:

```bash
python tools/mining_summit/import_institutions.py   # instituciones (matriz oficial)
python tools/mining_summit/seed_aulas.py            # aulas: capacidad + eje por aula
```

### 8.2 Carga de participantes (ETL)

Cada institución completa la plantilla
`templates/plantilla_registro_cumbre_minera.xlsx` (con la columna `Rol` por
persona) y la remite junto con los datos de un **responsable**. La carga se hace
contra el endpoint del ETL (rol `ADMIN`); la institución es un parámetro, por lo
que la columna «Institución» de la planilla es meramente informativa.

```bash
curl -X POST "$BASE_URL/v1/mining-summit/etl/participants" \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -F "institution_id=fencomin" \
  -F "responsible_name=Juana Perez" \
  -F "responsible_phone=70000000" \
  -F "file=@fencomin.xlsx"
```

El **rol va por fila** en la columna `Rol` del Excel (etiqueta en español o
código; p. ej. `Moderador` o `MODERADOR`). Una celda `Rol` vacía deja a la
persona en `SIN_ROL` (registrada sin aula). El campo `role` del `curl` es
**opcional** y solo actúa como valor por defecto para las filas con `Rol` vacía.

El proceso, fila por fila:

1. Resuelve el rol de la columna `Rol` (vacío → `SIN_ROL`; rol no reconocido →
   fila rechazada).
2. Valida los campos obligatorios (todos excepto el correo; el eje además es
   opcional cuando el rol es `SIN_ROL`).
3. Respeta el cupo de la institución: acredita solo a los que caben; el resto se
   reporta como no acreditado.
4. Resuelve el eje elegido (columna 1–6) y asigna el aula menos ocupada de ese
   eje. Con `SIN_ROL` no se asigna aula.
5. Registra el lote (responsable y resultado) y devuelve un resumen con los
   `accepted` y `rejected`.

La constancia consolidada de no acreditados está en
`GET /v1/mining-summit/reports/not-accredited`.

---

## 9. Desarrollo local

Para levantar el servicio localmente contra un DynamoDB en contenedor:

```bash
./dynamodb.sh                 # DynamoDB local + tablas (requiere Docker)
pip install -r requirements.txt
python main.py                # API en el puerto configurado; Swagger en /docs
```

Apunta el servicio al DynamoDB local exportando `DYNAMODB_ENDPOINT_URL`. Las
pruebas unitarias no requieren infraestructura (DynamoDB se simula con `moto`):

```bash
pytest
```
