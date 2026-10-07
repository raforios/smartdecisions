---
name: sin-hardcode
description: Barre un servicio buscando decisiones de negocio escritas en el código y las mueve al .env como variables requeridas. Es la corrección que más se ha repetido en este proyecto.
argument-hint: [servicio]
allowed-tools: Bash(cd *), Bash(grep *), Bash(python3 *), Read, Edit
---

Barre `$1` buscando valores de negocio incrustados y muévelos a `.env`.

## El criterio

**Si es una decisión, va al entorno. Si es aritmética, se queda.**

Y una segunda regla que costó dos rondas aprender: **las variables son
requeridas, no opcionales**. El patrón

```python
VALOR = ENV_VARS['X'] or 30      # ← mal
```

sigue siendo un número elegido por el código. El día que el servicio se despliegue
sin esa variable, corre callado sobre un valor que nadie decidió. Lo correcto es:

```python
ENV_VARS = load_and_validate_env_vars({'X': int})   # requerida
VALOR = ENV_VARS['X']
```

Si falta, el servicio no arranca y lo dice. Eso es lo que se busca.

## Qué buscar

```bash
cd services/$1

# Respaldos en el código
grep -rn "\] or [0-9'\"]" services/*.py controllers/*.py routes/*.py \
  | grep -v 'utils.py\|environment.py'

# Valores por defecto en firmas
grep -rnE ": int = [0-9]|: float = [0-9]|: bool = (True|False)" \
  services/*.py controllers/*.py routes/*.py | grep -v 'ge = |le = '

# Redondeos y precisiones
grep -rn "round(.*, [0-9])" services/*.py controllers/*.py

# Query() de FastAPI con literales
grep -rn "Query([0-9]" routes/*.py

# Umbrales sueltos
grep -rnE "^_[A-Z_]+: (int|float) = [0-9]" services/*.py
```

## Qué mover y qué no

**Se mueve** — porque alguien podría decidirlo distinto:

- Días, plazos, ventanas y horizontes
- Decimales de un importe, una cotización, un porcentaje o un error
- Umbrales de confianza, de corte, de muestra
- Parámetros de modelos (alfa, beta, phi, tamaños de ventana)
- Cuántas filas devuelve un listado por defecto
- Semillas de agrupamiento
- URLs y tiempos de espera de servicios externos
- Días de la semana que forman un bloque

**Se queda** — porque no es una decisión:

- Constantes físicas: el radio de la Tierra
- Conversiones de unidad: `/1000` de metros a km, `/60` de segundos a minutos
- `* 100` y `/ 100` de porcentaje a fracción
- Rangos de un formato: `randint(0, 255)` de RGB
- Coordenadas de maquetación de una plantilla de imagen, que describen esa
  imagen concreta

## Cómo dejarlo

Cada variable nueva va al `.env` **con un comentario que diga qué gobierna y por
qué ese valor**, no qué es:

```bash
# Días que cubre cada corrida programada. Más de uno a propósito: el BCB no
# publica fines de semana ni feriados, y una corrida que falló ayer debe
# repararla la siguiente.
SCHEDULED_SYNC_DAYS=7
```

## Trampa del despliegue

**Ningún valor puede llevar una coma.** `build_and_deploy.sh` pasa el `.env`
entero a `--environment Variables={...}`, donde la coma separa una variable de la
siguiente. Un `RATE_BLOCK_WEEKDAYS=5,6,0` rompe el despliegue con
`Error parsing parameter '--environment'`.

Usa otro separador y lee con `re.findall(r'\d+', ...)`, que tolera cualquiera.

## Al terminar

Corre la suite y Pylint, y **enumera lo que dejaste literal con su motivo**. Esa
lista es la que se revisa, no la de lo que moviste.
