# tools/ — herramientas que se vuelven a usar

Cada carpeta dice para qué sirve. Aquí sólo hay lo que se corre más de una vez;
una carga puntual se hace en línea y no se guarda (Rafael, 16-oct-2026).

Se corren desde la raíz del repositorio. Las que escriben en AWS empiezan en
simulación y sólo escriben con `--yes`.

| Carpeta | Para qué | Herramienta | Cuándo se corre |
|---|---|---|---|
| `verification/` | Revisar un servicio antes de entregarlo | `verify_service.py` | Antes de cada reporte: `python tools/verification/verify_service.py services/finance` (o `--all`, `--tools`) |
| | | `verify_checks.py` | No se corre sola: son las reglas que usa `verify_service.py` |
| | | `check_signatures.py` | La corre el hook al editar un `.py` de `services/`; `--fix` reescribe las firmas |
| `deploy/` | Publicar el frontend | `deploy_demo_portal.py` | Cada despliegue del portal demo: `python -m tools.deploy.deploy_demo_portal --yes` |
| `templates/` | Plantillas que el cliente llena | `build_sales_template.py` | Cuando cambia el contrato de COMMERCIAL |
| | | `build_finance_template.py` | Cuando cambia el contrato de FINANCE; escribe en `portal/demo/plantillas/` |
| | | `build_finance_catalog.py` | Cada vez que el `ADMIN` cambia el catálogo de cuentas: lo genera desde AWS en `portal/demo/plantillas/` y se publica con el portal |
| | | `convert_sales_export.py` | Al recibir el export de ventas de un ERP nuevo, para llevarlo a la plantilla |
| `seeds/` | Datos base que todo ambiente necesita | `seed_finance.py` | Catálogo de cuentas y tasas de ley de FINANCE, leídos del contrato aprobado |
| `seeds/` | | `seed_service_parameters.py` | Los valores de negocio de un servicio en su tabla `<servicio>_parameters`, desde `docs/parametros.md` |
| `demo/` | Preparar una demostración | `seed_demo_routes.py` | La mañana de cada demo de Rutas: `--date AAAA-MM-DD --yes --reset` |
| | | `seed_billing_demo.py` | La farmacia de demostración de BILLING |
| | | `samples/` | Archivos de ejemplo para subir en una demo (ventas, stock) |
| `testing/` | Probar sin depender de terceros | `dry_run_invoice.py` | Una factura completa con el SIAT simulado; la usa un test de BILLING |
| `documents/` | Convertir documentos | `md_to_docx.py` | Para entregar un informe en Word |
| | | `pdf_to_markdown.py` | Para leer un PDF largo por partes |
| `reports/` | Informes de uso | `traffic_report.py` | Visitas a los sitios de BearSoft, desde los logs de CloudFront |
| `notibol/` | Herramienta aparte | `notibol_scraper.py` | Noticias de economía de Notibol por fecha; su guía de instalación y sus dependencias están en la misma carpeta |
