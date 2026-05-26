# `seed_portal` — seed del CMS desde `mineria.gob.bo`

Importa contenido del portal WordPress oficial del Ministerio (`https://www.mineria.gob.bo`) hacia el CMS local/productivo:

- **News** ← CPTs `nota_prensa`, `comunicados`, `galeria`, `campania`.
- **Documents** ← CPTs `normativa`, `normativa-inter`, `boletin`, `memoria`, `auditoria`, `manual_organizacion`, `procedimientos`, `poa`, `presupuesto`, `rendicion_cuenta`, `investigacion`, `documentos`.
- **Entities** ← CPT `enlace_interes`.

Estrategia: usa la REST API pública de WP para enumerar items y luego scrapea cada página de detalle (los CPTs no exponen `content` por REST). PDFs e imágenes encontradas se descargan y se re-suben al bucket S3 vía el microservicio FILES.

## Estructura

```
services/cms/scripts/seed_portal/
├── __init__.py
├── __main__.py        entry CLI (argparse + orquestación)
├── auth.py            cliente AUTH (POST /v1/auth/login → JWT)
├── cms.py             cliente CMS admin (subset que necesita el seed)
├── files.py           cliente FILES (download remoto + POST /v1/s3/upload)
├── mappings.py        config CPT → entidad CMS + filtro de assets del tema
└── wordpress.py       cliente WP (REST discovery + parser HTML)
```

## Requisitos

Los 3 microservicios deben estar arriba localmente:

| Servicio | Default URL |
|---|---|
| AUTH  | `http://localhost:3000/v1/auth` |
| FILES | `http://localhost:3010/v1/s3` |
| CMS   | `http://localhost:3021/v1/cms` |

Y un usuario admin existente en AUTH (`POST /v1/auth/signup` previo).

Dependencias: ya están en `services/cms/requirements.txt` (`requests`, `beautifulsoup4`, `python-dotenv`).

## Credenciales

El script lee `SCRAPER_ADMIN_EMAIL` y `SCRAPER_ADMIN_PASSWORD` del entorno o del `.env` local del CMS. Si faltan, las pide interactivamente.

## Ejecución

```bash
cd services/cms

# Smoke test: 3 items por CPT, dry-run, no toca nada.
python -m scripts.seed_portal --limit 3 --dry-run

# Solo news + entities, con wipe previo.
python -m scripts.seed_portal --only news,entities --wipe

# Corrida completa contra prod (más adelante).
python -m scripts.seed_portal \
    --auth-url https://api.binaria.app/v1/auth \
    --cms-url https://api.binaria.app/v1/cms \
    --files-url https://api.binaria.app/v1/s3 \
    --wipe
```

## Flags

| Flag | Default | Qué hace |
|---|---|---|
| `--source-url` | `https://www.mineria.gob.bo` | Base URL del WP a importar. |
| `--auth-url` | `http://localhost:3000/v1/auth` | AUTH service. |
| `--cms-url` | `http://localhost:3021/v1/cms` | CMS service. |
| `--files-url` | `http://localhost:3010/v1/s3` | FILES service. |
| `--bucket` | `ml-data-file-handler` | Bucket S3 destino (compartido con admin UI). |
| `--base-path` | `cms/` | Prefijo dentro del bucket. Cada CPT agrega su `sub_path`. |
| `--rate-limit-ms` | `200` | Pausa entre fetches de detail (≤10 req/s). |
| `--only` | `news,documents,entities` | Restringe el scope. |
| `--limit N` | (sin límite) | Cap items por CPT, útil para smoke. |
| `--wipe` | off | Borra todos los items en scope **antes** de sembrar. |
| `--dry-run` | off | No escribe en CMS; solo log. |

## Códigos de salida

- `0` si nada falló.
- `1` si ≥1 item no se pudo sembrar (lista hasta 20 fallas en el summary final).

## Tiempos esperados

- Smoke (`--limit 3`): < 30 s.
- News + Entities completo: ~30 s.
- Todo (~330 items, principalmente normativa-inter con PDFs): 5–10 min según ancho de banda y velocidad del portal.

## Limitaciones conocidas

- Los CPTs **no exponen `content`** por REST, así que se scrapea HTML. Si el theme del portal cambia, hay que actualizar el selector `.detalle-nota` en `wordpress.py`.
- La URL externa de cada entidad se infiere como **primer link `http(s)://` fuera de `mineria.gob.bo`** dentro del body. Si la página tiene otros enlaces antes del oficial, el seed tomará el equivocado — revisa luego en el admin UI.
- Las imágenes del tema (logos, banderas, escudo) están filtradas via `THEME_ASSET_PATTERNS` en `mappings.py`. Si aparecen otros assets repetidos, agrégalos a ese listado.
- El script no deduplica: si lo corres dos veces sin `--wipe`, vas a tener entradas duplicadas en el CMS.
