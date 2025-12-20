# MICROSERVICIO FORMS

## Antecedentes:

El cliente tiene muchos retrasos y por ende `timeouts` para ciertos reportes y accesos tipo `POST` dentro del microservicio `FORMS`. concretamente los reportes se obtienen de los endpoints: `/reports/contacts-by-route` y `/reports/affiliation-monitor`.

Los archivos que tienes que ver para ambos endpoits son:

- Se inicia el llamdo en `routes/reports.py` acá encontrás los endpoints que llaman a un controlador diferente cada uno de ellos

- En la capa del controlador encontrarás `controllers/reports.py` desde esta capa se llama a los servicios.

- En la capa del servicio encontrarás `services/reports.py` acá es donde se realiza la mayoría de los procesos y conexiones, entre ellas el llamado a otros microservicios.

- Adicionalmente tenemos otra capa llamada `models` que para el proceso `reports` no tiene modelos en la base de datos utiliza los modelos que fueron definidos para `models/responses.py` y ahora que ya tenemos fusionados los microservicios `FORMS` y `PLANNING` es posible que necesitemos `models/planning.py`.

- Por último la capa `schemas` que maneja los modelos de `Pydantic` para `Request` y `Responses`, acá es posible que además del archivo `schemas/reports.py`, necesites también `schemas/responses.py` y `schemas/planning.py`

## Datos adicionales

**Todo el código debe estar basado en y mantener estas directrices:**

- Clean Code.
- Arquitectura Limpia.
- Principios SOLID y DRY.
- Código, comentarios y docstrings en inglés utilizar comilla simple (`'`) para el texto.
- El signo `=` debe tener espacios a ambos lados.
- Mantener el concepto de usar la variable `message` y `error_msg` para el logger y así evitar problemas con Pylint.
- Tomar en cuenta todas las recomendaciones de Pylint sobre las buenas prácticas del código en cantidad de caracteres por línea, numero de variables por función y cantidad de variables que se pueden pasar en cada función, `100` caracteres por cada línea, `5` variables en el paso de parámetros en el llamado de funciones y otras propias del Pylint.
- La comunicación conmigo es en español, sin embargo todo el código, variables y comentarios en los archivos de código deben ser en inglés.


## Cambios solicitados por el cliente

### Requerimiento 1: Mejora endpoint `/reports/contacts-by-route`

## Tareas por hacer:

1. Modificar el endpoint `/reports/contacts-by-route` ya que bajo ciertos parámetros llamaba al microservicio `PLANNING` para obtener el `planned_route_id` desde la creación de las tablas `t_planning` y `t_planninn_details` dentro del microservicio `FORMS` ya no se requiere ese llamado y se puede hacer directamente la consulta. Se debe limpiar todo el código que ya no sea necesario para ese proceso que ahora ya no es requerido.


### Requerimiento 2: Mejora endpoint `/reports/affiliation-monitor`

## Tareas por hacer:

1. Modificar el endpoint `/reports/affiliation-monitor` ya que bajo ciertos parámetros llamaba al microservicio `PLANNING` para obtener el `planned_route_id` desde la creación de las tablas `t_planning` y `t_planninn_details` dentro del microservicio `FORMS` ya no se requiere ese llamado y se puede hacer directamente la consulta. Se debe limpiar todo el código que ya no sea necesario para ese proceso que ahora ya no es requerido.

## Peticiones al Agente

- Puedes colaborarme bajo los lineamientos que te acabo de dar?

- Pide los archivos que necesites s egún el orden que definas para que los revises

- No asumas nada, no inventes código, pregunta siempre antes de escribir código.

- El código funciona y ya tiene varias pruebas y es parte d eun conjunto de varios microservicios.

- Los cambios deben agregar valor no entorpecer o complicar el mantenimiento y escalabilidad.

- Si necesitas saber algo pídeme, no trates de interpretar o crear cosas que no son necesarias.

- No modifiques el código a menos que sea necesario.

- Respeta la estructura que tienen los archivo que te voy a ir pasando acorde sea necesario.

Comenzamos? Pide lo que necesites...


Buenos días ahora más fresco ya tengo las ideas claras e hice el seguimiento que necesitaba al código para definir los cambios que requiero.

Nuevamente volvamos a la definición original de la función `calculate_affiliation_monitor` que es la siguiente:

```python

```

Donde el campo `status` está inmerso en el modelo `FormResponse` te queda claro?