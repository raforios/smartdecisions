# GESTIÓN DE INFRAESTRUCTURA DE AWS PARA DESPLIEGUE DE API DE MICROSERVICIOS

**Nota:** Esta infraestructura se ha construido bajo los principios de Clean Code, Arquitectura Limpia, SOLID y DRY. Toda la configuración es centralizada y parametrizable.

---

---

## 0. ESTADO ACTUAL DE LA INFRAESTRUCTURA

Inventario verificado directamente contra la cuenta de AWS el **18 de agosto de 2026**
(región `us-east-1`, perfil `deploy_binaria`).

### 0.1. Microservicios (AWS Lambda)

Los siete microservicios corren como funciones Lambda con **Python 3.13**, expuestas cada
una por su propio HTTP API Gateway.

| Microservicio | Función Lambda | Memoria | Timeout | API Gateway |
|---|---|---|---|---|
| AUTH | `binaria-auth-handler-service` | 256 MB | 30 s | `v65w34fghh` |
| EVENTS | `binaria-events-handler-service` | 256 MB | 30 s | `ozg7itcrvg` |
| FILES | `binaria-file-handler-service` | 256 MB | 30 s | `mijwvdu4g6` |
| FORMS | `binaria-forms-handler-service` | 256 MB | 120 s | `vk22i8orck` |
| LOCALIZATION | `binaria-localization-handler-service` | 256 MB | 120 s | `yvivgga9i8` |
| PLANNING | `binaria-planning-handler-service` | 256 MB | 300 s | `9bdyb0z3ol` |
| TRADE | `binaria-trade-handler-service` | **1024 MB** | 120 s | `z4utb6z4le` |

La URL de cada servicio es `https://<API_ID>.execute-api.us-east-1.amazonaws.com`.

TRADE lleva 1 GB de memoria por sus cargas masivas y la generación de reportes, que usan
`pandas`; el resto opera con 256 MB.

### 0.2. Base de datos relacional (RDS)

| Parámetro | Valor |
|---|---|
| Identificador | `api-binaria-mysql-db` |
| Motor | MySQL **8.4.9** |
| Clase | `db.t4g.small` |
| Almacenamiento | 20 GB |
| Multi-AZ | No |
| Acceso público | Sí |

La usan **FORMS, LOCALIZATION, PLANNING y TRADE** (base `binaria`). Estos cuatro
microservicios requieren la configuración de VPC descrita en el paso 3 para alcanzarla.

### 0.3. Bases de datos NoSQL (DynamoDB)

| Tabla | Uso | Registros | Tamaño | Capacidad | Índice secundario |
|---|---|---|---|---|---|
| `usage_logs` | Logs de uso (EVENTS) | 827.474 | 10,4 GB | Bajo demanda | `microservice-timestamp-index` |
| `audit_records` | Auditoría (EVENTS) | 162.553 | 0,05 GB | Bajo demanda | `microservice-timestamp-index` |

Ambas tablas se particionan por `id` y cuentan con un índice secundario global por
`microservice` + `timestamp`, que es el que permite filtrar los logs por microservicio y
rango de fechas sin recorrer la tabla completa.

### 0.4. Servidor de aplicación (EC2)

| Parámetro | Valor |
|---|---|
| Nombre | `API_BINARIA-Frontend-EC2` |
| Tipo | `t3.medium` |
| IP pública (Elastic IP) | `54.204.190.209` |
| Estado | En ejecución |

### 0.5. Almacenamiento de archivos (S3)

El microservicio FILES administra el bucket configurado en su `.env` (`BUCKET_NAME`), a
través del cual el resto de los servicios sube y recupera archivos y fotografías.

---

## 1. PRE-REQUISITOS

Antes de comenzar, asegurarse de que los siguientes componentes estén instalados y configurados:

1.  **AWS CLI:** Instalado y configurado correctamente.
2.  **Credenciales de AWS:** Un perfil nombrado (`[perfil_aws]`) configurado en `~/.aws/credentials` con permisos para crear/eliminar recursos de IAM, EC2, RDS y VPC. Por ejemplo:

```shell
nano ~/.aws/credentials

    [deploy_binaria]
    aws_access_key_id = XXXXXXXXXXXXXXXX
    aws_secret_access_key = XXXXXXXXXXXXXXXXXXXXX

nano ~/.aws/config

    [profile deploy_binaria]
    region = us-east-1
    output = json

```

3.  **Scripts Shell:** Los scripts principales de IaC son:

- `manage_infrastructure.sh`
- `build_and_deploy.sh`
- `create_dynamodb_tables.sh`
- `update_env_urls.sh`
- `configure_https.sh`
- `setup_elastic.sh`

Los otros scripts son complementarios, de soporte y necesariamente deben estar en el directorio `CI` y tener permisos de ejecución (`chmod +x *.sh`).

4. **Estructura del proceso de ejecuón:**

El script `build_and_deploy.sh` es el primer script que debe ser ejecutado. Este script sirve para el despliegue de los microservicios (servicios `LAMBDA`), una vez que todos los microservicios hayan sido desplegados, recién se debe proceder a la creación del resto de la infraestructura.

El script `create_dynamodb_tables.sh` es el segundo script que debe ser ejecutado. Este script sirve crear todas las tablas necesarias en DynamoDB para el manejo de los `eventos`.

El script `manage_infrastructure.sh` cuando se ejecuta con la opción `setup` utiliza los siguientes scripts y archivo de configuración de manera complementaria y requerida.

```text
manage_infrastructure.sh setup
├── infrastructure.config
├── setup_aws_infrastructure.sh
├── setup_rds_instance.sh
├── setup_ec2_instance.sh
├── configure_security_groups.sh
├── setup_alb.sh
└── setup_api_gateway.sh
```

El script `manage_infrastructure.sh` cuando se ejecuta con la opción `destroy` utiliza los siguientes scripts y archivo de configuración de manera complementaria y requerida.

```text
manage_infrastructure.sh destroy
├── infrastructure.config
└── destroy_aws_infrastructure.sh
```

Los otros archivos importantes para el despliegue de la infraestrtuctura son:

- `configure_https.sh`
- `setup_elastic.sh`
- `update_env_urls.sh`

Más adelante se explica el orden de ejecución de todos los archivos mencionados.

También tenemos archivos complementarios para hacer ajustes y configuraciones adicionales luego de que se realicen previamente algunas configuraciones manuales. Estos archivos son:

- **configure_https_and_api_domain.sh**
- **map_api_base_paths.sh**

5.  **Archivo de Configuración:** El archivo **`infrastructure.config`** debe estar presente y previamente configurado con los valores deseados para el despliegue de la infraestructura central.

---

## 2. CONFIGURACIÓN

Revisar y modificar el archivo **`infrastructure.config`**. Los parámetros clave a verificar son:

* `REGION`: Región de despliegue de AWS.
* `AWS_PROFILE`: Nombre de su perfil de AWS CLI.
* `VPC_CIDR`: Rango de red deseado.
* `EC2_AMI_ID`: **Crucial**. El ID de la AMI para el SO LINUX de preferencia en la región seleccionada.

Además, verificar de que cada microservicio tenga su archivo **`deploy.config`** y **`.env`** (si aplica) con los valores específicos necesarios (ej. `FUNCTION_NAME`, `DYNAMODB_TABLE_NAME`, etc.).


```shell
HOST='0.0.0.0'
PORT=3002
APP_ENV="production"
SECRET_KEY="ASDDSSDFASDSWEQEQWEERW"
ALGORITHM="HS256"
DB_USER="root"
DB_PASSWORD="PASSWORD"
DB_HOST="api-binaria-mysql-db.cgbqmuawkgko.us-east-1.rds.amazonaws.com"
DB_PORT="3306"
DATABASE="binaria"
DB_DIALECT="mysql+pymysql"
EVENTS_SERVICE_URL="https://[API_ID].execute-api.us-east-1.amazonaws.com"
FILES_SERVICE_URL="https://[API_ID].execute-api.us-east-1.amazonaws.com"
BUCKET_NAME="binaria-afiliaciones"
BUCKET_PATH=""

```

---

## 3. CREACIÓN Y DESPLIEGUE DE INFRAESTRUCTURA Y SERVICIOS


### CASO 1: DESPLIGUE DESDE INICIAL

```shell
# --- PASO 1 ---
# Deplegar servicios LAMBDA
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/auth 
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/events
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/files --skip-table-creation
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/localization --skip-table-creation
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/planning --skip-table-creation
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/forms 
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/trade --skip-table-creation

./create_dynamodb_tables.sh

# --- PASO 2 ---
# Crear toda la infraestructura
./manage_infrastructure.sh setup

# --- PASO 3 ---
# Modificar variables del archivo "deploy.config" con los valores obtenidos en el paso 2
# --- Configuración VPC (Obligatoria para acceso a RDS) ---
VPC_ID=vpc-00e5c84e1400a916f
PRIVATE_SUBNET_IDS=subnet-07c1a8b67d2047ec3,subnet-07c7eeb3c2e5be2e0,subnet-007d8f014baf297ef,subnet-02403fd7434746c2d
INTERNAL_SG_ID=sg-07495e1628e67b466
# Esta configuración debe ser para los microservicios LOCALIZATION, FORMS, PLANNING, TRADE

# --- PASO 4 ---
# Modificar el archivo ".env" con los valores del RDS
DB_USER="root"
DB_PASSWORD="D3s4P1_M1cr0S3rv"
DB_HOST="api-binaria-mysql-db.cgbqmuawkgko.us-east-1.rds.amazonaws.com"
DB_PORT="3306"

# --- PASO 5 ---
# Actualizar en el script "update_env_urls.sh" al inicio del archivo el segmento:
CUSTOM_DOMAIN_BASE="https://api.binaria.app"

# Esto se debe realizar con la URL del subdominio que se haya definido y a la cual se le ha creado un CERTIFICADO dentro del CERTIFICATE MANAGER de AWS. Este paso es manual y es mandatorio para los siguientes pasos. También se debe configurar el Cloud Flare con los valores del CNAME obtenido par ael dominio y los subdominios

# --- PASO 6 ---
# Configuración del ELASTIC IP para mantener el IP siempre igual indpendiente de la instancia EC2
./setup_elastic.sh

# --- PASO 7 ---
# Configuración del HTTPS
./configure_https.sh

# --- PASO 8 ---
# Configurando el subdominio para los microservicios, previamente se debe editar algunos valores de este earchivo:
CUSTOM_DOMAIN="api.binaria.app"
CERTIFICATE_ARN="" # ARN obtenido del certificado creado
ALB_ARN="" # Reemplaza con tu ALB ARN creado en el paso 2
TG_ARN="" # Reemplaza con tu TG ARN creado en el paso 2

./configure_https_and_api_domain.sh

# --- PASO 9 ---
# Mapear los ID de los lambdas creados en el paso 1 con la URL del subdominio que acaabmos de configurar
CUSTOM_DOMAIN="api.binaria.app"
API_MAPPINGS=(
    "ID-LAMBDA-file:files"      # binaria-file-handler-service
    "ID-LAMBDA-events:events"     # binaria-events-handler-service
    "ID-LAMBDA-forms:forms"      # binaria-forms-handler-service
    "ID-LAMBDA-localization:localization" # binaria-localization-handler-service
    "ID-LAMBDA-planning:planning"    # binaria-planning-handler-service
    "ID-LAMBDA-auth:auth"       # binaria-auth-handler-service
)

./map_api_base_paths.sh

# --- PASO 10 ---
# Actualización de los lambdas y sus variables de entorno y adesión a la infraestructura creada en el paso 2
./update_env_urls.sh


```

### CASO 2: CAMBIOS EN RED, VPC, EC2, RDS O OTRS EN LA INFRAESTRUCTURA

```shell
# --- PASO 1 ---
# Limpieza de toda la infraestructura (empezar desde 0)
./manage_infrastructure.sh destroy

# --- PASO 2 ---
# En caso de que no se pueda eliminar algunos elementos desde el script se deberá hacer un borrado forzoso desde la consola de AWS con el ussuario principal

# --- PASO 3 ---
# Crear toda la infraestructura
./manage_infrastructure.sh setup

# --- PASO 4 ---
# Modificar el archivo ".env" siguiendo el ejemplo del paso 4 del CASO 1

# --- PASO 5 ---
# Reinicio y reintegro de los servicios lambda que utilizan el RDS para que estén integrados a la nueva infraestructura

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/localization --skip-table-creation  --skip-code-update
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/planning --skip-table-creation  --skip-code-update
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/forms --skip-table-creation  --skip-code-update
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/trade --skip-table-creation  --skip-code-update

# --- PASO 6 ---
# Configuración del HTTPS
./configure_https.sh

# --- PASO 7 ---
# Actualizar en el script "map_api_base_paths.sh" y el script "configure_https_and_api_domain.sh" siguiendo el ejemplo de los pasos 8 y 9 del CASO 1 ejecutar ambos pasos según se describe. Esto se debe realizar con los ID y ARN de los servicios lambda y otros valores obtenidos durante el despliegue y ejecución del paso 3. Revisar en detalle el CASO 1.

# --- PASO 8 ---
# Actualización de los lambdas y sus variables de entorno y adesión a la nueva infraestructura creada en el paso 3
./update_env_urls.sh


```

### EJEMPLO DE SALIDA DE LA EJECUCIÓN DE CUALQUEIRA DE LOS CASOS

```shell

--------------------------------------------------------------------------------
| CONFIGURACIÓN DE RDS COMPLETADA |
--------------------------------------------------------------------------------

RDS Instance ID: api-binaria-mysql-db
RDS Subnet Group: api-binaria-rds-subnet-group
RDS Endpoint: api-binaria-mysql-db.cgbqmuawkgko.us-east-1.rds.amazonaws.com
RDS Database: binaria
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
| CONFIGURACIÓN DE EC2 COMPLETADA |
--------------------------------------------------------------------------------

ID de Instancia EC2: i-0f0ea3e94b7a4adbf
IP Pública de EC2: 34.201.100.254
Grupo de Seguridad Público Usado: sg-09fafff5d204ebd88
Comando de Conexión SSH (usuario 'ec2-user' para AlmaLinux):
ssh -i api-project-keypair.pem ec2-user@34.201.100.254


--------------------------------------------------------------------------------
| CONFIGURANDO API GATEWAY HTTP (V2) PARA: binaria-auth-handler-service |
--------------------------------------------------------------------------------

✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-auth-handler-service:
https://v65w34fghh.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://v65w34fghh.execute-api.us-east-1.amazonaws.com/docs


✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-file-handler-service:
https://mijwvdu4g6.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://mijwvdu4g6.execute-api.us-east-1.amazonaws.com/docs


✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-events-handler-service:
https://ozg7itcrvg.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://ozg7itcrvg.execute-api.us-east-1.amazonaws.com/docs


✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-forms-handler-service:
https://vk22i8orck.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://vk22i8orck.execute-api.us-east-1.amazonaws.com/docs


✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-localization-handler-service:
https://yvivgga9i8.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://yvivgga9i8.execute-api.us-east-1.amazonaws.com/docs


✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE.
URL de la API para binaria-planning-handler-service:
https://9bdyb0z3ol.execute-api.us-east-1.amazonaws.com/
Ejemplo de uso de Swagger:
-> https://9bdyb0z3ol.execute-api.us-east-1.amazonaws.com/docs

```

## OTROS DATOS IMPORTANTES

Una vez se desplegó toda la infraestructura usando `POSTMAN` podemos crear el ususairo de la aplicación, para este caso se utilizó:

```json
{
    "email" : "psoto@binariaconsultores.com",
    "password" : "PASSWORD"
}

```

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
