# Requerimiento 1: Mejora endpoint `/reports/contacts-by-route` microservicio FORMS

## Antecedentes:

El cliente tiene muchos retrasos y por ende `timeouts` para ciertos reportes y accesos tipo `GET` o `POST` dentro del microservicio `FORMS`. concretamente el reporte que se obtiene desde el endpoint `/reports/contacts-by-route`.

## Tareas por hacer:

1. Modificar el endpoint `/reports/contacts-by-route` ya que bajo ciertos parámetros llamaba al microservicio `PLANNING` para obtener el `planned_route_id` desde la creación de las tablas `t_planning` y `t_planninn_details` dentro del microservicio `FORMS` ya no se requiere ese llamado y se puede hacer directamente la consulta. Se debe limpiar todo el código que ya no sea necesario para ese proceso que ahora ya no es requerido.

2. Mejorar la documentación de los modelos y objetos que son mostrados en el `Swagger` para mejor entendimiento del usuario del `API`.


# Datos adicionales

- Respeta todo lo descrito en el documento `GEMINI.md`

- Debes actualizar el archivo `README.md` si es que existen cambios que deban reflejarse ahí

- Los microservicios ya están en producción y necesitan estos cambios

- Cualquier duda que tengas pregunta para que pueda darte más contexto de ser necesario
