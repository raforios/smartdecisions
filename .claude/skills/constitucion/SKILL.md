---
name: constitucion
description: Audita el código escrito contra las reglas de CLAUDE.md que se rompen en silencio — idioma, invenciones estructurales, DTOs y textos de UI. Córrela antes de reportar cualquier trabajo terminado, no después de que Rafael encuentre el error.
argument-hint: [servicio | ruta | vacío para el diff actual]
allowed-tools: Bash(cd *), Bash(git *), Bash(grep *), Bash(find *), Bash(python3 *), Bash(wc *), Bash(ls *), Read, Edit
---

Audita `$1` contra las reglas de `CLAUDE.md` que **no fallan solas**. Sin
argumento, audita lo que cambió en el árbol de trabajo:

```bash
git diff --name-only; git ls-files --others --exclude-standard
```

## Qué entra y qué no

Una revisión general alcanza **sólo los once servicios propios de BearSoft**:

```
SmartDecisions   AI · ANALYTICS · INGEST · MINING_ANALYSIS · OPTIMIZATION · QUOTES
SmartBilling     BILLING
Genéricos        AUTH · EVENTS · FILES
Capacitación     ML_FUNCTIONS
```

**Nunca se tocan sin que Rafael lo pida para ese servicio en concreto:**
FORMS, LOCALIZATION, TRADE, CMS y MINING_SUMMIT. Son
de clientes —Binaria y el Ministerio— y viven en el monorepo por conveniencia;
un cambio ahí toca código entregado y en varios casos ya cerrado. BILLING (el
antiguo SUPPLIES) **sí es nuestro** y entra en la revisión.

Si un hallazgo legítimo aparece en uno de esos cinco, **se reporta y se espera el
OK**. No se corrige de paso. El 15-09-2026 un barrido de idioma modificó 11
archivos de siete servicios de cliente y hubo que restaurarlos con
`git checkout`.

Los tests y Pylint no detectan nada de lo que sigue: un comentario en castellano
pasa la suite, un `__all__` decorativo pasa Pylint y un `dict` en vez de un DTO
pasa las dos cosas. Por eso existe esta skill aparte de `/verificar-servicio`.

**Corre los siete barridos, arregla lo que encuentres y sólo entonces reporta.**

---

## 1. Idioma: inglés en el código, castellano sólo de cara al usuario

`CLAUDE.md` §1: *código y su documentación interna en inglés, estricto*.
Identificadores, comentarios y docstrings. Sin excepciones y sin mezclas.

```bash
python3 - <<'PY'
import re, subprocess
from pathlib import Path

# Marcadores inequívocos del castellano. Se excluyen a propósito 'no', 'es',
# 'la', 'el', 'un', 'sin', 'con' y 'a': existen en inglés o coinciden con
# palabras inglesas, y con ellas el barrido marcaba comentarios correctos.
SPANISH = re.compile(
    r'\b(que|los|las|del|por|para|como|cuando|cada|toda|todos|hay|pero|porque|'
    r'acá|así|sólo|según|entre|desde|hasta|esto|esta|este|estos|sus|cuál|'
    r'está|están|más|aquí|qué|dónde|archivo|cliente|producto|venta|ventas|'
    r'cobro|cobros|fecha|días|monto|saldo|crédito|plazo|factura|facturas|'
    r'tramo|tramos|política|almacén|demanda|cobertura)\b', re.I)

# Los once servicios propios. Todo lo demás es de un cliente y queda fuera
# del barrido: se reporta, no se corrige.
OURS = ('ai', 'analytics', 'auth', 'billing', 'events', 'files', 'ingest',
        'mining_analysis', 'ml_functions', 'optimization', 'quotes')


def is_ours(path: Path) -> bool:
    '''True cuando la ruta pertenece a un servicio de SmartDecisions.'''
    parts = path.parts
    if 'services' not in parts:
        return True                       # tools/, portal/: son del producto
    index = parts.index('services')
    return len(parts) > index + 1 and parts[index + 1] in OURS


changed = subprocess.run(['git', 'diff', '--name-only'], capture_output = True,
                         text = True).stdout.split()
untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'],
                           capture_output = True, text = True).stdout.split()
total = 0
for name in sorted(set(changed + untracked)):
    path = Path(name)
    if path.suffix != '.py' or not path.exists() or not is_ours(path):
        continue
    for number, line in enumerate(path.read_text(encoding = 'utf-8').splitlines(), 1):
        stripped = line.strip()
        body = stripped.lstrip('#').strip() if stripped.startswith('#') else (
            stripped.strip("'").strip('"') if stripped.startswith(("'''", '"""')) else '')
        # Lo que va entre comillas puede ser un valor del contrato citado a
        # propósito ('CREDITO', 'Crédito'): no es documentación en castellano.
        outside = re.sub(r"'[^']*'|\"[^\"]*\"", '', body)
        if outside and len(SPANISH.findall(outside)) >= 2:
            print(f'{name}:{number}  {body[:72]}')
            total += 1
print(f'\ncomentarios en castellano: {total}')
PY
```

Cero resultados, **sin excepciones y el boilerplate incluido**. El boilerplate
nació enteramente en inglés: el `db_connection.py` original de EVENTS (agosto
2025) no tiene una palabra en castellano, y las que hay hoy las introdujo Claude
en commits posteriores. Que un archivo sea contrato significa que no se cambia su
comportamiento; no es permiso para dejarlo en otro idioma.

Las cadenas de cara al usuario —encabezados de la plantilla, etiquetas del
frontend, textos de un `.md` de cliente— **sí** van en castellano: ésas no son
documentación interna.

```bash
# Comprobar si un comentario ya estaba o lo agregó Claude, antes de afirmarlo:
git log --format='%h %ad %s' --date=short -S'<el texto exacto>' -- <archivo>
git show <primer-commit>:<archivo> | head -20
```

## 2. Nada que no esté en los servicios de referencia

`CLAUDE.md` §3: *no se inventan módulos de infraestructura*. La regla se rompe
agregando mecanismos que ningún servicio de referencia tiene. El criterio es
literal: **si `quotes` o `localization` no lo tienen, no va.**

```bash
grep -rn "^__all__" services/ schemas/ controllers/ routes/ 2>/dev/null
grep -rln "if TYPE_CHECKING\|@singledispatch\|metaclass=\|__init_subclass__" \
  services/ schemas/ 2>/dev/null
```

Cero en los dos. `__all__` es el caso testigo: sólo hace algo con
`from modulo import *`, que este proyecto nunca usa, y **no tiene nada que ver
con `__init__.py`** —ése marca el paquete y es obligatorio—. Se puso cuatro
veces por criterio propio no pedido; eso es exactamente lo que §10.2 prohíbe.

## 3. Carpetas y archivos que nadie pidió

```bash
git ls-files --others --exclude-standard | grep -v '\.pyc$'
find . -type d -not -path './.venv/*' -not -path '*/__pycache__*' \
  -not -path './.git/*' -maxdepth 2 | sort
```

Las cinco capas son `schemas/`, `models/`, `routes/`, `controllers/`,
`services/`, más `tests/`. Cualquier otra carpeta dentro de un microservicio se
pregunta antes de crearla.

## 4. DTOs, no diccionarios

`.claude/rules/python.md`: *DTOs Pydantic o dataclasses, no diccionarios
sueltos*. `rows: list[dict[str, Any]]` como contrato entre capas ya se corrigió
una vez.

```bash
grep -rn "Dict\[str, Any\]\|dict\[str, Any\]" \
  services/*.py controllers/*.py routes/*.py 2>/dev/null \
  | grep -v "utils.py\|crud.py\|environment.py\|payload\|# " 
```

Un `dict[str, Any]` es aceptable para el ítem de DynamoDB y para el payload que
la capa de IA recibe sin tocar. Como retorno de un motor de negocio, no.

## 5. El backend devuelve códigos, no frases

`CLAUDE.md` §6. Se rompe al escribir el texto que el usuario lee dentro de un
`Enum` o de un `detail`.

```bash
grep -rnE "'[A-Z][a-záéíóúñ ]{18,}'|\"[A-Z][a-záéíóúñ ]{18,}\"" \
  schemas/*.py services/*.py 2>/dev/null | grep -v "description =\|'''\|# "
```

Una frase larga en castellano dentro de un `Enum` o un `raise` es un hallazgo.
Los `description =` de Pydantic y los docstrings quedan fuera: documentan el
contrato, no viajan como respuesta.

## 6. Configuración requerida, sin respaldos en el código

```bash
grep -rnE "\] or [0-9'\"]|get\('[A-Z_]+', *[0-9]" services/*.py 2>/dev/null
grep -n '^[A-Z_][A-Z_0-9]*=.*,' .env 2>/dev/null
```

Cero en los dos. Una lista en el `.env` se separa con guiones, nunca con comas:
el despliegue pasa el archivo entero a `--environment Variables={...}`.

## 7. Lo aprobado no se reescribe

`CLAUDE.md` §10.8. Antes de tocar un archivo que ya estaba, comprueba qué se
quitó y no sólo qué se agregó:

```bash
git diff --stat
git diff | grep '^-' | grep -v '^---' | head -40
```

Cada línea borrada de código previo tiene que ser una decisión consciente y
declarada al reportar. Si no se pidió quitarla, se restituye.

---

## Cómo reportar

Una línea por barrido, con el número real:

```
alcance       11 servicios propios · 5 de cliente excluidos
idioma        0 comentarios en castellano (boilerplate incluido)
boilerplate   0 __all__, 0 mecanismos inventados
estructura    0 carpetas nuevas
DTOs          0 dict como contrato
códigos       0 frases de UI en el backend
configuración 0 respaldos en código · .env sin comas
lo aprobado   14 líneas borradas, todas declaradas
```

**Y lo más importante:** si un barrido encuentra algo, arréglalo y dilo al
reportar — con el número de hallazgos. Callarlo es peor que el hallazgo, porque
convierte un descuido en una afirmación falsa de que el trabajo está terminado.
