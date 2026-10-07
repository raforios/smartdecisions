---
name: desplegar-frontend
description: Publica el portal demo o la página de BearSoft en S3+CloudFront, estampando cada asset con el hash de su contenido y verificando que lo publicado coincide con lo local. Los deploys de frontend los hace Claude; los de backend, Rafael.
argument-hint: [demo|page|billing] [modulo-opcional]
allowed-tools: Bash(python3 -m tools.deploy_demo_portal *), Bash(aws s3 *), Bash(aws cloudfront *), Bash(curl *), Bash(python3 *), Read
---

Despliega el frontend indicado en `$1` (`demo`, `page` o `billing`). Si no se indica, pregunta.

## Reparto de responsabilidades

**El frontend lo despliegas tú. El backend lo despliega Rafael.** Nunca ejecutes
`build_and_deploy.sh`; si un cambio necesita backend, dilo al final y enuméralo.

## Portal demo — `smartdecisions.bearsoft.com.bo`

```bash
python3 -m tools.deploy_demo_portal            # informa qué cambiaría
python3 -m tools.deploy_demo_portal --yes      # estampa, sube e invalida
python3 -m tools.deploy_demo_portal --yes --only $2
```

La herramienta estampa cada `.js` y `.css` con el **hash de su contenido** antes
de subir. Eso resuelve el problema que el `?v=` manual causaba: era el paso que
se olvidaba, y el navegador servía código viejo.

## Página de BearSoft — `bearsoft.com.bo`

Bucket `bearsoft.com.bo`, distribución `E3P1IBW1V8N4P9`, perfil `deploy_ml`.

```bash
cd portal/page
aws s3 sync assets/ s3://bearsoft.com.bo/assets/ --profile deploy_ml --no-progress
aws s3 cp index.html s3://bearsoft.com.bo/index.html --profile deploy_ml \
    --content-type 'text/html; charset=utf-8' --no-progress
aws cloudfront create-invalidation --distribution-id E3P1IBW1V8N4P9 \
    --paths '/' '/index.html' --profile deploy_ml --query 'Invalidation.Status' --output text
```

## Portal de SmartBilling — `portal/billing`

Bucket `bearsoft-smartbilling-portal`, distribución `EWVWU4A03ZZ4Z`, perfil
`deploy_ml`. Módulos ES sin estampado de versión: la invalidación es la que
evita el código viejo.

```bash
cd portal/billing
aws s3 sync . s3://bearsoft-smartbilling-portal/ --exclude README.md --exclude ".*" \
    --profile deploy_ml --no-progress
aws cloudfront create-invalidation --distribution-id EWVWU4A03ZZ4Z \
    --paths '/*' --profile deploy_ml --query 'Invalidation.Status' --output text
```

## Verificación obligatoria

**Un despliegue no termina hasta comprobar que lo publicado es lo local.** Se ha
dado el caso de reportar “desplegado” con el archivo viejo todavía servido.

```python
python3 - <<'PY'
import hashlib, urllib.request
from pathlib import Path
BASE, HOST = Path('portal/demo'), 'https://smartdecisions.bearsoft.com.bo'
for rel in ('home.html', 'js/config.js', 'styles/demo.css'):
    local = hashlib.sha256((BASE / rel).read_bytes()).hexdigest()[:10]
    remote = hashlib.sha256(urllib.request.urlopen(
        f'{HOST}/{rel}', timeout = 20).read()).hexdigest()[:10]
    print(f'  {rel:24} {"OK" if local == remote else "DESFASADO"}')
PY
```

Antes de subir, comprueba también que **cada `id` que busca el JS existe en el
HTML** y que ningún `src`/`href` local apunta a un archivo inexistente. Un
`VIEW_TO_KIND is not defined` costó una demo entera.

## Gotchas comprobados

- **Rutas absolutas en el login.** La distribución mapea 404 → `/index.html`
  dejando la URL intacta, así que la página de login puede correr bajo
  cualquier subruta; con rutas relativas sus scripts devuelven HTML y el
  navegador lanza `Unexpected token '<'`. Las páginas de módulo usan rutas
  relativas (ver `.claude/rules/frontend.md`).
- **CloudFront cachea.** Después de invalidar, verifica con `?x=$RANDOM`.
- **`content-type` explícito** al subir HTML suelto con `aws s3 cp`.

## Al terminar

Di qué se publicó, el resultado de la verificación, y **qué servicios de backend
quedan pendientes de que Rafael despliegue**.
