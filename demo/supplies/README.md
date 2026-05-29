# Supplies — Frontend

UI estática que consume el microservicio Supplies (`/v1/supplies/*`) y
reusa el AUTH del ecosistema SmartBear. Sin frameworks: HTML5 + Vanilla
JS (módulos ES) + CSS3, responsive con drawer hamburguesa.

## Layout

```
demo/supplies/
├── index.html            shell (sidebar + topbar + page host + modal + toasts)
├── login.html            login → AUTH
├── css/supplies.css      design system A (sidebar + cards + tablas + badges)
└── js/
    ├── app.js                  entry de index.html (router + role gate)
    ├── login.js                entry de login.html
    ├── router.js               router por hash con guardas de rol
    ├── auth.js                 helpers de JWT (email, role, hasRole)
    ├── ui.js                   toast, modal, formateadores, statusBadge
    ├── services/
    │   ├── apiClient.js        transporte con fallback local↔remote
    │   ├── AuthService.js      POST /v1/auth/login + storage
    │   └── SuppliesService.js  todos los endpoints /v1/supplies/*
    └── pages/
        ├── DashboardPage.js    KPIs + actividad reciente
        ├── CatalogPage.js      tabs: ítems, categorías, unidades, parámetros
        ├── RequestsPage.js     creación + flujo de estados
        ├── ReplenishmentsPage.js  sugerencias + listado + recepciones
        ├── KardexPage.js       movimientos por ítem + ajuste manual
        └── ReportsPage.js      stock bajo + reposiciones + solicitudes
```

## URLs configurables

Definidas en `demo/data/config.json → api`:

- `suppliesBaseUrl` / `suppliesBaseUrlFallback`
- `authBaseUrl` / `authBaseUrlFallback`

`apiClient.resolveBases` aplica auto-detect: si el hostname es
`localhost`/`127.0.0.1`/`0.0.0.0` usa la URL local como primaria y la
remota como fallback, sino al revés.

## Setup local

Microservicios arriba:

| Servicio | Puerto |
|---|---|
| AUTH | 3000 |
| Supplies | 3004 |

Servir `demo/` con Live Server en `5500` y abrir:

- Login: `http://127.0.0.1:5500/supplies/login.html`
- Panel: `http://127.0.0.1:5500/supplies/index.html` (redirige a login si no hay JWT)

## Roles

El frontend lee el claim `role` del JWT para mostrar/ocultar secciones.
Acciones que requieren rol específico:

| Acción | Roles |
|---|---|
| Crear/editar/desactivar ítems, categorías, unidades, parámetros | ADMIN |
| Editar `min_stock` y `default_replenishment_qty` de un ítem | ADMIN, WAREHOUSE_MANAGER |
| Generar y recepcionar reposiciones | ADMIN, WAREHOUSE_MANAGER |
| Ajustar kárdex manualmente | ADMIN, WAREHOUSE_MANAGER |
| Procesar, entregar, rechazar, anular solicitudes | ADMIN, WAREHOUSE_MANAGER |
| Crear solicitudes y confirmar conformidad | ADMIN, WAREHOUSE_MANAGER, REQUESTER |

Las rutas con `data-roles` en `index.html` se ocultan automáticamente del
sidebar cuando el usuario no tiene el rol; igualmente el router rechaza
acceso si se intenta entrar por hash.

## Cómo extender

- **Nuevo endpoint**: agregar método en `services/SuppliesService.js`.
- **Nueva página**: crear `pages/Foo.js` exportando `mountFoo({ host, actions, api, router })`,
  registrar en `app.js` y agregar el botón al `<nav id="sup-nav">`.
- **Nuevo estado de solicitud / reposición**: extender `STATUS_CLASS` y `STATUS_LABEL`
  en `ui.js` y, si hay nuevas transiciones, ajustar `_buildTransitionButtons` en
  `RequestsPage.js`.
