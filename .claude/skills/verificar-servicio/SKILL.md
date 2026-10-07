---
name: verificar-servicio
description: Corre TODAS las revisiones mecánicas de un microservicio con un solo comando (tests, Pylint 10.00, firmas, type hints, sintaxis moderna de tipos, tamaño, duplicados, except mudo, comas en .env, os.getenv, variables de log) y después los tres puntos de criterio. Se corre antes de CADA reporte de avance que agregue código, no sólo al entregar.
argument-hint: [nombre-del-servicio | --all]
allowed-tools: Bash(cd *), Bash(python3 *), Bash(grep *), Bash(ls *), Bash(find *), Read
---

Verifica el microservicio `$1` (o los once servicios propios y `tools/` con `--all`;
sólo `tools/` con `--tools`). Si no se
indica, pregunta cuál.

**Reporta el resultado real, no la intención.** Si algo falla, arréglalo y
vuelve a correr; si no se puede arreglar, dilo explícitamente.

## 1. Lo mecánico — un comando

```bash
python3 tools/verify_service.py services/$1      # o --all
```

Imprime PASS/FAIL por chequeo y termina con `ALL PASS` o `FAILED: ...`. En `tools/`
corre Pylint 10.00 sobre cada herramienta con su servicio en el path (como se
ejecuta de verdad), código duplicado entre herramientas, firmas, type hints,
tamaño, `except` mudo, sintaxis de tipos e idioma de los comentarios. Lo que
cubre, y cómo se corrige cada cosa:

| Chequeo | Regla | Corrección |
|---|---|---|
| `tests` | suite en verde | arreglar el código, no el test |
| `pylint` | 10.00 sobre las cinco capas y tests | un `disable` sólo con comentario del porqué |
| `signatures` | más de un parámetro → uno por línea | `python3 tools/check_signatures.py services/$1 --fix` |
| `type-hints` | todo parámetro y todo retorno anotados (tests exentos; `self`/`cls` y `__init__` también) | anotar a mano; el retorno de un endpoint es su `response_model` |
| `size` | ningún archivo propio ≥ 800 líneas | partir por funcionalidad (`ingest_contract.py`, `ingest_files.py`) o, en `controllers/`, por proceso |
| `duplicates` | ningún cuerpo de función repetido | una función parametrizada (`store_companion(spec)`, `read_sheet(name)`) |
| `except-pass` | nunca `except: pass` | capturar la excepción específica y loguear `error_msg` |
| `env-shorthand` | ningún valor del `.env` con coma ni llave | listas con guion; plantillas con `%s`, no `{x}` |
| `events` | todo controlador reporta a EVENTS y toda escritura se audita | `@handle_service_errors` en cada controlador, `@audit_event` en POST/PUT/PATCH/DELETE |
| `getenv` | sólo `load_and_validate_env_vars` | mover al módulo que usa el valor |
| `modern-typing` | `list[str]`, `str \| None`; nada de `List`, `Dict`, `Optional`, `Union` de `typing` (boilerplate y tests incluidos) | `pyupgrade --py314-plus` desde `SmartBear/.venv` |
| `log-vars` | `message` en INFO, `error_msg` en WARNING/ERROR | renombrar |

**Antes de escribir una función nueva paralela a otra** (un contrato más, un
proceso más): extraer lo común de la existente y parametrizarlo; el nuevo se
escribe sobre eso. Es el error que más se ha repetido.

## 2. Lo que necesita criterio

El script no juzga; estos tres puntos sí:

**Nada hardcodeado.** Toda decisión de negocio va al `.env` como variable
requerida. Se queda en el código sólo la física y las conversiones de unidad.
Con `/sin-hardcode <servicio>` o el agente `auditor-hardcode`.

```bash
grep -nE "= *[0-9]+(\.[0-9]+)?\b" services/*.py controllers/*.py | grep -v "ENV_VARS\|test\|# \|range(\|\[0\]\|== 0\|!= 0"
```

**El backend no devuelve texto de UI.** Códigos en `Enum`, nunca frases.

```bash
grep -rnE "detail *= *f?'[A-ZÁÉÍÓÚ][a-záéíóú]" services/ controllers/ routes/ | grep -v "\.value"
```

**Boilerplate intacto.** `api_exceptions.py`, `crud.py`, `db_connection.py`,
`environment.py`, `exceptions.py`, `logger_config.py`, `security.py` y
`utils.py` no se modifican sin consulta previa.

```bash
for f in api_exceptions.py crud.py environment.py exceptions.py \
         logger_config.py security.py utils.py; do
  diff -q ../quotes/services/$f services/$f >/dev/null 2>&1 \
    && echo "  $f OK" || echo "  $f DIFIERE — revisar si la adición es legítima"
done
```

## 3. Cómo reportar

Una línea por chequeo con su resultado real. Si `verify_service.py` dice
`ALL PASS`, se pega su salida y se añaden los tres puntos de criterio. Se
termina con **qué servicios quedan pendientes de que Rafael despliegue** y se
actualiza `SMARTDECISIONS.md` §4 «Estado actual» (reemplazando, no anexando).
