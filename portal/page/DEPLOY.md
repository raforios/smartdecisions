# Roadmap de despliegue — BearSoft / SmartDecisions

## Recursos desplegados (DEMO `portal/demo/`) — 2026-06-30
> El landing (`portal/page/`) ya lo despliega el usuario en su propio S3; esta
> infra sirve el **demo**. (La distribución se creó inicialmente para el landing
> por un malentendido y se reutilizó para el demo — de ahí el nombre del bucket.)

| Recurso | Valor |
|---|---|
| Cuenta AWS | `732887652913` (perfil `deploy_ml`, región `us-east-1`) |
| Bucket S3 (privado) | `bearsoft-smartdecisions-landing` (contiene el DEMO) |
| Origin Access Control | `E3JC2PMKQG3VJE` |
| CloudFront distribution | `EXP60FDO0MJVI` |
| URL CloudFront | `https://dl18qv60n6qco.cloudfront.net` |
| Dominio objetivo | `smartdecisions.bearsoft.com.bo` |

Re-deploy del demo:
```bash
aws s3 sync portal/demo s3://bearsoft-smartdecisions-landing/ --profile deploy_ml \
  --delete --exclude ".DS_Store"
aws cloudfront create-invalidation --distribution-id EXP60FDO0MJVI --paths "/*" --profile deploy_ml
```

Dominio `smartdecisions.bearsoft.com.bo` (configurado 2026-06-30):
- Cert ACM (us-east-1, ISSUED): `arn:aws:acm:us-east-1:732887652913:certificate/f4ab5c00-d918-4bc1-961e-c084c0e98432`
- Alias + cert ya agregados a la distribución `EXP60FDO0MJVI` (SNI, TLS1.2_2021).
- Cloudflare (DNS-only): CNAME `smartdecisions` → `dl18qv60n6qco.cloudfront.net`.
- `LOGIN_PATH` del demo ya está en `/index.html` (raíz del subdominio).

---


Dos sitios estáticos independientes, mismo patrón **S3 (privado) + CloudFront +
ACM + Cloudflare (solo DNS)**. Región fija: `us-east-1` (CloudFront exige el
certificado ACM ahí).

| Carpeta | Qué es | Dominio |
|---|---|---|
| `portal/page/` | Landing de info SmartDecisions (tema blanco) | `<DOMAIN>` (ej. `bearsoft.com.bo` / `www.bearsoft.com.bo`) |
| `portal/demo/` | App demo (login + módulos) | `smartdecisions.bearsoft.com.bo` |

Los botones "Probar demo" del landing apuntan a
`https://smartdecisions.bearsoft.com.bo` (el demo, que vive aparte).

Placeholders: `<PROFILE>` (ej. `deploy_ml`), `<ACCOUNT_ID>`, `<BUCKET>`,
`<DIST_ID>`, `<CERT_ARN>`, `<DOMAIN>`.

---

## A) Pasos genéricos (valen para cada sitio)

### 1. Bucket S3 privado (origin)
```bash
aws s3api create-bucket --bucket <BUCKET> --region us-east-1 --profile <PROFILE>
aws s3api put-public-access-block --bucket <BUCKET> --profile <PROFILE> \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### 2. Subir el contenido
```bash
# Landing de info:
aws s3 sync /Users/rafael/Work/projects/back/SmartBear/app/portal/page \
  s3://<BUCKET>/ --profile <PROFILE> --delete \
  --exclude ".DS_Store" --exclude "DEPLOY.md"
```

### 3. Certificado ACM (us-east-1)
```bash
aws acm request-certificate --region us-east-1 --profile <PROFILE> \
  --domain-name <DOMAIN> --validation-method DNS \
  --query CertificateArn --output text
```
Crea el `CNAME` de validación que devuelve ACM en **Cloudflare** (DNS-only / nube
gris). Espera a `ISSUED`:
```bash
aws acm describe-certificate --region us-east-1 --profile <PROFILE> \
  --certificate-arn <CERT_ARN> --query 'Certificate.Status'
```

### 4. CloudFront + Origin Access Control (OAC)
- Origin: `<BUCKET>.s3.us-east-1.amazonaws.com` + OAC (S3, sigv4).
- **Default root object**: `index.html`.
- Viewer protocol policy: **redirect-to-https**; Compression: **on**.
- **Alternate domain name (CNAME)**: `<DOMAIN>`.
- **Custom SSL certificate**: `<CERT_ARN>`.
- Custom error responses (opcional): `403`/`404` → `/index.html` (200), por ser
  single-page con anclas.
- Adjuntar al bucket la policy que permite leer vía OAC (condición
  `AWS:SourceArn = arn:aws:cloudfront::<ACCOUNT_ID>:distribution/<DIST_ID>`).

### 5. DNS en Cloudflare
- **CNAME** `<DOMAIN>` → `dXXXXXXXX.cloudfront.net`.
- **Recomendado: DNS-only (nube gris).** CloudFront/ACM terminan el TLS.
- Si lo dejas **proxied (naranja)**: SSL mode de Cloudflare en **Full (strict)**
  y mantén el *alternate domain name* + cert ACM en CloudFront.

### 6. Verificación
```bash
curl -I https://<DOMAIN>            # 200 + via cloudfront
```

### 7. Re-despliegues (invalidar caché)
```bash
aws s3 sync ... && aws cloudfront create-invalidation \
  --distribution-id <DIST_ID> --paths "/*" --profile <PROFILE>
```
> Los assets ya usan cache-busting (`style.css?v=1`, `favicon.svg?v=1`); súbelos
> con `?v=N` o invalida todo en cada deploy.

---

## B) Específico del DEMO (`smartdecisions.bearsoft.com.bo`)
Mismos pasos A) con `<DOMAIN> = smartdecisions.bearsoft.com.bo` y un bucket/
distribución propios, sincronizando `portal/demo/`. **Antes de subir**:

- En `portal/demo/js/config.js`, si la raíz del subdominio es el login, deja
  `LOGIN_PATH = '/index.html'` (hoy está en `/demo/index.html`).
- Verifica que las 7 URLs de API Gateway en `config.js` sean las productivas
  (INGEST / OPTIMIZATION / ANALYTICS ya están deployadas).
