# AUTH — Auth-Handler-Service

Servicio **base** de BearSoft (CLAUDE.md §4 y §7).

## Para qué sirve

Es la puerta de entrada de toda la API: guarda los usuarios y emite el token
JWT que los demás servicios exigen en cada llamada. El token lleva `email`,
`role` y `client`; `client` es la empresa y es el **dueño de los datos** en
todos los servicios (un MANAGER y sus vendedores ven lo mismo).

Los demás servicios **no llaman a AUTH** para validar el token: lo verifican
ellos mismos con `security.py` y la misma `SECRET_KEY` / `ALGORITHM`. AUTH no
reporta a EVENTS (no se audita el inicio de sesión, Rafael 17-oct-2026).

## Endpoints y quién puede llamarlos

| Método | Ruta | Quién |
|---|---|---|
| POST | `/v1/auth/login` | Sin token: recibe email y contraseña, devuelve el JWT |
| POST | `/v1/auth/signup` | `ADMIN` (desde el 19-oct-2026): da de alta un usuario como `REQUESTER` y sin empresa; luego el `ADMIN` le pone rol y empresa con `PATCH /v1/users/{email}` |
| GET | `/v1/users/me` | Cualquier usuario activo: sus propios datos |
| POST | `/v1/users/me/password` | Cualquier usuario activo: cambia su contraseña |
| GET | `/v1/users/company` | `MANAGER` o `ADMIN`: los usuarios de su empresa |
| GET | `/v1/users/` | `ADMIN` |
| GET | `/v1/users/{email}` | `ADMIN` |
| PATCH | `/v1/users/{email}` | `ADMIN` |
| DELETE | `/v1/users/{email}` | `ADMIN` |

Roles en `schemas/role.py`.

**El primer administrador.** Como el alta exige un `ADMIN`, el primero (o uno
nuevo si no quedara ninguno) se crea escribiendo el ítem directo en
`auth-users`, con el hash de `services/security.py`. Desde ahí, cualquier
`ADMIN` da de alta a otro y lo promueve con `PATCH` (`role: ADMIN`).

## Qué servicios lo llaman

- **Portal demo** (`portal/demo/js/auth.js`, `account.js`, `home.js`): login,
  cambio de contraseña y usuarios de la empresa.
- **Portal de BILLING** (`portal/billing/js/services/AuthService.js`).
- Ningún microservicio lo llama por HTTP: todos verifican el token localmente.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Firma del JWT; **la misma en todos los servicios** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vida del token |
| `TABLE_NAME` | Tabla de usuarios (`auth-users`) |

## Tablas

`auth-users`, partición `email`. Cada ítem es un usuario: `email`,
`first_name`, `last_name`, `hashed_password` (nunca la contraseña), `client`,
`role`, `status` y `date_register`. Esquemas en `schemas/users.py`.

Las contraseñas se guardan con `bcrypt` directo (hash `$2b$`), sin `passlib`
desde el 19-oct-2026: `passlib` ya no se mantiene y obligaba a fijar
versiones. Los hashes anteriores siguen validando; `bcrypt` lee sólo los
primeros 72 bytes, y el servicio los corta igual que lo hacía `passlib`.

## Cómo correrlo y probarlo

```bash
cd services/auth
python main.py            # puerto del .env (PORT)
python -m pytest -q
pylint --fail-under=10.0 .
```

Se despliega con `services/ci/api/start.sh --redeploy auth` (lo despliega
Rafael).

## Qué revisa el CI

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**.

- `tests/test_auth.py` importa sólo esquemas y funciones puras
  (`services/sessions.py`, `services/security.py`), así que corre en el CI:
  sesiones, cambio de contraseña y el hash, incluido uno hecho por `passlib`.
- `tests/test_routes.py` (el alta sólo para `ADMIN`) importa las rutas, que
  leen configuración: `tests/conftest.py` lo deja fuera sin `.env` y corre en
  local.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
