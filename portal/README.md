# Portal — BearSoft

Static sites. **HTML5 + CSS3 + Vanilla JavaScript**: no framework, no
dependencies, no build step. Each site calls the API at
`api.bearsoft.com.bo/v1/<service>/…` and signs in against AUTH.

## Layout

```
portal/
├── page/      BearSoft landing, with the SmartDecisions product section
│              (content in page/js/content.json)      → bearsoft.com.bo
├── demo/      SmartDecisions app: sign-in, Financial Analysis, Commercial,
│              Minerals and Settings                  → smartdecisions.bearsoft.com.bo
├── billing/   SmartBilling app: counter, till, sales, catalog, receiving,
│              customers and SIN invoicing            → smartbilling.bearsoft.com.bo
│              (see billing/README.md)
├── raforios/  Rafael Ríos Bascón's personal site
└── README.md
```

There is one landing: `page/`. Shared images live inside each site; there is
no common `assets/` folder.

## Local development

```bash
cd app/portal/demo   # or page, billing
python3 -m http.server 8080
# open http://localhost:8080
```

## Deployment

Claude publishes every frontend; Rafael deploys the backend (`CLAUDE.md` §10).
All sites live on S3 + CloudFront, profile `deploy_ml`, `us-east-1`.

| Site | Bucket | CloudFront | How |
|---|---|---|---|
| `page/` | `bearsoft.com.bo` | `E3P1IBW1V8N4P9` | `aws s3 sync` + invalidation |
| `demo/` | `bearsoft-smartdecisions-landing` | `EXP60FDO0MJVI` | `python3 -m tools.deploy.deploy_demo_portal --yes` (stamps each asset with its content hash) |
| `billing/` | `bearsoft-smartbilling-portal` | `EWVWU4A03ZZ4Z` | `aws s3 sync portal/billing/ … --delete --exclude README.md --cache-control no-cache` + invalidation |

The step-by-step procedure, with the check that what is published matches
the local files, is the `/desplegar-frontend` skill.

## Testing

No automated tests: Rafael and Claude test every screen by hand in the
browser (Rafael, 2-nov-2026).
