# SmartDecisions — Portal Landing

Landing page estática del producto **SmartDecisions** (BearSoft).

## Stack

HTML5 + CSS3 + JavaScript vanilla. **Cero dependencias**, cero build step.

## Estructura

```
portal/
├── index.html
├── style.css
├── script.js
├── assets/
│   ├── favicon.svg
│   └── logo-bear.svg
└── README.md
```

## Desarrollo local

```bash
cd app/portal
python3 -m http.server 8080
# Abrir http://localhost:8080
```

## Despliegue (presupuesto $0)

Subir el contenido de `portal/` a un bucket S3 estático servido por CloudFront:

```bash
aws s3 sync portal/ s3://<bucket-smartdecisions-portal>/ --delete
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*"
```

Alternativas equivalentes en costo: GitHub Pages, Cloudflare Pages, Netlify.

## Decisiones de diseño

- **Oso reinterpretado** como símbolo de "decisiones firmes" (no más asociación con la
  marca antigua SmartBear; el oso ahora porta una curva ascendente).
- Paleta dark theme con acentos teal (`#5ad6c2`) y azul (`#7aa2ff`) para evocar datos
  y confianza.
- Formulario de contacto **sin backend**: usa `mailto:` (alineado con `SMARTDECISIONS.md §8`).

## Pendiente

- [ ] Conectar botón "Probar demo" al flujo real cuando exista (paso 4 del POC).
- [ ] Sustituir SVG inline del oso por una versión ilustrada cuando se defina arte definitivo.
- [ ] Añadir Open Graph / Twitter cards para compartir en redes.
