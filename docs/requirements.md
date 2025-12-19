# Requerimiento 1: Fusión de los microservicios FORMS y PLANNING.

## Antecedentes:

El cliente tiene muchos retrasos y por ende `timeouts` para ciertos reportes y accesos tipo `GET` o `POST` dentro del microservicio `FORMS`. concretamente el reporte que se obtiene desde el endpoint `/reports/contacts-by-route`.

Por otro lado en el diseño original del microservicio `PLANNING` se tenía un enfoque diferente y por esa razón se creo un microservicio separado, sin embargo sólo se llegaron a utilizar los procesos de `CRUD` para los modelos `Planning` y `PlanningDetail`, el modelo `MaterialAssignment` no se utilizó y otros modelos no se implementaron y ya no son necesarios por tanto este microservicio dejó de ser importante y/o útil y sólo pasó a ser un paso adicional que puede ser asumido por el microservicio `FORMS`.

## Trabajo realizado:

Ya se realizaron algunas modificaciones para tener una línea base para empezar el trabajo de `fusión` de los microservicios `PLANNING` y `FORMS`.

Según la arquitectura que se utilizó para el diseño y creación de los microservicios y considerando el uso del `BOILERPLATE` que utilizamos para los microservicios la modularidad nos permitió realizar las siguientes tareas:

1. Se importaron todos los archivos `planning.py` en las diferentes capas como ser: `controllers, models, routes, schemas y services`.

2. Se hizo lo limpieza de todo lo que incluía el proceso de `Materials`, sin embargo falta la revisión final que está descrita en las `tareas por hacer`.

3. Particularmente en el archivo `services/planning.py` en la función `create_planning_with_details` se debe tener especial cuidado en la revisión ya que tenía lógica combinada con el proceso de `Materials`.

4. Ya se configuró en el archivo `main.py` el `router` para acceder a los endpoints de `Planning`.

5. Se actualizó el archivo `README.md` con los cambios hechos se puede extraer la información necesaria del archivo `planning/README.md` para facilitar la actualización. Mejorar su redacción para que sea un archivo más entendible y que tenga bastante descripción técnica y haga referencia al `Swagger` para ver ejemplos y documentación más específica de los endpoints.

6. Ya fue actualizado el archivo `main.py` en la configuración de `Fast API`, se editó el contenido de `description` que va acorde a la nueva versión del microservicio `FORMS`.

## Tareas por hacer:

1. Realizar una revisión detallada de la fusión que se realizó y si no queda nada pendiente o código que pueda ser perjudicial.

2. Modificar el endpoint `/reports/contacts-by-route` ya que bajo ciertos parámetros llamaba al microservicio `PLANNING` para obtener el `planned_route_id` desde la combinación de las tablas `t_planning` y `t_planninn_details`. Ahora que estas tablas ya son parte del micro servicio no se requiere ese llamado y se puede hacer directamente la consulta. Se debe limpiar todo el código que ya no sea necesario para ese proceso que ahora ya no es requerido.

3. Mejorar la documentación de los modelos y objetos que son mostrados en el `Swagger` para mejor entendimiento del usuario del `API`.


# Datos adicionales

- Respeta todo lo descrito en el documento `GEMINI.md`

- Debes actualizar el archivo `README.md` si es que existen cambios que deban reflejarse ahí

- Los microservicios ya están en producción y necesitan estos cambios

- Cualquier duda que tengas pregunta para que pueda darte más contexto de ser necesario
