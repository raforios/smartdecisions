# Despliegue de la plataforma BearSoft en AWS

Esta carpeta despliega los microservicios de BearSoft (los servicios base, SmartDecisions y SmartBilling) como funciones **AWS Lambda** detrás de **API Gateway HTTP**, y los publica bajo un solo dominio: **`https://api.bearsoft.com.bo`**.

> Los microservicios de clientes (TRADE, FORMS, LOCALIZATION, CMS, MINING_SUMMIT) **no** se despliegan con esta guía. La carpeta `ci/` de arriba (con ALB, EC2 y RDS) es de BINARIA y tampoco se usa aquí.

---

## Índice

1. [Qué hay en esta carpeta](#1-qué-hay-en-esta-carpeta)
2. [Antes de empezar (una sola vez por computadora)](#2-antes-de-empezar-una-sola-vez-por-computadora)
3. [Caso A — Desplegar todo desde cero](#3-caso-a--desplegar-todo-desde-cero)
4. [Caso B — Desplegar uno o varios microservicios](#4-caso-b--desplegar-uno-o-varios-microservicios)
5. [Caso C — Cambios que NO necesitan reconstruir Docker](#5-caso-c--cambios-que-no-necesitan-reconstruir-docker)
6. [Cómo comprobar que un despliegue salió bien](#6-cómo-comprobar-que-un-despliegue-salió-bien)
7. [Problemas conocidos y cómo resolverlos](#7-problemas-conocidos-y-cómo-resolverlos)
8. [Referencia: el orden de despliegue y por qué](#8-referencia-el-orden-de-despliegue-y-por-qué)

---

## 1. Qué hay en esta carpeta

| Archivo | Para qué sirve | ¿Lo ejecutas tú? |
|---|---|---|
| `start.sh` | **El punto de entrada.** Despliega todo, o una parte, en el orden correcto. | **Sí, casi siempre este.** |
| `build_and_deploy.sh` | Despliega **un** microservicio: construye el paquete en Docker, lo sube a S3, crea o actualiza el Lambda y su API Gateway. | Normalmente no: `start.sh` lo llama. |
| `create_dynamodb_tables.sh` | Crea las tablas DynamoDB que faltan. No borra ni modifica las que existen. | Sólo si agregas una tabla nueva. |
| `create_schedules.sh` | Crea las tareas programadas (por ejemplo, la sincronización diaria del tipo de cambio). | No: `start.sh` lo llama. |
| `setup_api_domain.sh` | Configura `api.bearsoft.com.bo`: certificado, dominio y un mapeo por servicio. | Sólo la primera vez o si algo del dominio falla. |
| `update_service_urls.sh` | Cambia en los `.env` las direcciones con las que los servicios se llaman entre sí. | No: `start.sh --urls` lo llama. |

Cada microservicio tiene, en su propia carpeta (`services/<servicio>/`), dos archivos que estos scripts leen:

- **`deploy.config`**: cómo se despliega (nombre del Lambda, memoria, tiempo máximo, nombre del API, tabla principal, CORS…).
- **`.env`**: la configuración del servicio. **Viaja completa a las variables del Lambda** en cada despliegue.

---

## 2. Antes de empezar (una sola vez por computadora)

Haz estos pasos la primera vez que vayas a desplegar desde una computadora nueva.

### 2.1. Instalar las herramientas

1. **Docker Desktop.** Descárgalo de <https://www.docker.com/products/docker-desktop/>, instálalo y ábrelo. Debe quedar abierto (el ícono de la ballena en la barra) mientras despliegas.
2. **AWS CLI versión 2.** En una Mac con chip Apple instala la versión **nativa (arm64)**: desde macOS 27 los binarios para Intel dan el error `Bad CPU type`.
   ```bash
   aws --version        # debe responder aws-cli/2.x
   ```
3. **jq** (lo usa `build_and_deploy.sh`):
   ```bash
   brew install jq
   jq --version
   ```

### 2.2. Configurar las credenciales de AWS

Todos los scripts usan el perfil **`deploy_ml`**.

1. Pide a tu responsable las claves de acceso (Access Key ID y Secret Access Key) del usuario de despliegue. **Nunca** las guardes en el repositorio.
2. Configúralas:
   ```bash
   aws configure --profile deploy_ml
   # AWS Access Key ID:     <la que te dieron>
   # AWS Secret Access Key: <la que te dieron>
   # Default region name:   us-east-1
   # Default output format: json
   ```
3. Comprueba que funcionan:
   ```bash
   aws sts get-caller-identity --profile deploy_ml
   ```
   Debe responder la cuenta `732887652913`. Si da error, las claves están mal copiadas.

### 2.3. Ubicarte en la carpeta correcta

Todos los comandos de esta guía se ejecutan **desde esta carpeta**:

```bash
cd /ruta/al/repositorio/app/services/ci/api
```

---

## 3. Caso A — Desplegar todo desde cero

Úsalo cuando la cuenta de AWS está vacía, o cuando quieres asegurarte de que **todo** quede desplegado y alineado. Es seguro repetirlo: lo que ya existe se actualiza, no se duplica.

**Tiempo aproximado:** de 40 a 60 minutos (cada servicio se construye en Docker).

### Paso 1. Revisar los `.env`

Para cada servicio (`auth`, `events`, `files`, `ml_functions`, `ingest`, `quotes`, `analytics`, `optimization`, `mining_analysis`, `ai`, `billing`):

1. Abre `services/<servicio>/.env`.
2. Comprueba que **ningún valor tenga comas (`,`) ni llaves (`{` `}`)**. El despliegue pasa el `.env` a AWS en un formato donde la coma separa variables y la llave abre una estructura: un valor así rompe el despliegue a mitad de camino. Si necesitas una plantilla de URL, usa `%s` en lugar de `{nombre}`.

### Paso 2. Ejecutar el despliegue completo

```bash
./start.sh
```

El script hace, en este orden (ver la [sección 8](#8-referencia-el-orden-de-despliegue-y-por-qué)):

1. Crea las tablas DynamoDB que falten.
2. Despliega AUTH, EVENTS, FILES y ML_FUNCTIONS.
3. Despliega INGEST y QUOTES.
4. Despliega ANALYTICS, OPTIMIZATION, MINING_ANALYSIS y AI.
5. Despliega BILLING.
6. Crea las tareas programadas.
7. Configura el dominio `api.bearsoft.com.bo`.

No cierres la terminal mientras corre. Al final debe decir **`Proceso de despliegue finalizado. ✅`**.

### Paso 3. Configurar el dominio (sólo la primera vez en una cuenta nueva)

El paso 7 puede detenerse con un **AVISO** la primera vez. Es normal: el dominio necesita dos registros en **Cloudflare**, que se agregan a mano.

**3a. Si el aviso dice "valida el certificado en Cloudflare":**

1. Ejecuta:
   ```bash
   ./setup_api_domain.sh
   ```
2. Copia las dos columnas que imprime después de "Agrega este CNAME en Cloudflare". La primera es el **nombre**, la segunda el **destino**.
3. En Cloudflare, entra al dominio `bearsoft.com.bo` → **DNS** → **Add record**:
   - **Type:** `CNAME`
   - **Name:** la primera columna, **sin** `.bearsoft.com.bo.` al final.
   - **Target:** la segunda columna, **sin** el punto final.
   - **Proxy status:** **apagado** (nube gris, "DNS only").
4. Guarda y espera unos 5 minutos.
5. Vuelve a ejecutar `./setup_api_domain.sh` hasta que diga **"Certificado emitido."**

**3b. Cuando el certificado está emitido:**

1. El script imprime **"Destino para el CNAME 'api' en Cloudflare"**, seguido de una dirección del tipo `d-xxxxxxxx.execute-api.us-east-1.amazonaws.com`.
2. En Cloudflare agrega otro registro:
   - **Type:** `CNAME`
   - **Name:** `api`
   - **Target:** esa dirección.
   - **Proxy status:** **apagado** (nube gris). El certificado lo pone AWS, no Cloudflare.
3. Espera unos minutos y ejecuta otra vez `./setup_api_domain.sh`.
4. Al final, la **prueba de humo** debe mostrar las tres rutas con `HTTP 401 (OK)`. El 401 es lo correcto: significa que la petición **llegó al servicio**, y el servicio la rechazó porque no lleva token.

### Paso 4. Pasar las direcciones internas al dominio (sólo la primera vez)

Cuando la prueba de humo del paso 3 da 401 en todo:

```bash
./start.sh --urls
```

Esto cambia en los `.env` las direcciones con las que los servicios se llaman entre sí (`EVENTS_SERVICE_URL`, `FILES_SERVICE_URL`, `INGEST_SERVICE_URL`, `QUOTES_SERVICE_URL`) a `https://api.bearsoft.com.bo`, y vuelve a publicar **sólo la configuración** de esos servicios, sin reconstruirlos.

> El portal web (`portal/demo/js/config.js`) se actualiza aparte. Los despliegues de frontend no van en esta guía.

### Paso 5. Comprobar

Sigue la [sección 6](#6-cómo-comprobar-que-un-despliegue-salió-bien).

---

## 4. Caso B — Desplegar uno o varios microservicios

Úsalo cuando cambiaste el **código** de uno o varios servicios (archivos `.py` o `requirements.txt`).

**Tiempo aproximado:** de 3 a 6 minutos por servicio.

### Paso 1. Comprobar el servicio antes de desplegar

Desde la raíz del repositorio (`app/`), para cada servicio que vas a desplegar:

```bash
python tools/verify_service.py services/<servicio>
```

Debe terminar en **`ALL PASS`**. Si dice `FAILED`, **no despliegues**: corrige primero.

### Paso 2. Desplegar

Vuelve a `services/ci/api` y escribe los nombres de las carpetas de los servicios, separados por espacio:

```bash
# Un servicio
./start.sh --redeploy ingest

# Varios servicios
./start.sh --redeploy ingest optimization analytics
```

- **No importa en qué orden los escribas**: el script los despliega siempre en el orden correcto (base primero, después los dueños de datos, después el resto).
- Al terminar, el script revisa el dominio y corrige el mapeo si algún API cambió.

Los nombres válidos son los de las carpetas: `auth`, `events`, `files`, `ml_functions`, `ingest`, `quotes`, `analytics`, `optimization`, `mining_analysis`, `ai`, `billing`.

### Paso 3. Si agregaste una tabla DynamoDB nueva

1. Agrégala a la lista `TABLES` de `create_dynamodb_tables.sh`, con el formato `"nombre:clave:S"` o `"nombre:clave_particion:S:clave_orden:S"`.
2. Agrega su nombre al `.env` del servicio que la usa.
3. Ejecuta **antes** de desplegar el servicio:
   ```bash
   ./create_dynamodb_tables.sh
   ```

### Paso 4. Comprobar

Sigue la [sección 6](#6-cómo-comprobar-que-un-despliegue-salió-bien).

### Desplegar todos los servicios sin tocar tablas ni tareas programadas

```bash
./start.sh --redeploy
```

---

## 5. Caso C — Cambios que NO necesitan reconstruir Docker

Si **no cambiaste código** (ningún `.py` ni `requirements.txt`), no hace falta reconstruir el paquete en Docker, que es la parte lenta. Hay tres situaciones.

### C1. Cambiaste un valor del `.env` (configuración del servicio)

Ejemplos: un umbral de negocio, el nombre de una tabla, un tiempo de espera.

1. Edita `services/<servicio>/.env`. Recuerda: **sin comas ni llaves** en los valores.
2. Publica sólo la configuración:
   ```bash
   ./build_and_deploy.sh --path ../../<servicio> --skip-code-update --skip-table-creation
   ```
   Ejemplo:
   ```bash
   ./build_and_deploy.sh --path ../../analytics --skip-code-update --skip-table-creation
   ```
3. Tarda menos de un minuto. El Lambda usa el código que ya tenía, con la configuración nueva.

### C2. Cambiaste el CORS de un servicio (por ejemplo, para permitir PATCH)

El CORS de **cada** API se declara en el `deploy.config` de **su** servicio:

```bash
CORS_ALLOW_METHODS="GET,POST,PUT,PATCH,DELETE,OPTIONS"
```

- Hoy lo declaran AUTH, INGEST, OPTIMIZATION y BILLING, que son los que tienen rutas `PATCH`.
- Un servicio **sin** esa variable conserva el CORS que ya tiene: el despliegue no lo toca.

Para aplicar un cambio:

1. Edita la línea `CORS_ALLOW_METHODS` del `deploy.config` del servicio.
2. Publica sin reconstruir:
   ```bash
   ./build_and_deploy.sh --path ../../<servicio> --skip-code-update --skip-table-creation
   ```
3. Comprueba el resultado:
   ```bash
   aws apigatewayv2 get-apis --profile deploy_ml --region us-east-1 \
     --query "Items[].[Name,join(',',CorsConfiguration.AllowMethods)]" --output table
   ```

### C3. Cambiaste las direcciones entre servicios o el dominio

```bash
./start.sh --urls
```

Sólo funciona si el dominio responde (la prueba de humo da 401). Si no responde, no cambia nada y lo dice.

---

## 6. Cómo comprobar que un despliegue salió bien

Haz las tres comprobaciones. **Un despliegue no está terminado hasta comprobarlo.**

**1. El Lambda se actualizó ahora.** La fecha debe ser de hace pocos minutos (está en hora UTC, Bolivia es UTC−4):

```bash
aws lambda get-function-configuration --profile deploy_ml --region us-east-1 \
  --function-name <nombre-del-lambda> --query "[LastModified,LastUpdateStatus,CodeSize]"
```

Los nombres de los Lambda están en `FUNCTION_NAME` de cada `deploy.config` (por ejemplo, `ingest-handler-service`). El estado debe ser `Successful`.

**2. No hay errores al arrancar.** Revisa los registros de los últimos 15 minutos:

```bash
aws logs tail /aws/lambda/<nombre-del-lambda> --profile deploy_ml --region us-east-1 \
  --since 15m --filter-pattern "?ERROR ?Traceback"
```

Si no imprime nada, está bien. Un error típico al arrancar es una variable faltante en el `.env`: el servicio **se niega a arrancar** a propósito, y el registro dice cuál falta.

**3. El servicio responde por el dominio.** Sin token debe responder `401`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.bearsoft.com.bo/v1/ingest/datasets
```

---

## 7. Problemas conocidos y cómo resolverlos

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `Bad CPU type in executable` al usar `aws` | AWS CLI para Intel en una Mac con chip Apple | Reinstala AWS CLI v2 nativo (arm64). |
| `Cannot connect to the Docker daemon` | Docker Desktop cerrado | Ábrelo y espera a que la ballena quede quieta. |
| El despliegue termina bien pero el Lambda sigue con el código viejo | Con red lenta, la subida a S3 puede devolver "éxito" sin haber subido | Compara `LastModified` y `CodeSize` (sección 6.1). Si no cambiaron, repite el despliegue con una red estable. |
| El despliegue se corta al pasar las variables de entorno | Un valor del `.env` tiene coma o llave | Quita la coma o la llave (sección 3, paso 1) y repite. |
| El servicio no arranca: `Required environment variable "X" is not configured.` | Falta una variable en el `.env` | Agrégala y publica la configuración (caso C1). |
| El navegador da `Failed to fetch` en un botón que guarda | El API no permite ese método en CORS (por ejemplo, PATCH) | Caso C2. |
| La prueba de humo del dominio da `000` | El registro `api` de Cloudflare todavía no existe o no se propagó | Revisa el registro (sección 3, paso 3b) y espera unos minutos. |
| La prueba de humo da `404` | El servicio recibe la ruta sin el prefijo `/v1/<servicio>` | `setup_api_domain.sh` pasa cada API al formato de evento 1.0, que conserva la ruta completa. Vuelve a ejecutarlo. |
| La prueba de humo da `403` | No hay mapeo para esa ruta | Revisa la lista `MAPPINGS` de `setup_api_domain.sh` y vuelve a ejecutarlo. |
| Error de `pydantic_core` al arrancar el Lambda | Paquete compilado para otra arquitectura | `build_and_deploy.sh` ya construye para `linux/amd64`. Si aparece, revisa que nadie haya cambiado esa línea. |

Si algo falla y no está en la tabla: **lee primero los registros de CloudWatch** (sección 6.2). Casi siempre dicen exactamente qué pasó.

---

## 8. Referencia: el orden de despliegue y por qué

| # | Qué | Por qué en este lugar |
|---|---|---|
| 1 | Tablas DynamoDB | Un Lambda que arranca contra una tabla inexistente falla en la primera petición, no en el despliegue: el error aparecería tarde y lejos de su causa. |
| 2 | AUTH, EVENTS, FILES, ML_FUNCTIONS | Son la base. Todos los demás validan el token contra AUTH, registran auditoría en EVENTS y guardan archivos en FILES. |
| 3 | INGEST, QUOTES | Son dueños de datos que otros servicios piden: OPTIMIZATION pide stock y vendedores a INGEST, ANALYTICS pide el tipo de cambio a QUOTES. |
| 4 | ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, AI | Consumen lo anterior. |
| 5 | BILLING | SmartBilling, independiente de SmartDecisions. |
| 6 | Tareas programadas | Necesitan que los Lambdas existan. |
| 7 | Dominio y mapeos | Necesitan que los API existan. Se repite en cada despliegue porque es seguro repetirlo y corrige el mapeo si un API se recreó con otro ID. |

### Las direcciones públicas

| Servicio | Dirección |
|---|---|
| AUTH | `https://api.bearsoft.com.bo/v1/auth/...` y `/v1/users/...` |
| EVENTS | `https://api.bearsoft.com.bo/v1/events/...` |
| FILES | `https://api.bearsoft.com.bo/v1/s3/...` |
| ML_FUNCTIONS | `https://api.bearsoft.com.bo/v1/classification/...`, `/v1/common/...`, `/v1/prediction/...` |
| INGEST | `https://api.bearsoft.com.bo/v1/ingest/...` |
| QUOTES | `https://api.bearsoft.com.bo/v1/quotes/...` |
| ANALYTICS | `https://api.bearsoft.com.bo/v1/analytics/...` |
| OPTIMIZATION | `https://api.bearsoft.com.bo/v1/optimization/...` |
| MINING_ANALYSIS | `https://api.bearsoft.com.bo/v1/mining-analysis/...` |
| AI | `https://api.bearsoft.com.bo/v1/ai/...` |
| BILLING | `https://api.bearsoft.com.bo/v1/billing/...` |

**Costo del dominio:** el certificado de ACM, el dominio de API Gateway, los mapeos y el DNS de Cloudflare no tienen costo. Se paga sólo por llamada, igual que con las direcciones `execute-api` de antes.

**Si un servicio agrega un prefijo de rutas nuevo** (un `APIRouter(prefix = '/v1/algo')` que no estaba), agrégalo a la lista `MAPPINGS` de `setup_api_domain.sh` y ejecuta el script.
