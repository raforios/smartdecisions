# CMS Admin Panel

UI estática que consume los endpoints `/v1/cms/admin/*` del microservicio CMS y delega los uploads de assets al microservicio FILES. Sin frameworks: HTML + vanilla JS (módulos ES) + CSS.

## Layout

```
demo/admin/
├── index.html          shell con sidebar + tabla + modal
├── login.html          formulario de login → AUTH
├── css/admin.css
└── js/
    ├── app.js                       entry de index.html
    ├── login.js                     entry de login.html
    ├── EntityPanel.js               CRUD genérico config-driven
    ├── entityConfigs.js             campos / columnas / endpoints por entidad
    └── services/
        ├── apiClient.js             helpers (resolve bases, request, auth header)
        ├── AuthService.js           POST /v1/auth/login + JWT en localStorage
        ├── CmsAdminService.js       20 endpoints CMS admin
        └── FilesService.js          POST /v1/s3/upload (multipart)
```

## Setup local

Los 3 microservicios deben estar arriba:

| Servicio | Puerto local |
|---|---|
| AUTH (`services/auth`) | 3000 |
| FILES (`services/files`) | 3010 |
| CMS (`services/cms`) | 3021 |

Y DynamoDB Local en `:3100` (compartido). Si aún no creaste las tablas, corre `services/cms/dynamodb.sh`.

### Sembrar un usuario admin

El AUTH service expone `POST /v1/auth/signup`. Desde otra terminal:

```bash
curl -X POST http://localhost:3000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local","password":"changeme123","name":"Admin"}'
```

(Ajusta el payload al schema real de `UserRequest`.)

### Abrir el panel

Con Live Server (o equivalente) en `demo/` apuntando al puerto `5500`:

- Login: `http://127.0.0.1:5500/admin/login.html`
- Panel: `http://127.0.0.1:5500/admin/index.html` (redirige a login si no hay JWT)

El panel detecta hostname `127.0.0.1` y prefiere los backends locales sobre los productivos (mismo patrón que el portal público).

## URLs configurables

Todas viven en `demo/data/config.json → api`:

- `authBaseUrl` / `authBaseUrlFallback`
- `filesBaseUrl` / `filesBaseUrlFallback`
- `cmsBaseUrl` / `cmsBaseUrlFallback`
- `cmsAssetsBucket` — bucket donde los uploads aterrizan (default `ml-data-file-handler`).
- `cmsAssetsPath` — prefijo opcional dentro del bucket (default `cms/`). Cada entidad agrega su `subPath` (`news/`, `documents/`, etc.).

## Cómo extender

Para añadir un campo a una entidad: edita la entrada correspondiente en `entityConfigs.js`. Los tipos soportados son `text`, `textarea`, `number`, `date`, `datetime`, `checkbox`, `select` y `file`. El campo `file` produce el par `<refName>_s3_bucket` + `<refName>_s3_key` después del upload.

Para agregar una entidad nueva: registra el nuevo bloque en `entityConfigs.js`, suma el botón a `index.html → #admin-nav`, y verifica que los endpoints del backend existan.
