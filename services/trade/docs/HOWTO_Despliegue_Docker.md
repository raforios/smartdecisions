# HOW-TO — Despliegue de microservicios con Docker

**Cliente:** BINARIA
**Fecha:** 2026-08-18
**Alcance:** entorno local completo (bases de datos + microservicios) a partir de
`build_infra.sh` y `docker-compose.yml`.

---

## 1. Ficha técnica de los microservicios

| Microservicio | Python | Puerto | Base de datos | Imagen Docker |
|---|---|---|---|---|
| FORMS | 3.13 | 3000 | MySQL + DynamoDB | `micro-forms` |
| LOCALIZATION | 3.13 | 3001 | MySQL | `micro-localization` |
| PLANNING | 3.13 | 3002 | MySQL | `micro-planning` |
| TRADE | 3.13 | 3003 | MySQL | `micro-trade` |
| EVENTS | 3.14 | 3000 | DynamoDB | imagen base Lambda |

**Comando de arranque** (idéntico en todos): el punto de entrada es `main.py`, que levanta
Uvicorn con el host y el puerto tomados del `.env`.

```bash
pip install -r requirements.txt
python main.py
```

En AWS, los mismos servicios corren como función Lambda a través de **Mangum**, que adapta
la aplicación FastAPI al formato de eventos de Lambda. No hay dos versiones del código: es
el mismo `main.py`.

### 1.1. Dependencias externas

Comunes a todos los servicios:

| Paquete | Para qué |
|---|---|
| `fastapi` | Framework web |
| `uvicorn` | Servidor ASGI |
| `pydantic` / `pydantic-core` | Validación de datos |
| `python-jose[cryptography]` | Validación de tokens JWT |
| `python-dotenv` | Carga del archivo `.env` |
| `python-multipart` | Carga de archivos (fotografías, CSV) |
| `requests` | Comunicación entre microservicios |
| `mangum` | Adaptador para AWS Lambda |

Según la base de datos que use el servicio:

| Paquete | Servicios |
|---|---|
| `sqlalchemy` + `pymysql` | FORMS, LOCALIZATION, PLANNING, TRADE (MySQL) |
| `boto3` | EVENTS y todo lo que escriba en DynamoDB o S3 |
| `pandas`, `numpy` | TRADE (reportes y cargas masivas) |

Fuera de Python, cada servicio necesita: **MySQL 8.x o superior** (o **DynamoDB**, según
el caso), y acceso de red al **servicio AUTH** para validar los tokens y al **servicio
EVENTS** para emitir los logs de uso y auditoría.

---

## 2. Requisitos del equipo

- **Docker** y el plugin **Docker Compose** (`docker compose`, no `docker-compose`).
- Espacio en disco para las imágenes (~1 GB por servicio con sus dependencias).
- Puertos libres: `3000`, `3001`, `3002`, `3003`, `3100` (DynamoDB local) y `3310` (MySQL).

El script comprueba las dos primeras condiciones antes de empezar y aborta con un mensaje
claro si falta alguna.

---

## 3. Despliegue en un solo paso

Desde la carpeta que contiene `build_infra.sh`, `docker-compose.yml` y las carpetas de los
microservicios:

```bash
chmod +x build_infra.sh    # solo la primera vez
./build_infra.sh
```

El script hace, en orden:

1. **Verifica dependencias**: que Docker y Docker Compose estén instalados.
2. **Detecta la arquitectura del equipo** y elige la plataforma de construcción:
   `linux/arm64` en Mac con chip M1/M2, `linux/amd64` en Intel/AMD. Esto evita el error
   más común al mover imágenes entre equipos.
3. **Limpia el entorno anterior** (`docker compose down`), para que no queden contenedores
   viejos ocupando nombres o puertos.
4. **Construye las cuatro imágenes**: `micro-forms`, `micro-localization`,
   `micro-planning` y `micro-trade`.
5. **Levanta todo** con `docker compose up -d`: primero las bases de datos, después los
   microservicios.

Al terminar, para seguir el arranque:

```bash
docker compose logs -f
```

---

## 4. Qué levanta el `docker-compose.yml`

Todo corre sobre una red propia (`micro_network`, `192.168.30.0/24`) con IP fija por
contenedor, de modo que los servicios se encuentran entre sí por dirección o por nombre.

| Contenedor | Imagen | Puerto | IP interna |
|---|---|---|---|
| `dynamodb` | `amazon/dynamodb-local` | 3100 → 8000 | 192.168.30.21 |
| `mysqldb` | `mysql` | 3310 → 3306 | 192.168.30.22 |
| `micro-forms` | `micro-forms` | 3000 | 192.168.30.30 |
| `micro-localization` | `micro-localization` | 3001 | 192.168.30.31 |
| `micro-planning` | `micro-planning` | 3002 | 192.168.30.32 |
| `micro-trade` | `micro-trade` | 3003 | 192.168.30.33 |

### 4.1. Orden de arranque

Las bases de datos declaran un `healthcheck` y los microservicios dependen de él:

```yaml
depends_on:
    mysqldb:
        condition: service_healthy
```

Esto es importante y conviene no simplificarlo: la forma corta de `depends_on` (una lista
de nombres) solo espera a que el contenedor **arranque**, no a que el motor acepte
conexiones. MySQL tarda unos segundos más en abrir el puerto, y sin la condición
`service_healthy` los microservicios fallan al iniciar con
`Can't connect to MySQL server ... Connection refused`.

### 4.2. DynamoDB local

El contenedor `dynamodb` corre en memoria (`-inMemory`), por lo que **su contenido se
pierde al detenerlo**. Las tablas se crean al arrancar mediante el script
`create_dynamodb_tables.py`, que el compose monta dentro del contenedor de FORMS y ejecuta
desde `init-forms-service.sh` antes de iniciar la aplicación.

Las credenciales de AWS en local son ficticias a propósito (`AWS_ACCESS_KEY_ID: test`),
porque DynamoDB local no las valida. En AWS se usan las credenciales reales del rol de
ejecución del Lambda.

---

## 5. Operación cotidiana

```bash
docker compose ps                      # estado de los contenedores
docker compose logs -f micro-trade     # logs de un servicio
docker compose restart micro-trade     # reiniciar uno
docker compose down                    # detener y eliminar todo
docker compose up -d                   # levantar sin reconstruir
```

Para reconstruir un solo servicio tras un cambio de código, sin pasar por el script:

```bash
docker build -t micro-trade ./trade
docker compose up -d --force-recreate micro-trade
```

---

## 6. Verificación

Cada microservicio expone un healthcheck en su raíz. Con el entorno levantado:

```bash
curl http://localhost:3000/    # FORMS
curl http://localhost:3001/    # LOCALIZATION
curl http://localhost:3002/    # PLANNING
curl http://localhost:3003/    # TRADE
```

La respuesta esperada confirma el servicio, el entorno y la conexión a la base de datos:

```json
{
  "Api Healthcheck": "OK",
  "Environment": "production",
  "Status": "available",
  "Application": "Python - FastAPI",
  "Database": "MySQL transactional Database"
}
```

---

## 7. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `Connection refused` contra MySQL al arrancar | El servicio arrancó antes que la base | Verificar que el `depends_on` use `condition: service_healthy` (§4.1) |
| `exec format error` al correr la imagen | Imagen construida para otra arquitectura | Reconstruir con `--platform` correcto; `build_infra.sh` ya lo detecta |
| Puerto ocupado al levantar | Otro proceso usa 3000-3003, 3100 o 3310 | Liberarlo (`lsof -i :3003`) o cambiar el mapeo en el compose |
| Las tablas de DynamoDB no existen | El contenedor es `-inMemory` y se reinició | Volver a levantar FORMS, que ejecuta `create_dynamodb_tables.py` |
| Error 401 en todos los endpoints | Token vencido o AUTH inalcanzable | Regenerar el token; verificar `AUTH_SERVICE_URL` en el `.env` |
