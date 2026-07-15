# Despliegue del frontend "La Cumbre Minera"

Guía operativa para publicar `app/demo/cumbre-minera/` en
**https://cumbre.mineria.gob.bo** usando AWS S3 + CloudFront, con DNS gestionado
en Cloudflare.

## Arquitectura

```
Browser (https://cumbre.mineria.gob.bo)
        │ HTTPS
        ▼
   CloudFront Distribution ──── certificado ACM (us-east-1)
        │ vía Origin Access Control (OAC)
        ▼
   S3 bucket privado: cumbre-mineria-frontend
   └─ login.html, app.html, css/, js/, data/, ...

DNS:
   Cloudflare (zona mineria.gob.bo)
   └─ CNAME cumbre → d3xxxxxxx.cloudfront.net   (DNS only / proxy gris)
```

> **Importante**: el proxy de Cloudflare debe estar en **DNS only** (icono
> gris), no naranja. Si lo dejas naranja, Cloudflare hace MITM con su propio
> certificado y rompe la negociación SSL contra CloudFront.

---

## Estado actual

Los pasos marcados con `[✓]` ya fueron ejecutados desde la sesión de Claude
Code. Los `[ ]` te quedan a ti.

| Paso | Estado |
|---|---|
| A. Bucket S3 creado y privado | `[✓]` |
| B. Frontend sincronizado | `[✓]` |
| C. Certificado ACM solicitado | `[✓]` (`ISSUED`) |
| D. CNAME de validación en Cloudflare | `[✓]` |
| E. CloudFront distribution `EBN31O1IQA883` | `[✓]` (Deployed, dominio `d1wz098n1gidtt.cloudfront.net`) |
| F. CNAME `cumbre` → CloudFront en Cloudflare | `[✓]` |
| G. Bucket policy con OAC | `[✓]` |
| H. CORS de AUTH y mining_summit | `[✓]` |
| I. Smoke test (login + reportes en producción) | `[✓]` |
| Z. OriginPath corregido a `""` | `[✓]` |
| Z. Logo movido dentro del bucket (`img/cropped-escudo.png`) | `[✓]` |

**Despliegue completado el 2026-05-05.** El sitio está operativo en `https://cumbre.mineria.gob.bo`.

## Datos clave (úsalos en los pasos siguientes)

- **Region AWS**: `us-east-1`
- **Bucket S3**: `cumbre-mineria-frontend`
- **Account ID**: `732887652913`
- **ACM Certificate ARN**: `arn:aws:acm:us-east-1:732887652913:certificate/0264f6d5-6d62-4d9e-bcbb-5e8b05495362`
- **Dominio público**: `cumbre.mineria.gob.bo`
- **Endpoints API**:
  - AUTH: `https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth`
  - mining_summit: `https://dlhnaicgf2.execute-api.us-east-1.amazonaws.com`

---

## A. Bucket S3 [✓ ya ejecutado]

```bash
aws s3api create-bucket --bucket cumbre-mineria-frontend --region us-east-1

aws s3api put-public-access-block \
  --bucket cumbre-mineria-frontend \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Bucket privado. CloudFront lo accederá vía OAC en el paso E.

## B. Sync del frontend [✓ ya ejecutado]

```bash
aws s3 sync app/demo/cumbre-minera/ s3://cumbre-mineria-frontend/ \
  --delete \
  --exclude ".DS_Store" --exclude "**/.DS_Store" \
  --exclude "__pycache__/*" --exclude "**/__pycache__/*"
```

18 archivos subidos (~71 KiB). Para cada deploy posterior, el comando es el
mismo + invalidar CloudFront (paso final).

## C. Certificado ACM [✓ solicitado, pendiente de validación]

```bash
aws acm request-certificate \
  --domain-name cumbre.mineria.gob.bo \
  --validation-method DNS \
  --region us-east-1
```

ARN: `arn:aws:acm:us-east-1:732887652913:certificate/0264f6d5-6d62-4d9e-bcbb-5e8b05495362`

Para validar, debes crear el siguiente CNAME en Cloudflare ⬇️.

## D. CNAME de validación en Cloudflare ⚠️ **HAZLO TÚ AHORA**

En el panel de Cloudflare, zona `mineria.gob.bo`, agrega:

| Type  | Name                                                 | Target                                                              | Proxy       |
|-------|------------------------------------------------------|---------------------------------------------------------------------|-------------|
| CNAME | `_1823c04dc0cd15bb03913aa104435b45.cumbre`           | `_f13fe68d59bae9dbfd21ed871df6d764.jkddzztszm.acm-validations.aws.` | DNS only    |

> Cloudflare a veces muestra una advertencia "CNAME flattening". Está bien,
> deja el record tal cual.

Verificación después de crearlo (5-30 min hasta que pase a `ISSUED`):

```bash
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:732887652913:certificate/0264f6d5-6d62-4d9e-bcbb-5e8b05495362 \
  --region us-east-1 \
  --query 'Certificate.Status' --output text
```

Cuando devuelva `ISSUED`, sigues con el paso E.

## E. Crear la distribución CloudFront (Console)

Más cómodo desde la **AWS Console** porque tiene muchas opciones interactivas y
un wizard razonable. Pasos exactos:

1. **Console → CloudFront → Create distribution**.
2. **Origin**:
   - Origin domain: selecciona el bucket `cumbre-mineria-frontend.s3.us-east-1.amazonaws.com`.
   - **Origin access**: *Origin access control settings (recommended)*.
   - Click **Create new OAC** → Name: `cumbre-mineria-oac`. Sign requests: *Yes*. Create.
   - Cuando guardes, CloudFront mostrará un banner ofreciendo **Copy policy** para el bucket. Cópiala (la pegamos en el paso G).
3. **Default cache behavior**:
   - Viewer protocol policy: **Redirect HTTP to HTTPS**.
   - Allowed HTTP methods: **GET, HEAD, OPTIONS**.
   - Cache key and origin requests: **Cache policy = `CachingOptimized`**.
   - Compress objects automatically: *Yes*.
4. **Settings**:
   - Price class: **Use only North America and Europe** (`PriceClass_100`).
   - Alternate domain name (CNAME): **`cumbre.mineria.gob.bo`**.
   - Custom SSL certificate: el cert recién emitido (ACM `0264f6d5-...`).
   - Default root object: **`index.html`** (landing público; `login.html` es solo el acceso de operador).
5. **Create distribution** y espera 3-8 min al *Deployed*.
6. Anota el `Distribution domain name` (ej. `d3xxxxxxx.cloudfront.net`) y el
   `Distribution ID` (ej. `E1ABCXXXXXXX`). Los necesitas en los pasos F y al
   final.

### Behaviors adicionales (después de crear)

Volver a la distribución → pestaña **Behaviors** → **Create behavior** dos
veces, para que HTML y `config.json` no se cacheen y los deploys se vean
inmediatos:

| Path pattern        | Cache policy        |
|---------------------|---------------------|
| `*.html`            | `CachingDisabled`   |
| `data/config.json`  | `CachingDisabled`   |

### Custom error responses (para SPA)

Pestaña **Error pages** → **Create custom error response** dos veces:

| HTTP error code | Customize response | Response page path | HTTP response code |
|-----------------|--------------------|--------------------|--------------------|
| 403             | Yes                | `/login.html`      | 200                |
| 404             | Yes                | `/login.html`      | 200                |

Esto evita 403 cuando alguien recargue una ruta que solo existe como hash
(ej. `/app.html#registro`).

## F. CNAME `cumbre` → CloudFront en Cloudflare

En la zona `mineria.gob.bo`:

| Type  | Name     | Target                          | Proxy    |
|-------|----------|---------------------------------|----------|
| CNAME | `cumbre` | `<TU_DIST>.cloudfront.net`      | DNS only |

Sustituye `<TU_DIST>` por el `Distribution domain name` del paso E.

Cuando esto propague (1-5 min) podrás abrir https://cumbre.mineria.gob.bo —
todavía dará error porque falta la policy del bucket (paso G).

## G. Pegar la bucket policy generada por OAC

Desde la consola de CloudFront, en la pestaña **Origins** del distribution
→ selecciona el origin del bucket → **Copy policy**. La pegas con:

```bash
cat > /tmp/cumbre-bucket-policy.json <<'EOF'
<<<pega aquí el JSON que copiaste de CloudFront>>>
EOF

aws s3api put-bucket-policy \
  --bucket cumbre-mineria-frontend \
  --policy file:///tmp/cumbre-bucket-policy.json
```

Tendrá una forma como:

```json
{
  "Version": "2008-10-17",
  "Id": "PolicyForCloudFrontPrivateContent",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipal",
      "Effect": "Allow",
      "Principal": { "Service": "cloudfront.amazonaws.com" },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::cumbre-mineria-frontend/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::732887652913:distribution/<DIST_ID>"
        }
      }
    }
  ]
}
```

## H. Permitir el dominio en CORS de los backends

Una vez `https://cumbre.mineria.gob.bo` esté operativo, en el Lambda de **AUTH**
y de **mining_summit** agrega/actualiza la variable de entorno:

```
CORS_ALLOWED_ORIGINS=https://cumbre.mineria.gob.bo,http://127.0.0.1:5500,http://localhost:5500
```

Console → Lambda → función → Configuration → Environment variables →
**Edit** → guardar. No requiere redeploy del código (la lectura es en runtime
desde `os.environ`).

Si los servicios fueron desplegados con el `CORSMiddleware` ya en código (sí
lo están), basta actualizar la env var y CloudFront/Cloudflare reconocerán el
origen. Sin esto, el browser bloqueará las llamadas desde el dominio público.

## I. Smoke test (cuando todo esté listo)

```bash
# 1. ¿El cert quedó ISSUED?
aws acm describe-certificate \
  --certificate-arn arn:aws:acm:us-east-1:732887652913:certificate/0264f6d5-6d62-4d9e-bcbb-5e8b05495362 \
  --region us-east-1 --query 'Certificate.Status' --output text
#  esperado: ISSUED

# 2. ¿El CNAME apunta a CloudFront?
dig +short cumbre.mineria.gob.bo
#  esperado: <distribution>.cloudfront.net.  (un IP de CloudFront detrás)

# 3. ¿El TLS valida?
curl -I https://cumbre.mineria.gob.bo/login.html
#  esperado: HTTP/2 200, content-type: text/html

# 4. ¿config.json se sirve?
curl -s https://cumbre.mineria.gob.bo/data/config.json | jq '.endpoints'

# 5. ¿Preflight OPTIONS de AUTH responde 200 desde el nuevo origen?
curl -i -X OPTIONS 'https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth/login' \
  -H 'Origin: https://cumbre.mineria.gob.bo' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' | head -10
#  esperado: HTTP/2 200 con access-control-allow-origin: https://cumbre.mineria.gob.bo
```

Si los 5 pasan, abre `https://cumbre.mineria.gob.bo/login.html` en el browser
y completa un login real → debe redirigirte a `app.html`.

---

## Operación posterior (deploy de cambios)

```bash
# Sincroniza diferencias
aws s3 sync app/demo/cumbre-minera/ s3://cumbre-mineria-frontend/ \
  --delete \
  --exclude ".DS_Store" --exclude "**/.DS_Store" \
  --exclude "__pycache__/*" --exclude "**/__pycache__/*"

# Invalida cache de CloudFront para que los usuarios vean el cambio
aws cloudfront create-invalidation \
  --distribution-id <TU_DIST_ID> \
  --paths "/*"
```

> Tip: si solo cambiaste un archivo, restringe el `--paths` (`/js/app.js` por
> ejemplo). Las primeras 1.000 invalidaciones por mes son gratis; sé razonable
> para no acumular costo.

---

## Troubleshooting rápido

| Síntoma | Causa probable | Fix |
|---|---|---|
| `403 AccessDenied` (XML) en TODAS las rutas, incluso con OAC y bucket policy correctas | **Origin path** del origin tiene un valor (típicamente `/*`) en lugar de estar vacío | Ver "Origin path vs Path pattern" abajo. |
| `403 Forbidden` al abrir el dominio | Bucket policy aún sin pegar (paso G) | Copia la policy desde CloudFront → `aws s3api put-bucket-policy`. |
| `ERR_CERT_AUTHORITY_INVALID` | Cloudflare en proxy naranja | Cambia el record `cumbre` a **DNS only** (gris). |
| Login da `CORS error` | Falta `CORS_ALLOWED_ORIGINS` en Lambda | Paso H. |
| Cambios no se ven | Cache de CloudFront | `aws cloudfront create-invalidation`. |
| `Status: PENDING_VALIDATION` permanente | El CNAME del paso D está en proxy naranja | Cámbialo a DNS only. |

### "Origin path" vs "Path pattern" — confusión común

Son dos campos distintos en CloudFront que se confunden:

| Campo | Dónde está | Significado | Valor correcto para este proyecto |
|---|---|---|---|
| **Origin path** | En el origin | Prefijo que CloudFront *agrega* a cada request antes de pegarle al bucket | **vacío** (sirve desde la raíz del bucket) |
| **Path pattern** | En cada cache behavior | Filtro de qué requests caen en este behavior | `*.html`, `/data/*`, `Default (*)`, etc. |

Si "Origin path" tiene `/*`, CloudFront pide `/*/login.html` al S3 y nada existe ahí → 403 en todo. Para arreglarlo vía CLI:

```bash
DIST=<TU_DIST_ID>
aws cloudfront get-distribution-config --id $DIST > /tmp/dist-cfg.json
ETAG=$(python3 -c "import json; print(json.load(open('/tmp/dist-cfg.json'))['ETag'])")
python3 -c "
import json
data = json.load(open('/tmp/dist-cfg.json'))
for o in data['DistributionConfig']['Origins']['Items']:
    o['OriginPath'] = ''
json.dump(data['DistributionConfig'], open('/tmp/dist-cfg-fixed.json','w'))
"
aws cloudfront update-distribution \
  --id $DIST --if-match "$ETAG" \
  --distribution-config file:///tmp/dist-cfg-fixed.json
aws cloudfront wait distribution-deployed --id $DIST
aws cloudfront create-invalidation --distribution-id $DIST --paths "/*"
```

---

## Limpieza (si tienes que dar marcha atrás)

```bash
# 1. Vaciar y eliminar bucket
aws s3 rm s3://cumbre-mineria-frontend --recursive
aws s3api delete-bucket --bucket cumbre-mineria-frontend --region us-east-1

# 2. Borrar la distribución CloudFront (primero hay que deshabilitarla;
#    es más rápido por consola: Disabled → Delete cuando termine).

# 3. Borrar el cert ACM (después de quitarlo de CloudFront)
aws acm delete-certificate \
  --certificate-arn arn:aws:acm:us-east-1:732887652913:certificate/0264f6d5-6d62-4d9e-bcbb-5e8b05495362 \
  --region us-east-1

# 4. Borrar los CNAME en Cloudflare (cumbre y _1823c04...).
```
