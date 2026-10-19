# FILES — File-Handler-Service

Servicio **base** de BearSoft (CLAUDE.md §4, §7 y §9).

## Para qué sirve

Es el **único servicio que toca el bucket**: sube, baja, lista, borra y
**lee los datos** de los archivos de S3 (CSV, Excel, TXT). Un servicio que
necesita un archivo se lo pide a FILES por HTTP, reenviando el token de quien
llama; nunca abre su propio `boto3.client('s3')`. El binario sube directo a S3
con una URL pre-firmada, así no atraviesa API Gateway (límite de 10 MB).

FILES no reporta a EVENTS: mover un archivo no dice nada del negocio
(Rafael, 17-oct-2026).

## Endpoints y quién puede llamarlos

Todos exigen un token válido de AUTH, de cualquier rol.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/v1/s3/read/{bucket_name}/{file_key}` | Lee un archivo y devuelve sus filas |
| POST | `/v1/s3/upload` | Sube un archivo a través del servicio |
| DELETE | `/v1/s3/delete` | Borra un archivo |
| POST | `/v1/s3/list-files` | Lista los archivos, con prefijo opcional |
| POST | `/v1/s3/upload-presigned` | Devuelve una URL pre-firmada para subir directo a S3 |

`/read` no acepta `/` dentro de `file_key`: los archivos de una carga masiva
van a la raíz del bucket (`BUCKET_PATH=''` en quien llama), igual que en las
cargas de BINARIA.

## Qué servicios lo llaman

- **FINANCE, INGEST y MINING_ANALYSIS**, por el bloque FILES del final de su
  `services/utils.py` (el estándar vive en `services/finance/services/utils.py`).
- **Portal demo** (`portal/demo/js/api.js`, `uploadToBucket`): pide la URL
  pre-firmada y sube el archivo.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Verificación del JWT de AUTH |
| `ML_DATA_BUCKET_NAME` | Bucket del servicio (`ml-data-file-handler`) |

## Tablas y buckets

No tiene tablas. El bucket es `ml-data-file-handler`; lo que hay adentro lo
decide cada servicio que lo usa. INGEST guarda bajo `ingest/` los CSV de cada
contrato (estructura en `services/ingest/README.md`).

## Cómo correrlo y probarlo

```bash
cd services/files
python main.py            # puerto del .env (PORT); usa el bucket real de S3
python -m pytest -q
pylint --fail-under=10.0 .
```

Se despliega con `services/ci/api/start.sh --redeploy files` (lo despliega
Rafael).

## Qué revisa el CI

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**: un test que importe
algo que lea configuración al importarse rompe el CI. `tests/test_files.py`
prueba la lectura con S3 reemplazado (CSV con y sin separador, texto, binario
en base64), la traducción de los errores de AWS y la clave del archivo.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
