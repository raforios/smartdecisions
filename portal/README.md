# Portal — BearSoft / SmartDecisions

Sitios estáticos del portal. **HTML5 + CSS3 + JavaScript vanilla**, cero
dependencias, cero build step.

## Estructura

```
portal/
├── page/     # Landing OFICIAL de la empresa (BearSoft) → bearsoft.com.bo
│              #   incluye la sección de producto SmartDecisions (data-driven,
│              #   contenido en page/js/content.json). Ver page/DEPLOY.md.
├── demo/     # App demo de SmartDecisions (login + módulos) → smartdecisions.bearsoft.com.bo
├── assets/   # Imágenes/íconos compartidos (referenciados por la demo vía ../assets/)
└── README.md
```

> Hay **un solo landing**: `page/`. El antiguo landing de producto en la raíz
> (`portal/index.html`) se eliminó porque su contenido ya está —y más completo—
> en la sección SmartDecisions del landing de BearSoft (`page/`).

## Desarrollo local

```bash
cd app/portal/page   # o app/portal/demo
python3 -m http.server 8080
# Abrir http://localhost:8080
```

## Despliegue

- **Landing** (`page/`): ver `page/DEPLOY.md`. Bucket `bearsoft.com.bo` (S3 static
  website) — lo despliega Rafael en su propio S3.
- **Demo** (`demo/`): bucket `bearsoft-smartdecisions-landing` + CloudFront
  `EXP60FDO0MJVI` (perfil `deploy_ml`, us-east-1). Ver `page/DEPLOY.md`.

Alternativas equivalentes en costo $0: GitHub Pages, Cloudflare Pages, Netlify.
