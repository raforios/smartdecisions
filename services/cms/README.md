# CMS Service

Microservicio de contenidos del portal público
(`demo/index.html`, `demo/institucional.html`, `demo/documentacion.html`,
`demo/mercados.html`).

Reemplaza progresivamente el contenido hoy hardcoded en `demo/data/config.json`
y en literales HTML, permitiendo que operadores no técnicos lo gestionen vía
endpoints administrativos.

---

## Stack

| Capa | Tecnología |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy |
| BD | MySQL (compartida con el resto del stack) |
| Schemas | Pydantic V2 |
| Auth admin | JWT (mismo emisor que AUTH service) |
| Despliegue | AWS Lambda + API Gateway |

> **Migraciones:** v1 usa `Base.metadata.create_all()` al arranque (igual que
> `mining_analysis`). Pasar a Alembic queda pendiente cuando se introduzcan
> cambios destructivos de esquema.

---

## Entidades v1

| Tabla | Propósito | Multilenguaje |
|---|---|---|
| `t_cms_news` | Noticias, comunicados, fotos, artículos | sí (`lang`) |
| `t_cms_documents` | Boletines, normativas, leyes (descargables) | sí (`lang`) |
| `t_cms_slides` | Slider hero de la home | sí (`lang`) |
| `t_cms_entities` | Entidades adscritas (VINTO, COMIBOL, AJAM…) | no |

Campos comunes: `is_published`/`is_active` (boolean), `sort_order` (entero),
`created_at` / `updated_at`.

Ordenamiento del portal público: `sort_order ASC, fecha DESC`.

---

## Manejo de archivos (imágenes y PDFs)

El CMS **no recibe uploads binarios**. El flujo es:

1. Admin frontend pide presigned URL al microservicio **FILES**
   (`POST /v1/s3/upload-presigned`).
2. Frontend hace `PUT` directo a S3 con la URL firmada.
3. Frontend envía al CMS los campos `bucket` + `key` que devolvió FILES.
4. CMS persiste esa referencia. El portal público resuelve la URL final
   en lectura.

Los modelos exponen pares de columnas `*_s3_bucket` y `*_s3_key`. Para
documentos también se acepta `file_external_url` para legacy.

---

## Rutas (en construcción)

```
/v1/cms/public/news        GET  · GET /{id}
/v1/cms/public/documents   GET  · GET /{id}
/v1/cms/public/slides      GET
/v1/cms/public/entities    GET

/v1/cms/admin/news         POST · PUT · DELETE
/v1/cms/admin/documents    POST · PUT · DELETE
/v1/cms/admin/slides       POST · PUT · DELETE
/v1/cms/admin/entities     POST · PUT · DELETE
```

Endpoints `public/*` son anónimos (lectura para el sitio).
Endpoints `admin/*` requieren JWT (`services/security.get_current_user`).

---

## Ejecución local

```bash
pip install -r requirements.txt
python main.py
```

Variables de entorno requeridas (ver `services/environment.py`):
`HOST`, `PORT`, `APP_ENV`, `ROOT_PATH`, `CORS_ALLOWED_ORIGINS`,
`CORS_ALLOWED_ORIGIN_REGEX`, y las del `db_connection` (credenciales MySQL).
`CORS_ALLOWED_ORIGINS` es una lista CSV de orígenes exactos (opcional); el default
del regex ya cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo` y
`localhost`, así que no hace falta listar URLs una por una.

---

## Estado actual

- [x] Andamiaje del servicio (estructura, shared, main, models, Docker).
- [ ] Entidad **Noticias** (schemas / service / controller / route / tests).
- [ ] Entidad **Documentos**.
- [ ] Entidad **Slider**.
- [ ] Entidad **Entidades adscritas**.
- [ ] Cliente del portal (`demo/js/services/CmsApiService.js`) y wiring del
      contenido dinámico en las páginas.
